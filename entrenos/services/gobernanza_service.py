"""
Phase 38 — Gobernanza del ciclo de aprendizaje.

El sistema ya sabe aprender; ahora necesita saber olvidar, pausar y no insistir.

Reglas:
1. Max 2 hipótesis visibles al mismo tiempo (las más repetidas).
2. Hipótesis sin ocurrencias recientes en >30 días → silencio (no stale noise).
3. Hipótesis atenuada → cooldown 45 días antes de reproponerse.
4. Hipótesis persistente → cooldown 30 días.
5. Hipótesis ignorada 2+ veces → pausa 21 días.
6. Hipótesis muy antigua (>60 días desde primera ocurrencia) sin experimento → silencio.

CONTRACT:
- Read-only audit + SugerenciaPlan status updates only.
- NO changes to GymDecisionTrace, preferences, or motor decisions.
- Fails silently (returns governance report dict, never raises).
"""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Governance thresholds
_MAX_HIPOTESIS_VISIBLES   = 2
_DIAS_SIN_OCURRENCIA      = 30   # silence stale hypotheses
_COOLDOWN_ATENUADA        = 45   # days before re-proposing after 'atenuada'
_COOLDOWN_PERSISTE        = 30   # days before re-proposing after 'persiste'
_COOLDOWN_IGNORADA_N      = 2    # number of ignores before auto-pause
_COOLDOWN_IGNORADA_DIAS   = 21   # days to pause after too many ignores
_DIAS_SIN_EXPERIMENTO_MAX = 60   # hypothesis too old without experiment → silence


def _ultima_ocurrencia_senal(cliente, estado_decision: str, ventana_dias=60) -> 'date | None':
    """Returns the most recent senal_no_captada date for this decision state."""
    try:
        from entrenos.models import GymDecisionTraceEvaluation
        hoy = timezone.localdate()
        ev = (
            GymDecisionTraceEvaluation.objects.filter(
                trace__cliente=cliente,
                trace__decision_estado=estado_decision,
                resultado='senal_no_captada',
                trace__fecha__gte=hoy - timedelta(days=ventana_dias),
            )
            .order_by('-trace__fecha')
            .values_list('trace__fecha', flat=True)
            .first()
        )
        return ev
    except Exception:
        return None


def _primera_ocurrencia_senal(cliente, estado_decision: str) -> 'date | None':
    """Returns the oldest senal_no_captada date for this decision state."""
    try:
        from entrenos.models import GymDecisionTraceEvaluation
        ev = (
            GymDecisionTraceEvaluation.objects.filter(
                trace__cliente=cliente,
                trace__decision_estado=estado_decision,
                resultado='senal_no_captada',
            )
            .order_by('trace__fecha')
            .values_list('trace__fecha', flat=True)
            .first()
        )
        return ev
    except Exception:
        return None


def _veces_ignorada(cliente, patron: str) -> int:
    """Count how many times this hypothesis suggestion was ignored."""
    try:
        from entrenos.models import SugerenciaPlan
        return SugerenciaPlan.objects.filter(
            cliente=cliente,
            patron=patron,
            estado=SugerenciaPlan.ESTADO_IGNORADA,
        ).count()
    except Exception:
        return 0


def _tiene_experimento_reciente_atenuado(cliente, patron: str, dias: int) -> bool:
    """True if there was a vigilar_senal experiment that ended as 'atenuada' in the last N days."""
    try:
        from entrenos.models import IntervencionPlan
        hoy = timezone.localdate()
        return IntervencionPlan.objects.filter(
            cliente=cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            origen_patron=patron,
            fecha_fin__gte=hoy - timedelta(days=dias),
        ).exists()
    except Exception:
        return False


