"""Perfil por tramos de una petición (17-nov-2026, lentitud).

El middleware de peticiones lentas dice cuántas consultas hay y cuánto suman,
pero no a qué parte del código pertenece el resto del tiempo. Aquí se marcan
los tramos principales (``@tramo('nombre')`` o ``with tramo('nombre')``) y, al
final de una petición lenta, el registro lleva por cada tramo:

- ``propio``: tiempo del tramo SIN el de los tramos anidados dentro de él, para
  no contar dos veces el mismo trabajo (la suma de todos los ``propio`` es el
  total de la petición);
- ``bd``: tiempo de las consultas lanzadas directamente por ese tramo;
- ``q``: número de esas consultas;
- ``fuera_sql``: ``propio`` menos ``bd`` (Python, caché, archivos, llamadas externas…).

Fuera de una petición (tests, comandos) o con la medición apagada no hace nada
y casi no cuesta. No guarda ningún dato del usuario ni cambia ninguna respuesta.
Tramo reservado ``resto``: lo que ocurre fuera de cualquier otro tramo
(middleware, plantilla, procesadores de contexto…).
"""
from __future__ import annotations

import functools
import threading
import time
from contextlib import contextmanager

_local = threading.local()
RESTO = 'resto'


class _Marco:
    __slots__ = ('nombre', 't0', 'hijos', 'bd', 'q')

    def __init__(self, nombre):
        self.nombre = nombre
        self.t0 = time.perf_counter()
        self.hijos = 0.0
        self.bd = 0.0
        self.q = 0


def iniciar():
    """Empieza a medir esta petición (lo llama el middleware)."""
    _local.pila = [_Marco(RESTO)]
    _local.acum = {}


def activo():
    return getattr(_local, 'pila', None) is not None


def consulta(segundos):
    """Atribuye una consulta al tramo abierto (lo llama el middleware)."""
    pila = getattr(_local, 'pila', None)
    if pila:
        marco = pila[-1]
        marco.bd += segundos
        marco.q += 1


def _cerrar(marco, ahora, acum):
    incl = ahora - marco.t0
    propio = max(incl - marco.hijos, 0.0)
    a = acum.setdefault(marco.nombre, [0, 0.0, 0.0, 0])
    a[0] += 1
    a[1] += propio
    a[2] += marco.bd
    a[3] += marco.q
    return incl


@contextmanager
def tramo(nombre):
    pila = getattr(_local, 'pila', None)
    if pila is None:
        yield
        return
    marco = _Marco(nombre)
    pila.append(marco)
    try:
        yield
    finally:
        # la pila puede haberse reiniciado si la petición terminó a mitad
        if getattr(_local, 'pila', None) is pila and pila and pila[-1] is marco:
            pila.pop()
            incl = _cerrar(marco, time.perf_counter(), _local.acum)
            if pila:
                pila[-1].hijos += incl


def tramo_de(nombre):
    """Decorador: ``@tramo_de('estado_carga')``."""
    def deco(func):
        @functools.wraps(func)
        def envuelta(*args, **kwargs):
            if getattr(_local, 'pila', None) is None:
                return func(*args, **kwargs)
            with tramo(nombre):
                return func(*args, **kwargs)
        return envuelta
    return deco


def terminar():
    """Cierra la petición y devuelve ``{nombre: (llamadas, propio, bd, q)}``."""
    pila = getattr(_local, 'pila', None)
    acum = getattr(_local, 'acum', None)
    _local.pila = None
    _local.acum = None
    if not pila or acum is None:
        return {}
    ahora = time.perf_counter()
    while len(pila) > 1:  # tramos que no llegaron a cerrarse
        marco = pila.pop()
        incl = _cerrar(marco, ahora, acum)
        pila[-1].hijos += incl
    _cerrar(pila[0], ahora, acum)
    return {k: tuple(v) for k, v in acum.items()}


def resumen(acum, maximo=14):
    """Texto para el registro: los tramos que más pesan, de mayor a menor ``propio``."""
    filas = sorted(acum.items(), key=lambda kv: kv[1][1], reverse=True)[:maximo]
    return ' | '.join(
        f'{n} x{c} propio={p:.2f}s bd={b:.2f}s q={q} fuera_sql={max(p - b, 0):.2f}s'
        for n, (c, p, b, q) in filas
    )
