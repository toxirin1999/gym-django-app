"""Un solo cerebro para el peso y las reps de hoy (24-oct-2026, paso 1, "a la sombra").

Hoy el número que ves sale de varias capas que se pisan (planificador anual,
progresión ejecutiva, techo de la última sesión, escala, entre series, cierre).
Aquí está la regla entera en una función, a partir de las series reales de la
última vez:

1. Sin historial reciente (42 días) → no decide: manda el plan.
2. Tope de máquina → ese peso y reps = mejor serie + margen de RPE (máx. 25).
3. Rango nuevo de otra familia (fuerza ↔ hipertrofia) → peso estimado para el
   rango de hoy desde la serie de referencia.
4. Si no, el techo de la última sesión (``techo_peso``):
   - se quedó muy corta o se hundió → baja un salto (o lo que dé la estimación);
   - entró y no llegó al tope del rango → mismo peso, una rep más (regla C);
   - llegó al tope del rango → sube un salto y vuelve al mínimo.

De momento NO cambia nada en la app: lo usa ``comparar_cerebro_carga`` para
ver, con el historial real, en qué se diferencia de lo que sale hoy.
"""

from datetime import timedelta


def _kg(valor):
    v = round(float(valor), 2)
    return str(int(v)) if v == int(v) else f'{v:g}'.replace('.', ',')


def _a_escala_empate_arriba(peso, salto):
    """Al peso más cercano que existe; justo en medio, hacia arriba (como la app)."""
    from entrenos.services.maquina_service import a_escala
    abajo, arriba = a_escala(peso, salto, 'abajo'), a_escala(peso, salto, 'arriba')
    return arriba if (arriba - peso) <= (peso - abajo) + 1e-9 else abajo


HUNDIMIENTO_REPS = 4  # caída de golpe entre dos series seguidas al mismo peso (27-oct: 5 → 4, press de hombro 16 → 12)


def hundimiento_en_sesion(series, minimo, rpe_obj):
    """(primera, siguiente) si la primera serie entró con el esfuerzo pedido y la
    siguiente, al mismo peso, cayó de golpe por debajo del rango; si no, None.

    Un descenso gradual (curl martillo 15, 13 y 8) no cuenta: eso sí dice que
    el peso es demasiado.
    """
    validas = [s for s in series if s['reps'] > 0 and s['peso'] > 0]
    if len(validas) < 2:
        return None
    primera, siguiente = validas[0], validas[1]
    if primera['reps'] < minimo or primera.get('rpe') is None or primera['rpe'] > rpe_obj:
        return None
    if abs(siguiente['peso'] - primera['peso']) > 1e-6 or siguiente['reps'] >= minimo:
        return None
    if primera['reps'] - siguiente['reps'] < HUNDIMIENTO_REPS:
        return None
    return primera, siguiente


def hecho_fuera_de_orden(entreno, nombre):
    """27-oct-2026 (E4): ¿se hizo este ejercicio después de otros que el plan ponía detrás?

    Jalón al pecho, tercero en el plan, hecho el séptimo porque la máquina
    estaba ocupada. Se mira el orden de la primera serie de cada ejercicio.
    """
    from entrenos.models import SerieRealizada
    from entrenos.services.decision_log_service import normalizar_ejercicio

    version = getattr(entreno, 'gym_decision_version', None)
    plan = [normalizar_ejercicio(e.get('nombre')) for e in
            ((getattr(version, 'snapshot', None) or {}).get('entrenamiento') or {}).get('ejercicios') or []]
    clave = normalizar_ejercicio(nombre)
    if clave not in plan:
        return False
    primera = {}
    for sid, n in SerieRealizada.objects.filter(entreno=entreno, completado=True).order_by('id').values_list(
        'id', 'ejercicio__nombre',
    ):
        primera.setdefault(normalizar_ejercicio(n), sid)
    if clave not in primera:
        return False
    detras = plan[plan.index(clave) + 1:]
    return any(primera.get(otro, float('inf')) < primera[clave] for otro in detras)


def contexto_cansancio(cliente, entreno, nombre):
    """Por qué esa sesión pudo ir peor sin que el peso fuera el problema, o None."""
    from entrenos.services.criterios_entrenador_service import energia_baja
    try:
        if hecho_fuera_de_orden(entreno, nombre):
            return 'lo hiciste al final, fuera de su orden'
    except Exception:  # noqa: BLE001
        pass
    baja = energia_baja(cliente, entreno.fecha, entreno.energia_pre_sesion)
    if baja:
        e, habitual = baja
        hab = str(int(habitual)) if float(habitual).is_integer() else f'{habitual:g}'.replace('.', ',')
        return f'llegabas con energía {e} frente a tu {hab} habitual'
    return None


