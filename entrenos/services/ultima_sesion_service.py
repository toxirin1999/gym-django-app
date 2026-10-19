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
    # 17-oct-2026: una serie posterior más ligera que se hundió por debajo
    # del rango (jalón 59,5 × 12 y después 55,5 × 8): la referencia no se
    # sostuvo en todas las series.
    caida = None
    if en_rango and reps_min is not None:
        ultima_ref = max(i for i, s in enumerate(validas) if s['peso'] == peso_ref and s['reps'] >= reps_min)
        caidas = [s for s in validas[ultima_ref + 1:] if s['peso'] < peso_ref and s['reps'] < reps_min]
        caida = caidas[-1] if caidas else None
    return {
        'peso': peso_ref,
        'reps': reps,
        'rpe': max(rpes) if rpes else None,
        'en_rango': bool(en_rango),
        'superior': superior,
        'caida': caida,
        'validas': validas,
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


def _a_por(reps, rango):
    """', a por 16 reps' cuando aún no se llega al tope del rango (regla C)."""
    objetivo = objetivo_reps_hoy(reps, rango)
    return f', a por {objetivo} reps' if objetivo and objetivo > int(round(float(reps))) else ''


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
            # 17-oct-2026: con todas las series, no solo la más pesada (Arnold
            # 40 × 9 y después 30 × 12: lo que entra en 15-20 lo dice el 30).
            otras = [s for s in (ref.get('validas') or []) if s['peso'] < peso and s['reps'] > 0]
            estimaciones = [peso_para_reps(peso, int(reps), rpe, minimo, rpe_objetivo)] + [
                peso_para_reps(s['peso'], int(s['reps']), s['rpe'], minimo, rpe_objetivo) for s in otras
            ]
            estimaciones = [e for e in estimaciones if e]
            if estimaciones:
                from entrenos.services.maquina_service import a_escala
                techo = a_escala(min(estimaciones), incremento)
                if techo >= peso:
                    techo = a_escala(peso - incremento, incremento, 'abajo')
                if techo > 0:
                    if otras:
                        ligera = min(otras, key=lambda s: s['peso'])
                        antes = (f'La última vez {kg(peso)} kg × {reps_txt(reps)} y '
                                 f'{kg(ligera["peso"])} kg × {ligera["reps"]}')
                    else:
                        antes = f'La última vez {kg(peso)} kg × {reps_txt(reps)}'
                    return (techo, f'{antes}; para {rango_txt}, hoy {kg(techo)} kg.', 'bajar')
        return (
            peso,
            f'La última vez {kg(peso)} kg × {reps_txt(reps)}: mantengo el peso '
            f'hasta llegar a {minimo}.',
            'mantener',
        )

    caida = ref.get('caida')
    if caida:
        from entrenos.services.maquina_service import a_escala
        techo = a_escala(peso - incremento, incremento)
        if 0 < techo < peso:
            return (
                techo,
                f'La última vez {kg(peso)} kg × {reps_txt(reps)}, pero después '
                f'{kg(caida["peso"])} kg × {caida["reps"]}: hoy {kg(techo)} kg para que '
                f'todas las series entren en {rango_txt}.',
                'bajar',
            )

    superior = ref['superior']
    if superior:
        # 17-oct-2026: si después de la serie pesada se bajó el peso (back-off),
        # la serie ligera llega cansada y subestima. La pesada también dice
        # algo: con ella se estima el peso para el rango de hoy, sin pasar
        # nunca de esa serie pesada (menos un salto) ni bajar de la que entró.
        # Solo si esa serie pesada no fue al fallo (RPE conocido y < 10): una
        # serie a RPE 10 por encima no debe tirar del peso (gemelos 79 × 8 @10).
        # 19-oct-2026: se estima con TODAS las series por encima de la que
        # entró y manda la más prudente. Extensiones en polea: 40 × 10 @9,
        # 35 × 10, 30 × 11 @8, 25 × 12 @8 y 20 × 15 @7 — con solo la de 40
        # salía 35 kg para 15-20, cuando 30 ya se quedó en 11.
        pesadas = [
            s for s in (ref.get('validas') or [superior])
            if s['peso'] > peso and s['reps'] > 0 and s.get('rpe') is not None and s['rpe'] < 10
        ]
        estimaciones = [
            e for e in (
                peso_para_reps(s['peso'], int(s['reps']), s['rpe'], minimo, rpe_objetivo) for s in pesadas
            ) if e
        ]
        estimado = min(estimaciones) if estimaciones else None
        cortas = [s for s in (ref.get('validas') or []) if s['peso'] > peso and s['reps'] < minimo]
        if estimado and cortas:
            # Nunca a la altura de una serie que ya se quedó corta del rango.
            estimado = min(estimado, min(s['peso'] for s in cortas) - 0.01)
        if estimado:
            # El salto de máquina se deduce de los pesos usados; con solo una
            # serie pesada y una ligera saldría enorme (45 − 26 = 19 kg).
            salto = min(incremento, 5.0)
            propuesto = min(_redondear_abajo(estimado, salto), superior['peso'] - salto)
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
            f'y {kg(peso)} kg × {reps_txt(reps)} sí entró en {rango_txt}: hoy {kg(peso)} kg'
            f'{_a_por(reps, rango_hoy)}.',
            'mantener',
        )
    if reps <= minimo and rpe is not None and rpe >= RPE_ALTO:
        return (
            peso,
            f'La última vez {kg(peso)} kg × {reps_txt(reps)} a RPE {kg(rpe)}: '
            f'mantengo hasta que salga con margen.',
            'mantener',
        )
    # 17-oct-2026 (regla C): primero las repeticiones, luego el peso.
    if reps < maximo:
        return (peso, texto_doble_progresion(reps, rango_hoy), 'mantener')
    return (peso + incremento, None, 'mantener')


