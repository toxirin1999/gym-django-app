"""Captura TEMPORAL de lo que manda el Atajo de Salud (19-nov-2026).

Para poder comprobar con un envío real qué llega (formato de fechas y de fases,
número de muestras, solapes) sin guardar nada más de lo necesario.

- Apagada por defecto. Se activa con la variable de entorno
  ``SALUD_CAPTURA_HASTA=AAAA-MM-DD`` (último día de captura, inclusive); pasada
  esa fecha deja de escribir sola.
- Solo conserva una lista blanca de campos del Atajo: nunca el token ni nada más.
- Guarda como mucho ``MAX_CAPTURAS`` envíos (los más recientes) en
  ``logs/salud_captura_temporal.log`` (un JSON por línea, ignorado por git).
- Un fallo aquí nunca puede romper la importación.
"""
import json
import logging
import os
from datetime import date, datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_CAPTURAS = 40
MAX_CARACTERES = 6000
CAMPOS = ('fecha', 'pulso_reposo', 'hrv', 'hrv_inicios', 'sueno', 'fases', 'inicios')
NOMBRE = 'salud_captura_temporal.log'


def _hasta():
    texto = (os.environ.get('SALUD_CAPTURA_HASTA') or '').strip()
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def activa(hoy=None):
    hasta = _hasta()
    return hasta is not None and (hoy or timezone.localdate()) <= hasta


def _ruta():
    return os.path.join(getattr(settings, 'LOGS_DIR', os.path.join(settings.BASE_DIR, 'logs')), NOMBRE)


def _recortar(valor):
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    return texto[:MAX_CARACTERES]


def capturar(cliente_id, payload, guardado=None, ahora=None):
    """Añade este envío (solo los campos de ``CAMPOS``) si la captura está activa."""
    try:
        ahora = ahora or timezone.now()
        if not activa(timezone.localtime(ahora).date()) or not isinstance(payload, dict):
            return False
        recibido = {c: _recortar(payload[c]) for c in CAMPOS if c in payload}
        if not recibido:
            return False
        linea = json.dumps({
            'recibido_en': timezone.localtime(ahora).isoformat(),
            'cliente': cliente_id,
            'campos': sorted(recibido),
            'recibido': recibido,
            'guardado': guardado or {},
        }, ensure_ascii=False, default=str)
        ruta = _ruta()
        previas = []
        if os.path.exists(ruta):
            with open(ruta, encoding='utf-8') as f:
                previas = [l.rstrip('\n') for l in f if l.strip()]
        previas = (previas + [linea])[-MAX_CAPTURAS:]
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('\n'.join(previas) + '\n')
        return True
    except Exception:  # nunca romper la importación
        logger.warning('salud-iphone: no pude guardar la captura temporal', exc_info=True)
        return False
