"""El historial completado de un ejercicio, leído una vez por petición (17-nov-2026).

En el cierre, ``_sesion_anterior``, ``_cambios_relevantes`` y
``proxima_vez_texto`` buscaban por separado el historial del mismo ejercicio
(``entrenos_ejerciciorealizado`` x56 en el cierre 407). Dentro de una petición
se lee una vez por ejercicio, con el mismo filtro en la base de datos
(``nombre_ejercicio__iexact``, ``completado=True``), y cada función aplica
después su filtro de fechas y su desempate. Fuera de una petición se usan las
consultas de siempre. La memoria se vacía si algo escribe.

No trae más datos que antes: los bucles que la usan ya recorrían el historial
completo del ejercicio.
"""

from core import memo_peticion
from core.memo_peticion import por_peticion

# Desempates de las consultas originales
POR_ENTRENO = 'entreno'   # order_by('-entreno__fecha', '-entreno_id')
POR_ID = 'id'             # order_by('-entreno__fecha', '-id')


def _consulta(cliente, nombre):
    from entrenos.models import EjercicioRealizado

    return EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, completado=True,
    )


@por_peticion
def _historial_completado(cliente_id, nombre):
    """Del más reciente al más antiguo; dentro de una misma sesión, por id ascendente.

    Tupla para que la memoria por petición no la copie.
    """
    return tuple(
        _consulta(cliente_id, nombre).select_related('entreno')
        .order_by('-entreno__fecha', '-entreno_id', 'id')
    )


def _en_bloque(cliente):
    cliente_id = getattr(cliente, 'pk', cliente)
    return cliente_id if (memo_peticion.activa() and cliente_id is not None) else None


def anteriores(cliente, entreno, nombre, desempate=POR_ENTRENO, desde=None):
    """Ejercicios completados con ese nombre en o antes de la fecha de ``entreno``, sin ``entreno``.

    ``desde``: fecha mínima opcional. Devuelve un iterable en el orden de la
    consulta original (``desempate``).
    """
    orden = ('-entreno__fecha', '-entreno_id') if desempate == POR_ENTRENO else ('-entreno__fecha', '-id')
    cliente_id = _en_bloque(cliente)
    if cliente_id is None:
        qs = _consulta(cliente, nombre).filter(entreno__fecha__lte=entreno.fecha)
        if desde is not None:
            qs = qs.filter(entreno__fecha__gte=desde)
        return qs.exclude(entreno_id=entreno.id).select_related('entreno').order_by(*orden)
    filas = [
        e for e in _historial_completado(cliente_id, nombre)
        if e.entreno.fecha <= entreno.fecha
        and (desde is None or e.entreno.fecha >= desde)
        and e.entreno_id != entreno.id
    ]
    if desempate == POR_ID:
        filas.sort(key=lambda e: (e.entreno.fecha, e.id), reverse=True)
    return filas


def hay_posterior(cliente, nombre, fecha):
    """¿Hay algún ejercicio completado con ese nombre después de ``fecha``?"""
    cliente_id = _en_bloque(cliente)
    if cliente_id is None:
        return _consulta(cliente, nombre).filter(entreno__fecha__gt=fecha).exists()
    return any(e.entreno.fecha > fecha for e in _historial_completado(cliente_id, nombre))
