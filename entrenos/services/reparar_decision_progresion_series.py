from decimal import Decimal, InvalidOperation

from django.db import transaction

from entrenos.models import EjercicioRealizado, GymAdaptationProfile, GymDecisionLog
from entrenos.services.decision_log_service import (
    _formatear_reps,
    _objetivo_repeticiones_snapshot,
    _rendimiento_representativo_desde_series,
    _reps_para_log,
    _tecnicas_sesion,
    normalizar_ejercicio,
)
from rutinas.models import EjercicioBase


class ReparacionDecisionSeriesError(ValueError):
    pass


@transaction.atomic
def reparar_decision_progresion_series(
    *, decision_id, apply=False, objetivo_reps=None,
):
    """Revalida una progresión legacy aún pendiente con sus series canónicas."""
    decisiones = GymDecisionLog.objects.select_related(
        'entreno_origen', 'entreno_origen__gym_decision_version',
    )
    if apply:
        decisiones = decisiones.select_for_update()
    try:
        decision = decisiones.get(pk=decision_id)
    except GymDecisionLog.DoesNotExist as exc:
        raise ReparacionDecisionSeriesError(
            f'GymDecisionLog {decision_id} no existe'
        ) from exc

    if decision.estado_aplicacion != 'pendiente':
        raise ReparacionDecisionSeriesError(
            f'la decisión {decision_id} no está pendiente'
        )
    if decision.resultado is not None or decision.fecha_evaluacion is not None:
        raise ReparacionDecisionSeriesError(
            f'la decisión {decision_id} ya fue evaluada'
        )
    entreno = decision.entreno_origen
    if entreno is None:
        raise ReparacionDecisionSeriesError('la decisión no tiene entreno de origen')

    nombre = normalizar_ejercicio(decision.ejercicio_normalizado or decision.ejercicio)
    ejercicio = next((
        item for item in EjercicioRealizado.objects.filter(entreno=entreno, completado=True)
        if normalizar_ejercicio(item.nombre_ejercicio) == nombre
    ), None)
    if ejercicio is None:
        raise ReparacionDecisionSeriesError('no existe el ejercicio completado de origen')
    if ejercicio.fallo_muscular or ejercicio.es_tope_maquina:
        raise ReparacionDecisionSeriesError(
            'la decisión contiene una señal protectora o un tope de máquina'
        )
    if ejercicio.molestia_reportada or 'comprometida' in _tecnicas_sesion(entreno, nombre):
        raise ReparacionDecisionSeriesError(
            'la decisión contiene una señal protectora de molestia o técnica'
        )

    rendimiento = _rendimiento_representativo_desde_series(entreno, nombre)
    if rendimiento is None:
        raise ReparacionDecisionSeriesError(
            'faltan series canónicas'
        )
    objetivo_snapshot = _objetivo_repeticiones_snapshot(entreno, nombre)
    objetivo_explicito = None
    if objetivo_reps is not None:
        try:
            objetivo_explicito = Decimal(str(objetivo_reps))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ReparacionDecisionSeriesError(
                'el objetivo explícito de repeticiones no es válido'
            ) from exc
        if objetivo_explicito <= 0:
            raise ReparacionDecisionSeriesError(
                'el objetivo explícito de repeticiones debe ser positivo'
            )
    if (
        objetivo_snapshot is not None
        and objetivo_explicito is not None
        and objetivo_snapshot != objetivo_explicito
    ):
        raise ReparacionDecisionSeriesError(
            'el objetivo explícito contradice el snapshot inmutable'
        )
    if objetivo_snapshot is not None:
        objetivo = objetivo_snapshot
        objetivo_origen = 'snapshot_inmutable'
    elif objetivo_explicito is not None:
        objetivo = objetivo_explicito
        objetivo_origen = 'argumento_explicito'
    else:
        raise ReparacionDecisionSeriesError(
            'falta el objetivo inmutable de repeticiones; '
            'usa --objetivo-reps solo después de verificarlo'
        )
    peso, media = rendimiento
    rpe = float(ejercicio.rpe) if ejercicio.rpe is not None else None
    if media <= objetivo or rpe is None or rpe > 8:
        raise ReparacionDecisionSeriesError(
            'las series no superan el objetivo con RPE controlado'
        )

    base = next((
        item for item in EjercicioBase.objects.all()
        if normalizar_ejercicio(item.nombre) == nombre
    ), None)
    tipo = base.tipo_progresion if base else 'peso_reps'
    if tipo not in ('peso_reps', 'peso_corporal_lastre', 'progresion_reps'):
        raise ReparacionDecisionSeriesError(
            'el tipo de progresión no se gobierna por repeticiones'
        )
    perfil = GymAdaptationProfile.objects.filter(
        cliente=decision.cliente,
        ejercicio=nombre,
    ).first()
    if perfil is None:
        if apply:
            perfil = GymAdaptationProfile.objects.create(
                cliente=decision.cliente,
                ejercicio=nombre,
            )
        else:
            perfil = GymAdaptationProfile(
                cliente=decision.cliente,
                ejercicio=nombre,
            )
    accion = 'subir_reps' if tipo == 'progresion_reps' else 'subir_peso'
    valor_cambio = 1 if accion == 'subir_reps' else perfil.incremento_peso_pct
    motivo_codigo = 'progresion_reps' if accion == 'subir_reps' else 'progresion_peso'
    motivo = (
        f'Media {_formatear_reps(media)} frente al objetivo '
        f'{_formatear_reps(objetivo)} — objetivo superado con esfuerzo controlado'
    )
    propuesto = {
        'peso_anterior': float(peso),
        'reps_anteriores': _reps_para_log(media),
        'rpe_anterior': rpe,
        'accion': accion,
        'valor_cambio': valor_cambio,
        'motivo': motivo,
        'motivo_codigo': motivo_codigo,
    }
    antes = {
        campo: getattr(decision, campo)
        for campo in propuesto
    }
    ya_consistente = antes == propuesto
    resultado = {
        'decision_id': decision.pk,
        'entreno_id': entreno.pk,
        'ejercicio': decision.ejercicio,
        'modo': 'apply' if apply else 'dry-run',
        'solo_lectura': not apply,
        'estado': 'ya_consistente' if ya_consistente else ('aplicada' if apply else 'candidata'),
        'media_reps': str(media.normalize()),
        'objetivo_reps': str(objetivo.normalize()),
        'objetivo_origen': objetivo_origen,
        'antes': antes,
        'propuesto': propuesto,
    }
    if apply and not ya_consistente:
        for campo, valor in propuesto.items():
            setattr(decision, campo, valor)
        decision.save(update_fields=list(propuesto))
    return resultado
