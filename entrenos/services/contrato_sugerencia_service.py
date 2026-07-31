"""Contrato verificable v1 para sugerencias ordinarias del plan."""

from django.utils import timezone

from entrenos.services.analisis_semanal_service import _recopilar_semanas


PATRON_V1 = 'esenciales_frecuentes'
VERSION = 1


def construir_contrato_sugerencia(cliente, patron, fecha_ref=None):
    """Construye evidencia actual. No persiste ni modifica sugerencias."""
    if patron != PATRON_V1:
        raise ValueError(f'No existe contrato de sugerencia para {patron!r}.')
    fecha_ref = fecha_ref or timezone.localdate()
    semanas = _recopilar_semanas(cliente, 3, fecha_ref)
    evidencia = []
    for semana in semanas[:3]:
        completadas = int(semana.get('sesiones_completadas') or 0)
        esenciales = int(semana.get('sesiones_esenciales') or 0)
        ratio = esenciales / completadas if completadas else 0
        evidencia.append({
            'desde': semana.get('lunes').isoformat() if semana.get('lunes') else None,
            'hasta': semana.get('domingo').isoformat() if semana.get('domingo') else None,
            'rango': (
                f"{semana.get('lunes'):%d/%m/%Y}–{semana.get('domingo'):%d/%m/%Y}"
                if semana.get('lunes') and semana.get('domingo') else None
            ),
            'completadas': completadas,
            'esenciales': esenciales,
            'porcentaje_esenciales': round(ratio * 100),
            'cumple_umbral': completadas > 0 and ratio >= 0.5,
        })
    cumplen = sum(1 for semana in evidencia if semana['cumple_umbral'])
    return {
        'version': VERSION,
        'patron': PATRON_V1,
        'fecha_referencia': fecha_ref.isoformat(),
        'vigente': cumplen >= 2,
        'evidencia': {
            'ventana_semanas': 3,
            'semanas_observadas': evidencia,
            'semanas_que_cumplen': cumplen,
            'regla': 'Al menos 50% de sesiones esenciales en 2 de hasta 3 semanas.',
        },
        'diagnostico': (
            'Las versiones esenciales se repiten; puede que la progresión de cargas '
            'no esté encontrando margen en la semana real.'
        ),
        'limites': {
            'no_demuestra': ['volumen', 'fatiga'],
            'texto': 'No demuestra que tengas demasiado volumen ni que exista fatiga fisiológica.',
        },
        'cambio': {
            'codigo': 'freeze_load_increases',
            'tipo_intervencion': 'no_subir_cargas',
            'duracion_dias': 7,
            'descripcion': (
                'Impedir subidas por encima del último peso realizado durante 7 días; '
                'si el plan propone una bajada, se respeta.'
            ),
            'no_cambia': ['ejercicios', 'series', 'repeticiones', 'días de entrenamiento'],
        },
        'unchanged': ['ejercicios', 'series', 'repeticiones', 'días de entrenamiento'],
        'evaluacion': {
            'criterio': 'Comparar sesiones completas y esenciales al terminar los 7 días.',
        },
    }


def validar_contrato_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    try:
        semanas = snapshot['evidencia']['semanas_observadas']
        semanas_validas = all(
            isinstance(semana.get('completadas'), int)
            and isinstance(semana.get('esenciales'), int)
            and isinstance(semana.get('cumple_umbral'), bool)
            for semana in semanas
        )
        return (
            snapshot['version'] == VERSION
            and snapshot['patron'] == PATRON_V1
            and isinstance(snapshot['evidencia']['semanas_observadas'], list)
            and 2 <= len(semanas) <= 3
            and semanas_validas
            and snapshot['evidencia']['semanas_que_cumplen'] >= 2
            and snapshot['cambio']['codigo'] == 'freeze_load_increases'
            and snapshot['cambio']['tipo_intervencion'] == 'no_subir_cargas'
            and snapshot['cambio']['duracion_dias'] == 7
            and bool(snapshot['unchanged'])
            and bool(snapshot['evaluacion']['criterio'])
        )
    except (AttributeError, KeyError, TypeError):
        return False


def revalidar_sugerencia(sugerencia, fecha_ref=None):
    if sugerencia.patron != PATRON_V1 or not validar_contrato_snapshot(sugerencia.contrato_snapshot):
        return None
    actual = construir_contrato_sugerencia(
        sugerencia.cliente, sugerencia.patron, fecha_ref=fecha_ref,
    )
    if not actual['vigente']:
        return None
    if actual['evidencia'] != sugerencia.contrato_snapshot['evidencia']:
        return None
    return actual
