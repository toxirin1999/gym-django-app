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
from datetime import timedelta

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
        desde = hoy - timedelta(days=ventana_dias)

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