def objetivo_reps_hoy(reps_ultima, rango, mismo_peso=True):
    """Regla C: con el mismo peso, una repetición más que la última vez, dentro del rango."""
    minimo, maximo = rango
    if not mismo_peso or reps_ultima is None:
        return minimo
    try:
        reps_ultima = int(round(float(reps_ultima)))
    except (TypeError, ValueError):
        return minimo
    return max(minimo, min(maximo, reps_ultima + 1))


def texto_doble_progresion(reps_ultima, rango):
    minimo, maximo = rango
    objetivo = objetivo_reps_hoy(reps_ultima, rango)
    return (
        f'Mismo peso: hoy a por {objetivo} reps (la última vez {reps_txt(reps_ultima)}); '
        f'con {maximo} en todas las series, sube la carga.'
    )


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

    from entrenos.services.maquina_service import salto_carga
    incremento = salto_carga(cliente, nombre)
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
    ref_peso = lectura['referencia']['peso']
    # 18-oct-2026 (regla C): si la última vez entró en el rango, hoy toca ese
    # mismo peso; el plan no baja sin motivo (gemelos 100 → 95, hip thrust).
    protegido = (
        ej.get('_deload_aplicado') or ej.get('deload') or ej.get('progresion_bloqueada')
        or ej.get('molestia_reciente_aplicada') or ej.get('postura_local') == 'sostener'
        or (ej.get('progresion_aplicada') and ej.get('progresion_accion') == 'bajar_peso')
        or str((ej.get('motivo_peso') or {}).get('tipo', '')).startswith('recalculado')
    )
    if (
        not protegido and accion == 'mantener' and lectura['referencia']['en_rango']
        and not lectura['referencia'].get('caida') and propuesto < ref_peso - 1e-6
        and techo >= ref_peso - 1e-6
    ):
        ej['peso_kg_anterior'] = propuesto
        ej['peso_kg'] = ref_peso
        if 'peso_recomendado_kg' in ej:
            ej['peso_recomendado_kg'] = ref_peso
        ej['progresion_pospuesta'] = True
        ej['progresion_aplicada'] = False
        ej['progresion_accion'] = 'subir_peso'
        ej['progresion_motivo'] = frase or texto_doble_progresion(
            lectura['referencia']['reps'], rango_hoy,
        )
        ej['progresion_motivo_local'] = 'techo_ultima_sesion'
        ej.pop('motivo_peso', None)
        return {
            'tipo': 'progresion_pospuesta', 'ejercicio_original': nombre, 'ejercicio_nuevo': None,
            'accion': 'subir_peso', 'peso_sugerido': ref_peso, 'razon': ej['progresion_motivo'],
        }
    if propuesto <= techo + 1e-6:
        # 17-oct-2026: si el plan ya propone justo ese peso, no hay que
        # corregir nada, pero el porqué sigue valiendo (curl femoral tras un
        # back-off salía sin explicación).
        if frase and abs(propuesto - techo) < 1e-6 and not ej.get('progresion_motivo'):
            ej['progresion_motivo'] = frase
            ej['progresion_motivo_local'] = 'techo_ultima_sesion'
        return None

    ej['peso_kg_anterior'] = propuesto
    ej['peso_kg'] = techo
    if 'peso_recomendado_kg' in ej:
        ej['peso_recomendado_kg'] = techo
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


