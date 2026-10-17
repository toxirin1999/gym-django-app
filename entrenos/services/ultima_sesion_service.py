"""La última sesión de un ejercicio, leída desde sus series reales (13-oct-2026).

Antes, "la última vez" salía del resumen por ejercicio (``EjercicioRealizado``),
que guarda la **media** de las series: 62,5 + 60 + 60 + 60 kg se convertía en
"60,1 kg", una serie a RPE 10 y otra a RPE 7 en "RPE 8", y cada pantalla
(briefing, entrenamiento activo, cierre) acababa enseñando una "última vez"
distinta. Ese número, además, era la base del peso propuesto.

Aquí hay una sola lectura, desde las series de trabajo:

- **Serie de referencia**: la más pesada que llegó al mínimo del rango. Si
  ninguna llegó, la más pesada. Así una pirámide 15,5 / 18 / 20 × 12 deja
  20 × 12 como referencia, y 79 × 8 (corto) + 60 × 15 deja 60 × 15.
- **RPE de la referencia**: el de esas series, no la media de la sesión.
- **Intento por encima**: si hubo una serie más pesada que quedó por debajo
  del rango, se sabe (y se cita).

Y una regla de techo para el peso propuesto (``techo_peso``): nunca subir si
la última vez se quedó corto, bajar si se quedó muy corto, mantener si llegó
justo al mínimo con RPE alto, y como mucho un salto de máquina por sesión.
La regla solo baja o limita: nunca sube un peso.
"""

from datetime import timedelta
from decimal import Decimal

VENTANA_DIAS = 42          # más allá, la última sesión ya no sirve de techo
DEFICIT_PARA_BAJAR = 3     # reps por debajo del mínimo a partir de las que se baja peso
RPE_ALTO = 9


# ─────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────

def rango_reps(texto):
    """'12-15' → (12, 15); '16' → (16, 16); None si no es un rango de reps."""
    try:
        partes = [int(p.strip()) for p in str(texto).split('-') if p.strip()]
    except (TypeError, ValueError):
        return None
    if not partes:
        return None
    return partes[0], partes[-1]


def series_de_trabajo(entreno, nombre):
    """Series completadas (sin aproximaciones) del ejercicio en ese entreno."""
    from entrenos.models import SerieRealizada
    from entrenos.services.decision_log_service import normalizar_ejercicio

    clave = normalizar_ejercicio(nombre)
    return [
        {
            'peso': float(s.peso_kg or 0),
            'reps': int(s.repeticiones or 0),
            'rpe': float(s.rpe_real) if s.rpe_real is not None else None,
            'metros': float(s.distancia_metros) if s.distancia_metros is not None else None,
        }
        for s in SerieRealizada.objects.filter(
            entreno=entreno, completado=True, es_aproximacion=False,
        ).select_related('ejercicio').order_by('serie_numero', 'id')
        if normalizar_ejercicio(s.ejercicio.nombre) == clave
    ]


def serie_referencia(series, reps_min=None):
    """Lee unas series y devuelve la referencia (ver docstring del módulo).

    Devuelve None si no hay series con repeticiones, o un dict con:
    peso, reps (media a ese peso, Decimal), rpe (máx. a ese peso o None),
    en_rango (bool), superior (la serie más pesada que quedó corta, o None).
    """
    validas = [s for s in series if s['reps'] > 0]
    if not validas:
        return None
    en_rango = [s for s in validas if reps_min is None or s['reps'] >= reps_min]
    base = en_rango or validas
    peso_ref = max(s['peso'] for s in base)
    a_ese_peso = [s for s in base if s['peso'] == peso_ref]
    reps = sum(Decimal(s['reps']) for s in a_ese_peso) / Decimal(len(a_ese_peso))
    rpes = [s['rpe'] for s in a_ese_peso if s['rpe'] is not None]
    superiores = [s for s in validas if s['peso'] > peso_ref]
    superior = max(superiores, key=lambda s: s['peso']) if superiores else None
    return {
        'peso': peso_ref,
        'reps': reps,
        'rpe': max(rpes) if rpes else None,
        'en_rango': bool(en_rango),
        'superior': superior,
    }


def rango_de_sesion(entreno, nombre):
    """Rango de reps que se prescribió en esa sesión (snapshot), o None."""
    from entrenos.services.decision_log_service import normalizar_ejercicio

    version = getattr(entreno, 'gym_decision_version', None)
    snapshot = getattr(version, 'snapshot', None) or {}
    clave = normalizar_ejercicio(nombre)
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) == clave:
            return rango_reps(ej.get('repeticiones'))
    return None


