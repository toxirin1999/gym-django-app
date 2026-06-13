"""
Descanso — Fase 64B: fuente única para la sugerencia de descanso entre series.

Extrae el cálculo que ya existía (enterrado) en
PlanificadorHelms._calcular_descanso_pormenorizado, sin cambiar sus valores,
y le añade una explicación legible (label/motivo) para mostrar en sesión.
"""


def get_descanso_sugerido(tipo_ejercicio=None, rpe_objetivo=None, es_principal=False):
    """
    Minutos de descanso recomendados y su explicación.

    Reproduce exactamente la fórmula original de Helms:
      - principal (tipo_ejercicio == 'compuesto_principal' o es_principal=True)
        con RPE >= 8 → 4 min; si no, 3 min.
      - resto (compuesto_secundario / aislamiento) con RPE >= 8 → 2 min;
        si no, 1 min.

    Devuelve {'minutos': int, 'label': str, 'motivo': str, 'fuente': 'helms'}.
    """
    rpe = rpe_objetivo if rpe_objetivo is not None else 0
    if tipo_ejercicio is not None:
        es_principal = tipo_ejercicio == 'compuesto_principal'

    if es_principal:
        if rpe >= 8:
            return {'minutos': 4, 'label': '3-4 min', 'motivo': 'principal con RPE alto', 'fuente': 'helms'}
        return {'minutos': 3, 'label': '3-4 min', 'motivo': 'principal', 'fuente': 'helms'}

    if rpe >= 8:
        return {'minutos': 2, 'label': '1-2 min', 'motivo': 'accesorio con RPE alto', 'fuente': 'helms'}
    return {'minutos': 1, 'label': '1-2 min', 'motivo': 'accesorio', 'fuente': 'helms'}
