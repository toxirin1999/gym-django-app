"""¿Tu RPE en fuerza es fiable? Se mide con tu propio rendimiento (14-oct-2026).

El "sesgo RPE vs FC" de Memoria sale de Hyrox/cardio: en fuerza el pulso no
dice cuántas repeticiones quedaban en reserva, y no se aplica al gym. Aquí
se mira otra cosa: si dices RPE 9 con 140 kg × 12 (quedaba ~1 repetición) y
pocos días después haces 140 kg × 15, ese RPE 9 era más bien un 7.

Regla: para dos sesiones seguidas del mismo ejercicio (≤ 14 días), cada
serie de la primera con RPE ≥ 8 marca un máximo de repeticiones posible a ese
peso (reps + reserva). Si en la segunda, con el mismo peso, se hacen 2 o más
repeticiones por encima de ese máximo, el RPE estaba alto. Solo se informa:
las reglas de peso no lo usan hasta que haya casos suficientes y lo veamos.
"""

from datetime import timedelta

from django.utils import timezone

DIAS_ENTRE_SESIONES = 14
EXCESO_CLARO = 2
RPE_MINIMO = 8
CASOS_MINIMOS = 5


def _kg(valor):
    texto = f'{float(valor):.2f}'.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def calibracion_rpe_gym(cliente, dias=90, hoy=None):
    """Devuelve un resumen de la fiabilidad del RPE en fuerza, o None sin datos."""
    from entrenos.models import SerieRealizada

    hoy = hoy or timezone.localdate()
    series = list(
        SerieRealizada.objects.filter(
            entreno__cliente=cliente, completado=True, es_aproximacion=False,
            entreno__fecha__gte=hoy - timedelta(days=dias), peso_kg__gt=0,
            ejercicio__tipo_progresion__in=('peso_reps', 'peso_corporal_lastre'),
        ).select_related('entreno', 'ejercicio').order_by('ejercicio_id', 'entreno__fecha', 'entreno_id')
    )
    # {ejercicio_id: [(fecha, entreno_id, [series])]}
    por_ejercicio = {}
    for s in series:
        sesiones = por_ejercicio.setdefault(s.ejercicio_id, [])
        if not sesiones or sesiones[-1][1] != s.entreno_id:
            sesiones.append((s.entreno.fecha, s.entreno_id, []))
        sesiones[-1][2].append(s)

    casos, altos, ejemplo = 0, 0, None
    for sesiones in por_ejercicio.values():
        for (fa, _, sa), (fb, _, sb) in zip(sesiones, sesiones[1:]):
            if (fb - fa).days > DIAS_ENTRE_SESIONES:
                continue
            for a in sorted(sa, key=lambda x: -(float(x.rpe_real) if x.rpe_real is not None else 0)):
                if a.rpe_real is None or float(a.rpe_real) < RPE_MINIMO:
                    continue
                mismas = [b for b in sb if abs(float(b.peso_kg) - float(a.peso_kg)) < 0.01]
                if not mismas:
                    continue
                tope_posible = a.repeticiones + (10 - float(a.rpe_real))
                mejor = max(b.repeticiones for b in mismas)
                casos += 1
                if mejor >= tope_posible + EXCESO_CLARO:
                    altos += 1
                    if ejemplo is None or mejor - tope_posible > ejemplo['exceso']:
                        ejemplo = {
                            'exceso': mejor - tope_posible,
                            'texto': (
                                f'{a.ejercicio.nombre}: dijiste RPE {_kg(a.rpe_real)} con '
                                f'{_kg(a.peso_kg)} kg × {a.repeticiones} y {(fb - fa).days} días después '
                                f'hiciste {_kg(a.peso_kg)} kg × {mejor}.'
                            ),
                        }
                break  # una comparación por ejercicio y par de sesiones
    if not casos:
        return None
    pct = round(100 * altos / casos)
    if casos < CASOS_MINIMOS:
        lectura = 'insuficiente'
    elif pct >= 50:
        lectura = 'alto'
    elif pct >= 25:
        lectura = 'algo_alto'
    else:
        lectura = 'fiable'
    return {
        'casos': casos,
        'altos': altos,
        'pct': pct,
        'lectura': lectura,
        'ejemplo': ejemplo['texto'] if ejemplo else None,
        'dias': dias,
    }
