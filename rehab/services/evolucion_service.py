from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from ..models import RegistroDiarioRehab, SesionRehab, TransicionFase


def construir_evolucion(episodio, fecha=None, dias_ventana=60):
    fecha = fecha or timezone.localdate()
    fecha_desde = max(episodio.fecha_inicio, fecha - timedelta(days=dias_ventana))

    registros = RegistroDiarioRehab.objects.filter(
        episodio=episodio, fecha__gte=fecha_desde, fecha__lte=fecha,
    ).values('fecha', 'dolor_manana')
    dolor_manana_por_fecha = {r['fecha']: r['dolor_manana'] for r in registros}

    # Si un mismo día tiene más de una sesión (no debería ser lo normal, pero se
    # es defensivo), se toma el dolor_durante máximo: el pico del día es la señal
    # relevante para detectar si una fase empeora el dolor, no el promedio.
    sesiones = (
        SesionRehab.objects.filter(episodio=episodio, fecha__gte=fecha_desde, fecha__lte=fecha)
        .values('fecha')
        .annotate(dolor_durante_max=Max('dolor_durante'))
    )
    dolor_durante_por_fecha = {s['fecha']: s['dolor_durante_max'] for s in sesiones}

    fechas_con_dato = sorted(set(dolor_manana_por_fecha) | set(dolor_durante_por_fecha))
    puntos = [
        {
            'fecha': f,
            'dolor_manana': dolor_manana_por_fecha.get(f),
            'dolor_durante': dolor_durante_por_fecha.get(f),
        }
        for f in fechas_con_dato
    ]

    transiciones = (
        TransicionFase.objects.filter(episodio=episodio, fecha__gte=fecha_desde, fecha__lte=fecha)
        .select_related('fase_hasta')
        .order_by('fecha')
    )
    eventos = [
        {
            'fecha': t.fecha,
            'direccion': t.direccion,
            'fase_nombre': t.fase_hasta.nombre,
        }
        for t in transiciones
    ]

    return {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha,
        'puntos': puntos,
        'eventos': eventos,
    }
