"""
Tempo — Fase 64A: fuente única para sugerencias de tempo.

Centraliza la sugerencia de tempo por ejercicio para que voz_entrenador,
briefing y la sesión activa hablen desde el mismo criterio.
"""

_TEMPO_SUGERIDO = {
    'sentadilla': '3-1-2', 'press banca': '3-1-2', 'peso muerto': '2-1-3',
    'press militar': '2-1-2', 'remo': '2-1-2', 'jalón': '2-1-2',
    'hip thrust': '2-1-2', 'zancada': '2-1-2', 'prensa': '3-1-2',
}

# Fallback prudente orientado a control técnico (hipertrofia/fuerza general);
# no pretende ser una prescripción óptima para movimientos de potencia o carries.
_TEMPO_GENERICO = '3-1-2'


def get_tempo_sugerido(nombre_ejercicio):
    """Tempo sugerido (excéntrica-pausa-concéntrica-pausa) para un ejercicio.
    Si no reconoce el ejercicio, devuelve un tempo genérico prudente."""
    nl = nombre_ejercicio.lower()
    for k, v in _TEMPO_SUGERIDO.items():
        if k in nl:
            return v
    return _TEMPO_GENERICO


def get_mensaje_tempo(nombre_ejercicio):
    """Frase breve para sugerir el tempo de este ejercicio en briefing."""
    return f'cambiar el tempo a {get_tempo_sugerido(nombre_ejercicio)}'


def resolver_tempo_sesion(nombre_ejercicio, tempo_registrado=None):
    """
    Decide qué tempo mostrar en la sesión activa para un ejercicio.
    - Si hay un tempo_registrado no vacío (última vez, vía Liftin), se usa ese.
    - Si no (None o cadena vacía), se usa el tempo sugerido centralizado.
    Devuelve (tempo, fuente) con fuente en {'registrado', 'sugerido'}.
    """
    if tempo_registrado:
        return tempo_registrado, 'registrado'
    return get_tempo_sugerido(nombre_ejercicio), 'sugerido'