def decidir_carga(cliente, ej, hoy):
    """{'peso', 'reps', 'regla', 'frase'} para un ejercicio del plan de hoy, o None.

    28-oct-2026: además ``peso_antes`` (el peso real de la última vez, para el
    tachado del briefing: salía el 32,5 del plan anual, que nunca se levantó) y
    la fecha cuando la última vez fue hace más de dos semanas.
    """
    decision = _decidir_carga(cliente, ej, hoy)
    if not decision:
        return decision
    from entrenos.services.ultima_sesion_service import rango_reps, ultima_sesion
    rango = rango_reps(ej.get('repeticiones_plan') or ej.get('repeticiones'))
    lectura = ultima_sesion(cliente, ej.get('nombre') or '', hoy, reps_min=rango[0] if rango else None)
    if lectura:
        decision['peso_antes'] = float(lectura['referencia']['peso'])
        dias = (hoy - lectura['fecha']).days
        frase = decision.get('frase') or ''
        if dias > 14 and frase.startswith('La última vez'):
            decision['frase'] = f"El {lectura['fecha']:%d/%m} (hace {dias} días)" + frase[len('La última vez'):]
    return decision


def _decidir_carga(cliente, ej, hoy):
    """{'peso', 'reps', 'regla', 'frase'} para un ejercicio del plan de hoy, o None."""
    from analytics.planificador_helms.calculo.compatibilidad_fase import son_rangos_compatibles
    from entrenos.services.maquina_service import a_escala, salto_carga, tope_de
    from entrenos.services.progreso_service import reps_tope_con_margen
    from entrenos.services.ultima_sesion_service import (
        VENTANA_DIAS, objetivo_reps_hoy, peso_para_reps, rango_reps, techo_peso, ultima_sesion,
    )

    tipo = ej.get('tipo_progresion') or 'peso_reps'
    if tipo not in ('peso_reps', 'peso_corporal_lastre'):
        return None
    rango_txt = ej.get('repeticiones_plan') or ej.get('repeticiones')
    rango = rango_reps(rango_txt)
    if not rango:
        return None
    nombre = ej.get('nombre') or ''
    lectura = ultima_sesion(cliente, nombre, hoy, reps_min=rango[0])
    if not lectura:
        return None
    antigua = (hoy - lectura['fecha']) > timedelta(days=VENTANA_DIAS)

    minimo, maximo = rango
    salto = salto_carga(cliente, nombre)
    tope = tope_de(cliente, nombre)
    try:
        rpe_obj = float(ej.get('rpe_objetivo') or 8)
    except (TypeError, ValueError):
        rpe_obj = 8.0
    # 26-oct-2026: la regla trabaja con la mediana de las series a ese peso.
    if lectura['referencia'].get('reps_mediana') is not None:
        lectura = dict(lectura, referencia=dict(lectura['referencia'], reps=lectura['referencia']['reps_mediana']))
    ref = lectura['referencia']
    peso_ref = float(ref['peso'])
    reps_ref = int(round(float(ref['reps'])))

    # 2. Tope de máquina.
    if lectura.get('es_tope_maquina') or (tope and peso_ref >= tope - 1e-6):
        peso = float(tope or peso_ref)
        reps, aviso = reps_tope_con_margen(cliente, nombre, hoy, reps_ref + 1)
        frase = f'{_kg(peso)} kg es el tope de la máquina: hoy a por {reps} reps.'
        if aviso:
            frase += ' ' + aviso
        return {'peso': peso, 'reps': reps, 'regla': 'tope', 'frase': frase}

    # 2b. 25-oct-2026: un día de fatiga (15 × 15 y luego 15 × 4) no baja el peso:
    # se repite con el objetivo de la vez anterior.
    from entrenos.services.ultima_sesion_service import dia_de_fatiga
    fatiga = dia_de_fatiga(cliente, nombre, lectura['entreno'], reps_min=minimo)
    if fatiga and not antigua:
        reps = max(minimo, min(maximo, fatiga['reps_antes']))
        return {
            'peso': float(fatiga['peso']), 'reps': reps, 'regla': 'fatiga',
            'reps_hoy': fatiga['reps_hoy'], 'reps_antes': fatiga['reps_antes'],
            'frase': (f"La última vez llegaste muy cansado ({_kg(fatiga['peso'])} kg × {fatiga['reps_hoy']}; "
                      f"antes hacías {_kg(fatiga['peso'])} × {fatiga['reps_antes']}). "
                      f"Repetimos {_kg(fatiga['peso'])} kg a por {reps}."),
        }

    # 2c. 26-oct-2026: cansancio dentro de la sesión. La primera serie entró con
    # el esfuerzo pedido y la siguiente se hundió de golpe (Convergent 62,5 × 14
    # a RPE 8 y luego 62,5 × 8 a RPE 10, después de un cable fly al fallo): el
    # peso es el bueno; no se baja por ese día.
    hundida = hundimiento_en_sesion(lectura['series'], minimo, rpe_obj)
    if hundida and not antigua:
        primera, siguiente = hundida
        reps = max(minimo, min(maximo, primera['reps']))
        return {
            'peso': float(primera['peso']), 'reps': reps, 'regla': 'fatiga', 'tipo_fatiga': 'sesion',
            'reps_hoy': siguiente['reps'], 'reps_antes': primera['reps'],
            'frase': (f"La última vez la primera serie entró ({_kg(primera['peso'])} kg × {primera['reps']} "
                      f"a RPE {_kg(primera['rpe'])}) y la siguiente se hundió a {siguiente['reps']}: "
                      f"fue cansancio, no el peso. Repetimos {_kg(primera['peso'])} kg a por {reps}."),
        }

    # 2d. 27-oct-2026 (nota 14, E4): la primera serie entró y las últimas
    # cayeron en un día que lo explica (ejercicio aplazado al final, o energía
    # 2 puntos por debajo de lo habitual). Jalón 50 × 15, 15, 12 y 9 hecho el
    # séptimo: no se baja a 45.
    validas = [x for x in lectura['series'] if x['reps'] > 0 and x['peso'] > 0]
    if validas and not antigua:
        primera = validas[0]
        cayeron = [x for x in validas[1:] if abs(x['peso'] - primera['peso']) < 1e-6 and x['reps'] < minimo]
        if (primera['reps'] >= minimo and cayeron
                and (primera.get('rpe') is None or primera['rpe'] <= rpe_obj + 1)):
            motivo = contexto_cansancio(cliente, lectura['entreno'], nombre)
            if motivo:
                reps = objetivo_reps_hoy(primera['reps'], rango)
                peor = min(cayeron, key=lambda x: x['reps'])
                return {
                    'peso': float(primera['peso']), 'reps': reps, 'regla': 'fatiga', 'tipo_fatiga': 'contexto',
                    'reps_hoy': peor['reps'], 'reps_antes': primera['reps'], 'motivo': motivo,
                    'frase': (f"La última vez {_kg(primera['peso'])} kg × {primera['reps']} entró y después "
                              f"cayó a {peor['reps']}, pero {motivo}: repetimos {_kg(primera['peso'])} kg "
                              f"a por {reps}."),
                }

    # 2e. 27-oct-2026 (nota 4): vuelta al peso de antes. Press de hombro: 40 × 16
    # a RPE 8 y se hundió; se bajó a 35 y salió 35 × 15 × 3 a RPE 8. El 40 era
    # el peso bueno: se vuelve a él a por el mínimo.
    if not antigua and ref['en_rango']:
        al_peso = [x for x in validas if abs(x['peso'] - peso_ref) < 1e-6]
        rpes = [x['rpe'] for x in al_peso]
        if al_peso and None not in rpes and max(rpes) <= rpe_obj and all(x['reps'] >= minimo for x in al_peso):
            previa = ultima_sesion(cliente, nombre, lectura['fecha'], reps_min=minimo)
            from entrenos.services.ultima_sesion_service import rango_de_sesion
            if (previa and (lectura['fecha'] - previa['fecha']).days <= 21
                    and rango_de_sesion(previa['entreno'], nombre) == rango_de_sesion(lectura['entreno'], nombre)):
                prev_validas = [x for x in previa['series'] if x['reps'] > 0 and x['peso'] > 0]
                p1 = prev_validas[0] if prev_validas else None
                # Solo si allí se hundió de golpe (16 → 12), no poco a poco (15, 13, 8:
                # eso sí era demasiado peso).
                p2 = next((x for x in prev_validas[1:] if p1 and abs(x['peso'] - p1['peso']) < 1e-6), None)
                de_golpe = p2 is None or (p1['reps'] - p2['reps'] >= HUNDIMIENTO_REPS)
                if (p1 and de_golpe and p1['peso'] > peso_ref + 1e-6 and p1['reps'] >= minimo
                        and p1.get('rpe') is not None and p1['rpe'] <= rpe_obj
                        and (not tope or p1['peso'] <= tope + 1e-6)):
                    return {
                        'peso': float(p1['peso']), 'reps': minimo, 'regla': 'volver',
                        'frase': (f"Con {_kg(peso_ref)} kg te sobró poco esfuerzo (RPE {_kg(max(rpes))}) y antes "
                                  f"{_kg(p1['peso'])} kg × {p1['reps']} entró: hoy vuelves a {_kg(p1['peso'])} kg "
                                  f"a por {minimo}."),
                    }

    # 3. Cambio de familia de rango, o última vez de hace más de 6 semanas:
    # se estima para el rango de hoy, no se arrastra el peso (remo en polea
    # 60 × 8 hace dos meses → no "60 a por 15").
    if antigua or not son_rangos_compatibles(reps_ref, rango_txt):
        estimado = peso_para_reps(peso_ref, reps_ref, ref['rpe'], minimo, rpe_obj)
        if not estimado:
            return None
        # 24-oct-2026: al más cercano; hacia abajo, con pesos pequeños y saltos
        # de 5 kg, se quedaba en la mitad (curl inclinado 10 → 5 kg).
        peso = a_escala(estimado, salto, 'cerca')
        if tope:
            peso = min(peso, float(tope))
        cuando = f"El {lectura['fecha'].strftime('%d/%m')}" if antigua else 'La última vez'
        return {
            'peso': peso, 'reps': minimo, 'regla': 'antigua' if antigua else 'recalcular',
            'frase': f'{cuando} {_kg(peso_ref)} kg × {reps_ref}; para {minimo}-{maximo}, hoy {_kg(peso)} kg.',
        }

    # 4. Techo de la última sesión + regla C.
    resultado = techo_peso(lectura, rango, rpe_obj, salto)
    if not resultado:
        return None
    techo, frase, accion = resultado
    if accion == 'bajar':
        return {'peso': float(techo), 'reps': minimo, 'regla': 'bajar', 'frase': frase}
    if frase is None and any(t in nombre.casefold() for t in ('pallof', 'antirrot', 'anti-rot')):
        # 27-oct-2026 (E2): en antirrotación lo que cuenta es no girar. Al tope
        # del rango no se sube peso: se endurece con una pausa.
        return {
            'peso': peso_ref, 'reps': maximo, 'regla': 'mantener', 'pausa': True,
            'frase': (f'Ya llegas a {maximo} con {_kg(peso_ref)} kg: mismo peso y aguanta 2 s con los brazos '
                      f'estirados en cada repetición, en vez de subir.'),
        }
    if frase is None:
        # Llegó al tope del rango: un salto arriba (nunca por encima del tope).
        peso = a_escala(peso_ref + salto, salto, 'cerca')
        if tope:
            peso = min(peso, float(tope))
        return {
            'peso': peso, 'reps': minimo, 'regla': 'subir',
            'frase': (f'{reps_ref} reps con {_kg(peso_ref)} kg, arriba del rango: '
                      f'hoy {_kg(peso)} kg y vuelta a {minimo}.'),
        }
    from entrenos.services.maquina_service import tipo_equipo_carga
    if abs(float(techo) - peso_ref) < 1e-6 and tipo_equipo_carga(nombre) not in (
        'mancuerna_una', 'mancuerna_dos', 'kettlebell',
    ):
        # 25-oct-2026: el peso real que usaste se respeta aunque no esté en la
        # escala (Bayesian con una placa de 2 kg encima: 22,5). Antes se
        # redondeaba a 25, dejaba de ser "el mismo peso" y las reps no subían.
        # Las mancuernas y kettlebells sí van a su escala (46 kg no existe).
        peso = peso_ref
    else:
        peso = _a_escala_empate_arriba(float(techo), salto)
    mismo = abs(peso - peso_ref) < salto / 2
    reps = objetivo_reps_hoy(ref['reps'], rango, mismo and ref['en_rango'])
    if mismo and ref['en_rango'] and reps < maximo:
        al_peso = [x for x in lectura['series'] if abs(x['peso'] - peso_ref) < 1e-6 and x['reps'] > 0]
        rpes = [x['rpe'] for x in al_peso]
        if al_peso and None not in rpes and all(x['reps'] >= minimo for x in al_peso) \
                and max(rpes) <= rpe_obj - 1:
            # 25-oct-2026: con margen de sobra (fondos 75 × 15 y 16 a RPE 6 con
            # objetivo 7), dos reps más en vez de una.
            reps = min(maximo, reps + 1)
            frase = (f'La última vez RPE {_kg(max(rpes))}, por debajo del {_kg(rpe_obj)} que pide: '
                     f'hoy {_kg(peso)} kg a por {reps} reps.')
    return {'peso': peso, 'reps': reps, 'regla': 'mantener' if mismo else 'ajustar', 'frase': frase}


