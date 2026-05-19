"""
Phase 36 — Acumulación de hipótesis desde senal_no_captada.

CONTRACT:
- Read-only: no escribe en el motor, no modifica decisiones.
- Una señal no captada no corrige el plan; enseña al sistema dónde mirar.
- Solo genera observación cuando hay ≥ MIN_OCURRENCIAS de senal_no_captada.
- Lenguaje: "parece que", "puede que", "en N decisiones", "quizá".
- NO dice: "el motor falló", "debes cambiar", "esto es incorrecto".
- Silencio honesto: si no hay patrón, devuelve lista vacía.
"""

import logging
from datetime import timedelta as _td

logger = logging.getLogger(__name__)

_MIN_OCURRENCIAS = 3   # mínimo de senal_no_captada para generar observación
_VENTANA_DIAS   = 30  # ventana de búsqueda en días


# Textos de observación por tipo de decisión
# Subject: "el sistema" (not the user), tentative tone.
_OBSERVACIONES = {
    'posponer': (
        'En {n} decisiones recientes de posponer, la sesión siguiente tuvo '
        'margen bajo. Puede que el sistema deba mirar mejor si la causa de '
        'posponer resuelve la fatiga o solo la desplaza.'
    ),
    'recuperar': (
        'En {n} decisiones de recuperación, las señales posteriores sugieren '
        'que quizá el margen no mejoró tanto como cabría esperar. '
        'Puede que haya una fuente de fatiga que el sistema todavía no capta.'
    ),
    'entrenar': (
        'En {n} sesiones propuestas como normales, apareció margen bajo después. '
        'Quizá el sistema deba mirar mejor señales de fatiga acumulada antes de '
        'proponer entrenar sin condiciones.'
    ),
    'version_reducida': (
        'En {n} sesiones en versión esencial, la continuidad no mejoró tan claramente '
        'como sugería la señal. Puede que la causa que activó el modo esencial '
        'persista más allá de una sesión.'
    ),
}

_DEFAULT_OBSERVACION = (
    'En {n} decisiones recientes de tipo "{estado}", aparecieron señales posteriores '
    'de margen bajo. Quizá haya una señal que el sistema todavía no está mirando bien.'
)


_PATRON_PREFIX = 'hipotesis_senal_'  # SugerenciaPlan.patron prefix for hypothesis suggestions
_DURACION_EXPERIMENTO = 14  # days


def _hipotesis_mas_relevante(hipotesis: list[dict]) -> dict | None:
    """Returns the single most repeated hypothesis (highest ocurrencias)."""
    if not hipotesis:
        return None
    return max(hipotesis, key=lambda h: h['ocurrencias'])


def get_sugerencia_hipotesis_activa(cliente) -> 'SugerenciaPlan | None':
    """
    Phase 37 — Returns pending hypothesis suggestion if one exists.
    Only one active at a time (prevents Centro becoming a lab).
    """
    try:
        from entrenos.models import SugerenciaPlan
        return SugerenciaPlan.objects.filter(
            cliente=cliente,
            patron__startswith=_PATRON_PREFIX,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        ).order_by('-fecha_generada').first()
    except Exception:
        return None


def generar_sugerencia_hipotesis(cliente, fecha_ref=None) -> 'SugerenciaPlan | None':
    """
    Phase 37 — Creates a SugerenciaPlan from the most repeated hypothesis.

    Rules:
    - Only if ≥ MIN_OCURRENCIAS senal_no_captada.
    - Only one pending hypothesis suggestion at a time.
    - Only if no vigilar_senal IntervencionPlan is currently active.
    - Text: experimental, no verdicts. "Probar" not "Aplicar".
    """
    from entrenos.models import SugerenciaPlan, IntervencionPlan
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()

    # Guard: no active vigilar_senal intervention
    if IntervencionPlan.objects.filter(
        cliente=cliente,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_fin__gte=fecha_ref,
    ).exists():
        return None

    # Guard: no pending hypothesis suggestion
    if get_sugerencia_hipotesis_activa(cliente):
        return None

    hipotesis = detectar_hipotesis_abiertas(cliente)
    mejor = _hipotesis_mas_relevante(hipotesis)
    if not mejor:
        return None

    estado = mejor['estado']
    n = mejor['ocurrencias']
    patron = f"{_PATRON_PREFIX}{estado}"

    # Guard: no recent cooldown for this pattern
    if SugerenciaPlan.objects.filter(
        cliente=cliente,
        patron=patron,
        estado=SugerenciaPlan.ESTADO_IGNORADA,
        cooldown_hasta__gte=fecha_ref,
    ).exists():
        return None

    texto = (
        f"Esta señal se ha repetido {n} veces.\n\n"
        f"Puede que el plan necesite observar mejor esta variable antes de decidir. "
        f"¿Quieres probar durante {_DURACION_EXPERIMENTO} días que el plan "
        f"vigile esta señal con más atención antes de proponer entrenar?"
    )

    return SugerenciaPlan.objects.create(
        cliente=cliente,
        patron=patron,
        texto=texto,
        estado=SugerenciaPlan.ESTADO_PENDIENTE,
    )


def aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=None) -> 'IntervencionPlan':
    """
    Phase 37 — Converts an accepted hypothesis suggestion into a 14-day experiment.
    Creates IntervencionPlan(tipo='vigilar_senal'). Does NOT change loads.
    """
    from entrenos.models import IntervencionPlan, SugerenciaPlan
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()
    fecha_fin = fecha_ref + _td(days=_DURACION_EXPERIMENTO)

    sugerencia.estado = SugerenciaPlan.ESTADO_ACEPTADA
    sugerencia.save(update_fields=['estado'])

    return IntervencionPlan.objects.create(
        cliente=sugerencia.cliente,
        sugerencia=sugerencia,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        origen_patron=sugerencia.patron,
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_fin,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )


def evaluar_fin_experimento_hipotesis(cliente, fecha_ref=None) -> dict | None:
    """
    Phase 37 — After the vigilar_senal experiment ends, check if senal_no_captada
    occurrences decreased during the experiment window.

    Returns {resultado: 'atenuada' | 'persiste' | 'insuficiente', texto: str} or None.
    Does NOT change the motor. Just records the observation.
    """
    from entrenos.models import IntervencionPlan, GymDecisionTraceEvaluation
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()

    # Find recently expired vigilar_senal intervention
    intervencion = IntervencionPlan.objects.filter(
        cliente=cliente,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado__in=[IntervencionPlan.ESTADO_EXPIRADA, IntervencionPlan.ESTADO_ACTIVA],
        fecha_fin__lte=fecha_ref,
    ).order_by('-fecha_fin').first()

    if not intervencion:
        return None

    # Count senal_no_captada during and before experiment
    antes_desde = intervencion.fecha_inicio - _td(days=_DURACION_EXPERIMENTO)
    antes_n = GymDecisionTraceEvaluation.objects.filter(
        trace__cliente=cliente,
        trace__fecha__gte=antes_desde,
        trace__fecha__lt=intervencion.fecha_inicio,
        resultado='senal_no_captada',
    ).count()

    durante_n = GymDecisionTraceEvaluation.objects.filter(
        trace__cliente=cliente,
        trace__fecha__gte=intervencion.fecha_inicio,
        trace__fecha__lte=intervencion.fecha_fin,
        resultado='senal_no_captada',
    ).count()

    if antes_n == 0:
        return {'resultado': 'insuficiente', 'texto': 'Sin datos previos suficientes para comparar.'}

    if durante_n < antes_n * 0.6:  # 40%+ reduction
        return {
            'resultado': 'atenuada',
            'texto': (
                f'Durante el experimento, la señal apareció {durante_n} vez/veces '
                f'(antes: {antes_n}). Parece que observar esta variable con más '
                f'atención redujo la señal. Hipótesis provisionalmente atenuada.'
            ),
        }
    return {
        'resultado': 'persiste',
        'texto': (
            f'La señal siguió apareciendo ({durante_n} vez/veces durante el experimento). '
            f'La hipótesis permanece abierta. Puede que haya otras variables implicadas.'
        ),
    }


def detectar_hipotesis_abiertas(cliente, ventana_dias=_VENTANA_DIAS, min_ocurrencias=_MIN_OCURRENCIAS) -> list[dict]:
    """
    Phase 36 — Detects repeated senal_no_captada patterns for a client.

    Returns a list of observations (not corrections). Each observation:
        estado:      decision type where the pattern appeared
        ocurrencias: number of senal_no_captada instances
        texto:       human-readable, tentative observation
        fechas:      dates of the pattern (up to 3, for context)

    Returns [] when:
    - No senal_no_captada exists
    - Fewer than min_ocurrencias in the window
    - Any error (degrades silently)
    """
    try:
        from django.utils import timezone
        from entrenos.models import GymDecisionTraceEvaluation, GymDecisionTrace

        hoy = timezone.localdate()
        desde = hoy - _td(days=ventana_dias)

        # Fetch all senal_no_captada evaluations in the window
        evaluaciones = list(
            GymDecisionTraceEvaluation.objects.filter(
                trace__cliente=cliente,
                trace__fecha__gte=desde,
                resultado='senal_no_captada',
            ).select_related('trace').order_by('-trace__fecha')
        )

        if not evaluaciones:
            return []

        # Group by decision_estado
        from collections import defaultdict
        por_estado = defaultdict(list)
        for ev in evaluaciones:
            por_estado[ev.trace.decision_estado].append(ev.trace.fecha)

        hipotesis = []
        for estado, fechas in por_estado.items():
            n = len(fechas)
            if n < min_ocurrencias:
                continue

            texto_template = _OBSERVACIONES.get(estado, _DEFAULT_OBSERVACION)
            texto = texto_template.format(n=n, estado=estado)

            hipotesis.append({
                'estado':      estado,
                'ocurrencias': n,
                'texto':       texto,
                'fechas':      sorted(fechas, reverse=True)[:3],
            })

        # Sort by ocurrencias desc (most repeated first)
        hipotesis.sort(key=lambda x: x['ocurrencias'], reverse=True)
        return hipotesis

    except Exception as e:
        logger.warning('detectar_hipotesis_abiertas falló: %s', e)
        return []
