"""Errores 500 registrados (8-nov-2026).

Producción no avisaba de nada: /panel/ estuvo dando 500 sin que nadie lo
viera. Ahora ``django.request`` escribe cada 500 en ``logs/errores_500.log``
(«fecha|Internal Server Error: /ruta/» y su traza) y esto lo lee para
enseñarlo en /clientes/errores/ y como aviso en el Centro.
"""

import os
import re
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings

_LINEA = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\|(.*)$')
_RUTA = re.compile(r'(?:Internal Server Error|Server Error)[^:]*:\s*(\S+)')


def ruta_log():
    return os.path.join(getattr(settings, 'LOGS_DIR', os.path.join(settings.BASE_DIR, 'logs')), 'errores_500.log')


def errores_recientes(dias=7, ahora=None, ruta=None):
    """[{'fecha': datetime, 'ruta': '/panel/', 'mensaje': ...}] de los últimos ``dias``, más reciente primero."""
    ruta = ruta or ruta_log()
    ahora = ahora or datetime.now()
    desde = ahora - timedelta(days=dias)
    if not os.path.exists(ruta):
        return []
    errores = []
    try:
        with open(ruta, encoding='utf-8', errors='replace') as f:
            for linea in f:
                m = _LINEA.match(linea.rstrip('\n'))
                if not m:
                    continue  # líneas de la traza
                try:
                    fecha = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
                if fecha < desde:
                    continue
                mensaje = m.group(2).strip()
                r = _RUTA.search(mensaje)
                errores.append({'fecha': fecha, 'ruta': r.group(1) if r else None, 'mensaje': mensaje[:200]})
    except OSError:
        return []
    errores.reverse()
    return errores


def resumen_errores(dias=7, ahora=None, ruta=None):
    """{'total', 'por_ruta': [(ruta, n)], 'ultimo'} o None si no hubo ninguno."""
    errores = errores_recientes(dias, ahora, ruta)
    if not errores:
        return None
    por_ruta = Counter(e['ruta'] or '(sin ruta)' for e in errores).most_common()
    return {'total': len(errores), 'por_ruta': por_ruta, 'ultimo': errores[0], 'dias': dias}
