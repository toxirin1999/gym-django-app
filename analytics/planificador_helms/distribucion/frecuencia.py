import math

from analytics.planificador_helms.config import GRUPOS_GRANDES, LIMITES_SERIES_SESION


def cap_sesion_para_grupo(grupo: str) -> int:
    """
    Devuelve el techo de series/sesión para el grupo según LIMITES_SERIES_SESION.

    Encapsula la distinción grupos_grandes/grupos_pequenos para que el código
    que llama a frecuencia_desde_volumen no tenga que repetir esa lógica.
    """
    clave = 'grupos_grandes' if grupo in GRUPOS_GRANDES else 'grupos_pequenos'
    return LIMITES_SERIES_SESION[clave]['max']


def frecuencia_desde_volumen(volumen_objetivo: int, cap_por_sesion: int, dias_disponibles: int) -> int:
    """
    Calcula cuántas sesiones semanales necesita un grupo muscular dado su volumen objetivo.

    freq_deseada = ceil(volumen_objetivo / cap_por_sesion)
    freq = min(3, freq_deseada, dias_disponibles)   # tope duro 3 — decisión del usuario

    Si volumen_objetivo <= 0, devuelve 0 (descarga extrema o dato inválido).
    El tope duro de 3 es una decisión explícita del usuario, no un parámetro.
    """
    if volumen_objetivo <= 0:
        return 0
    freq_deseada = math.ceil(volumen_objetivo / cap_por_sesion)
    return min(3, freq_deseada, dias_disponibles)


def calcular_frecuencia(grupo: str, volumen_objetivo: int, dias_disponibles: int) -> int:
    """
    Combina cap_sesion_para_grupo y frecuencia_desde_volumen en una sola llamada.

    Punto de entrada conveniente para quien solo conoce el grupo y el volumen objetivo,
    sin necesidad de resolver manualmente el cap de sesión.
    """
    cap = cap_sesion_para_grupo(grupo)
    return frecuencia_desde_volumen(volumen_objetivo, cap, dias_disponibles)
