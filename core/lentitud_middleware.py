"""Peticiones lentas (16-nov-2026, nota 23).

Desde hace una semana las páginas tardan 20-98 s en producción. La CPU no es
(6 s de 5.000 s) y los logs del servidor solo dicen que el cliente cortó. Este
middleware deja una línea por cada petición que pase del umbral, con lo que
hace falta para saber dónde se va el tiempo:

- ruta, método, código y tiempo total;
- tiempo hasta empezar la vista y tiempo dentro de la vista;
- número de consultas a la base de datos y el tiempo que sumaron;
- las consultas más lentas (solo el principio del SQL, sin valores);
- (17-nov) la mediana por consulta y los 8 sitios del código que más consultas
  lanzan (archivo:línea función xN), para atacar lo que pesa en producción.

Si el tiempo total es grande y el de base de datos pequeño, la espera está en
otra cosa (una llamada externa, disco, el propio servidor), y eso ya es una
pista. No cambia ninguna respuesta ni guarda datos del usuario: la ruta se
registra sin la cadena de consulta (lleva tokens).
"""

import logging
import os
import re
import sys
import time
from collections import Counter

from django.conf import settings
from django.db import connection

from core import memo_peticion, perfil_tramos

logger = logging.getLogger('lentitud')

UMBRAL_POR_DEFECTO_S = 2.0
RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IGNORAR = ('lentitud_middleware.py', 'memo_peticion.py')


def _umbral():
    try:
        return float(getattr(settings, 'LENTITUD_UMBRAL_S', UMBRAL_POR_DEFECTO_S))
    except (TypeError, ValueError):
        return UMBRAL_POR_DEFECTO_S


def _escribe(sql):
    """True si la sentencia puede cambiar datos. Leer y abrir/cerrar un savepoint no los cambia."""
    inicio = str(sql).lstrip()[:20].upper()
    return not (inicio.startswith('SELECT') or inicio.startswith('SAVEPOINT')
                or inicio.startswith('RELEASE SAVEPOINT'))


def _sitio_de_llamada():
    """Primer sitio del código del proyecto que lanzó la consulta ('ruta:línea función')."""
    try:
        marco = sys._getframe(2)
        while marco is not None:
            ruta = marco.f_code.co_filename
            if (ruta.startswith(RAIZ_PROYECTO) and 'site-packages' not in ruta
                    and not ruta.endswith(_IGNORAR)):
                return f'{os.path.relpath(ruta, RAIZ_PROYECTO)}:{marco.f_lineno} {marco.f_code.co_name}'
            marco = marco.f_back
    except Exception:
        pass
    return 'n/d'


_TABLA = re.compile(r'(?:\bFROM|\bINTO|\bUPDATE)\s+[`"]?([A-Za-z0-9_$]+)[`"]?', re.IGNORECASE)


def _resumen_tablas(consultas, maximo=8):
    """Tablas que más tiempo suman: ``tabla xN 1.23s``. Solo el nombre de la tabla, nunca valores."""
    por_tabla = {}
    for seg, sql in consultas:
        # Todo el SQL: en un SELECT con muchas columnas el FROM queda lejos del
        # principio (19:28 en producción: «otra x168»). Solo sale el nombre.
        m = _TABLA.search(str(sql))
        nombre = m.group(1) if m else 'otra'
        a = por_tabla.setdefault(nombre, [0, 0.0])
        a[0] += 1
        a[1] += seg
    filas = sorted(por_tabla.items(), key=lambda kv: kv[1][1], reverse=True)[:maximo]
    return ', '.join(f'{n} x{c} {s:.2f}s' for n, (c, s) in filas) or 'n/d'


TABLAS_VIGILADAS_POR_DEFECTO = ('joi_mensajejoi',)