def aplicar_decision_carga(ej, decision):
    """Impone la decisión de la regla única en un ejercicio del plan de hoy.

    Solo toca lo que cambia: si el plan ya decía ese peso y esas reps, se
    queda con su texto. Devuelve True si cambió algo.
    """
    # 25-oct-2026: la etiqueta del briefing sabe por qué cambia el peso
    # (un cambio de rango no es "bajar"; un día de fatiga se repite).
    ej['regla_carga'] = decision['regla']
    try:
        peso_actual = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        peso_actual = 0.0
    reps_actuales = ej.get('reps_objetivo_hoy')
    if decision['regla'] == 'tope':
        reps_actuales = ej.get('reps_sugeridas_tope') or reps_actuales
    if decision.get('peso_antes') and ej.get('peso_kg_anterior') is not None:
        # El tachado es el peso real de la última vez, no el del plan anual.
        ej['peso_kg_anterior'] = decision['peso_antes']
    if abs(peso_actual - decision['peso']) < 0.01 and str(reps_actuales) == str(decision['reps']):
        # 26-oct-2026: mismos números, pero el texto venía de otra capa y podía
        # contradecirlos (prensa: "hoy a por 13 reps (la última vez 12)" cuando
        # la última vez fueron 13 y la regla pedía 14). El texto sigue a la regla.
        motivo = str(ej.get('progresion_motivo') or '')
        # 27-oct-2026 (nota 3): crunch 75 → 70 kg con el texto "Mismo peso: hoy a
        # por 15": si la regla cambia el peso, el texto tiene que nombrarlo.
        if decision.get('frase') and (
            f"a por {decision['reps']}" not in motivo
            or (decision['regla'] != 'mantener' and f"{_kg(decision['peso'])} kg" not in motivo)
            or (decision['regla'] != 'mantener' and motivo.startswith('Mismo peso'))
        ):
            ej['progresion_motivo'] = decision['frase']
            ej['progresion_motivo_local'] = 'regla_unica'
            ej.pop('motivo_peso', None)
        return False
    if decision.get('peso_antes') and abs(decision['peso_antes'] - decision['peso']) >= 0.01:
        ej['peso_kg_anterior'] = decision['peso_antes']
    ej['peso_kg'] = decision['peso']
    if 'peso_recomendado_kg' in ej:
        ej['peso_recomendado_kg'] = decision['peso']
    ej['reps_objetivo_hoy'] = decision['reps']
    if decision['regla'] == 'tope':
        ej['sugerencia_tope'] = True
        ej['reps_sugeridas_tope'] = decision['reps']
    if decision.get('frase'):
        ej['progresion_motivo'] = decision['frase']
        ej['progresion_motivo_local'] = 'regla_unica'
        ej.pop('motivo_peso', None)
    return True


