"""
Phase 34 — Seguimiento posterior de decisiones.

CONTRACT:
- No evalúa si el motor "tenía razón".
- No puntúa al motor ni culpa al usuario.
- No declara causalidad fuerte.
- Lenguaje: "parece", "puede", "señal", "provisionalmente", "quizá".
- Automática: se ejecuta 2+ días después de la decisión.
- Un evaluación por trace. No duplica.

Pregunta que responde:
    ¿Qué señales observables aparecieron después de esta decisión?
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# Ventana de observación posterior (días)
_VENTANA_POSTERIOR = 4   # mirar hasta 4 días después de la decisión
_MIN_DIAS_ESPERA   = 2   # no evaluar el mismo día ni el día siguiente


def _recopilar_senales_posteriores(cliente, fecha_decision: 'date') -> dict:
    """
    Reads observable signals from fecha_decision+1 to fecha_decision+VENTANA.
    Returns a dict — never raises; returns {} on any error.
    """
    from entrenos.models import EntrenoRealizado, EjercicioRealizado
    senales = {}
    fecha_desde = fecha_decision + timedelta(days=1)
    fecha_hasta = fecha_decision + timedelta(days=_VENTANA_POSTERIOR)

    try:
        entrenos = list(
            EntrenoRealizado.objects.filter(
                cliente=cliente,
                fecha__gte=fecha_desde,
                fecha__lte=fecha_hasta,
            ).order_by('fecha')
        )
        senales['sesiones_posteriores'] = len(entrenos)

        if entrenos:
            primer = entrenos[0]
            senales['dias_hasta_sesion'] = (primer.fecha - fecha_decision).days
            senales['modo_reducido']      = getattr(primer, 'modo_reducido', False)

            # RPE medio de ejercicios de la primera sesión posterior
            rpes = list(
                EjercicioRealizado.objects.filter(
                    entreno=primer,
                ).exclude(rpe__isnull=True).values_list('rpe', flat=True)
            )
            if rpes:
                senales['rpe_medio_posterior'] = round(sum(rpes) / len(rpes), 1)

    except Exception as e:
        logger.debug('_recopilar_senales_posteriores falló: %s', e)

    return senales


def _calcular_resultado(estado_decision: str, senales: dict, trace) -> tuple[str, str]:
    """
    Returns (resultado, resumen) based on decision state and posterior signals.
    Language is deliberately provisional — no strong causality.
    """
    from entrenos.models import GymDecisionTraceEvaluation as Eval
    n_sesiones = senales.get('sesiones_posteriores', 0)
    dias       = senales.get('dias_hasta_sesion')
    rpe        = senales.get('rpe_medio_posterior')
    reducido   = senales.get('modo_reducido', False)

    # ── Decisiones de pausar/recuperar (posponer, recuperar) ─────────────────
    if estado_decision in ('posponer', 'recuperar'):
        if n_sesiones == 0:
            return (
                Eval.INSUFICIENTE,
                'No hubo sesión en los días siguientes. Sin datos para valorar si mover la sesión aportó margen.',
            )
        if dias is not None and dias <= 2 and rpe is not None and rpe <= 7 and not reducido:
            return (
                Eval.LIBERO_MARGEN,
                f'Después de mover la sesión, el bloque siguiente se completó dentro de {dias} día{"s" if dias > 1 else ""} '
                f'con un margen razonable (RPE ~{rpe}). '
                f'Esa señal refuerza provisionalmente la decisión de separar la carga.',
            )
        if rpe is not None and rpe >= 9:
            return (
                Eval.SENAL_NO_CAPTADA,
                f'Aunque la sesión se movió, el RPE posterior fue alto (~{rpe}). '
                f'Puede que hubiera fatiga no captada que persistió, aunque también '
                f'pueden influir otros factores. No hay suficiente evidencia para '
                f'una lectura definitiva.',
            )
        return (
            Eval.NEUTRO,
            'La sesión se realizó después, aunque sin una señal clara de que moverla haya cambiado mucho el margen. '
            'Resultado inconcluso.',
        )

    # ── Sesión normal (entrenar, sesion_hoy) ──────────────────────────────────
    if estado_decision in ('entrenar', 'sesion_hoy'):
        if rpe is not None and rpe >= 9:
            return (
                Eval.SENAL_NO_CAPTADA,
                f'La sesión se propuso sin señales especiales, pero el margen posterior fue bajo (RPE ~{rpe}). '
                f'Quizá había una señal de fatiga que el sistema no captó ese día. '
                f'No es seguro — puede haber otros factores.',
            )
        if reducido:
            return (
                Eval.SENAL_NO_CAPTADA,
                'La sesión fue propuesta normal pero acabó en versión esencial. '
                'Puede que el cuerpo estuviera más ajustado de lo que reflejaban las métricas.',
            )
        if n_sesiones == 0:
            return (Eval.INSUFICIENTE, 'Sin datos posteriores suficientes para valorar.')
        return (
            Eval.NEUTRO,
            'La sesión se completó sin señales de alarma posterior. Sin evidencia de que faltara captar algo.',
        )

    # ── Versión esencial ──────────────────────────────────────────────────────
    if estado_decision == 'version_reducida':
        if n_sesiones > 0 and not reducido:
            return (
                Eval.LIBERO_MARGEN,
                'Después de la versión esencial, la continuidad se mantuvo sin señal de sobrecarga. '
                'Parece que reducir el volumen ese día protegió el margen.',
            )
        if n_sesiones == 0:
            return (Eval.INSUFICIENTE, 'Sin sesión posterior disponible para valorar.')
        return (Eval.NEUTRO, 'Continuidad razonable tras la versión esencial.')

    return (Eval.INSUFICIENTE, 'Tipo de decisión no reconocido para evaluación.')


def evaluar_trace_decision(trace, fecha_ref=None) -> 'GymDecisionTraceEvaluation | None':
    """
    Phase 34 — Evaluates a single GymDecisionTrace based on posterior signals.

    Returns the GymDecisionTraceEvaluation created, or None if:
    - Too soon (< MIN_DIAS_ESPERA days after the decision)
    - Already evaluated
    - Any error (degrades silently)
    """
    from django.utils import timezone
    from entrenos.models import GymDecisionTraceEvaluation

    try:
        hoy = fecha_ref or timezone.localdate()
        if (hoy - trace.fecha).days < _MIN_DIAS_ESPERA:
            return None

        if GymDecisionTraceEvaluation.objects.filter(trace=trace).exists():
            return trace.evaluacion

        senales = _recopilar_senales_posteriores(trace.cliente, trace.fecha)
        resultado, resumen = _calcular_resultado(trace.decision_estado, senales, trace)

        return GymDecisionTraceEvaluation.objects.create(
            trace=trace,
            resultado=resultado,
            resumen=resumen,
            senales_posteriores=senales,
        )

    except Exception as e:
        logger.warning('evaluar_trace_decision falló para trace %s: %s', getattr(trace, 'id', '?'), e)
        return None


def evaluar_traces_pendientes(cliente, fecha_ref=None, max_batch: int = 10) -> int:
    """
    Phase 34 — Evaluates all non-evaluated traces old enough for the client.
    Returns count of new evaluations created.
    """
    from django.utils import timezone
    from entrenos.models import GymDecisionTrace, GymDecisionTraceEvaluation

    try:
        fecha_ref = fecha_ref or timezone.localdate()
        limite = fecha_ref - timedelta(days=_MIN_DIAS_ESPERA)

        ya_evaluados = set(
            GymDecisionTraceEvaluation.objects.filter(
                trace__cliente=cliente,
            ).values_list('trace_id', flat=True)
        )

        pendientes = (
            GymDecisionTrace.objects.filter(
                cliente=cliente,
                fecha__lte=limite,
            ).exclude(id__in=ya_evaluados)
            .order_by('-fecha')[:max_batch]
        )

        count = 0
        for trace in pendientes:
            ev = evaluar_trace_decision(trace, fecha_ref=fecha_ref)
            if ev:
                count += 1
        return count

    except Exception as e:
        logger.warning('evaluar_traces_pendientes falló: %s', e)
        return 0
