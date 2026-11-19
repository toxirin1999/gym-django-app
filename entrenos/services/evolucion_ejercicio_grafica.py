"""Gráfica SVG sencilla (móvil) de la evolución de un ejercicio. Solo dibuja lo que le da la consulta."""

from __future__ import annotations

import math
from datetime import timedelta
from html import escape

from django.utils.safestring import mark_safe

COLOR_FAMILIA = {
    'hipertrofia': '#65caff', 'fuerza': '#f2b48c', 'potencia': '#c9a6ff',
    'descarga': '#b3bdb8', 'desconocido': '#9da5ad',
}
NOMBRE_FAMILIA = {
    'hipertrofia': 'Hipertrofia', 'fuerza': 'Fuerza', 'potencia': 'Potencia',
    'descarga': 'Descarga', 'desconocido': 'Sin bloque',
}
ANCHO, ALTO = 340, 190
IZQ, DER, ARR, ABA = 38, 14, 26, 30


def _num(v):
    t = f'{v:.1f}'.rstrip('0').rstrip('.')
    return t.replace('.', ',')


def _ticks(vmin, vmax):
    """Marcas redondeadas (3-4) que cubren los datos."""
    rango = max(vmax - vmin, 1.0)
    paso = next((p for p in (1, 2, 5, 10, 20, 50, 100) if rango / p <= 3), 100)
    bajo = math.floor(vmin / paso) * paso
    alto = math.ceil(vmax / paso) * paso
    if alto == bajo:
        alto += paso
    return list(range(int(bajo), int(alto) + 1, paso))


def _fecha_corta(f):
    return f'{f:%d/%m}'


def grafica_svg(consulta, titulo_aria):
    """Devuelve el SVG (marcado como seguro) o '' si no hay puntos."""
    puntos = consulta['puntos']
    if not puntos:
        return ''
    desde, hoy = consulta['desde'] + timedelta(days=1), consulta['hoy']
    dias = max((hoy - desde).days, 1)
    valores = [p['valor'] for p in puntos]
    marcas = _ticks(min(valores), max(valores))
    vmin, vmax = marcas[0], marcas[-1]

    def x(f):
        return IZQ + (f - desde).days / dias * (ANCHO - IZQ - DER)

    def y(v):
        return ARR + (1 - (v - vmin) / max(vmax - vmin, 1)) * (ALTO - ARR - ABA)

    o = [f'<svg viewBox="0 0 {ANCHO} {ALTO}" width="100%" role="img" aria-label="{escape(titulo_aria)}" '
         f'style="display:block;overflow:visible">']
    for m in marcas:
        o.append(f'<line x1="{IZQ}" x2="{ANCHO - DER}" y1="{y(m):.1f}" y2="{y(m):.1f}" stroke="#273039" stroke-width="1"/>'
                 f'<text x="{IZQ - 6}" y="{y(m) + 4:.1f}" text-anchor="end" font-size="11" fill="#9da5ad">{m}</text>')
    for ini, fin, texto in consulta.get('bandas') or []:
        x0, x1 = x(max(ini, desde)), x(min(fin, hoy))
        if x1 - x0 < 6:
            x0, x1 = x0 - 3, x0 + 3
        o.append(f'<rect x="{x0:.1f}" y="{ARR}" width="{x1 - x0:.1f}" height="{ALTO - ARR - ABA}" '
                 f'fill="rgba(170,180,175,.10)" stroke="#3a5247" stroke-dasharray="3 3"/>'
                 f'<text x="{(x0 + x1) / 2:.1f}" y="{ARR + 14}" text-anchor="middle" font-size="11" fill="#b3bdb8">{escape(texto)}</text>')
    # Líneas: solo entre puntos consecutivos confirmados y del mismo estado (no se unen cargas pendientes).
    for a, b in zip(puntos, puntos[1:]):
        if a['pendiente'] or b['pendiente']:
            continue
        o.append(f'<line x1="{x(a["fecha"]):.1f}" y1="{y(a["valor"]):.1f}" x2="{x(b["fecha"]):.1f}" y2="{y(b["valor"]):.1f}" '
                 f'stroke="#4b6b5c" stroke-width="2"/>')
    ocupadas = []
    for i, p in enumerate(puntos):
        cx, cy = x(p['fecha']), y(p['valor'])
        color = COLOR_FAMILIA.get(p['familia'], '#9da5ad')
        if p['pendiente']:
            o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="#05080b" stroke="{color}" stroke-width="2"/>')
        else:
            o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{color}"/>')
        etiqueta = _num(p['valor'])
        if i in (0, len(puntos) - 1) or len(puntos) <= 6 or p['valor'] in (min(valores), max(valores)):
            ty = cy - 10 if not any(abs(cx - ox) < 22 and abs((cy - 10) - oy) < 12 for ox, oy in ocupadas) else cy + 19
            ocupadas.append((cx, ty))
            o.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#f2f3f5">{etiqueta}</text>')
    for f in (desde, desde + timedelta(days=dias // 2), hoy):
        o.append(f'<text x="{x(f):.1f}" y="{ALTO - 8}" text-anchor="{"start" if f == desde else "end" if f == hoy else "middle"}" '
                 f'font-size="11" fill="#9da5ad">{_fecha_corta(f)}</text>')
    o.append('</svg>')
    return mark_safe(''.join(o))


def leyenda(consulta):
    """Familias que aparecen en la gráfica, con su color."""
    vistas = []
    for p in consulta['puntos']:
        if p['familia'] not in vistas:
            vistas.append(p['familia'])
    return [{'nombre': NOMBRE_FAMILIA.get(f, f), 'color': COLOR_FAMILIA.get(f, '#9da5ad')} for f in vistas]
