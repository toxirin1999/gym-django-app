"""Peticiones lentas (16-nov-2026, nota 23).

Desde hace una semana las páginas tardan 20-98 s en producción. La CPU no es
(6 s de 5.000 s) y los logs del servidor solo dicen que el cliente cortó. Este
middleware deja una línea por cada petición que pase del umbral, con lo que
hace falta para saber dónde se va el tiempo:

- ruta, método, código y tiempo total;
- tiempo hasta empezar la vista y tiempo dentro de la vista;
- número de consultas a la base de datos y el tiempo que sumaron;
- las consultas más lentas (solo el principio del SQL, sin valores).

Si el tiempo total es grande y el de base de datos pequeño, la espera está en
otra cosa (una llamada externa, disco, el propio servidor), y eso ya es una
pista. No cambia ninguna respuesta ni guarda datos del usuario: la ruta se
registra sin la cadena de consulta (lleva tokens).
"""

import logging
import time

from django.conf import settings
from django.db import connection

from core import memo_peticion

logger = logging.getLogger('lentitud')

UMBRAL_POR_DEFECTO_S = 2.0


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


class PeticionesLentasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.monotonic()
        consultas = []

        def medir(execute, sql, params, many, context):
            # cualquier cosa que no sea una lectura vacía la memoria de la petición
            escribe = _escribe(sql)
            if escribe:
                memo_peticion.invalidar()
            ini = time.monotonic()
            try:
                return execute(sql, params, many, context)
            finally:
                consultas.append((time.monotonic() - ini, sql))
                if escribe:
                    memo_peticion.invalidar()

        request._lentitud_t0 = t0
        request._lentitud_vista = None
        memo_peticion.iniciar()
        try:
            with connection.execute_wrapper(medir):
                response = self.get_response(request)
        finally:
            memo_peticion.terminar()
        total = time.monotonic() - t0
        if total >= _umbral():
            try:
                self._registrar(request, response, total, consultas)
            except Exception:  # medir nunca debe romper una respuesta
                pass
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        request._lentitud_vista = time.monotonic()
        return None

    @staticmethod
    def _registrar(request, response, total, consultas):
        t0 = request._lentitud_t0
        ini_vista = getattr(request, '_lentitud_vista', None)
        antes = (ini_vista - t0) if ini_vista else None
        db = sum(c[0] for c in consultas)
        lentas = sorted(consultas, key=lambda c: c[0], reverse=True)[:3]
        detalle = ' || '.join(
            f'{seg:.2f}s {" ".join(str(sql).split())[:140]}' for seg, sql in lentas if seg >= 0.2
        )
        logger.warning(
            '%s %s -> %s total=%.1fs antes_de_vista=%s db=%.1fs consultas=%d%s',
            request.method,
            request.path,
            getattr(response, 'status_code', '?'),
            total,
            f'{antes:.1f}s' if antes is not None else 'n/d',
            db,
            len(consultas),
            f' lentas: {detalle}' if detalle else '',
        )
