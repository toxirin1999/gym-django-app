from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from entrenos.models import EjercicioRealizado, EntrenoRealizado


DIAS_POR_RANGO = {'30d': 30, '90d': 90, '180d': 180}


def _redondear(valor, decimales=1):
    return round(float(valor), decimales) if valor is not None else None


def construir_rendimiento_global(cliente, rango='30d'):
    """Lectura retrospectiva determinista; nunca proyecta rendimiento futuro."""
    hoy = timezone.localdate()
    dias = DIAS_POR_RANGO.get(rango)
    entrenos = EntrenoRealizado.objects.filter(cliente=cliente)
    if dias:
        entrenos = entrenos.filter(fecha__gte=hoy - timedelta(days=dias - 1))
    entrenos = entrenos.order_by('fecha', 'id')
    ids = list(entrenos.values_list('id', flat=True))
    total = len(ids)

    base = {
        'sesiones_observadas': total,
        'cobertura': {
            'sesiones': total,
            'con_volumen': entrenos.exclude(volumen_total_kg__isnull=True).count(),
            'con_duracion': entrenos.exclude(duracion_minutos__isnull=True).count(),
        },
        'progresion': {'estado': 'sin_evidencia', 'ejercicio': None, 'cambio_pct': None},
        'esfuerzo': {'estado': 'sin_evidencia', 'rpe_reciente': None, 'rpe_anterior': None},
        'constancia': {'estado': 'sin_evidencia', 'sesiones_recientes': 0, 'sesiones_anteriores': 0},
    }
    if not ids:
        return base

    mitad = max(1, total // 2)
    ids_anteriores = ids[:mitad]
    ids_recientes = ids[mitad:] or ids[:mitad]
    base['constancia'].update({
        'sesiones_anteriores': len(ids_anteriores),
        'sesiones_recientes': len(ids_recientes),
        'estado': 'estable' if len(ids_recientes) >= len(ids_anteriores) else 'descenso',
    })

    ejercicios = EjercicioRealizado.objects.filter(
        entreno_id__in=ids, completado=True, peso_kg__gt=0, repeticiones__gt=0,
    ).values('entreno_id', 'nombre_ejercicio', 'peso_kg', 'repeticiones', 'rpe')
    por_ejercicio = defaultdict(lambda: {'anterior': [], 'reciente': []})
    ids_anteriores_set = set(ids_anteriores)
    for item in ejercicios:
        tramo = 'anterior' if item['entreno_id'] in ids_anteriores_set else 'reciente'
        # Epley, rotulado en interfaz como estimación.
        e1rm = float(item['peso_kg']) * (1 + float(item['repeticiones']) / 30)
        por_ejercicio[item['nombre_ejercicio']][tramo].append(e1rm)

    candidatos = []
    for nombre, tramos in por_ejercicio.items():
        if tramos['anterior'] and tramos['reciente']:
            anterior = max(tramos['anterior'])
            reciente = max(tramos['reciente'])
            cambio = ((reciente - anterior) / anterior * 100) if anterior else 0
            candidatos.append((abs(cambio), cambio, nombre, anterior, reciente))
    if candidatos:
        _, cambio, nombre, anterior, reciente = max(candidatos)
        base['progresion'] = {
            'estado': 'mejora' if cambio > 1 else ('descenso' if cambio < -1 else 'estable'),
            'ejercicio': nombre,
            'cambio_pct': _redondear(cambio),
            'e1rm_anterior': _redondear(anterior),
            'e1rm_reciente': _redondear(reciente),
        }

    rpe_anterior = EjercicioRealizado.objects.filter(
        entreno_id__in=ids_anteriores, completado=True, rpe__isnull=False,
    ).aggregate(media=Avg('rpe'))['media']
    rpe_reciente = EjercicioRealizado.objects.filter(
        entreno_id__in=ids_recientes, completado=True, rpe__isnull=False,
    ).aggregate(media=Avg('rpe'))['media']
    if rpe_reciente is not None:
        reciente = _redondear(rpe_reciente)
        base['esfuerzo'] = {
            'estado': 'alto' if reciente >= 8.5 else ('contenido' if reciente <= 6 else 'sostenible'),
            'rpe_reciente': reciente,
            'rpe_anterior': _redondear(rpe_anterior),
        }
    return base

