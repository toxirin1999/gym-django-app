"""Ciclo contractual de la intervención ``esenciales_frecuentes``."""

import logging
from statistics import median

from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta

from entrenos.models import (
    ContratoSemanalGym, EntrenoRealizado, IntervencionPlan, SesionProgramada,
    SugerenciaPlan,
)
from entrenos.services.contrato_sugerencia_service import (
    PATRON_V1, construir_contrato_sugerencia, validar_contrato_snapshot,
)

logger = logging.getLogger(__name__)


def _mediana(valores):
    valores = [float(valor) for valor in valores if valor is not None]
    return {'mediana': float(median(valores)) if valores else None, 'n': len(valores)}


def medir_ventana(cliente, desde, hasta):
    """Mide una ventana inclusiva desde sesiones programadas, una fila una vez.

    ``pospuesta_hasta`` es la fecha efectiva de una sesión reubicada. Para una
    completada manda ``EntrenoRealizado.fecha_ejecucion`` y se conserva la fecha
    efectiva de la programación para decidir su elegibilidad.
    """
    excluidos = {
        SesionProgramada.ESTADO_OMITIDA_SISTEMA,
        SesionProgramada.ESTADO_CANCELADA_LESION,
    }
    programadas = SesionProgramada.objects.filter(cliente=cliente).select_related(
        'entreno_realizado', 'contrato_semanal',
    ).prefetch_related('entreno_realizado__ejercicios_realizados')
    elegibles = []
    completadas = []
    for sesion in programadas:
        efectiva_programada = sesion.pospuesta_hasta or sesion.fecha_prevista
        if sesion.estado in excluidos or not (desde <= efectiva_programada <= hasta):
            continue
        elegibles.append(sesion)
        entreno = sesion.entreno_realizado
        efectiva_real = (
            entreno.fecha_ejecucion if entreno and entreno.fecha_ejecucion
            else sesion.fecha_realizada
        )
        if (
            sesion.estado == SesionProgramada.ESTADO_COMPLETADA
            and entreno is not None and efectiva_real is not None
            and desde <= efectiva_real <= hasta
        ):
            completadas.append(entreno)

    # Un vínculo accidentalmente duplicado no duplica una sesión realizada.
    completadas = list({entreno.pk: entreno for entreno in completadas}.values())
    esenciales = sum(bool(entreno.modo_reducido) for entreno in completadas)
    planificados = sum(
        entreno.principales_planificados
        for entreno in completadas if entreno.principales_planificados
    )
    principales_completados = sum(
        1 for entreno in completadas
        for ejercicio in entreno.ejercicios_realizados.all()
        if ejercicio.es_bloque_principal is True and ejercicio.completado
    )
    rpes = []
    for entreno in completadas:
        try:
            rpe_sesion = entreno.sesion_detalle.rpe_medio
        except EntrenoRealizado.sesion_detalle.RelatedObjectDoesNotExist:
            rpe_sesion = None
        if rpe_sesion is not None:
            rpes.append(rpe_sesion)
    energias = [entreno.energia_pre_sesion for entreno in completadas if entreno.energia_pre_sesion is not None]

    contratos = list(ContratoSemanalGym.objects.filter(
        cliente=cliente, semana__lte=hasta, semana__gte=desde - timedelta(days=6),
    ))
    if contratos:
        objetivo = contratos[-1].objetivo_sesiones
        minimo = contratos[-1].minimo_valido
        fuente = 'ContratoSemanalGym'
    else:
        # Fallback explícito para datos históricos previos al contrato semanal.
        objetivo = int(getattr(cliente, 'dias_disponibles', None) or 5)
        minimo = min(3, objetivo)
        fuente = 'fallback_historico_5_3'
    if len(elegibles) < 3:
        estado_continuidad = 'no_evaluable'
    elif len(completadas) >= objetivo:
        estado_continuidad = 'objetivo'
    elif len(completadas) >= minimo:
        estado_continuidad = 'minima_valida'
    else:
        estado_continuidad = 'insuficiente'
    return {
        'ventana': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'sesiones_elegibles': len(elegibles),
        'sesiones_completadas': len(completadas),
        'sesiones_esenciales': esenciales,
        'porcentaje_esenciales': round(esenciales * 100 / len(completadas)) if completadas else None,
        'principales': {
            'planificados': planificados,
            'completados': principales_completados,
            'porcentaje': round(principales_completados * 100 / planificados) if planificados else None,
        },
        'rpe': _mediana(rpes),
        'energia_pre': _mediana(energias),
        'continuidad': {
            'objetivo_sesiones': objetivo, 'minimo_valido': minimo, 'fuente': fuente,
            'estado': estado_continuidad,
            'cumple_minimo': len(completadas) >= minimo,
            'cumple_objetivo': len(completadas) >= objetivo,
        },
    }


