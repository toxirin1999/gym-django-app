"""
Phase 32 — Servicio de trazabilidad de decisiones del plan.

CONTRACT:
- Writes one trace per (cliente, fecha). Updates in place if called again.
- Only traces non-trivial decisions (estado != 'descanso' OR señales relevantes).
- Saves the explicacion from construir_explicacion_decision() — already audited
  by Phase 31 to be free of absolute/identity/diagnostic language.
- Safe to call asynchronously; degrades silently if it fails.
- Does NOT duplicate GymDecisionLog (per-exercise load decisions).
  This records: what the PANEL looked like and why.
"""

import logging

logger = logging.getLogger(__name__)


def _extraer_senales_motor(decision: dict) -> dict:
    ctx = decision.get('contexto_fisico') or {}
    return {
        'lesion_activa':      ctx.get('lesion_activa', False),
        'lesion_fase':        ctx.get('lesion_fase'),
        'futbol_reciente':    ctx.get('futbol_reciente', False),
        'energia_baja':       ctx.get('energia_baja', False),
        'energia_valor':      ctx.get('energia_valor'),
        'readiness_bajo':     ctx.get('readiness_bajo', False),
        'readiness_valor':    ctx.get('readiness_valor'),
        'preferencias_activas': ctx.get('preferencias_activas', []),
    }


def _extraer_capas_visibles(decision: dict, explicacion: dict) -> list[str]:
    capas = []
    if decision.get('lesion_aviso'):
        capas.append('lesion_aviso')
    if decision.get('preferencia_aplicada'):
        capas.append('preferencia_aplicada')
    if decision.get('distribucion_aviso') and not (explicacion or {}).get('distribucion_aviso_suprimido'):
        capas.append('distribucion_aviso')
    if decision.get('modo_reducido'):
        capas.append('modo_reducido')
    perm = (decision.get('entrenamiento') or {}).get('permiso_progresion', {})
    if perm.get('accion', 'progresion_permitida') != 'progresion_permitida':
        capas.append('freno_progresion')
    return capas


def _extraer_capas_suprimidas(decision: dict, explicacion: dict) -> list[str]:
    suprimidas = []
    if decision.get('distribucion_aviso') and (explicacion or {}).get('distribucion_aviso_suprimido'):
        suprimidas.append('distribucion_aviso')
    return suprimidas


def _extraer_preferencias(decision: dict) -> list[str]:
    ctx = decision.get('contexto_fisico') or {}
    return list(ctx.get('preferencias_activas', []))


def _extraer_intervenciones(cliente) -> list[str]:
    try:
        from entrenos.models import IntervencionPlan
        from django.utils import timezone
        hoy = timezone.localdate()
        return list(
            IntervencionPlan.objects.filter(
                cliente=cliente,
                estado=IntervencionPlan.ESTADO_ACTIVA,
                fecha_fin__gte=hoy,
            ).values_list('tipo', flat=True)
        )
    except Exception:
        return []


def _extraer_lesion_contexto(decision: dict) -> dict:
    aviso = decision.get('lesion_aviso')
    if not aviso:
        return {}
    return {
        'zona':              aviso.get('zona', ''),
        'fase':              aviso.get('fase', ''),
        'es_bloqueante':     aviso.get('es_bloqueante', False),
        'ejercicios_riesgo': aviso.get('ejercicios_en_riesgo', []),
    }


def registrar_decision_trace(cliente, decision: dict, fecha=None) -> None:
    """
    Phase 32 — Creates or updates a GymDecisionTrace for today's panel decision.

    Designed to be called AFTER the panel response has been sent (async-safe).
    Degrades silently if any part fails.

    Args:
        cliente:  Cliente instance
        decision: result of obtener_sesion_recomendada_hoy()
        fecha:    date override (defaults to today)
    """
    try:
        from django.utils import timezone
        from entrenos.models import GymDecisionTrace
        from entrenos.services.explicacion_decision_service import construir_explicacion_decision

        fecha = fecha or timezone.localdate()
        estado = decision.get('estado', 'entrenar')

        # Build the explanation (already narrative-audited by Phase 31)
        explicacion = construir_explicacion_decision(decision)

        # Skip descanso days with no active signals (nothing relevant to record)
        if estado == 'descanso' and not explicacion.get('senales_activas'):
            return

        sp = decision.get('sesion_programada')

        campos = {
            'decision_estado':      estado,
            'causa_principal':      decision.get('causa_principal') or '',
            'sesion_programada':    sp,
            'senales_motor':        _extraer_senales_motor(decision),
            'capas_visibles':       _extraer_capas_visibles(decision, explicacion),
            'capas_suprimidas':     _extraer_capas_suprimidas(decision, explicacion),
            'explicacion_senales':  explicacion.get('senales_activas', []),
            'preferencias_activas': _extraer_preferencias(decision),
            'intervenciones_activas': _extraer_intervenciones(cliente),
            'lesion_contexto':      _extraer_lesion_contexto(decision),
        }

        GymDecisionTrace.objects.update_or_create(
            cliente=cliente,
            fecha=fecha,
            defaults=campos,
        )

    except Exception as e:
        logger.warning('registrar_decision_trace falló para cliente %s: %s', getattr(cliente, 'id', '?'), e)
