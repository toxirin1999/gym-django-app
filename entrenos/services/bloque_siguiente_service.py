"""El bloque que empieza la semana que viene (7-nov-2026, notas 6 y 7 del Día 5).

El cierre del último día de la descarga decía «Mañana toca descanso» y
«Vuelve a 80 kg» sin avisar de que el lunes empezaba otro bloque con otro
rango de reps (dips a 6-8). Aquí se lee, con la misma periodización que el
planificador, si la semana siguiente cambia de bloque y con qué rango va cada
ejercicio.
"""

from datetime import timedelta


def _lunes_siguiente(fecha):
    return fecha - timedelta(days=fecha.weekday()) + timedelta(days=7)


def bloque_nuevo(cliente, fecha):
    """{'nombre', 'lunes', 'frase'} si la semana siguiente empieza un bloque nuevo, o None."""
    from entrenos.services.periodizacion_dinamica_service import _periodizacion, bloque_para_semana, resolver_semana

    try:
        periodizacion = _periodizacion()
        lunes = _lunes_siguiente(fecha)
        actual, _ = bloque_para_semana(resolver_semana(cliente, fecha), periodizacion)
        siguiente, _ = bloque_para_semana(resolver_semana(cliente, lunes), periodizacion)
    except Exception:  # noqa: BLE001
        return None
    if not siguiente or siguiente.get('fase') == 'descarga':
        return None
    if actual and actual.get('nombre') == siguiente.get('nombre'):
        return None
    reps = siguiente.get('rep_range')
    detalle = (f'{reps} reps en los básicos y {siguiente["reps_secundarios"]} en el resto'
               if siguiente.get('reps_secundarios') else f'{reps} reps')
    if siguiente.get('ejercicios_del_bloque_anterior'):
        detalle += ', con los mismos ejercicios'
    return {
        'nombre': siguiente['nombre'],
        'lunes': lunes,
        'frase': f'El lunes {lunes:%d/%m} empieza {siguiente["nombre"]}: {detalle}.',
    }


def rango_proximo(cliente, nombre, fecha):
    """El rango de reps con el que vuelve ``nombre`` la semana siguiente a ``fecha``, o None."""
    from entrenos.services.decision_log_service import normalizar_ejercicio
    from entrenos.services.sesion_recomendada import _build_planificador, _normalizar_entrenamiento

    clave = normalizar_ejercicio(nombre)
    planificador = _build_planificador(cliente)
    lunes = _lunes_siguiente(fecha)
    for i in range(7):
        try:
            ent = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(lunes + timedelta(days=i)))
        except Exception:  # noqa: BLE001
            continue
        for ej in (ent or {}).get('ejercicios') or []:
            if normalizar_ejercicio(ej.get('nombre') or '') == clave:
                return str(ej.get('repeticiones') or '') or None
    return None
