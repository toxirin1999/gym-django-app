"""
Phase 44 — Auditoría de salida real de JOI.

Phase 43 decidió el tono antes de generar.
Phase 44 comprueba que la voz generada no traicione ese tono.

El ciclo completo:
  lectura semanal → estado de presencia → prompt blindado
  → salida generada → validación → apertura segura

CONTRACT:
- No censura creatividad: solo rechaza lo que rompe el contrato de presencia.
- Fallos tienen fallback seguro, nunca silencio forzoso (excepto minima).
- Nunca lanza excepción: degrada silenciosamente.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Configuración por estado ──────────────────────────────────────────────────

_MAX_SENTENCES_MINIMA = 2       # minima puede tener como mucho 2 frases cortas
_MAX_CHARS_SERENA     = 300     # serena debe ser breve
_MAX_SENTENCES_SERENA = 3

_CELEBRACION_PATTERNS = [
    r'gran semana', r'increíble', r'excepcional', r'fenomenal',
    r'disciplina increíble', r'estás demostrando', r'impresionante',
    r'!{2,}',  # multiple exclamation marks
]

_CONCLUSION_PATTERNS = [
    r'has acumulado', r'estás acumulando', r'el sistema ha detectado que',
    r'definitivamente', r'claramente estás', r'es evidente que',
    r'estás atravesando una fase',
]

_URGENCIA_PATTERNS = [
    r'\bdebes\b', r'tienes que', r'necesitas ahora', r'urgente', r'inmediatamente',
]

_ENUMERACION_PATTERNS = [
    r'has (pausado|recuperado|reducido|completado) \d',  # "has pausado 3 veces"
    r'\d+ (veces|sesiones|bloques|días)',   # "3 veces", "2 sesiones"
]

_IDENTIDAD_PATTERNS = [
    r'eres alguien que', r'esto te define', r'tu forma de ser',
    r'siempre eres', r'nunca eres',
]

_AUDIT_PATTERNS = _CELEBRACION_PATTERNS + _CONCLUSION_PATTERNS + _IDENTIDAD_PATTERNS


def _contar_frases(texto: str) -> int:
    """Counts sentences by splitting on '.', '!', '?' (rough estimate)."""
    if not texto:
        return 0
    frases = re.split(r'[.!?]+', texto.strip())
    return sum(1 for f in frases if f.strip())


def _tiene_patron(texto: str, patrones: list) -> str | None:
    """Returns first matching pattern or None."""
    texto_lower = texto.lower()
    for patron in patrones:
        if re.search(patron, texto_lower):
            return patron
    return None


_FALLBACKS = {
    'minima':      '',  # silence
    'observadora': 'Hay una señal que se ha repetido. Todavía no dice qué cambiar, solo dónde mirar.',
    'serena':      'Esta semana hubo margen. No hace falta forzarlo.',  # neutral, not celebratory
    'acompañante': None,  # truncate to first sentence
}


def _primer_frase(texto: str) -> str:
    """Returns only the first sentence of the text."""
    if not texto:
        return ''
    match = re.search(r'[.!?]', texto)
    if match:
        return texto[:match.end()].strip()
    return texto[:120].strip()


def validar_salida_presencia_joi(texto: str, estado_presencia: str) -> dict:
    """
    Phase 44 — Validates that a generated JOI response respects its presence contract.

    Returns:
        valida:       bool
        motivo:       str | None  — reason for rejection
        texto_seguro: str         — safe text to use (may be '' for minima, fallback for others)
    """
    try:
        if not texto or not texto.strip():
            return {'valida': True, 'motivo': None, 'texto_seguro': texto or ''}

        texto_limpio = texto.strip()

        # ── Universal: identidad y absolutos (Phase 31 audit) ────────────────
        patron_id = _tiene_patron(texto_limpio, _IDENTIDAD_PATTERNS)
        if patron_id:
            return {
                'valida': False,
                'motivo': f'identidad_detectada: {patron_id}',
                'texto_seguro': _aplicar_fallback(estado_presencia, texto_limpio),
            }

        # ── Estado: minima ────────────────────────────────────────────────────
        if estado_presencia == 'minima':
            n_frases = _contar_frases(texto_limpio)
            if n_frases > _MAX_SENTENCES_MINIMA:
                return {
                    'valida': False,
                    'motivo': f'minima_demasiado_larga: {n_frases} frases',
                    'texto_seguro': '',  # silence for minima
                }
            patron_inv = _tiene_patron(texto_limpio, _CONCLUSION_PATTERNS)
            if patron_inv:
                return {
                    'valida': False,
                    'motivo': f'minima_interpreta_sin_datos: {patron_inv}',
                    'texto_seguro': '',
                }
            return {'valida': True, 'motivo': None, 'texto_seguro': texto_limpio}

        # ── Estado: serena ────────────────────────────────────────────────────
        if estado_presencia == 'serena':
            patron_cel = _tiene_patron(texto_limpio, _CELEBRACION_PATTERNS)
            if patron_cel:
                return {
                    'valida': False,
                    'motivo': f'serena_celebracion: {patron_cel}',
                    'texto_seguro': _FALLBACKS['serena'],  # fixed neutral fallback
                }
            if len(texto_limpio) > _MAX_CHARS_SERENA or _contar_frases(texto_limpio) > _MAX_SENTENCES_SERENA:
                return {
                    'valida': False,
                    'motivo': 'serena_demasiado_larga',
                    'texto_seguro': _primer_frase(texto_limpio),  # truncate when just too long
                }
            return {'valida': True, 'motivo': None, 'texto_seguro': texto_limpio}

        # ── Estado: observadora ───────────────────────────────────────────────
        if estado_presencia == 'observadora':
            patron_conc = _tiene_patron(texto_limpio, _CONCLUSION_PATTERNS)
            if patron_conc:
                return {
                    'valida': False,
                    'motivo': f'observadora_conclusion: {patron_conc}',
                    'texto_seguro': _FALLBACKS['observadora'],
                }
            # Should use tentative language
            tentativo = ['quizá', 'puede', 'todavía', 'señal', 'repetid', 'parece', 'quiza']
            if not any(k in texto_limpio.lower() for k in tentativo):
                return {
                    'valida': False,
                    'motivo': 'observadora_sin_lenguaje_tentativo',
                    'texto_seguro': _FALLBACKS['observadora'],
                }
            return {'valida': True, 'motivo': None, 'texto_seguro': texto_limpio}

        # ── Estado: acompañante ───────────────────────────────────────────────
        if estado_presencia == 'acompañante':
            patron_urg = _tiene_patron(texto_limpio, _URGENCIA_PATTERNS)
            if patron_urg:
                return {
                    'valida': False,
                    'motivo': f'acompañante_urgencia: {patron_urg}',
                    'texto_seguro': _primer_frase(texto_limpio),
                }
            patron_enum = _tiene_patron(texto_limpio, _ENUMERACION_PATTERNS)
            if patron_enum:
                return {
                    'valida': False,
                    'motivo': f'acompañante_enumeracion: {patron_enum}',
                    'texto_seguro': _primer_frase(texto_limpio),
                }
            return {'valida': True, 'motivo': None, 'texto_seguro': texto_limpio}

        # ── Estado desconocido: pasa sin modificar ─────────────────────────────
        return {'valida': True, 'motivo': None, 'texto_seguro': texto_limpio}

    except Exception as e:
        logger.warning('validar_salida_presencia_joi falló: %s', e)
        return {'valida': True, 'motivo': None, 'texto_seguro': texto or ''}


def _aplicar_fallback(estado: str, texto_original: str) -> str:
    fallback = _FALLBACKS.get(estado)
    if fallback is None:
        return _primer_frase(texto_original)
    return fallback