def construir_evaluacion_v1(cliente, inicio, fin):
    baseline_fin = inicio - timedelta(days=1)
    baseline_inicio = inicio - timedelta(days=21)
    return {
        'version': 1,
        'baseline': medir_ventana(cliente, baseline_inicio, baseline_fin),
        'intervencion': {'ventana': {'desde': inicio.isoformat(), 'hasta': fin.isoformat()}},
        'decision': {
            'reversion': 'pendiente', 'no_promocion': True,
            'estrategia_modificada': False, 'preferencia_aprendida_creada': False,
            'manual_david_modificado': False,
        },
    }


def _atribucion(baseline, medicion):
    if baseline.get('sesiones_completadas', 0) < 2 or medicion.get('sesiones_completadas', 0) < 2:
        return 'no_evaluable'
    porcentaje_base = baseline.get('porcentaje_esenciales')
    porcentaje_actual = medicion.get('porcentaje_esenciales')
    if porcentaje_base is None or porcentaje_actual is None:
        return 'no_evaluable'
    delta_esencial = porcentaje_base - porcentaje_actual
    base_principal = baseline.get('principales', {}).get('porcentaje')
    actual_principal = medicion.get('principales', {}).get('porcentaje')
    if delta_esencial > 0 and actual_principal is not None and (base_principal is None or actual_principal >= base_principal):
        return 'compatible_con_freeze'
    if delta_esencial > 0:
        return 'compatible_con_esencial'
    if delta_esencial == 0 and (base_principal is None or actual_principal == base_principal):
        return 'sin_cambio'
    return 'mixta'


def producir_sugerencia_tras_finalizacion(cliente_id, fecha_ref=None):
    """Productor explícito e idempotente; se invoca tras finalizar una sesión."""
    from clientes.models import Cliente
    fecha_ref = fecha_ref or timezone.localdate()
    contrato = construir_contrato_sugerencia(
        Cliente.objects.get(pk=cliente_id), PATRON_V1, fecha_ref,
    )
    if not contrato.get('vigente'):
        return None
    with transaction.atomic():
        cliente = Cliente.objects.select_for_update().get(pk=cliente_id)
        if IntervencionPlan.objects.select_for_update().filter(
            cliente=cliente, origen_patron=PATRON_V1,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio__lte=fecha_ref, fecha_fin__gte=fecha_ref,
        ).exists():
            return None
        existentes = SugerenciaPlan.objects.filter(
            cliente=cliente, patron=PATRON_V1,
        ).exclude(estado=SugerenciaPlan.ESTADO_DESCARTADA).order_by('-pk')
        for existente in existentes:
            misma = (existente.contrato_snapshot or {}).get('evidencia') == contrato.get('evidencia')
            if (
                existente.estado == SugerenciaPlan.ESTADO_IGNORADA
                and existente.cooldown_hasta and existente.cooldown_hasta > fecha_ref
            ):
                return None
            if existente.estado == SugerenciaPlan.ESTADO_PENDIENTE and misma:
                return existente
            if existente.estado == SugerenciaPlan.ESTADO_PENDIENTE and not misma:
                existente.estado = SugerenciaPlan.ESTADO_DESCARTADA
                existente.save(update_fields=['estado'])
        return SugerenciaPlan.objects.create(
            cliente=cliente, patron=PATRON_V1,
            texto='Las versiones esenciales se están repitiendo.',
            contrato_snapshot=contrato,
        )