def auditar_hipotesis(cliente, hipotesis: list[dict], fecha_ref=None) -> list[dict]:
    """
    Phase 38 — Applies governance rules to a list of raw hypotheses.

    Returns a filtered + annotated list:
    - Only the top MAX_HIPOTESIS_VISIBLES
    - Each entry may have 'gobernanza_suprimida': True if filtered out
    - Reason included for auditing

    Does NOT modify DB. Just filters what's shown.
    """
    if not hipotesis:
        return []

    fecha_ref = fecha_ref or timezone.localdate()
    resultado = []

    for h in hipotesis:
        estado = h['estado']
        patron = f"hipotesis_senal_{estado}"
        motivo_supresion = None

        # Rule 2: no recent occurrences in 30 days → stale
        ultima = _ultima_ocurrencia_senal(cliente, estado)
        if ultima is None or (fecha_ref - ultima).days > _DIAS_SIN_OCURRENCIA:
            motivo_supresion = 'sin_ocurrencias_recientes'

        # Rule 6: first occurrence too long ago without experiment
        if not motivo_supresion:
            primera = _primera_ocurrencia_senal(cliente, estado)
            if primera and (fecha_ref - primera).days > _DIAS_SIN_EXPERIMENTO_MAX:
                motivo_supresion = 'demasiado_antigua_sin_experimento'

        # Rule 3/4: cooldown after recent experiment
        if not motivo_supresion:
            if _tiene_experimento_reciente_atenuado(cliente, patron, _COOLDOWN_ATENUADA):
                motivo_supresion = 'cooldown_atenuada'

        # Rule 5: too many ignores → auto-pause
        if not motivo_supresion:
            veces = _veces_ignorada(cliente, patron)
            if veces >= _COOLDOWN_IGNORADA_N:
                from entrenos.models import SugerenciaPlan
                ultima_ignorada = (
                    SugerenciaPlan.objects.filter(
                        cliente=cliente, patron=patron,
                        estado=SugerenciaPlan.ESTADO_IGNORADA,
                    ).order_by('-fecha_generada').values_list('fecha_generada', flat=True).first()
                )
                if ultima_ignorada:
                    from datetime import datetime
                    if hasattr(ultima_ignorada, 'date'):
                        ultima_ignorada = ultima_ignorada.date()
                    if (fecha_ref - ultima_ignorada).days < _COOLDOWN_IGNORADA_DIAS:
                        motivo_supresion = f'ignorada_{veces}_veces'

        if motivo_supresion:
            resultado.append({**h, 'gobernanza_suprimida': True, 'motivo': motivo_supresion})
        else:
            resultado.append({**h, 'gobernanza_suprimida': False})

    # Rule 1: cap at MAX visible
    activas = [h for h in resultado if not h.get('gobernanza_suprimida')]
    suprimidas = [h for h in resultado if h.get('gobernanza_suprimida')]

    # Return top MAX + supressed (supressed for audit only, not shown in UI)
    activas = sorted(activas, key=lambda x: x['ocurrencias'], reverse=True)[:_MAX_HIPOTESIS_VISIBLES]
    return activas + suprimidas


def aplicar_gobernanza_hipotesis(cliente, hipotesis: list[dict], fecha_ref=None) -> list[dict]:
    """
    Phase 38 — Public entry point: returns only visible (non-suppressed) hypotheses.
    Suppressed ones are filtered from the UI but the audit info is available in logs.
    """
    try:
        auditadas = auditar_hipotesis(cliente, hipotesis, fecha_ref)
        visibles = [h for h in auditadas if not h.get('gobernanza_suprimida')]
        suprimidas = [h for h in auditadas if h.get('gobernanza_suprimida')]
        if suprimidas:
            logger.debug(
                'Gobernanza suprimió %d hipótesis para cliente %s: %s',
                len(suprimidas),
                getattr(cliente, 'id', '?'),
                [h.get('motivo') for h in suprimidas],
            )
        return visibles
    except Exception as e:
        logger.warning('aplicar_gobernanza_hipotesis falló: %s', e)
        return hipotesis  # safe fallback: return unfiltered
