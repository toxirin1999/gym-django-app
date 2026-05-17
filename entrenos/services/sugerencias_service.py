"""
Phase 10B — Plan suggestion management.

CONTRACT:
- get_sugerencia_activa() returns the current SugerenciaPlan for display (creates lazily).
- An ignored suggestion respects COOLDOWN_DIAS before reappearing.
- Accepting a suggestion does NOT auto-modify the plan. The user decides what to do.
- The plan can propose, but must know when to be silent.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from entrenos.models import SugerenciaPlan

logger = logging.getLogger(__name__)


def get_sugerencia_activa(cliente, fecha_ref=None):
    """
    Returns the SugerenciaPlan to display today, or None if:
    - No pattern detected this week.
    - The suggestion was recently ignored (cooldown active).
    - The suggestion was discarded.

    Creates a new SugerenciaPlan(pendiente) lazily if a pattern is detected and none exists.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    try:
        from entrenos.services.analisis_semanal_service import obtener_sugerencia_con_patron
        sugerencia_datos = obtener_sugerencia_con_patron(cliente, fecha_ref=fecha_ref)
    except Exception:
        logger.exception('get_sugerencia_activa: error generating suggestion')
        return None

    if not sugerencia_datos:
        return None

    patron = sugerencia_datos['patron']
    texto = sugerencia_datos['texto']

    # Check for an existing record for this pattern
    existente = (
        SugerenciaPlan.objects
        .filter(cliente=cliente, patron=patron)
        .order_by('-fecha_generada')
        .first()
    )

    if existente:
        if existente.estado == SugerenciaPlan.ESTADO_DESCARTADA:
            return None  # permanently dismissed

        if existente.estado == SugerenciaPlan.ESTADO_IGNORADA:
            if existente.cooldown_hasta and existente.cooldown_hasta > fecha_ref:
                return None  # still in cooldown
            # Cooldown expired — reset to pendiente for re-display
            existente.estado = SugerenciaPlan.ESTADO_PENDIENTE
            existente.cooldown_hasta = None
            existente.save(update_fields=['estado', 'cooldown_hasta'])
            return existente

        if existente.estado in (SugerenciaPlan.ESTADO_ACEPTADA, SugerenciaPlan.ESTADO_APLICADA):
            return None  # already acted on this week

        return existente  # estado == pendiente

    # No record exists — create one
    try:
        return SugerenciaPlan.objects.create(
            cliente=cliente,
            patron=patron,
            texto=texto,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
    except Exception:
        logger.exception('get_sugerencia_activa: error creating SugerenciaPlan')
        return None


def ignorar_sugerencia(sugerencia):
    """
    User chose "Ignorar por ahora".
    The suggestion won't reappear for COOLDOWN_DIAS days.
    """
    sugerencia.estado = SugerenciaPlan.ESTADO_IGNORADA
    sugerencia.cooldown_hasta = timezone.localdate() + timedelta(days=SugerenciaPlan.COOLDOWN_DIAS)
    sugerencia.fecha_respuesta = timezone.now()
    sugerencia.save(update_fields=['estado', 'cooldown_hasta', 'fecha_respuesta'])
    return sugerencia


_PATRON_A_INTERVENCION = {
    'carga_alta_sostenida':     'no_subir_cargas',
    'bloque_parcial_repetido':  'no_subir_cargas',
    'esenciales_frecuentes':    'no_subir_cargas',
    'margen_bajo_repetido':     'reducir_accesorios',
    'alta_continuidad':         'mantener_estructura',
}


def _fin_de_semana(fecha):
    """Returns the Sunday (end of week) for the given date."""
    return fecha + timedelta(days=(6 - fecha.weekday()))


def aceptar_sugerencia(sugerencia, fecha_ref=None):
    """
    Phase 10C — User chose "Aplicar esta semana".
    Creates an IntervencionPlan active until end of the current week.
    The freno contextual reads this intervention and enforces it.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()
    fecha_fin = _fin_de_semana(fecha_ref)

    tipo = _PATRON_A_INTERVENCION.get(sugerencia.patron, IntervencionPlan.TIPO_MANTENER)

    IntervencionPlan.objects.create(
        cliente=sugerencia.cliente,
        sugerencia=sugerencia,
        tipo=tipo,
        origen_patron=sugerencia.patron,
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_fin,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )

    sugerencia.estado = SugerenciaPlan.ESTADO_ACEPTADA
    sugerencia.fecha_respuesta = timezone.now()
    sugerencia.save(update_fields=['estado', 'fecha_respuesta'])
    return sugerencia


def evaluar_intervencion_semana(cliente, fecha_ref=None):
    """
    Phase 12 — Evaluates the outcome of accepted interventions from the previous week.

    Returns a dict or None if no interventions were active last week.

    Return dict:
        tipo_intervencion: str
        resultado: 'favorable' | 'neutral' | 'sin_datos'
        lectura: str  (human-readable, JOI-safe, no blame)
    """
    from entrenos.models import IntervencionPlan
    from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento

    fecha_ref = fecha_ref or timezone.localdate()
    semana_pasada = fecha_ref - timedelta(weeks=1)

    try:
        intervenciones = IntervencionPlan.objects.filter(
            cliente=cliente,
            estado__in=[IntervencionPlan.ESTADO_ACTIVA, IntervencionPlan.ESTADO_EXPIRADA],
            fecha_inicio__lte=semana_pasada + timedelta(days=6),
            fecha_fin__gte=semana_pasada,
        ).exclude(tipo=IntervencionPlan.TIPO_MANTENER)

        if not intervenciones.exists():
            return None

        semana_data = analizar_semana_entrenamiento(cliente, semana_pasada)
        if not semana_data or not semana_data.get('hay_datos'):
            return None

        for intervencion in intervenciones:
            resultado = _evaluar_resultado_intervencion(intervencion, semana_data)
            if resultado:
                return resultado

    except Exception:
        logger.exception('evaluar_intervencion_semana: error para cliente %s', cliente.id)

    return None


def _evaluar_resultado_intervencion(intervencion, semana_data):
    from entrenos.models import IntervencionPlan

    tipo = intervencion.tipo
    estado_semana = semana_data.get('estado_semana', 'sin_datos')
    pct_principal = semana_data.get('porcentaje_principal_medio')

    if tipo == IntervencionPlan.TIPO_NO_SUBIR:
        if estado_semana in ('solida', 'margen_extra'):
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'La semana anterior mantuviste cargas y la semana se sostuvo. La intervención parece haber liberado margen.',
            }
        elif estado_semana == 'carga_alta':
            return {
                'tipo_intervencion': tipo,
                'resultado': 'neutral',
                'lectura': 'Mantuviste cargas, pero la semana siguió siendo exigente. Puede que el problema sea de volumen, no solo de progresión.',
            }
        return {
            'tipo_intervencion': tipo,
            'resultado': 'sin_datos',
            'lectura': 'No hay suficientes datos de la semana pasada para evaluar la intervención.',
        }

    elif tipo == IntervencionPlan.TIPO_REDUCIR:
        if pct_principal is not None and pct_principal >= 80:
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'Redujiste accesorios y el bloque principal se sostuvo. La intervención parece haber sido útil.',
            }
        elif estado_semana in ('solida', 'margen_extra'):
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'La semana con accesorios reducidos fue sólida. El plan puede absorber ese ajuste.',
            }
        return {
            'tipo_intervencion': tipo,
            'resultado': 'neutral',
            'lectura': 'Reducir accesorios no cambió visiblemente el patrón. El plan puede necesitar un ajuste más profundo.',
        }

    return None


_RECOMENDACION_REPETIR = {
    'no_subir_cargas':    'La semana anterior el ajuste funcionó. Mantener cargas sin subir una semana más.',
    'reducir_accesorios': 'Reducir accesorios liberó margen. Mantener el mismo criterio esta semana.',
}

_RECOMENDACION_PROFUNDIZAR = {
    'no_subir_cargas':    'Mantener cargas no fue suficiente. Puede ser momento de revisar el volumen total o repetir el microciclo actual.',
    'reducir_accesorios': 'Reducir accesorios no cambió el patrón. El volumen total puede estar por encima del margen real de la semana.',
}


def generar_recomendacion_continuidad(cliente, fecha_ref=None):
    """
    Phase 13 — Generates a continuation recommendation based on last week's evaluation.

    CONTRACT (Phase 13.1 update):
    - Returns None if no evaluation, active intervention, or user dismissed recently.
    - 'repetir': the same intervention type, applied this week.
    - 'profundizar': a different, deeper suggestion.
    - NEVER auto-applies. Waits for user consent.
    - A favorable intervention is NOT made permanent; it becomes a candidate to repeat.
    - If user dismisses "No por ahora": cooldown 7 days via SugerenciaPlan patron='continuidad_X'.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    # Don't pile up if there's already an active intervention this week
    if get_intervencion_activa(cliente, fecha_ref):
        return None

    evaluacion = evaluar_intervencion_semana(cliente, fecha_ref)
    if not evaluacion:
        return None

    # Phase 13.1: check cooldown from "No por ahora" dismissal
    tipo_eval = evaluacion.get('tipo_intervencion', '')
    patron_clave = f'continuidad_{tipo_eval}'
    cooldown_activo = SugerenciaPlan.objects.filter(
        cliente=cliente,
        patron=patron_clave,
        estado=SugerenciaPlan.ESTADO_IGNORADA,
        cooldown_hasta__gt=fecha_ref,
    ).exists()
    if cooldown_activo:
        return None

    tipo = evaluacion.get('tipo_intervencion')
    resultado = evaluacion.get('resultado')

    if resultado == 'favorable':
        texto = _RECOMENDACION_REPETIR.get(tipo, 'Mantener el ajuste una semana más.')
        return {
            'accion': 'repetir',
            'tipo_intervencion': tipo,
            'texto': texto,
        }
    elif resultado == 'neutral':
        texto = _RECOMENDACION_PROFUNDIZAR.get(tipo, 'El ajuste puede necesitar revisión más profunda.')
        return {
            'accion': 'profundizar',
            'tipo_intervencion': tipo,
            'texto': texto,
        }

    return None


def repetir_intervencion(cliente, tipo_intervencion, fecha_ref=None):
    """
    Phase 13 — Creates a new IntervencionPlan this week (same type as last week).
    Called when the user accepts 'Repetir esta semana'.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()
    fecha_fin = _fin_de_semana(fecha_ref)

    return IntervencionPlan.objects.create(
        cliente=cliente,
        tipo=tipo_intervencion,
        origen_patron='continuidad_fase13',
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_fin,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )


def get_intervencion_activa(cliente, fecha_ref=None):
    """
    Returns the active IntervencionPlan for today, or None.
    Called by evaluar_permiso_progresion — takes precedence over pattern detection.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()

    # Expire stale active interventions
    IntervencionPlan.objects.filter(
        cliente=cliente,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_fin__lt=fecha_ref,
    ).update(estado=IntervencionPlan.ESTADO_EXPIRADA)

    return (
        IntervencionPlan.objects
        .filter(
            cliente=cliente,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio__lte=fecha_ref,
            fecha_fin__gte=fecha_ref,
        )
        .exclude(tipo=IntervencionPlan.TIPO_MANTENER)  # mantener_estructura = no freno effect
        .order_by('-creada_en')
        .first()
    )
