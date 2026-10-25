"""
Descanso — Fase 64B: fuente única para la sugerencia de descanso entre series.

Extrae el cálculo que ya existía (enterrado) en
PlanificadorHelms._calcular_descanso_pormenorizado, sin cambiar sus valores,
y le añade una explicación legible (label/motivo) para mostrar en sesión.
"""


# 20-oct-2026: descansos según la evidencia (Singer et al., 2024: más de 60 s
# ayuda a la hipertrofia; pasados ~90 s apenas añade). Los básicos piden algo
# más para llegar enteros a la siguiente serie; 4 min en un crunch sobraba.
_AISLAMIENTO = (
    'crunch', 'pallof', 'plancha', 'plank', 'dead bug', 'ab wheel', 'elevaciones de piernas',
    'curl', 'extension', 'extensión', 'elevación', 'elevacion', 'lateral', 'gemelo',
    'abducci', 'aducci', 'patada', 'fly', 'apertura', 'face pull', 'encogimiento',
    'y-raise', 'pec deck', 'pull-over', 'pullover', 'brazos rectos', 'aguante', 'muñeca',
)


_COMPUESTOS_PIERNA = (
    'sentadilla', 'búlgara', 'bulgara', 'zancada', 'lunge', 'hack', 'prensa', 'peso muerto',
    'hip thrust', 'step up', 'subida al cajón',
)


def _rep_max(reps):
    try:
        return int(str(reps).split('-')[-1])
    except (TypeError, ValueError):
        return None


def get_descanso_sugerido(tipo_ejercicio=None, rpe_objetivo=None, es_principal=False, nombre=None, reps=None):
    """
    Minutos de descanso recomendados y su explicación.

      - Fuerza (rango que no pasa de 6 reps): 3 min.
      - Aislamiento y core (por tipo o por nombre): 1:30.
      - Resto (básicos: prensa, rumano, jalón, remo, press…): 2:30.

    Devuelve {'minutos': float, 'label': str, 'motivo': str, 'fuente': 'evidencia'}.
    """
    tope = _rep_max(reps)
    if tope is not None and tope <= 6:
        return {'minutos': 3, 'label': '3 min', 'motivo': 'series pesadas de fuerza', 'fuente': 'evidencia'}
    texto = (nombre or '').casefold()
    if any(t in texto for t in _COMPUESTOS_PIERNA):
        # 25-oct-2026: la búlgara salía con 1:30 (marcada como aislamiento en
        # la base); un básico de pierna, y además a una pierna, pide 2:30.
        return {'minutos': 2.5, 'label': '2:30', 'motivo': 'ejercicio básico', 'fuente': 'evidencia'}
    aislamiento = tipo_ejercicio == 'aislamiento' or any(t in texto for t in _AISLAMIENTO)
    if aislamiento and not es_principal:
        return {'minutos': 1.5, 'label': '1:30', 'motivo': 'aislamiento o core', 'fuente': 'evidencia'}
    return {'minutos': 2.5, 'label': '2:30', 'motivo': 'ejercicio básico', 'fuente': 'evidencia'}
