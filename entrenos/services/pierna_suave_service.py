"""Pierna en versión suave tras el fútbol (30-oct-2026, notas 2, 7 y 8).

Antes, el briefing decía "hoy pierna en versión suave" y la sesión no
cambiaba nada de pierna; la "versión esencial" incluso adelantaba el hip
thrust como ejercicio imprescindible. Ahora, si la versión esencial es por
piernas cargadas (fútbol o Hyrox de los dos días anteriores):

- los ejercicios de pierna llevan una serie menos (nunca menos de 2),
- pasan a opcionales y van al final,
- y se dice en una frase, con el partido.

Lo demás (tren superior) queda como lo pedía el plan.
"""

from datetime import timedelta

PIERNA = {'cuádriceps', 'isquios', 'gemelos', 'glúteos'}
SERIES_MINIMAS = 2


def actividad_de_piernas(cliente, hoy):
    """El partido (o Hyrox) de los dos días anteriores, o None."""
    from entrenos.models import ActividadRealizada
    return (
        ActividadRealizada.objects.filter(
            cliente=cliente, tipo__in=('futbol', 'hyrox'),
            fecha__gte=hoy - timedelta(days=2), fecha__lt=hoy,
        ).order_by('-fecha').first()
    )


def es_de_pierna(ej):
    from entrenos.services.criterios_entrenador_service import _grupo_ejercicio
    try:
        return _grupo_ejercicio(ej.get('nombre') or '', ej.get('grupo_muscular')) in PIERNA
    except Exception:  # noqa: BLE001
        return False


def _cuando(fecha, hoy):
    dias = (hoy - fecha).days
    return 'ayer' if dias == 1 else 'anteayer'


def aplicar_pierna_suave(cliente, ejercicios, hoy):
    """Rebaja la pierna en ``ejercicios`` (in place) y devuelve la frase, o None.

    Idempotente: un ejercicio ya marcado no vuelve a perder series.
    """
    actividad = actividad_de_piernas(cliente, hoy)
    if actividad is None or not ejercicios:
        return None
    rebajados = []
    for ej in ejercicios:
        if not es_de_pierna(ej):
            continue
        ej['pierna_suave'] = True
        if ej.get('_pierna_suave_aplicada'):
            rebajados.append(ej)
            continue
        try:
            series = int(ej.get('series') or 0)
        except (TypeError, ValueError):
            series = 0
        if series > SERIES_MINIMAS:
            ej['series_plan'] = series
            ej['series'] = series - 1
        ej['_pierna_suave_aplicada'] = True
        rebajados.append(ej)
    if not rebajados:
        return None
    # Pierna al final, conservando el orden dentro de cada bloque.
    ejercicios.sort(key=lambda e: 1 if e.get('pierna_suave') else 0)
    que = 'el fútbol' if actividad.tipo == 'futbol' else 'el Hyrox'
    duracion = f' ({actividad.duracion_minutos} min)' if actividad.duracion_minutos else ''
    return (f'Por {que} de {_cuando(actividad.fecha, hoy)}{duracion}: primero lo que no es pierna; '
            f'la pierna va al final, con una serie menos y como opcional '
            f'({len(rebajados)} ejercicios).')
