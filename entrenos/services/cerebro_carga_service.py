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
        peso = a_escala(estimado, salto, 'abajo')
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
