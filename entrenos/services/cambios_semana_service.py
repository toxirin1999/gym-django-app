"""Qué cambia esta semana frente a la anterior (5-nov-2026).

Plan repetía en «Objetivo del bloque» la fase, la semana y las repeticiones
que ya están en la cabecera. En su lugar, lo que de verdad cambia en la
prescripción: series, esfuerzo y peso, con el dato. «La mitad de series»
solo si de verdad es la mitad.
"""

from datetime import timedelta


def _totales(planificador, lunes):
    from entrenos.services.sesion_recomendada import _es_descanso, _normalizar_entrenamiento

    series, rpes = 0, []
    for i in range(7):
        try:
            ent = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(lunes + timedelta(days=i)))
        except Exception:  # noqa: BLE001
            continue
        if _es_descanso(ent):
            continue
        for ej in ent.get('ejercicios') or []:
            try:
                series += int(ej.get('series') or 0)
            except (TypeError, ValueError):
                pass
            try:
                if ej.get('rpe_objetivo') is not None:
                    rpes.append(float(ej['rpe_objetivo']))
            except (TypeError, ValueError):
                pass
    return series, (sum(rpes) / len(rpes) if rpes else None)


def _n(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.').replace('.', ',')


def frases_cambio(actual, anterior, descarga):
    """Las líneas de «Qué cambia esta semana» a partir de (series, rpe medio)."""
    (s_hoy, rpe_hoy), (s_antes, rpe_antes) = actual, anterior
    lineas = []
    if s_hoy and s_antes:
        ratio = s_hoy / s_antes
        if s_hoy == s_antes:
            lineas.append(f'Series: las mismas que la semana pasada ({s_hoy}).')
        elif 0.45 <= ratio <= 0.55:
            lineas.append(f'Series: la mitad, {s_hoy} frente a {s_antes} la semana pasada.')
        else:
            pct = round((ratio - 1) * 100)
            lineas.append(f'Series: {s_hoy} frente a {s_antes} la semana pasada ({pct:+d} %).'.replace('+-', '-'))
    if rpe_hoy is not None and rpe_antes is not None:
        if abs(rpe_hoy - rpe_antes) < 0.25:
            lineas.append(f'Esfuerzo: el mismo, RPE {_n(rpe_hoy)} de media.')
        else:
            lineas.append(f'Esfuerzo: RPE {_n(rpe_hoy)} de media (la semana pasada, {_n(rpe_antes)}).')
    if descarga:
        lineas.append('Peso: un 10 % menos que tu última sesión normal (si bajar un salto quitara más '
                      'del 20 %, el mismo peso con menos reps). Nada busca subir.')
    else:
        lineas.append('Peso: sale de tu última sesión de cada ejercicio, con las reglas de siempre.')
    return lineas


def cambios_semana(cliente, hoy):
    """{'titulo', 'lineas', 'descarga'} o None si no hay con qué comparar."""
    from django.core.cache import cache
    from entrenos.models import SemanaPlanGym
    from entrenos.services.sesion_recomendada import _build_planificador

    lunes = hoy - timedelta(days=hoy.weekday())
    clave = f'cambios_semana:{cliente.pk}:{lunes.isoformat()}'
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado or None
    planificador = _build_planificador(cliente)
    actual = _totales(planificador, lunes)
    anterior = _totales(planificador, lunes - timedelta(days=7))
    descarga = SemanaPlanGym.objects.filter(cliente=cliente, lunes=lunes, descarga=True).exists()
    if not actual[0] or not anterior[0]:
        cache.set(clave, {}, 600)
        return None
    datos = {
        'titulo': 'Semana de descarga' if descarga else 'Frente a la semana pasada',
        'lineas': frases_cambio(actual, anterior, descarga),
        'descarga': descarga,
    }
    cache.set(clave, datos, 600)
    return datos
