"""Criterios de entrenador que cambian el esfuerzo pedido hoy (26-oct-2026).

Salen del repaso del Día 1 (E1/E7 y el sueño corto con carga alta). Son
ajustes del día: bajan un punto el RPE objetivo de un ejercicio, nunca por
debajo de 7, y lo dicen en una frase con el dato. No cambian ejercicios ni
el orden de la semana (eso se propone, no se impone).

1. Músculo trabajado ayer: si ayer hiciste 4 series o más del mismo grupo
   (pecho el lunes después de dips, press inclinado y fondos el domingo),
   hoy ese grupo va un punto por debajo.
2. Has dormido poco y llevas mucha carga: con menos de 6 h 30 de sueño y la
   semana un 30 % o más por encima de lo normal en ti, todo un punto por
   debajo.

Los dos juntos no suman: como mucho, un punto menos.
"""

from collections import Counter
from datetime import timedelta
import unicodedata

SERIES_AYER_MIN = 4
RPE_SUELO = 7
SUENO_CORTO_H = 6.5
CARGA_ALTA = 1.3

GRUPOS = (
    ('pecho', 'pecho'), ('pector', 'pecho'),
    ('tricep', 'tríceps'), ('bicep', 'bíceps'),
    ('espalda', 'espalda'), ('dorsal', 'espalda'),
    ('hombro', 'hombros'), ('deltoid', 'hombros'),
    ('cuadricep', 'cuádriceps'), ('isquio', 'isquios'), ('femoral', 'isquios'),
    ('glute', 'glúteos'), ('gemelo', 'gemelos'), ('pantorr', 'gemelos'),
)


def _limpio(texto):
    texto = unicodedata.normalize('NFD', str(texto or '').casefold())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def grupo_de(texto):
    t = _limpio(texto)
    for clave, grupo in GRUPOS:
        if clave in t:
            return grupo
    return None


def _grupo_ejercicio(nombre, por_defecto=None):
    from rutinas.models import EjercicioBase
    base = EjercicioBase.objects.filter(nombre__iexact=nombre).only('grupo_muscular').first()
    return grupo_de(base.grupo_muscular if base else por_defecto) or grupo_de(por_defecto)


def series_ayer_por_grupo(cliente, hoy):
    from entrenos.models import SerieRealizada
    ayer = hoy - timedelta(days=1)
    cuenta = Counter()
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, entreno__fecha=ayer, completado=True, es_aproximacion=False,
    ).select_related('ejercicio'):
        grupo = grupo_de(s.ejercicio.grupo_muscular) or grupo_de(s.ejercicio.nombre)
        if grupo:
            cuenta[grupo] += 1
    return cuenta


def _sueno_y_carga(cliente, hoy):
    """(horas de sueño de hoy o None, ratio de carga o None)."""
    sueno = ratio = None
    try:
        from entrenos.services.recuperacion_service import _datos_hoy
        sueno = _datos_hoy(cliente, hoy).get('horas_sueno')
    except Exception:  # noqa: BLE001
        pass
    try:
        from entrenos.services.estado_carga_service import lectura_carga
        ratio = lectura_carga(cliente, hoy)['ratio']
    except Exception:  # noqa: BLE001
        pass
    return sueno, ratio


def aplicar_criterios(cliente, ejercicios, hoy):
    """Baja el RPE objetivo donde toca y deja la frase en ``criterio_entrenador``.

    Devuelve la lista de frases aplicadas (para la lista de cambios del plan).
    """
    from entrenos.services.recuperacion_service import horas_texto

    ayer = series_ayer_por_grupo(cliente, hoy)
    sueno, ratio = _sueno_y_carga(cliente, hoy)
    cansado = bool(sueno and sueno < SUENO_CORTO_H and ratio and ratio >= CARGA_ALTA)
    aplicadas = []
    for ej in ejercicios:
        try:
            rpe = float(ej.get('rpe_objetivo') or 0)
        except (TypeError, ValueError):
            continue
        if rpe <= RPE_SUELO or ej.get('_deload_aplicado') or ej.get('deload'):
            continue
        motivos = []
        grupo = _grupo_ejercicio(ej.get('nombre') or '', ej.get('grupo_muscular'))
        if grupo and ayer.get(grupo, 0) >= SERIES_AYER_MIN:
            motivos.append(f'ayer ya hiciste {ayer[grupo]} series de {grupo}')
        if cansado:
            motivos.append(f'has dormido {horas_texto(sueno)} y esta semana llevas un '
                           f'{round((ratio - 1) * 100)} % más de carga de lo normal en ti')
        if not motivos:
            continue
        nuevo = max(RPE_SUELO, rpe - 1)
        nuevo = int(nuevo) if float(nuevo).is_integer() else nuevo
        antes = int(rpe) if rpe.is_integer() else rpe
        ej['rpe_objetivo_plan'] = ej.get('rpe_objetivo')
        ej['rpe_objetivo'] = nuevo
        ej['criterio_entrenador'] = (f'Hoy RPE {nuevo} en vez de {antes}: '
                                     f'{" y ".join(motivos)}. Deja una o dos reps en reserva.')
        aplicadas.append({'ejercicio': ej.get('nombre'), 'frase': ej['criterio_entrenador']})
    return aplicadas