def programar_produccion_tras_finalizacion(entreno):
    """Registra el productor después del commit; nunca desde post_save."""
    def producir_seguro():
        try:
            producir_sugerencia_tras_finalizacion(entreno.cliente_id, timezone.localdate())
        except Exception:
            # La inteligencia posterior nunca invalida una sesión ya guardada.
            logger.exception('No se pudo producir la sugerencia tras finalizar entreno=%s', entreno.pk)
    transaction.on_commit(producir_seguro)


def _resultado_existente(intervencion):
    if not intervencion.sugerencia_id:
        return None
    return ((intervencion.sugerencia.contrato_snapshot or {}).get('evaluacion') or {}).get('resultado')


def _payload_existente(intervencion):
    snap = intervencion.sugerencia.contrato_snapshot or {}
    payload = dict(snap.get('evaluacion') or {})
    if snap.get('evaluacion_v1') is not None:
        payload['evaluacion_v1'] = snap['evaluacion_v1']
    return payload


def evaluar_intervencion(intervencion, fecha_ref=None, aplicar=False):
    """Evalúa exactamente [inicio, fin], únicamente al día posterior o más tarde."""
    fecha_ref = fecha_ref or timezone.localdate()
    if isinstance(fecha_ref, str):
        fecha_ref = date.fromisoformat(fecha_ref)
    if aplicar:
        return _evaluar_intervencion_atomica(intervencion.pk, fecha_ref)
    if (
        intervencion.estado == IntervencionPlan.ESTADO_CANCELADA
        or intervencion.origen_patron != PATRON_V1
        or not intervencion.sugerencia_id
        or fecha_ref <= intervencion.fecha_fin
    ):
        return None
    existente = _resultado_existente(intervencion)
    if existente:
        return _payload_existente(intervencion)
    medicion = medir_ventana(intervencion.cliente, intervencion.fecha_inicio, intervencion.fecha_fin)
    completadas = medicion['sesiones_completadas']
    esenciales = medicion['sesiones_esenciales']
    porcentaje = medicion['porcentaje_esenciales']
    # Compatibilidad de episodios ya aceptados antes de evaluacion_v1: su
    # veredicto legacy se definió sobre EntrenoRealizado y no se reinterpreta.
    if not (intervencion.sugerencia.contrato_snapshot or {}).get('evaluacion_v1'):
        sesiones_legacy = EntrenoRealizado.objects.filter(
            cliente=intervencion.cliente,
            fecha__range=(intervencion.fecha_inicio, intervencion.fecha_fin),
        )
        completadas = sesiones_legacy.count()
        esenciales = sesiones_legacy.filter(modo_reducido=True).count()
        porcentaje = round(esenciales * 100 / completadas) if completadas else 0
    if completadas < 2:
        codigo = 'datos_insuficientes'
    elif porcentaje < 50:
        codigo = 'senal_reducida'
    else:
        codigo = 'persistente'
    resultado = {
        'resultado': codigo,
        'sesiones_completadas': completadas,
        'sesiones_esenciales': esenciales,
        'porcentaje_esenciales': porcentaje,
        'fecha_evaluacion': fecha_ref.isoformat(),
        'ventana': {'desde': intervencion.fecha_inicio.isoformat(), 'hasta': intervencion.fecha_fin.isoformat()},
    }
    contrato_v1 = (intervencion.sugerencia.contrato_snapshot or {}).get('evaluacion_v1') or construir_evaluacion_v1(
        intervencion.cliente, intervencion.fecha_inicio, intervencion.fecha_fin,
    )
    contrato_v1 = dict(contrato_v1)
    contrato_v1['medicion'] = medicion
    contrato_v1['atribucion'] = _atribucion(contrato_v1.get('baseline') or {}, medicion)
    contrato_v1['abandono_evitado'] = 'no_demostrable'
    decision = dict(contrato_v1.get('decision') or {})
    decision.update({'reversion': 'automatica', 'no_promocion': True, 'estrategia_modificada': False})
    contrato_v1['decision'] = decision
    resultado['evaluacion_v1'] = contrato_v1
    return resultado


