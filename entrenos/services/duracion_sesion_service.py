"""Duración plausible de una sesión de gimnasio.

El cronómetro del entrenamiento activo cuenta desde que se abrió la sesión y
sobrevive a recargas. Si la sesión se deja abierta y se guarda días después,
el navegador envía miles de minutos y la carga (sRPE × minutos) dispara el
ACWR. Aquí se decide qué duración es creíble antes de guardarla.
"""

DURACION_MAX_MIN = 240          # Más de 4 h de gimnasio no es una sesión real.
MINUTOS_POR_SERIE = 3           # Serie + descanso, estimación conservadora.
ESTIMACION_MIN = 20
ESTIMACION_MAX = 180


def estimar_duracion_por_series(series_completadas):
    """Duración aproximada a partir de las series hechas; None si no hay series."""
    try:
        n = int(series_completadas or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return None
    return max(ESTIMACION_MIN, min(ESTIMACION_MAX, n * MINUTOS_POR_SERIE))


def sanear_duracion_minutos(valor, series_completadas=0):
    """Devuelve ``(minutos | None, corregida)``.

    - Vacío, no numérico o negativo → ``(None, False)``; 0 se conserva (sesión
      retroactiva enviada al instante): el resto del flujo ya busca la
      duración en otras fuentes.
    - Más de ``DURACION_MAX_MIN`` → se sustituye por una estimación según las
      series completadas y ``corregida`` es True.
    """
    try:
        minutos = int(str(valor).strip()) if valor not in (None, '') else None
    except (TypeError, ValueError):
        minutos = None
    if minutos is None or minutos < 0:
        return None, False
    if minutos > DURACION_MAX_MIN:
        return estimar_duracion_por_series(series_completadas), True
    return minutos, False
