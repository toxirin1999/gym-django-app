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


def decidir_carga(cliente, ej, hoy):
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
    peso = _a_escala_empate_arriba(float(techo), salto)
    mismo = abs(peso - peso_ref) < salto / 2
    reps = objetivo_reps_hoy(ref['reps'], rango, mismo and ref['en_rango'])
    return {'peso': peso, 'reps': reps, 'regla': 'mantener' if mismo else 'ajustar', 'frase': frase}


def aplicar_decision_carga(ej, decision):
    """Impone la decisión de la regla única en un ejercicio del plan de hoy.

    Solo toca lo que cambia: si el plan ya decía ese peso y esas reps, se
    queda con su texto. Devuelve True si cambió algo.
    """
    try:
        peso_actual = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        peso_actual = 0.0
    reps_actuales = ej.get('reps_objetivo_hoy')
    if decision['regla'] == 'tope':
        reps_actuales = ej.get('reps_sugeridas_tope') or reps_actuales
    if abs(peso_actual - decision['peso']) < 0.01 and str(reps_actuales) == str(decision['reps']):
        return False
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