def ajustar_escala_y_reps(cliente, ej, hoy):
    """Último paso del plan de hoy (17-oct-2026): peso en la escala real y reps de hoy.

    - El peso se lleva a la escala del equipo (máquina 5, discos 2,5,
      mancuernas 2,5 o 5 en total de dos). Si lo fijó el techo de la última
      sesión, se redondea hacia abajo: el techo es un máximo.
    - ``reps_objetivo_hoy``: regla C. Con el mismo peso que la última vez,
      una repetición más (dentro del rango); con otro peso, el mínimo.
      Briefing y ejercicio arrancan con este número.
    """
    from entrenos.services.maquina_service import a_escala, salto_carga, tope_de

    tipo = ej.get('tipo_progresion') or 'peso_reps'
    if tipo not in ('peso_reps', 'peso_corporal_lastre'):
        return
    nombre = ej.get('nombre') or ''
    # Ejercicios de estabilidad (antirrotación): se trata de no girar, no de
    # acercarse al fallo. RPE de la fase, como mucho 8.
    if any(t in nombre.casefold() for t in ('pallof', 'antirrot', 'anti-rot')):
        try:
            ej['rpe_objetivo'] = min(float(ej.get('rpe_objetivo') or 8), 8)
        except (TypeError, ValueError):
            ej['rpe_objetivo'] = 8
        if float(ej['rpe_objetivo']).is_integer():
            ej['rpe_objetivo'] = int(ej['rpe_objetivo'])
    salto = salto_carga(cliente, nombre)
    ej['incremento_kg'] = salto
    try:
        peso = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        peso = 0
    rango = rango_reps(ej.get('repeticiones'))
    lectura = ultima_sesion(cliente, nombre, hoy, reps_min=rango[0]) if rango else None
    if lectura and (hoy - lectura['fecha']) > timedelta(days=VENTANA_DIAS):
        lectura = None
    ref_peso = lectura['referencia']['peso'] if lectura else None
    # El mismo peso que usó la última vez no se toca: es el que hay en su gimnasio.
    mantiene = ej.get('progresion_motivo_local') == 'doble_progresion'
    # Solo se redondea a la escala de un equipo que se reconoce.
    from entrenos.services.maquina_service import salto_fisico
    from rutinas.models import EjercicioBase
    _base = EjercicioBase.objects.filter(nombre__iexact=nombre).first()
    equipo_conocido = salto_fisico(nombre, _base.equipo if _base else None) is not None
    if peso > 0 and equipo_conocido and not mantiene and not (ref_peso and abs(peso - ref_peso) < 0.01):
        hacia = 'abajo' if ej.get('progresion_motivo_local') == 'techo_ultima_sesion' else 'cerca'
        nuevo = a_escala(peso, salto, hacia)
        # Nunca por debajo de la serie que sí entró si el plan proponía más.
        if ref_peso and peso >= ref_peso and nuevo < ref_peso:
            nuevo = ref_peso
        tope = tope_de(cliente, nombre)
        if tope:
            nuevo = min(nuevo, float(tope))
        if abs(nuevo - peso) > 1e-6:
            ej['peso_kg'] = nuevo
            if 'peso_recomendado_kg' in ej:
                ej['peso_recomendado_kg'] = nuevo
            motivo = ej.get('progresion_motivo') or ''
            if motivo and kg(peso) in motivo:
                ej['progresion_motivo'] = motivo.replace(f'hoy {kg(peso)} kg', f'hoy {kg(nuevo)} kg')
        peso = nuevo

    if not rango or ej.get('sugerencia_tope'):
        return
    if not lectura:
        ej['reps_objetivo_hoy'] = rango[0]
        return
    ref = lectura['referencia']
    mismo_peso = peso > 0 and abs(peso - ref['peso']) < salto / 2
    ej['reps_objetivo_hoy'] = objetivo_reps_hoy(ref['reps'], rango, mismo_peso and ref['en_rango'])


