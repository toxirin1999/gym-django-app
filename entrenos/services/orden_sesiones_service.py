"""Orden entre dos sesiones de gimnasio (17-nov-2026, nota 52).

El cierre de una sesión antigua comparaba con una sesión POSTERIOR: el cierre
del 10/11 decía «Jalón 75 × 6 → 60 × 6 (−15 kg)» porque tomaba como «anterior»
la del 17/11. Aquí se decide, sin adivinar, si una sesión es claramente
anterior a otra.

Cada sesión tiene dos fechas: ``fecha`` (el día del plan) y ``fecha_ejecucion``
(el día en que se guardó, o el día real si Strava lo corrigió). Pueden
discrepar (sesión movida de día, guardada tarde). Regla de David:

- Solo se dice «anterior» o «posterior» si las DOS fechas coinciden en el
  orden y no hay empate de día.
- Con empate de día, solo se ordenan si las dos sesiones tienen
  ``hora_inicio`` y es distinta. Si falta una hora o coinciden, no se sabe.
- Cuando no se sabe, quien llama omite la comparación entre esas dos sesiones.
"""
from __future__ import annotations

import datetime as _dt

ANTERIOR = -1
POSTERIOR = 1
DESCONOCIDO = 0


def _dia(valor):
    if isinstance(valor, _dt.datetime):
        return valor.date()
    return valor


def _fecha_ejecucion(entreno):
    return _dia(getattr(entreno, 'fecha_ejecucion', None) or entreno.fecha)


def _signo(a, b, hora_a, hora_b):
    if a is None or b is None:
        return DESCONOCIDO
    if a < b:
        return ANTERIOR
    if a > b:
        return POSTERIOR
    if hora_a and hora_b and hora_a != hora_b:
        return ANTERIOR if hora_a < hora_b else POSTERIOR
    return DESCONOCIDO


def orden_entre_sesiones(otra, actual):
    """ANTERIOR si ``otra`` es claramente anterior a ``actual``; POSTERIOR si es
    claramente posterior; DESCONOCIDO si no se puede saber con seguridad."""
    hora_o = getattr(otra, 'hora_inicio', None)
    hora_a = getattr(actual, 'hora_inicio', None)
    por_plan = _signo(_dia(otra.fecha), _dia(actual.fecha), hora_o, hora_a)
    por_ejecucion = _signo(_fecha_ejecucion(otra), _fecha_ejecucion(actual), hora_o, hora_a)
    if por_plan == DESCONOCIDO or por_ejecucion == DESCONOCIDO or por_plan != por_ejecucion:
        return DESCONOCIDO
    return por_plan


def primera_anterior(candidatas, actual, saltar=None):
    """La primera sesión claramente anterior de ``candidatas`` (de la más
    reciente a la más antigua), o None.

    ``candidatas`` son ``EjercicioRealizado`` (con ``.entreno``). Las claramente
    posteriores se ignoran. Si aparece una de orden desconocido (mismo día sin
    hora, fechas que discrepan) se para y se devuelve None: la comparación entre
    esas dos sesiones se omite, no se salta a una más antigua. ``saltar(c)``
    permite descartar candidatas (descarga) antes de mirar el orden.
    """
    for c in candidatas:
        if saltar is not None and saltar(c):
            continue
        orden = orden_entre_sesiones(c.entreno, actual)
        if orden == POSTERIOR:
            continue
        if orden == DESCONOCIDO:
            return None
        return c
    return None
