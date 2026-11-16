"""Agenda de pendientes con fecha (16-nov-2026, petición de David).

Un archivo del repositorio (``core/data/pendientes.json``) con las tareas de
la app y sus fechas; se actualiza en cada paquete de reparaciones. Esto lo
lee y las agrupa según el día de hoy, para verlas en /clientes/pendientes/.

Cada tarea: ``id``, ``titulo``, ``detalle`` (opcional), ``fecha``
(``AAAA-MM-DD`` o ``null``), ``estado`` (``pendiente`` | ``hecho`` |
``descartado``), ``origen`` (de qué repaso viene) y ``hecho_el`` (si está
hecha).
"""

import json
import os
from datetime import date, timedelta

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pendientes.json')
ESTADOS = ('pendiente', 'hecho', 'descartado')


def _fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        return None


def cargar(ruta=None):
    """Lista de tareas válidas; un archivo roto o ausente da lista vacía, nunca un error."""
    try:
        with open(ruta or RUTA, encoding='utf-8') as f:
            crudo = json.load(f)
    except (OSError, ValueError):
        return []
    tareas = []
    for t in crudo if isinstance(crudo, list) else []:
        if not isinstance(t, dict) or not t.get('titulo'):
            continue
        estado = t.get('estado') if t.get('estado') in ESTADOS else 'pendiente'
        tareas.append({
            'id': str(t.get('id') or ''),
            'titulo': str(t['titulo']),
            'detalle': str(t.get('detalle') or ''),
            'fecha': _fecha(t.get('fecha')),
            'estado': estado,
            'origen': str(t.get('origen') or ''),
            'hecho_el': _fecha(t.get('hecho_el')),
        })
    return tareas


def agrupar(tareas, hoy=None):
    """{'vencidas', 'hoy', 'semana', 'despues', 'sin_fecha', 'cerradas'}; cada grupo ordenado por fecha."""
    hoy = hoy or date.today()
    fin_semana = hoy + timedelta(days=7)
    grupos = {k: [] for k in ('vencidas', 'hoy', 'semana', 'despues', 'sin_fecha', 'cerradas')}
    for t in tareas:
        if t['estado'] != 'pendiente':
            grupos['cerradas'].append(t)
        elif t['fecha'] is None:
            grupos['sin_fecha'].append(t)
        elif t['fecha'] < hoy:
            grupos['vencidas'].append(t)
        elif t['fecha'] == hoy:
            grupos['hoy'].append(t)
        elif t['fecha'] <= fin_semana:
            grupos['semana'].append(t)
        else:
            grupos['despues'].append(t)
    for clave in ('vencidas', 'hoy', 'semana', 'despues'):
        grupos[clave].sort(key=lambda t: t['fecha'])
    grupos['cerradas'].sort(key=lambda t: t['hecho_el'] or date.min, reverse=True)
    return grupos


def resumen(tareas, hoy=None):
    g = agrupar(tareas, hoy)
    return {'vencidas': len(g['vencidas']), 'hoy': len(g['hoy']), 'pendientes': sum(
        len(g[k]) for k in ('vencidas', 'hoy', 'semana', 'despues', 'sin_fecha'))}