def proxima_vez_texto(cliente, entreno, nombre, tipo_progresion, porque_actual=None, con_efecto=False):
    """(texto, acción) de "la próxima vez" para el cierre, según la regla única.

    Usa el rango y el RPE que tuvo la sesión y lee esta sesión como "la última
    vez". Si el texto que ya había dice el mismo peso y las mismas reps, se
    queda (no se cambia por cambiar). Devuelve None si la regla no decide.
    """
    from datetime import timedelta as _td
    from entrenos.services.decision_log_service import _rpe_objetivo_snapshot, normalizar_ejercicio
    from entrenos.services.ultima_sesion_service import rango_de_sesion, ultima_sesion

    if tipo_progresion not in ('peso_reps', 'peso_corporal_lastre'):
        return None
    rango = rango_de_sesion(entreno, nombre)
    if not rango:
        return None
    ej = {
        'nombre': nombre,
        'repeticiones': f'{rango[0]}-{rango[1]}' if rango[1] != rango[0] else str(rango[0]),
        'rpe_objetivo': _rpe_objetivo_snapshot(entreno, normalizar_ejercicio(nombre)) or 8,
        'tipo_progresion': tipo_progresion,
    }
    siguiente = entreno.fecha + _td(days=1)
    lectura = ultima_sesion(cliente, nombre, siguiente, reps_min=rango[0])
    if not lectura or lectura['entreno'].pk != entreno.pk:
        return None
    from entrenos.models import EjercicioRealizado
    if EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, completado=True,
        entreno__fecha__gt=entreno.fecha,
    ).exists():
        return None  # ya hay una sesión posterior: este cierre es historia
    decision = decidir_carga(cliente, ej, siguiente)
    if not decision:
        return None
    peso, reps, regla = decision['peso'], decision['reps'], decision['regla']
    peso_hoy = float(lectura['referencia']['peso'])
    if regla == 'fatiga' and decision.get('tipo_fatiga') == 'contexto':
        texto = (f"La próxima vez repetimos {_kg(peso)} kg a por {reps} reps: la primera serie entró "
                 f"({_kg(peso)} × {decision['reps_antes']}) y la caída a {decision['reps_hoy']} fue porque "
                 f"{decision['motivo']}.")
        return (texto, 'Mantener', f'Repite {_kg(peso)} kg') if con_efecto else (texto, 'Mantener')
    if regla == 'volver':
        texto = f'Vuelvo a {_kg(peso)} kg a por {reps} reps: con {_kg(peso_hoy)} kg te sobró y {_kg(peso)} ya te entró.'
        return (texto, 'Subir peso', f'Vuelve a {_kg(peso)} kg') if con_efecto else (texto, 'Subir peso')
    if regla == 'fatiga' and decision.get('tipo_fatiga') == 'sesion':
        texto = (f"La próxima vez repetimos {_kg(peso)} kg a por {reps} reps: la primera serie entró "
                 f"({_kg(peso)} × {decision['reps_antes']}) y luego se hundió a {decision['reps_hoy']}; "
                 f"fue cansancio, no el peso.")
        return (texto, 'Mantener', f'Repite {_kg(peso)} kg') if con_efecto else (texto, 'Mantener')
    if regla == 'fatiga':
        texto = (f"La próxima vez repetimos {_kg(peso)} kg a por {reps} reps: hoy llegabas muy cansado "
                 f"(antes hacías {_kg(peso)} × {decision['reps_antes']}).")
        return (texto, 'Mantener', f'Repite {_kg(peso)} kg') if con_efecto else (texto, 'Mantener')
    if regla == 'tope':
        texto = f'{_kg(peso)} kg es el máximo de la máquina: la próxima vez a por {reps} reps.'
        accion = 'Subir repeticiones'
        efecto = f'A por {reps} reps'
    elif peso < peso_hoy - 1e-6:
        texto = f'La próxima vez {_kg(peso)} kg a por {reps} reps, para que entren todas las series en {ej["repeticiones"]}.'
        accion = 'Bajar peso'
        efecto = f'Bajará a {_kg(peso)} kg'
    elif peso > peso_hoy + 1e-6:
        texto = f'Subo a {_kg(peso)} kg y vuelvo a {reps} reps.'
        accion = 'Subir peso'
        efecto = f'Subirá a {_kg(peso)} kg'
    else:
        texto = (f'Mantengo {_kg(peso)} kg: la próxima vez a por {reps} reps. '
                 f'Con {rango[1]} en todas las series, subo el peso.')
        accion = 'Mantener'
        efecto = f'A por {reps} reps'
    if porque_actual and f'{_kg(peso)} kg' in porque_actual and (
        f'{reps} reps' in porque_actual or regla in ('bajar', 'subir')
    ):
        texto = porque_actual
    # 25-oct-2026: la etiqueta sale de la misma decisión (antes, "Reducirá la
    # carga un 10 %" del registro antiguo cuando bajaba de 50 a 35 kg).
    return (texto, accion, efecto) if con_efecto else (texto, accion)
