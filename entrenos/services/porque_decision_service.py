"""El "por qué" de la decisión de hoy, en una frase y con el dato.

Regla 3 del rumbo (docs/rumbo_entrenador_vivo.md): el entrenador dice por qué
en una frase y con el dato. Regla de oro: si no puede citar el dato, no lo
dice. Por eso cada frase sale solo de valores presentes en la decisión
(``contexto_fisico``); si falta el dato, devuelve None y la pantalla no
inventa nada.
"""


def _num(valor, decimales=2):
    texto = f'{float(valor):.{decimales}f}'.replace('.', ',')
    if ',' in texto:
        texto = texto.rstrip('0').rstrip(',')
    return texto


def _frase_acwr(acwr):
    """Lectura del ACWR con su porcentaje respecto a la carga habitual."""
    diferencia = round((float(acwr) - 1) * 100)
    if diferencia > 0:
        return f'ACWR {_num(acwr)}: esta semana llevas un {diferencia} % más de carga que tu media.'
    if diferencia < 0:
        return f'ACWR {_num(acwr)}: esta semana llevas un {-diferencia} % menos de carga que tu media.'
    return f'ACWR {_num(acwr)}: esta semana llevas la misma carga que tu media.'


def construir_porque(decision_gym):
    """Frase con el dato que justifica la decisión de Gym, o None si no hay dato."""
    decision_gym = decision_gym or {}
    contexto = decision_gym.get('contexto_fisico') or {}
    causa = decision_gym.get('causa_principal') or ''
    acwr = contexto.get('acwr_valor')

    if causa == 'carga_alta' and acwr:
        return _frase_acwr(acwr) + ' Hoy, versión reducida.'
    if causa == 'fatiga_alta' and contexto.get('readiness_valor') is not None:
        return f"Readiness {contexto['readiness_valor']}/100 hoy (por debajo de 45): toca recuperar."
    if causa == 'energia_baja' and contexto.get('energia_valor') is not None:
        return f"Energía {contexto['energia_valor']}/10 en el check-in de hoy: versión mínima."
    if causa == 'futbol_reciente':
        return 'Fútbol en las últimas 48 h y hoy toca pierna: versión reducida.'
    if causa == 'hyrox_reciente':
        return 'Hyrox intenso (RPE 7 o más) en las últimas 48 h y hoy toca pierna: versión reducida.'
    if causa == 'lesion' and contexto.get('lesion_fase'):
        fase = str(contexto['lesion_fase']).replace('_', '-').lower()
        return f'Lesión en fase {fase} que afecta a ejercicios de hoy.'
    if contexto.get('acwr_dudoso') and acwr:
        return (
            f'El ACWR marca {_num(acwr)}, pero una actividad reciente parece un error: '
            'no la tengo en cuenta para decidir.'
        )
    if decision_gym.get('estado') in ('entrenar', 'version_reducida') and acwr:
        if 0.8 <= float(acwr) <= 1.3:
            return _frase_acwr(acwr) + ' Carga estable: hay margen.'
        return _frase_acwr(acwr)
    return None
