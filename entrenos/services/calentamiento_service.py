"""
Calentamiento — Fase 64C: fuente única para las series de aproximación
(calentamiento) antes del peso de trabajo.

Extrae el cálculo que ya existía (enterrado) en vista_entrenamiento_activo,
sin cambiar sus valores: 50% / 70% / 85% del peso de trabajo, redondeados al
2.5 kg más cercano.
"""


def get_aproximaciones_calentamiento(peso_trabajo, usa_peso=True):
    """
    Series de aproximación (calentamiento) antes del peso de trabajo.

    Reproduce exactamente el cálculo original:
      - Si peso_trabajo <= 0 o usa_peso es False → None (no aplica calentamiento
        con peso, p.ej. ejercicios de solo-reps, tiempo o distancia sin carga).
      - Si no, devuelve {'peso1': 50%, 'peso2': 70%, 'peso3': 85%} del peso de
        trabajo, cada uno redondeado al 2.5 kg más cercano.
    """
    try:
        peso_trabajo = float(peso_trabajo or 0)
    except (TypeError, ValueError):
        return None

    if peso_trabajo <= 0 or not usa_peso:
        return None

    def _redondear(p):
        return round(round(p / 2.5) * 2.5, 1)

    return {
        'peso1': _redondear(peso_trabajo * 0.50),
        'peso2': _redondear(peso_trabajo * 0.70),
        'peso3': _redondear(peso_trabajo * 0.85),
    }
