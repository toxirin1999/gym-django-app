"""
Calentamiento — Fase 64C: fuente única para las series de aproximación
(calentamiento) antes del peso de trabajo.

Extrae el cálculo que ya existía (enterrado) en vista_entrenamiento_activo,
sin cambiar sus valores: 50% / 70% / 85% del peso de trabajo, redondeados al
2.5 kg más cercano.
"""


def get_aproximaciones_calentamiento(peso_trabajo, usa_peso=True, incremento=None):
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

    try:
        incremento = float(incremento or 0)
    except (TypeError, ValueError):
        incremento = 0
    if incremento > 0 and abs(incremento - 2.5) > 1e-9:
        # 21-oct-2026: en la escala real del equipo, hacia abajo (kettlebell de
        # 4 en 4: 8/12/16 y no 10/15/17,5; máquina de 5 en 5: 40 y no 42,5).
        from entrenos.services.maquina_service import a_escala

        def _redondear(p):  # noqa: F811
            return round(a_escala(p, incremento, 'abajo'), 1)

    p1 = _redondear(peso_trabajo * 0.50)
    p2 = _redondear(peso_trabajo * 0.70)
    p3 = _redondear(peso_trabajo * 0.85)
    if incremento > 0:
        # 22-oct-2026: sin escalones repetidos (laterales 5/10/10 → 5/10/15;
        # kettlebell 8/8/12 → 4/8/12), siempre por debajo del peso de trabajo.
        if p2 <= p1 and p1 + incremento < peso_trabajo - 1e-9:
            p2 = round(p1 + incremento, 1)
        if p3 <= p2 and p2 + incremento < peso_trabajo - 1e-9:
            p3 = round(p2 + incremento, 1)
        if p2 <= p1 or p3 <= p2:
            p2 = min(p2, round(p3 - incremento, 1))
            p1 = min(p1, round(p2 - incremento, 1))
            if p1 <= 0 or p2 <= 0:
                p1, p2 = _redondear(peso_trabajo * 0.50), _redondear(peso_trabajo * 0.70)
    return {'peso1': p1, 'peso2': p2, 'peso3': p3}