def ultima_sesion(cliente, nombre, antes_de, reps_min=None):
    """La última sesión del ejercicio antes de ``antes_de`` (fecha), con su referencia.

    ``reps_min``: mínimo del rango con el que se lee la referencia. Si no se
    pasa, se usa el rango que se prescribió en esa sesión.
    Devuelve None si no hay sesión con series registradas.
    """
    from entrenos.models import EjercicioRealizado

    for ej in (
        EjercicioRealizado.objects.filter(
            entreno__cliente=cliente, nombre_ejercicio__iexact=nombre,
            completado=True, entreno__fecha__lt=antes_de,
        ).select_related('entreno').order_by('-entreno__fecha', '-entreno_id')[:3]
    ):
        series = series_de_trabajo(ej.entreno, nombre)
        if not series:
            continue
        minimo = reps_min
        if minimo is None:
            rango = rango_de_sesion(ej.entreno, nombre)
            minimo = rango[0] if rango else None
        ref = serie_referencia(series, minimo)
        if ref is None:
            continue
        return {
            'entreno': ej.entreno,
            'fecha': ej.entreno.fecha,
            'series': series,
            'referencia': ref,
            'es_tope_maquina': ej.es_tope_maquina,
        }
    return None


# ─────────────────────────────────────────────────────────────
# Techo para el peso propuesto
# ─────────────────────────────────────────────────────────────

def kg(valor):
    texto = f'{float(valor):.2f}'.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def reps_txt(valor):
    return kg(valor)


def peso_para_reps(peso, reps, rpe, reps_objetivo, rpe_objetivo):
    """Peso con el que se harían ``reps_objetivo`` a ``rpe_objetivo`` (Epley + RIR)."""
    from analytics.utils import estimar_1rm_con_rpe

    e1rm = estimar_1rm_con_rpe(float(peso), int(reps), float(rpe or 9))
    if not e1rm:
        return None
    reps_al_fallo = reps_objetivo + max(0.0, 10 - float(rpe_objetivo or 8))
    return e1rm / (1 + reps_al_fallo / 30)


def _redondear_abajo(valor, incremento):
    import math
    incremento = float(incremento or 2.5)
    # Tolerancia pequeña: el e1RM viene redondeado (19,998 kg debe ser 20).
    return round(math.floor(valor / incremento + 0.02) * incremento, 2)


def techo_peso(lectura, rango_hoy, rpe_objetivo, incremento):
    """Peso máximo razonable para hoy según la última sesión real.

    Devuelve (techo_kg, frase, accion) o None si la última sesión no limita.
    ``accion``: 'bajar' (hoy menos que la referencia) o 'mantener'.
    """
    if not lectura or not rango_hoy:
        return None
    ref = lectura['referencia']
    peso, reps, rpe = ref['peso'], ref['reps'], ref['rpe']
    if peso <= 0:
        return None
    minimo, maximo = rango_hoy
    rango_txt = f'{minimo}-{maximo}' if maximo != minimo else f'{minimo}'
    incremento = float(incremento or 2.5)

    if not ref['en_rango']:
        deficit = minimo - reps
        if deficit >= DEFICIT_PARA_BAJAR:
            objetivo = peso_para_reps(peso, int(reps), rpe, minimo, rpe_objetivo)
            if objetivo:
                techo = min(_redondear_abajo(objetivo, incremento), peso - incremento)
                if techo > 0:
                    return (
                        techo,
                        f'La última vez {kg(peso)} kg × {reps_txt(reps)}; '
                        f'para {rango_txt}, hoy {kg(techo)} kg.',
                        'bajar',
                    )
        return (
            peso,
            f'La última vez {kg(peso)} kg × {reps_txt(reps)}: mantengo el peso '
            f'hasta llegar a {minimo}.',
            'mantener',
        )

    superior = ref['superior']
    if superior:
        # 17-oct-2026: si después de la serie pesada se bajó el peso (back-off),
        # la serie ligera llega cansada y subestima. La pesada también dice
        # algo: con ella se estima el peso para el rango de hoy, sin pasar
        # nunca de esa serie pesada (menos un salto) ni bajar de la que entró.
        estimado = peso_para_reps(
            superior['peso'], int(superior['reps']), superior.get('rpe'), minimo, rpe_objetivo,
        ) if superior['reps'] > 0 else None
        if estimado:
            propuesto = min(_redondear_abajo(estimado, incremento), superior['peso'] - incremento)
            if propuesto > peso:
                return (
                    propuesto,
                    f'La última vez {kg(superior["peso"])} kg × {superior["reps"]} y después '
                    f'{kg(peso)} kg × {reps_txt(reps)}; para {rango_txt}, hoy {kg(propuesto)} kg.',
                    'mantener',
                )
        return (
            peso,
            f'La última vez {kg(superior["peso"])} kg se quedó en {superior["reps"]} reps '
            f'y {kg(peso)} kg × {reps_txt(reps)} sí entró en {rango_txt}: hoy {kg(peso)} kg.',
            'mantener',
        )
    if reps <= minimo and rpe is not None and rpe >= RPE_ALTO:
        return (
            peso,
            f'La última vez {kg(peso)} kg × {reps_txt(reps)} a RPE {kg(rpe)}: '
            f'mantengo hasta que salga con margen.',
            'mantener',
        )
    return (peso + incremento, None, 'mantener')


