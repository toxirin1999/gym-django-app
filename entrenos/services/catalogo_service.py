"""La fila del catálogo de un ejercicio, buscada una vez por petición (17-nov-2026).

``salto_carga``, ``_nombre_visible``, ``peso_sugerido``, ``_grupo_ejercicio``,
``ajustar_escala_y_reps``, el plan dinámico y el cierre buscaban la misma fila
por separado (``rutinas_ejerciciobase`` x36 en el cierre 407 y x50 en Ahora),
todas con ``EjercicioBase.objects.filter(nombre__iexact=…).first()``. El modelo
no define orden, así que ``.first()`` es la fila de id menor; ``nombre`` es
único (en MySQL, sin distinguir mayúsculas ni tildes: casa una como mucho).

Dentro de una petición se busca una vez por nombre: la clave no distingue
mayúsculas y el filtro de la base de datos sigue siendo ``iexact``. Fuera de una
petición, la consulta de siempre. La memoria se vacía si algo escribe. Devuelve
la instancia compartida: no modificarla.
"""

from core import memo_peticion
from core.memo_peticion import por_peticion


def _consulta(nombre):
    from rutinas.models import EjercicioBase

    return EjercicioBase.objects.filter(nombre__iexact=nombre).first()


@por_peticion
def _base_en_peticion(clave):
    return _consulta(clave)


def base_por_nombre(nombre):
    """``EjercicioBase.objects.filter(nombre__iexact=nombre).first()``, o None."""
    valor = nombre or ''
    if not memo_peticion.activa():
        return _consulta(valor)
    return _base_en_peticion(valor.lower())
