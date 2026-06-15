"""
Phase 56.11 — Validador semántico JOI (contrato cross-módulo).

Principio: JOI puede tener profundidad, pero no autoridad para definir al usuario.

CONTRACT:
  - No diagnostica estados psicológicos.
  - No atribuye estados mentales sin evidencia directa.
  - No usa escala de readiness inconsistente ("bajo" reservado para < READINESS_BAJO_UMBRAL).
  - No emite caracteres cirílicos.
  - Aplica igual a Gym, Hyrox y Diario.

La validación NO bloquea el mensaje (JOI no se silencia por un fallo).
Solo registra la violación para trazabilidad y tests.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Umbral de readiness a partir del cual "bajo" es aceptable ───────────────
# < 35 → "Carga alta acumulada". Por encima, nunca usar la palabra "bajo".
READINESS_BAJO_UMBRAL = 35

# ── Patrones prohibidos ──────────────────────────────────────────────────────

# Diagnósticos existenciales o psicológicos como conclusiones sobre el usuario
_DIAGNOSTICOS = [
    r'es\s+apatía\s+de\s+(vivir|vida)',
    r'apatía\s+de\s+vivir',
    r'estás\s+en\s+(una\s+)?crisis',
    r'(eso\s+es|esto\s+es)\s+depresi[oó]n',
    r'eso\s+es\s+ansiedad',
    r'crisis\s+existencial',
    r'trastorno',
]

# Atribución de estados mentales sin dato explícito
_ATRIBUCIONES_MENTALES = [
    r'tu\s+mente\s+(intenta|sabe|cree|teme|quiere)',
    r'(intenta|intentas)\s+convencerte',
    r'te\s+convences',
    r'subconsciente',
    r'inconscientemente',
    r'tu\s+cabeza\s+sabe',
    r'en\s+el\s+fondo\s+sabes',
]

# "bajo" referido a readiness cuando probablemente no lo sea
_READINESS_BAJO_INCORRECTO = [
    r'readiness\s+(está\s+)?(bajo|muy\s+bajo)',
    r'bajo\s+readiness',
    r'readiness\s+\d+[.,]\s*(bajo|reducido)',
]

# Declaraciones de necesidad corporal — JOI lee márgenes, no prescribe necesidades.
# "tu cuerpo necesita X" / "necesitas descansar" / "debes entrenar" → autoridad no trazable.
# Excepción: señal crítica explícita (RPE extremo, lesión) — el validador no tiene contexto
# para distinguirla, así que solo registra la violación; no bloquea.
_NECESIDAD_CORPORAL = [
    r'tu\s+cuerpo\s+necesita',
    r'el\s+cuerpo\s+necesita',
    r'necesitas\s+(descansar|parar|entrenar|moverte|recuperar)',
    r'debes\s+(descansar|parar|entrenar|moverte|recuperar)',
]


# Vocabulario de alarma inapropiado para readiness 55-79 ("disponible con reserva/margen").
# Frases que implican estar al límite cuando el cuerpo simplemente tiene reserva moderada.
_VOCABULARIO_ALARMA_READINESS = [
    r'sin\s+colch[oó]n',
    r'llega(s)?\s+justo',
    r'al\s+l[ií]mite',
    r'en\s+el\s+l[ií]mite',
    r'(vas|est[aá]s)\s+justo(\s+de\s+(fondo|gas|margen|energ[ií]a))?',
]


# Phase 59E — Narrativa con bisturí. Frases absolutas que convierten una
# hipótesis narrativa en sentencia/diagnóstico ("cero hábitos", "no haces
# nada"...). Red de seguridad de salida; la regla principal vive como
# instrucción de prompt en _bloque_marco_narrativo().
_ABSOLUTOS_NARRATIVOS = [
    r'cero\s+l[ií]mites',
    r'cero\s+h[aá]bitos',
    r'no\s+haces\s+nada',
    r'est[aá]s\s+evitando\s+todo',
]


def _compilar(patrones: list) -> list:
    return [re.compile(p, re.IGNORECASE) for p in patrones]


_RE_DIAGNOSTICOS                = _compilar(_DIAGNOSTICOS)
_RE_ATRIBUCIONES_MENTALES       = _compilar(_ATRIBUCIONES_MENTALES)
_RE_READINESS_BAJO              = _compilar(_READINESS_BAJO_INCORRECTO)
_RE_NECESIDAD_CORPORAL          = _compilar(_NECESIDAD_CORPORAL)
_RE_VOCABULARIO_ALARMA_READINESS = _compilar(_VOCABULARIO_ALARMA_READINESS)
_RE_ABSOLUTOS_NARRATIVOS         = _compilar(_ABSOLUTOS_NARRATIVOS)


def _tiene_ciriilicos(texto: str) -> bool:
    return any('Ѐ' <= c <= 'ӿ' for c in texto)


def validar_semantica_joi(texto: str, modulo: str = 'desconocido') -> dict:
    """
    Valida el texto generado por JOI contra el contrato semántico.

    Args:
        texto: salida generada por JOI.
        modulo: 'gym', 'hyrox', 'diario' — solo para trazabilidad en logs.

    Returns:
        {
          'valida': bool,
          'violaciones': list[str],   # nombres de las reglas infringidas
          'texto': str,               # el mismo texto (no se modifica)
        }
    """
    violaciones = []

    if not texto:
        return {'valida': True, 'violaciones': [], 'texto': texto}

    for pat in _RE_DIAGNOSTICOS:
        if pat.search(texto):
            violaciones.append(f'diagnostico:{pat.pattern}')

    for pat in _RE_ATRIBUCIONES_MENTALES:
        if pat.search(texto):
            violaciones.append(f'atribucion_mental:{pat.pattern}')

    for pat in _RE_READINESS_BAJO:
        if pat.search(texto):
            violaciones.append(f'readiness_bajo_incorrecto:{pat.pattern}')

    for pat in _RE_NECESIDAD_CORPORAL:
        if pat.search(texto):
            violaciones.append(f'necesidad_corporal:{pat.pattern}')

    for pat in _RE_VOCABULARIO_ALARMA_READINESS:
        if pat.search(texto):
            violaciones.append(f'vocabulario_alarma_readiness:{pat.pattern}')

    for pat in _RE_ABSOLUTOS_NARRATIVOS:
        if pat.search(texto):
            violaciones.append(f'absoluto_narrativo:{pat.pattern}')

    if _tiene_ciriilicos(texto):
        violaciones.append('ciriilico_detectado')

    if violaciones:
        logger.warning(
            "[JOI][semantica][%s] %d violación(es): %s | texto: %.120s",
            modulo, len(violaciones), violaciones, texto,
        )

    return {'valida': not violaciones, 'violaciones': violaciones, 'texto': texto}


# ── Vocabulario de readiness compartido ─────────────────────────────────────

def readiness_etiqueta(score: int) -> str:
    """
    Etiqueta semántica de readiness. Misma escala en Gym, Hyrox y Diario.

    Umbrales:
      >= 80 → Disponibilidad alta
      >= 70 → Disponible con margen   (70-79)
      >= 55 → Disponible con reserva  (55-69, incluye 67)
      >= 35 → Disponibilidad reducida (35-54)
      <  35 → Carga alta acumulada

    Regla: la palabra 'bajo' nunca aparece — solo 'carga alta acumulada'.
    """
    if score >= 80:
        return 'Disponibilidad alta'
    if score >= 70:
        return 'Disponible con margen'
    if score >= 55:
        return 'Disponible con reserva'
    if score >= 35:
        return 'Disponibilidad reducida'
    return 'Carga alta acumulada'


def readiness_descripcion_corta(score: int) -> str:
    """Versión compacta para incluir en contexto de prompts."""
    if score >= 80:
        return 'disponibilidad alta'
    if score >= 70:
        return 'disponible con margen'
    if score >= 55:
        return 'disponible con reserva'
    if score >= 35:
        return 'disponibilidad reducida'
    return 'carga alta acumulada'
