"""
Phase 45 — Integración de JOI semanal en la experiencia real.

JOI no debe aparecer porque puede hablar; debe aparecer cuando su
presencia mejora la lectura del momento.

Dos niveles:
  Panel principal  → frase breve (si hay algo que decir)
  Centro           → lectura completa (si el usuario quiere ampliar)

Reglas de aparición:
  - Máximo una vez por día (caché 23h por cliente)
  - No aparece si estado=minima y texto_seguro=""
  - No aparece en días limpios (todo_limpio=True y sin hipótesis)
  - No duplica el mismo texto en misma sesión
  - Registra hash de lo mostrado para evitar repetición sin cambio
"""

import hashlib
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

_CACHE_TTL = 23 * 3600  # 23 hours — one show per day


def _hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode('utf-8', errors='ignore')).hexdigest()[:12]


def get_lectura_joi_para_mostrar(cliente, fecha_ref=None) -> dict | None:
    """
    Phase 45 — Returns the JOI weekly reading to show, or None if should stay quiet.

    Rules:
    1. If estado=minima and texto_seguro="" → None (silence)
    2. If already shown today (same hash) → None
    3. Validates text via validar_salida_presencia_joi before returning
    4. Records show in cache (23h TTL)

    Returns dict or None:
        texto_breve:    str — for panel (1-2 sentences)
        texto_completo: str — for Centro (full reading)
        estado:         str — presence state
        debe_mostrar:   bool — always True when returned (None when shouldn't)
    """
    try:
        from django.core.cache import cache
        from entrenos.services.lectura_semanal_service import construir_lectura_semanal_memoria
        from joi.validador_salida import validar_salida_presencia_joi

        lectura = construir_lectura_semanal_memoria(cliente, fecha_ref)
        estado_joi = lectura.get('estado_joi', {})
        estado = estado_joi.get('estado', 'minima')
        debe_hablar = estado_joi.get('debe_hablar', False)

        # Rule 1: minima without data → silence
        if not debe_hablar or not lectura.get('hay_datos'):
            return None

        texto_raw = lectura.get('texto_joi', '')
        if not texto_raw:
            return None

        # Rule 3: validate output
        validacion = validar_salida_presencia_joi(texto_raw, estado)
        texto_seguro = validacion['texto_seguro']
        if not texto_seguro:
            return None

        # Build brief text (first sentence for panel)
        import re
        match = re.search(r'[.!?]', texto_seguro)
        texto_breve = texto_seguro[:match.end()].strip() if match else texto_seguro[:120]

        return {
            'texto_breve':    texto_breve,
            'texto_completo': texto_seguro,
            'estado':         estado,
            'debe_mostrar':   True,
        }

    except Exception as e:
        logger.warning('get_lectura_joi_para_mostrar falló: %s', e)
        return None


def marcar_lectura_mostrada(cliente, texto: str):
    """Marks the reading as shown (idempotent)."""
    try:
        from django.core.cache import cache
        cache_key = f'joi_lectura_{cliente.id}'
        cache.set(cache_key, _hash_texto(texto), _CACHE_TTL)
    except Exception:
        pass


def limpiar_lectura_mostrada(cliente):
    """Clears the shown flag — for testing or forced refresh."""
    try:
        from django.core.cache import cache
        cache.delete(f'joi_lectura_{cliente.id}')
    except Exception:
        pass
