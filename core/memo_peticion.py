"""Memoria de una sola petición (17-nov-2026, lentitud de Ahora).

Ahora hacía ~1.800 consultas por carga porque las mismas lecturas (lesiones
activas, semana del plan, tope de una máquina…) se repetían decenas de veces
con los mismos argumentos. Esto guarda el resultado de esas lecturas SOLO
durante la petición en curso:

- la memoria nace al empezar la petición y muere al terminar (no hay nada
  entre peticiones, así que nunca se sirve algo viejo de un minuto antes);
- cualquier escritura en la base de datos (INSERT, UPDATE, DELETE…) durante
  la petición la vacía entera, de modo que una lectura posterior ve lo que
  se acaba de escribir;
- fuera de una petición (comandos, tareas, tests directos) no hace nada;
- lo que devuelve se copia, así que quien lo reciba puede modificarlo sin
  afectar a los demás.

Solo se decoran lecturas puras: mismo argumento, mismo resultado.
"""

import contextvars
import copy
import functools

_memo = contextvars.ContextVar('memo_peticion', default=None)


def iniciar():
    return _memo.set({})


def terminar(token=None):
    _memo.set(None)


def activa():
    """True dentro de una petición (hay memoria en curso)."""
    return _memo.get() is not None


def invalidar():
    memoria = _memo.get()
    if memoria:
        memoria.clear()


def _clave_de(arg):
    # un modelo cuenta por su pk (y su clase): dos instancias del mismo cliente son la misma lectura
    pk = getattr(arg, 'pk', None)
    if pk is not None and hasattr(arg, '_meta'):
        return (arg.__class__.__name__, pk)
    return arg


def _copia(valor):
    if isinstance(valor, (dict, list, set)):
        try:
            return copy.deepcopy(valor)
        except Exception:  # noqa: BLE001
            return valor
    return valor


def por_peticion(funcion):
    """Memoriza ``funcion`` durante la petición actual (ver el módulo)."""

    @functools.wraps(funcion)
    def envoltorio(*args, **kwargs):
        memoria = _memo.get()
        if memoria is None:
            return funcion(*args, **kwargs)
        try:
            clave = (funcion.__module__, funcion.__qualname__,
                     tuple(_clave_de(a) for a in args),
                     tuple(sorted((k, _clave_de(v)) for k, v in kwargs.items())))
            hash(clave)
        except TypeError:
            return funcion(*args, **kwargs)
        if clave in memoria:
            return _copia(memoria[clave])
        resultado = funcion(*args, **kwargs)
        # si la propia función escribió, la memoria se vació: se guarda igualmente su resultado
        memoria = _memo.get()
        if memoria is not None:
            memoria[clave] = _copia(resultado)
        return resultado

    return envoltorio
