"""Un partido apuntado no es un partido jugado (8-nov-2026).

Si el partido del miércoles se cancela, el jueves no se rebaja la pierna por
una cita que quedó anotada. Una actividad cuenta como jugada si trae algo de
lo que pasó: fecha de realización, importación de Strava, duración, pulso,
carga o RPE. Sin nada de eso (solo la fecha y el título), está apuntada.
"""

from django.db.models import Q


def q_jugada():
    return (Q(fecha_realizado__isnull=False) | Q(fuente='strava') | Q(duracion_minutos__gt=0)
            | Q(hr_media__isnull=False) | Q(carga_ua__gt=0) | Q(rpe_medio__isnull=False))


def es_jugada(actividad):
    return bool(
        actividad.fecha_realizado
        or getattr(actividad, 'fuente', None) == 'strava'
        or (actividad.duracion_minutos or 0) > 0
        or actividad.hr_media is not None
        or (actividad.carga_ua or 0) > 0
        or actividad.rpe_medio is not None
    )