def anotar_ultima_vez(cliente, ej, hoy):
    """19-oct-2026: el dato al lado de la propuesta, y un aviso solo si no cuadra.

    - ``ultima_vez_texto``: '13/10: 40 kg × 10 @9 · 35 kg × 10 @8 · …' para que
      la propuesta se vea junto a lo que la justifica.
    - ``aviso_coherencia``: solo cuando el peso de hoy es igual o mayor que uno
      con el que la última vez no se llegó al mínimo del rango. En silencio
      cuando todo cuadra (es una red de seguridad, no un visto bueno).
    """
    from entrenos.services.cierre_porque_service import texto_series

    nombre = ej.get('nombre') or ''
    tipo = ej.get('tipo_progresion') or 'peso_reps'
    rango = rango_reps(ej.get('repeticiones'))
    lectura = ultima_sesion(cliente, nombre, hoy, reps_min=rango[0] if rango else None)
    if not lectura or (hoy - lectura['fecha']) > timedelta(days=VENTANA_DIAS):
        return
    texto = texto_series(lectura['entreno'], nombre, tipo)
    if texto:
        ej['ultima_vez_texto'] = f"{lectura['fecha']:%d/%m}: {texto}"

    if tipo not in ('peso_reps', 'peso_corporal_lastre') or not rango or ej.get('sugerencia_tope'):
        return
    try:
        peso = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        return
    if peso <= 0:
        return
    cortas = [
        s for s in lectura['series']
        # Una rep menos es justo la progresión que se pide hoy (regla C: 15 → 16
        # con el mismo peso); el aviso es para faltas de 2 o más.
        if 0 < s['peso'] <= peso + 1e-6 and 0 < s['reps'] <= rango[0] - 2 and s.get('metros') is None
    ]
    if not cortas:
        return
    ligera = min(cortas, key=lambda s: s['peso'])
    ej['aviso_coherencia'] = (
        f"Ojo: hoy {kg(peso)} kg, pero la última vez con {kg(ligera['peso'])} kg hiciste "
        f"{ligera['reps']} reps, por debajo de {rango[0]}. Si no llegas, baja el peso."
    )


def peso_contractual(ej):
    """El peso que enseña el briefing: con el mismo número arranca el ejercicio."""
    if ej.get('progresion_aplicada') or ej.get('progresion_pospuesta') or ej.get('progresion_bloqueada'):
        valor = ej.get('peso_kg')
    else:
        valor = ej.get('peso_recomendado_kg') or ej.get('peso_kg')
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0
