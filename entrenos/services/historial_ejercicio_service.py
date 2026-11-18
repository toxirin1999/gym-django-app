"""El historial completado de un ejercicio, leído una vez por petición (17-nov-2026).

En el cierre, ``_sesion_anterior``, ``_cambios_relevantes`` y
``proxima_vez_texto`` buscaban por separado el historial del mismo ejercicio
(``entrenos_ejerciciorealizado`` x56 en el cierre 407). Dentro de una petición
se lee una vez por ejercicio, con el mismo filtro en la base de datos
(``nombre_ejercicio__iexact``, ``completado=True``), y cada función aplica
después su filtro de fechas. Fuera de una petición se usan consultas
equivalentes. La memoria se vacía si algo escribe.

Orden (decisión de David, 17-nov-2026): de la sesión más reciente a la más
antigua (fecha y, el mismo día, la de id mayor) y, si el mismo ejercicio
aparece dos veces en una sesión, **la primera fila registrada** (id menor):
suele ser el ejercicio principal y la segunda su repetición como alternativa
(nota 18, curl femoral por el rumano). Antes no estaba definido: el porqué de la
decisión ordenaba por fecha y entreno (la base de datos devolvía la primera) y
la sección de cambios por fecha e id de fila (cogía la última). Ahora las dos
usan este orden.

La clave de la memoria no distingue mayúsculas («Press banca» y «press banca»
comparten lectura); el filtro de la base de datos sigue siendo ``iexact``.

No trae más datos que antes: los bucles que la usan ya recorrían el historial
completo del ejercicio.
"""

from core import memo_peticion
from core.memo_peticion import por_peticion

ORDEN = ('-entreno__fecha', '-entreno_id', 'id')


def _consulta(cliente, nombre):
    from entrenos.models import EjercicioRealizado

    return EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, completado=True,
    )


@por_peticion
def _historial_completado(cliente_id, nombre):
    """En ``ORDEN``. Tupla para que la memoria por petición no la copie."""
    return tuple(_consulta(cliente_id, nombre).select_related('entreno').order_by(*ORDEN))


def _clave(nombre):
    return (nombre or '').lower()


def _en_bloque(cliente):
    cliente_id = getattr(cliente, 'pk', cliente)
    return cliente_id if (memo_peticion.activa() and cliente_id is not None) else None


def anteriores(cliente, entreno, nombre, desde=None):
    """Ejercicios completados con ese nombre en o antes de la fecha de ``entreno``, sin ``entreno``, en ``ORDEN``.

    ``desde``: fecha mínima opcional.
    """
    cliente_id = _en_bloque(cliente)
    if cliente_id is None:
        qs = _consulta(cliente, nombre).filter(entreno__fecha__lte=entreno.fecha)
        if desde is not None:
            qs = qs.filter(entreno__fecha__gte=desde)
        return qs.exclude(entreno_id=entreno.id).select_related('entreno').order_by(*ORDEN)
    return [
        e for e in _historial_completado(cliente_id, _clave(nombre))
        if e.entreno.fecha <= entreno.fecha
        and (desde is None or e.entreno.fecha >= desde)
        and e.entreno_id != entreno.id
    ]


def hay_posterior(cliente, nombre, fecha):
    """¿Hay algún ejercicio completado con ese nombre después de ``fecha``?"""
    cliente_id = _en_bloque(cliente)
    if cliente_id is None:
        return _consulta(cliente, nombre).filter(entreno__fecha__gt=fecha).exists()
    return any(e.entreno.fecha > fecha for e in _historial_completado(cliente_id, _clave(nombre)))


def posteriores(cliente, nombre, entreno_origen_id=None, desde_fecha=None, limite=12):
    """Ejercicios completados con ese nombre posteriores a una decisión (``_sesion_evaluadora``).

    Con ``entreno_origen_id``: los de entrenos con id mayor; si no, desde
    ``desde_fecha``. De la sesión más antigua a la más reciente (fecha, id de
    entreno) y, dentro de una sesión, la primera fila registrada (antes no
    estaba definido; mismo criterio que ``ORDEN``). Como mucho ``limite``.
    """
    cliente_id = _en_bloque(cliente)
    if cliente_id is None:
        qs = _consulta(cliente, nombre).select_related('entreno')
        if entreno_origen_id:
            qs = qs.exclude(entreno_id=entreno_origen_id).filter(entreno__id__gt=entreno_origen_id)
        else:
            qs = qs.filter(entreno__fecha__gte=desde_fecha)
        return list(qs.order_by('entreno__fecha', 'entreno__id', 'id')[:limite])
    if entreno_origen_id:
        filas = [e for e in _historial_completado(cliente_id, _clave(nombre)) if e.entreno_id > entreno_origen_id]
    else:
        filas = [e for e in _historial_completado(cliente_id, _clave(nombre)) if e.entreno.fecha >= desde_fecha]
    filas.sort(key=lambda e: (e.entreno.fecha, e.entreno_id, e.id))
    return filas[:limite]
