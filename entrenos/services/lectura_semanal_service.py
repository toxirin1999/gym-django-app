"""
Phase 40 — Lectura semanal del sistema de memoria.

No para añadir más decisión diaria, sino para resumir la semana con el mismo
contrato: qué decidió el plan, qué señales aparecieron, qué aprendió,
y qué decidió callar.

CONTRACT:
- Read-only. No modifica nada.
- Mismo vocabulario que Phase 34/36/38: tentativo, sin veredictos.
- Si no hay datos suficientes, devuelve texto vacío o mínimo.
- Diseñado para JOI y para el panel semanal.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def construir_lectura_semanal_memoria(cliente, fecha_ref=None) -> dict:
    """
    Phase 40 — Builds a weekly memory reading for the client.

    Returns:
        n_decisiones:        int — traces in the week
        balance_estados:     dict — {estado: count}
        senales_positivas:   int — libero_margen evaluations
        senales_no_captadas: int — senal_no_captada evaluations
        n_hipotesis_abiertas: int
        n_preferencias_activas: int
        texto_joi:           str — tentative, JOI-ready text
        hay_datos:           bool
    """
    try:
        from django.utils import timezone
        from entrenos.models import GymDecisionTrace, GymDecisionTraceEvaluation
        from entrenos.services.hipotesis_service import detectar_hipotesis_abiertas
        from entrenos.services.gobernanza_service import aplicar_gobernanza_hipotesis

        fecha_ref = fecha_ref or timezone.localdate()
        lunes = fecha_ref - timedelta(days=fecha_ref.weekday())

        # 1. Traces this week
        traces = list(
            GymDecisionTrace.objects.filter(
                cliente=cliente, fecha__gte=lunes, fecha__lte=fecha_ref,
            ).values('decision_estado', 'id')
        )
        n_decisiones = len(traces)

        if n_decisiones == 0:
            return _vacio()

        # Balance de estados
        balance = {}
        for t in traces:
            e = t['decision_estado']
            balance[e] = balance.get(e, 0) + 1

        trace_ids = [t['id'] for t in traces]

        # 2. Evaluations this week
        evaluaciones = list(
            GymDecisionTraceEvaluation.objects.filter(
                trace_id__in=trace_ids,
            ).values_list('resultado', flat=True)
        )
        senales_positivas   = evaluaciones.count('libero_margen')
        senales_no_captadas = evaluaciones.count('senal_no_captada')

        # 3. Hipótesis abiertas (gobernadas)
        hipotesis_raw = detectar_hipotesis_abiertas(cliente)
        hipotesis     = aplicar_gobernanza_hipotesis(cliente, hipotesis_raw, fecha_ref)
        n_hipotesis   = len(hipotesis)

        # 4. Preferencias activas
        from entrenos.models import PreferenciaPlanAprendida
        n_pref = PreferenciaPlanAprendida.objects.filter(
            cliente=cliente, estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
        ).count()

        texto = _construir_texto(
            n_decisiones, balance, senales_positivas,
            senales_no_captadas, n_hipotesis, n_pref,
        )

        return {
            'n_decisiones':          n_decisiones,
            'balance_estados':       balance,
            'senales_positivas':     senales_positivas,
            'senales_no_captadas':   senales_no_captadas,
            'n_hipotesis_abiertas':  n_hipotesis,
            'n_preferencias_activas': n_pref,
            'texto_joi':             texto,
            'hay_datos':             True,
        }

    except Exception as e:
        logger.warning('construir_lectura_semanal_memoria falló: %s', e)
        return _vacio()


def _vacio():
    return {
        'n_decisiones': 0, 'balance_estados': {}, 'senales_positivas': 0,
        'senales_no_captadas': 0, 'n_hipotesis_abiertas': 0,
        'n_preferencias_activas': 0, 'texto_joi': '', 'hay_datos': False,
    }


def _construir_texto(n, balance, positivas, no_captadas, n_hip, n_pref) -> str:
    """Builds a tentative, JOI-ready weekly summary. No verdicts."""
    lineas = []

    # Decisiones
    lineas.append(f"Esta semana el plan registró {n} decisión{'es' if n > 1 else ''}.")

    # Balance de estados (solo los relevantes)
    if balance.get('recuperar', 0) > 0 or balance.get('posponer', 0) > 0:
        partes = []
        if balance.get('recuperar', 0):
            partes.append(f"{balance['recuperar']} recuperación{'es' if balance['recuperar'] > 1 else ''}")
        if balance.get('posponer', 0):
            partes.append(f"{balance['posponer']} pospuesta{'s' if balance['posponer'] > 1 else ''}")
        lineas.append(f"De ellas: {', '.join(partes)}.")

    # Señales positivas
    if positivas > 0:
        lineas.append(
            f"En {positivas} decisión{'es' if positivas > 1 else ''} aparecieron "
            f"señales de margen liberado."
        )

    # Señales no captadas
    if no_captadas > 0:
        lineas.append(
            f"En {no_captadas} decisión{'es' if no_captadas > 1 else ''} apareció "
            f"una señal que quizá no se captó antes. "
            f"{'El sistema ya lo tiene anotado.' if no_captadas >= 2 else ''}"
        )

    # Hipótesis abiertas
    if n_hip > 0:
        lineas.append(
            f"{'Hay' if n_hip == 1 else 'Siguen abiertas'} {n_hip} "
            f"hipótesis{'s' if n_hip > 1 else ''} acumulada{'s' if n_hip > 1 else ''} "
            f"pendiente{'s' if n_hip > 1 else ''} de valorar."
        )

    # Preferencias activas
    if n_pref > 0:
        lineas.append(
            f"El plan mantiene {n_pref} preferencia{'s' if n_pref > 1 else ''} "
            f"aprendida{'s' if n_pref > 1 else ''} como referencia."
        )

    return ' '.join(lineas)