def aplicar_techo(cliente, ej, hoy):
    """Limita el peso de un ejercicio del plan con su última sesión real.

    Modifica ``ej`` si el peso propuesto supera el techo. Devuelve un dict de
    cambio (para la lista de cambios del plan) o None.
    """
    tipo = ej.get('tipo_progresion') or 'peso_reps'
    if tipo not in ('peso_reps', 'peso_corporal_lastre'):
        return None
    try:
        propuesto = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        return None
    if propuesto <= 0:
        return None
    rango_hoy = rango_reps(ej.get('repeticiones'))
    if not rango_hoy:
        return None
    nombre = ej.get('nombre') or ''
    lectura = ultima_sesion(cliente, nombre, hoy, reps_min=rango_hoy[0])
    if not lectura or (hoy - lectura['fecha']) > timedelta(days=VENTANA_DIAS):
        return None
    # Cambio de familia de estímulo (fuerza ↔ hipertrofia): lo resuelve el
    # cálculo por fase, no esta regla.
    from analytics.planificador_helms.calculo.compatibilidad_fase import son_rangos_compatibles
    if not son_rangos_compatibles(int(lectura['referencia']['reps']), ej.get('repeticiones')):
        return None

    from rutinas.models import EjercicioBase
    from entrenos.services.maquina_service import incremento_real
    base = EjercicioBase.objects.filter(nombre__iexact=nombre).first()
    incremento = incremento_real(cliente, nombre, float(base.incremento_fisico_kg) if base else 2.5)
    resultado = techo_peso(lectura, rango_hoy, ej.get('rpe_objetivo') or 8, incremento)
    if lectura.get('es_tope_maquina'):
        # La última vez se marcó tope: ese peso es el máximo de la máquina.
        pesos = [s['peso'] for s in lectura['series'] if s['peso'] > 0]
        if pesos:
            resultado = (
                max(pesos),
                f'La última vez marcaste tope en {kg(max(pesos))} kg: progreso por repeticiones.',
                'mantener',
            )
    if not resultado:
        return None
    techo, frase, accion = resultado
    if propuesto <= techo + 1e-6:
        return None

    ej['peso_kg_anterior'] = propuesto
    ej['peso_kg'] = techo
    if 'peso_recomendado_kg' in ej:
        ej['peso_recomendado_kg'] = techo
    ref_peso = lectura['referencia']['peso']
    if accion == 'bajar' or techo < ref_peso:
        ej['progresion_aplicada'] = True
        ej['progresion_pospuesta'] = False
        ej['progresion_accion'] = 'bajar_peso'
    else:
        ej['progresion_pospuesta'] = True
        ej['progresion_aplicada'] = False
        ej['progresion_accion'] = 'subir_peso'
    if frase:
        ej['progresion_motivo'] = frase
    else:
        ej['progresion_motivo'] = (
            f'Como mucho un salto de máquina por sesión: '
            f'de {kg(ref_peso)} a {kg(techo)} kg.'
        )
    ej['progresion_motivo_local'] = 'techo_ultima_sesion'
    ej.pop('motivo_peso', None)
    return {
        'tipo': 'progresion_aplicada' if ej['progresion_aplicada'] else 'progresion_pospuesta',
        'ejercicio_original': nombre,
        'ejercicio_nuevo': None,
        'accion': ej['progresion_accion'],
        'peso_sugerido': techo,
        'razon': ej['progresion_motivo'],
    }
