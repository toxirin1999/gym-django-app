"""Cierre causal del contrato semanal Gym, sin inferencias por fecha."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from entrenos.models import EvaluacionSemanalGym, SesionProgramada
from entrenos.services.estrategia_semanal_gym_service import evaluar_contrato_semanal_gym


class SemanaAbierta(ValueError):
    """El contrato todavía puede recibir ejecuciones dentro de su semana."""


class ContratoNoMaterializado(ValueError):
    """El contrato no contiene exactamente las identidades prescritas."""


class EvaluacionSemanalRevisada(RuntimeError):
    """Una revisión humana no puede ser reemplazada por evidencia posterior."""


class ActorNoAutorizado(PermissionError):
    """El actor no puede revisar el cierre de este cliente."""


def _media(valores):
    valores = [float(valor) for valor in valores if valor is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def _rpe_atribuible(entreno):
    try:
        detalle = entreno.sesion_detalle
    except ObjectDoesNotExist:
        detalle = None
    if detalle is not None and detalle.rpe_medio is not None:
        return float(detalle.rpe_medio)
    return entreno.ejercicios_realizados.filter(rpe__isnull=False).aggregate(
        media=Avg('rpe'),
    )['media']


def _snapshot(contrato):
    sesiones = list(
        contrato.sesiones.select_related('entreno_realizado').order_by('id')
    )
    conteos = {
        codigo: sum(sesion.estado == codigo for sesion in sesiones)
        for codigo, _ in SesionProgramada.ESTADOS
    }
    completadas = [
        sesion for sesion in sesiones
        if sesion.estado == SesionProgramada.ESTADO_COMPLETADA
    ]
    reubicadas = sum(
        sesion.fecha_realizada is not None
        and (
            sesion.fecha_realizada != sesion.fecha_prevista
            or (
                sesion.pospuesta_hasta is not None
                and sesion.pospuesta_hasta != sesion.fecha_prevista
            )
        )
        for sesion in completadas
    )

    # Un entrenamiento solo puede contribuir una vez aunque un dato corrupto lo
    # enlace desde más de una identidad. El vínculo explícito sigue siendo la
    # única puerta de entrada; nunca se buscan coincidencias por fecha.
    entrenos = []
    vistos = set()
    for sesion in completadas:
        entreno = sesion.entreno_realizado
        if entreno is not None and entreno.pk not in vistos:
            entrenos.append(entreno)
            vistos.add(entreno.pk)

    volumenes = [entreno.volumen_total_kg for entreno in entrenos if entreno.volumen_total_kg is not None]
    duraciones = [entreno.duracion_minutos for entreno in entrenos if entreno.duracion_minutos is not None]
    energias = [entreno.energia_pre_sesion for entreno in entrenos if entreno.energia_pre_sesion is not None]
    rpes = [_rpe_atribuible(entreno) for entreno in entrenos]
    rpes_disponibles = [rpe for rpe in rpes if rpe is not None]

    volumen_total = sum(volumenes, Decimal('0')) if volumenes else None
    resultado_base = evaluar_contrato_semanal_gym(contrato)
    return {
        'version_calculo': 1,
        'contrato_id': contrato.pk,
        'semana': contrato.semana.isoformat(),
        'objetivo_sesiones': contrato.objetivo_sesiones,
        'minimo_valido': contrato.minimo_valido,
        'estado_cumplimiento': resultado_base['estado_cumplimiento'],
        'conteos_estado': conteos,
        'sesiones_completadas': len(completadas),
        'sesiones_reubicadas': reubicadas,
        'sesiones': [
            {
                'id': sesion.pk,
                'estado': sesion.estado,
                'fecha_prevista': sesion.fecha_prevista.isoformat(),
                'pospuesta_hasta': sesion.pospuesta_hasta.isoformat() if sesion.pospuesta_hasta else None,
                'fecha_realizada': sesion.fecha_realizada.isoformat() if sesion.fecha_realizada else None,
                'entreno_realizado_id': sesion.entreno_realizado_id,
            }
            for sesion in sesiones
        ],
        'metricas': {
            'volumen_total_kg': f'{volumen_total:.2f}' if volumen_total is not None else None,
            'duracion_total_minutos': sum(duraciones) if duraciones else None,
            'energia_pre_sesion_media': _media(energias),
            'rpe_medio': _media(rpes_disponibles),
            'cobertura': {
                'entrenos_enlazados': {'disponibles': len(entrenos), 'total': len(completadas)},
                'volumen': {'disponibles': len(volumenes), 'total': len(entrenos)},
                'duracion': {'disponibles': len(duraciones), 'total': len(entrenos)},
                'energia_pre_sesion': {'disponibles': len(energias), 'total': len(entrenos)},
                'rpe': {'disponibles': len(rpes_disponibles), 'total': len(entrenos)},
            },
        },
    }


@transaction.atomic
def evaluar_y_persistir_contrato_semanal_gym(contrato, force=False, hoy=None):
    """Persiste una única evaluación reproducible del contrato materializado."""
    hoy = hoy or timezone.localdate()
    fin_semana = contrato.semana + timedelta(days=6)
    if not force and hoy <= fin_semana:
        raise SemanaAbierta(
            f'La semana {contrato.semana.isoformat()} no ha cerrado todavía.'
        )

    contrato = type(contrato).objects.select_for_update().get(pk=contrato.pk)
    if contrato.sesiones.count() != contrato.objetivo_sesiones:
        raise ContratoNoMaterializado(
            f'El contrato exige {contrato.objetivo_sesiones} sesiones y contiene '
            f'{contrato.sesiones.count()}.'
        )

    evidencia = _snapshot(contrato)
    existente = EvaluacionSemanalGym.objects.select_for_update().filter(
        contrato=contrato,
    ).first()
    if existente is not None and existente.evidencia_snapshot == evidencia:
        return existente
    if existente is not None and existente.estado_revision != EvaluacionSemanalGym.ESTADO_PENDIENTE:
        raise EvaluacionSemanalRevisada(
            'La evaluación ya fue revisada y su evidencia original queda preservada.'
        )

    defaults = {
        'version_calculo': 1,
        'estado_cumplimiento': evidencia['estado_cumplimiento'],
        'sesiones_completadas': evidencia['sesiones_completadas'],
        'sesiones_reubicadas': evidencia['sesiones_reubicadas'],
        'evidencia_snapshot': evidencia,
    }
    evaluacion, _ = EvaluacionSemanalGym.objects.update_or_create(
        contrato=contrato,
        defaults=defaults,
    )
    return evaluacion


@transaction.atomic
def responder_evaluacion_semanal_gym(evaluacion, *, actor, aceptar):
    """Registra revisión humana sin ejecutar efectos laterales sobre el plan."""
    evaluacion = EvaluacionSemanalGym.objects.select_for_update().select_related(
        'contrato__cliente__user',
    ).get(pk=evaluacion.pk)
    if actor is None or actor.pk != evaluacion.contrato.cliente.user_id:
        raise ActorNoAutorizado('Solo el usuario propietario del cliente puede responder.')

    nuevo_estado = (
        EvaluacionSemanalGym.ESTADO_ACEPTADA
        if aceptar else EvaluacionSemanalGym.ESTADO_RECHAZADA
    )
    if evaluacion.estado_revision == nuevo_estado:
        return evaluacion
    if evaluacion.estado_revision != EvaluacionSemanalGym.ESTADO_PENDIENTE:
        raise EvaluacionSemanalRevisada('La evaluación ya tiene una respuesta distinta.')

    evaluacion.estado_revision = nuevo_estado
    evaluacion.respondida_por = actor
    evaluacion.respondida_en = timezone.now()
    evaluacion.save(update_fields=[
        'estado_revision', 'respondida_por', 'respondida_en', 'actualizada_en',
    ])
    return evaluacion