def _vigiladas(consultas, tablas=None):
    """Cuántas consultas tocan cada tabla vigilada, aunque sean 0 (``joi_mensajejoi=0``).

    17-nov-2026: que una tabla no salga entre las 8 más caras de ``tablas:`` no
    prueba que no se consultara. Esto cuenta sobre todas las consultas, y una
    tabla cuenta también si aparece en un JOIN.
    """
    if tablas is None:
        tablas = getattr(settings, 'LENTITUD_TABLAS_VIGILADAS', TABLAS_VIGILADAS_POR_DEFECTO)
    partes = []
    for tabla in tablas:
        patron = re.compile(r'[`"\s.(]' + re.escape(tabla) + r'[`"\s.)]')
        n = sum(1 for _, sql in consultas if patron.search(f' {sql} '))
        partes.append(f'{tabla}={n}')
    return ', '.join(partes) or 'n/d'


class PeticionesLentasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.monotonic()
        consultas = []
        sitios = Counter()
        request._lentitud_sitios = sitios

        def medir(execute, sql, params, many, context):
            # cualquier cosa que no sea una lectura vacía la memoria de la petición
            escribe = _escribe(sql)
            if escribe:
                memo_peticion.invalidar()
            sitios[_sitio_de_llamada()] += 1
            ini = time.monotonic()
            try:
                return execute(sql, params, many, context)
            finally:
                dur = time.monotonic() - ini
                consultas.append((dur, sql))
                perfil_tramos.consulta(dur)
                if escribe:
                    memo_peticion.invalidar()

        request._lentitud_t0 = t0
        request._lentitud_vista = None
        memo_peticion.iniciar()
        perfil_tramos.iniciar()
        tramos = {}
        motivo_sin_tramos = ''
        try:
            with connection.execute_wrapper(medir):
                response = self.get_response(request)
        finally:
            memo_peticion.terminar()
            try:
                tramos = perfil_tramos.terminar()
                if not tramos:
                    motivo_sin_tramos = 'vacio'
            except Exception as exc:  # el motivo queda en el registro
                tramos = {}
                motivo_sin_tramos = f'error {type(exc).__name__}: {exc}'[:120]
        total = time.monotonic() - t0
        if total >= _umbral():
            try:
                try:
                    texto_tramos = perfil_tramos.resumen(tramos) if tramos else f'n/d ({motivo_sin_tramos})'
                except Exception as exc:
                    texto_tramos = f'n/d (error {type(exc).__name__}: {exc})'[:160]
                self._registrar(request, response, total, consultas, texto_tramos)
            except Exception:  # medir nunca debe romper una respuesta
                pass
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        request._lentitud_vista = time.monotonic()
        return None

    @staticmethod
    def _registrar(request, response, total, consultas, texto_tramos='n/d'):
        t0 = request._lentitud_t0
        ini_vista = getattr(request, '_lentitud_vista', None)
        antes = (ini_vista - t0) if ini_vista else None
        db = sum(c[0] for c in consultas)
        tiempos = sorted(c[0] for c in consultas)
        mediana = tiempos[len(tiempos) // 2] if tiempos else 0.0
        sitios = getattr(request, '_lentitud_sitios', None) or {}
        top = ', '.join(f'{k} x{n}' for k, n in Counter(sitios).most_common(8))
        lentas = sorted(consultas, key=lambda c: c[0], reverse=True)[:3]
        detalle = ' || '.join(
            f'{seg:.2f}s {" ".join(str(sql).split())[:140]}' for seg, sql in lentas if seg >= 0.2
        )
        logger.warning(
            '%s %s -> %s total=%.1fs antes_de_vista=%s db=%.1fs consultas=%d mediana=%.0fms sitios: %s%s'
            ' tablas: %s vigiladas: %s tramos: %s',
            request.method,
            request.path,
            getattr(response, 'status_code', '?'),
            total,
            f'{antes:.1f}s' if antes is not None else 'n/d',
            db,
            len(consultas),
            mediana * 1000,
            top or 'n/d',
            f' lentas: {detalle}' if detalle else '',
            _resumen_tablas(consultas),
            _vigiladas(consultas),
            texto_tramos,
        )
