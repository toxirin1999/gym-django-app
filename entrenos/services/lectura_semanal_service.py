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
    """
    Builds a JOI-voice weekly summary. Not a report — a reading.

    Rule: lead with the most significant signal, connect naturally,
    don't enumerate everything mechanically. End with open threads.
    """
    if n == 0:
        return ''

    partes = []

    # ── Señal dominante de la semana ──────────────────────────────────────────
    pausas = balance.get('recuperar', 0) + balance.get('posponer', 0)

    if positivas > 0 and no_captadas == 0:
        # Good week: margin appeared
        if positivas >= 2:
            partes.append(
                f"Esta semana el margen apareció en {positivas} de las {n} decisiones. "
                f"Una señal de continuidad."
            )
        else:
            partes.append(
                f"Esta semana hubo margen suficiente en la decisión que importaba."
            )

    elif no_captadas > 0 and positivas == 0:
        # Signal not captured, nothing positive
        if no_captadas >= 2:
            partes.append(
                f"Esta semana aparecieron {no_captadas} señales que quizá el sistema "
                f"no captó bien antes de decidir."
            )
        else:
            partes.append(
                f"Esta semana apareció una señal que quizá el sistema no captó del todo."
            )

    elif positivas > 0 and no_captadas > 0:
        # Mixed week
        partes.append(
            f"Esta semana el plan dejó señales mixtas: "
            f"hubo margen en {positivas} {'decisión' if positivas == 1 else 'decisiones'}, "
            f"pero también apareció una señal que quizá merece observarse mejor."
        )

    else:
        # Neutral: just count
        if pausas > 0:
            partes.append(
                f"Esta semana el plan priorizó {'el descanso o la pausa' if pausas == n else 'pausar en algún momento'}. "
                f"Sin señal clara en ningún sentido."
            )
        else:
            partes.append(
                f"Esta semana el plan tomó {n} decisión{'es' if n > 1 else ''} sin señales llamativas."
            )

    # ── Hilo abierto: hipótesis ────────────────────────────────────────────────
    if n_hip >= 1:
        if n_hip == 1:
            partes.append(
                "Sigue abierta una hipótesis que el sistema está observando, "
                "pendiente de que decidas si vale la pena convertirla en experimento."
            )
        else:
            partes.append(
                f"Hay {n_hip} hipótesis abiertas que el sistema mantiene anotadas."
            )

    # ── Preferencias como contexto de fondo ───────────────────────────────────
    if n_pref > 0 and len(partes) < 2:  # solo si la lectura es corta
        partes.append(
            f"El plan sigue usando {'una preferencia aprendida' if n_pref == 1 else f'{n_pref} preferencias'} "
            f"como referencia de fondo."
        )

    return ' '.join(partes)
