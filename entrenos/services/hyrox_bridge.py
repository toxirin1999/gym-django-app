"""
Bridge de sincronización Gym → Hyrox.

Punto único para las dos operaciones cross-app que los signals
de entrenos y hyrox disparan cuando se guarda un EntrenoRealizado:

  1. sync_rm_to_hyrox   — escribe rm_sentadilla / rm_peso_muerto en HyroxObjective.
  2. sync_gym_fatigue   — inyecta muscle_fatigue_index en la próxima HyroxSession.

Reglas del contrato (ver también HYROX_GYM_BRIDGE.md):
- Solo actualiza el RM si el nuevo valor es estrictamente mayor al almacenado.
- Siempre invalida la caché de readiness después de un cambio de RM.
- La inyección de fatiga solo escribe en la sesión PLANIFICADA más próxima;
  nunca modifica sesiones ya completadas.
- No lee ni escribe campos de periodicización ni readiness score
  (esos pertenecen al soberano Hyrox).
"""

import logging

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Sincronización de RM ──────────────────────────────────────────────────────

def sync_rm_to_hyrox(objetivo, campo: str, nuevo_valor: float) -> bool:
    """
    Escribe un RM en HyroxObjective si el nuevo valor supera al actual.

    Retorna True si hubo actualización efectiva.

    Nota sobre fuentes:
    - Llamado desde sincronizar_rm_con_hyrox (fuente: PR oficial, siempre exacto)
    - Llamado desde sync_gym_impact_to_hyrox (fuente: estimación Brzycki, puede inflar)
    Ambas usan la misma guarda "solo si mayor" — si el PR real es menor que una
    estimación previa, no retrocede. Es un límite conocido documentado en
    HYROX_GYM_BRIDGE.md §Conflicto doble escritura RM.
    """
    actual = getattr(objetivo, campo, None) or 0
    if nuevo_valor <= actual:
        return False

    setattr(objetivo, campo, round(nuevo_valor, 1))
    objetivo.save(update_fields=[campo])

    # Invalidar caché — ambos signals deben dejar el sistema en estado consistente
    cache.delete(f'hyrox_readiness_{objetivo.pk}')
    cache.delete(f'dashboard_acwr_unificado_{objetivo.cliente_id}')

    logger.info(
        '[hyrox_bridge] RM actualizado: cliente=%s campo=%s anterior=%.1f nuevo=%.1f',
        objetivo.cliente_id, campo, actual, nuevo_valor,
    )
    return True


# ── Inyección de fatiga de piernas ────────────────────────────────────────────

def sync_gym_fatigue(objetivo, fatiga_nivel: str, motivo: str, desde_fecha) -> bool:
    """
    Inyecta fatiga en la próxima HyroxSession planificada a partir de desde_fecha.

    fatiga_nivel: 'Alta' | 'Media' | 'Baja'
    Retorna True si inyectó fatiga en alguna sesión.
    """
    from hyrox.models import HyroxSession

    proxima = (
        HyroxSession.objects
        .filter(objective=objetivo, fecha__gte=desde_fecha, estado='planificado')
        .order_by('fecha')
        .first()
    )
    if not proxima:
        return False

    proxima.muscle_fatigue_index = fatiga_nivel
    proxima.fatiga_updated_at = timezone.now()
    proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])

    logger.info(
        '[hyrox_bridge] Fatiga inyectada: cliente=%s sesion=%s nivel=%s motivo=%.60s',
        objetivo.cliente_id, proxima.pk, fatiga_nivel, motivo,
    )
    return True


# ── Helpers de detección (reutilizados por ambos signals) ────────────────────

_SENTADILLA_KW = ('sentadilla', 'squat', 'goblet', 'hack squat', 'front squat')
_PESO_MUERTO_KW = ('peso muerto', 'deadlift', 'rdl', 'romanian', 'sumo dead')


def campo_rm_para_ejercicio(nombre_ejercicio: str) -> str | None:
    """
    Devuelve 'rm_sentadilla' o 'rm_peso_muerto' según el nombre del ejercicio.
    Devuelve None si no es un ejercicio de RM relevante.
    """
    nombre = (nombre_ejercicio or '').lower()
    if any(kw in nombre for kw in _SENTADILLA_KW):
        return 'rm_sentadilla'
    if any(kw in nombre for kw in _PESO_MUERTO_KW):
        return 'rm_peso_muerto'
    return None
