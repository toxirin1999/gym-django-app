"""Las series completadas de un entreno, leídas una vez por petición (17-nov-2026).

Cuatro funciones leían las series del mismo entreno por separado, cada una con
su filtro (cierre 407: ``_series_trabajo`` x8,
``_rendimiento_representativo_desde_series`` x8, más ``_series_completadas`` y
``_series_del_entreno``). Dentro de una petición se leen una vez —las
completadas, con su ejercicio, en orden ``serie_numero, id``— y cada función
aplica después su filtro (aproximaciones, peso, nombre). Fuera de una petición,
una consulta en cada llamada, con el mismo resultado. La memoria se vacía si
algo escribe. Devuelve instancias compartidas: no modificarlas.
"""

from core.memo_peticion import por_peticion


@por_peticion
def series_completadas(entreno_id):
    """Tupla de ``SerieRealizada`` completadas del entreno, con ``ejercicio``, en ``serie_numero, id``."""
    from entrenos.models import SerieRealizada

    return tuple(
        SerieRealizada.objects.filter(entreno_id=entreno_id, completado=True)
        .select_related('ejercicio').order_by('serie_numero', 'id')
    )