@transaction.atomic
def _evaluar_intervencion_atomica(intervencion_id, fecha_ref):
    """Orden estable de locks: Cliente → Intervención → Sugerencia."""
    from clientes.models import Cliente
    referencia = IntervencionPlan.objects.only('cliente_id').get(pk=intervencion_id)
    Cliente.objects.select_for_update().get(pk=referencia.cliente_id)
    bloqueada = IntervencionPlan.objects.select_for_update().select_related('sugerencia').get(pk=intervencion_id)
    if bloqueada.sugerencia_id:
        sugerencia = SugerenciaPlan.objects.select_for_update().get(pk=bloqueada.sugerencia_id)
        bloqueada.sugerencia = sugerencia
    resultado = evaluar_intervencion(bloqueada, fecha_ref, aplicar=False)
    if resultado is None:
        return None
    ya = _resultado_existente(bloqueada)
    if ya:
        return _payload_existente(bloqueada)
    snap = dict(bloqueada.sugerencia.contrato_snapshot or {})
    evaluacion = dict(snap.get('evaluacion') or {})
    evaluacion_v1 = resultado.pop('evaluacion_v1', None)
    evaluacion.update(resultado)
    evaluacion['joi'] = {'estado': 'pendiente', 'mensaje_id': None}
    snap['evaluacion'] = evaluacion
    if evaluacion_v1 is not None:
        snap['evaluacion_v1'] = evaluacion_v1
    bloqueada.sugerencia.contrato_snapshot = snap
    bloqueada.sugerencia.save(update_fields=['contrato_snapshot'])
    bloqueada.estado = IntervencionPlan.ESTADO_EXPIRADA
    bloqueada.save(update_fields=['estado'])
    if evaluacion_v1 is not None:
        evaluacion['evaluacion_v1'] = evaluacion_v1
    return evaluacion


def candidatos(fecha_ref=None, cliente_id=None, limit=None):
    fecha_ref = fecha_ref or timezone.localdate()
    if isinstance(fecha_ref, str):
        fecha_ref = date.fromisoformat(fecha_ref)
    qs = IntervencionPlan.objects.filter(
        estado=IntervencionPlan.ESTADO_ACTIVA,
        origen_patron=PATRON_V1,
        fecha_fin__lt=fecha_ref,
        sugerencia__contrato_snapshot__isnull=False,
    ).select_related('cliente', 'sugerencia').order_by('fecha_fin', 'pk')
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    return list(qs[:limit] if limit else qs)


@transaction.atomic
def cancelar_intervencion(intervencion_id, cliente_id):
    from clientes.models import Cliente
    Cliente.objects.select_for_update().get(pk=cliente_id)
    iv = IntervencionPlan.objects.select_for_update().select_related('sugerencia').get(
        pk=intervencion_id, cliente_id=cliente_id,
        origen_patron=PATRON_V1, sugerencia__patron=PATRON_V1,
    )
    if iv.estado == IntervencionPlan.ESTADO_ACTIVA and iv.fecha_inicio <= timezone.localdate() <= iv.fecha_fin:
        iv.estado = IntervencionPlan.ESTADO_CANCELADA
        iv.save(update_fields=['estado'])
        if iv.sugerencia_id:
            snap = dict(iv.sugerencia.contrato_snapshot or {})
            ev1 = dict(snap.get('evaluacion_v1') or {})
            decision = dict(ev1.get('decision') or {})
            decision.update({'reversion': 'cancelada', 'no_promocion': True, 'estrategia_modificada': False})
            ev1['decision'] = decision
            snap['evaluacion_v1'] = ev1
            iv.sugerencia.contrato_snapshot = snap
            iv.sugerencia.save(update_fields=['contrato_snapshot'])
    return iv
