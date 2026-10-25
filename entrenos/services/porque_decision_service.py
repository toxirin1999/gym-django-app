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
    """La carga de esta semana frente a la habitual, en palabras (24-oct-2026: sin siglas)."""
    diferencia = round((float(acwr) - 1) * 100)
    if diferencia > 0:
        return f'Esta semana llevas un {diferencia} % más de carga que en tus semanas normales.'
    if diferencia < 0:
        return f'Esta semana llevas un {-diferencia} % menos de carga que en tus semanas normales.'
    return 'Esta semana llevas la misma carga que en tus semanas normales.'


# Paso 4: decisiones de la periodización que cambian la semana y se explican.
_ORIGENES_CON_PORQUE = {
    'repeticion', 'descarga_programada', 'descarga_saltada', 'descarga_senal', 'descarga_obligatoria',
}

_DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')


def _frase_cola(cola):
    """'El Día 2 era del martes: no se pierde, lo haces hoy.'"""
    from datetime import date
    try:
        dia_semana = _DIAS_SEMANA[date.fromisoformat(cola['fecha_prevista']).weekday()]
    except (TypeError, ValueError):
        return None
    return f"El {cola['dia']} era del {dia_semana}: no se pierde, lo haces hoy."


def construir_porque(decision_gym):
    """Frase con el dato que justifica la decisión de Gym, o None si no hay dato."""
    decision_gym = decision_gym or {}
    contexto = decision_gym.get('contexto_fisico') or {}
    causa = decision_gym.get('causa_principal') or ''
    acwr = contexto.get('acwr_valor')

    recuperacion = contexto.get('recuperacion') or {}
    futbol = contexto.get('futbol_esfuerzo') or {}

    if causa == 'recuperacion_baja' and recuperacion.get('frase'):
        return recuperacion['frase']
    if causa == 'carga_alta' and acwr:
        return _frase_acwr(acwr) + ' Hoy, versión reducida para no pasarnos.'
    if causa == 'fatiga_alta' and contexto.get('readiness_valor') is not None:
        return (f"Tu preparación de hoy está baja ({contexto['readiness_valor']} de 100): "
                f"hoy toca recuperar, no apretar.")
    if causa == 'energia_baja' and contexto.get('energia_valor') is not None:
        return (f"Me has dicho que tienes la energía en {contexto['energia_valor']} de 10: "
                f"hoy lo mínimo y bien hecho.")
    if causa == 'futbol_reciente':
        return futbol.get('frase') or 'Jugaste al fútbol hace poco y hoy toca pierna: versión suave.'
    if causa == 'hyrox_reciente':
        return 'Hyrox intenso (RPE 7 o más) en las últimas 48 h y hoy toca pierna: versión reducida.'
    if causa == 'lesion' and contexto.get('lesion_fase'):
        fase = str(contexto['lesion_fase']).replace('_', '-').lower()
        return f'Lesión en fase {fase} que afecta a ejercicios de hoy.'
    cola = decision_gym.get('cola') or {}
    if decision_gym.get('tipo') == 'pendiente' and cola.get('dia') and cola.get('fecha_prevista'):
        return _frase_cola(cola)
    if decision_gym.get('nota_semana'):
        return decision_gym['nota_semana']
    periodizacion = (decision_gym.get('entrenamiento') or {}).get('periodizacion') or {}
    if periodizacion.get('origen') in _ORIGENES_CON_PORQUE and periodizacion.get('motivo'):
        return periodizacion['motivo']
    if recuperacion.get('nivel') in ('ambar', 'verde', 'normal') and recuperacion.get('frase'):
        return recuperacion['frase']
    if contexto.get('acwr_dudoso') and acwr:
        return 'Una actividad reciente parece un error en los datos: no la tengo en cuenta para decidir.'
    if decision_gym.get('estado') in ('entrenar', 'version_reducida') and acwr:
        if 0.8 <= float(acwr) <= 1.3:
            return _frase_acwr(acwr) + ' Carga estable: hay margen.'
        return _frase_acwr(acwr)
    return None
