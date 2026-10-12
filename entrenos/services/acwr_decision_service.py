"""ACWR como señal de la decisión diaria de Gym.

Una semana con mucha más carga de la habitual (ACWR ≥ 1,5) pide la versión
reducida de la sesión. Antes de frenar se comprueba que el pico no venga de un
dato imposible: el 11-oct-2026 una sola sesión con el cronómetro olvidado
(2.525 min) llevó el ACWR a 2,32. Un pico así se marca para revisar y no
gobierna la decisión.
"""

from datetime import timedelta
from statistics import median

ACWR_ALTO = 1.5
FACTOR_ATIPICO = 4          # Una actividad > 4× la mediana habitual es sospechosa.
MIN_MUESTRAS_MEDIANA = 5


def _actividades_con_fecha(cliente, desde, hasta):
    from django.db.models.functions import Coalesce
    from entrenos.models import ActividadRealizada

    return list(
        ActividadRealizada.objects.filter(cliente=cliente, carga_ua__isnull=False)
        .annotate(fecha_carga=Coalesce('fecha_realizado', 'fecha'))
        .filter(fecha_carga__gte=desde, fecha_carga__lte=hasta)
        .values('id', 'carga_ua', 'duracion_minutos', 'fecha_carga')
    )


def actividad_atipica_reciente(cliente, fecha_hoy):
    """Devuelve la actividad de los últimos 7 días que parece un error, o None."""
    from entrenos.services.duracion_sesion_service import DURACION_MAX_MIN

    corte = fecha_hoy - timedelta(days=6)
    recientes = _actividades_con_fecha(cliente, corte, fecha_hoy)
    if not recientes:
        return None
    for a in recientes:
        if (a['duracion_minutos'] or 0) > DURACION_MAX_MIN:
            return a
    previas = [
        float(a['carga_ua'])
        for a in _actividades_con_fecha(cliente, corte - timedelta(days=42), corte - timedelta(days=1))
        if a['carga_ua']
    ]
    if len(previas) < MIN_MUESTRAS_MEDIANA:
        return None
    referencia = median(previas)
    mayor = max(recientes, key=lambda a: float(a['carga_ua']))
    if referencia > 0 and float(mayor['carga_ua']) > FACTOR_ATIPICO * referencia:
        return mayor
    return None


def contexto_acwr(cliente, fecha_hoy):
    """Claves para ``contexto_fisico``: acwr_valor, acwr_alto, acwr_dudoso."""
    ctx = {'acwr_valor': None, 'acwr_alto': False, 'acwr_dudoso': False}
    from entrenos.services.services import EstadisticasService

    datos = EstadisticasService.analizar_acwr_unificado(cliente) or {}
    if datos.get('fuente') != 'unificado_ewma' or datos.get('zona_riesgo') == 'insuficiente_historial':
        return ctx
    try:
        valor = float(datos.get('acwr_actual') or 0)
    except (TypeError, ValueError):
        return ctx
    if valor <= 0:
        return ctx
    ctx['acwr_valor'] = round(valor, 2)
    if valor >= ACWR_ALTO:
        if actividad_atipica_reciente(cliente, fecha_hoy) is not None:
            ctx['acwr_dudoso'] = True
        else:
            ctx['acwr_alto'] = True
    return ctx
