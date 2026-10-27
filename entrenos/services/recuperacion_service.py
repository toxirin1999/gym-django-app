"""Cómo llegas hoy: recuperación desde el reloj y esfuerzo del fútbol desde Strava.

24-oct-2026, paso 4 del informe ("acercar la app a Whoop/Bevel", a la manera
de esta app). Dos lecturas, cada una con su frase de entrenador:

1. ``lectura_recuperacion`` — el Atajo del iPhone deja cada mañana en el
   check-in (``BitacoraDiaria``) la variabilidad cardiaca (HRV), el pulso en
   reposo y las horas de sueño. Se comparan con TU media de los 28 días
   anteriores, no con tablas:

   - variabilidad un 15 % o más por debajo de tu media → señal de cansancio;
   - pulso en reposo 5 pulsaciones o más por encima de tu media → señal;
   - menos de 6 h de sueño (o 1 h 15 menos que tu media) → señal.

   Dos señales (o la variabilidad muy hundida, −25 %) = ``rojo``: versión
   reducida. Una = ``ambar``: se entrena igual y se avisa. Ninguna y datos de
   hoy = ``verde``.

2. ``esfuerzo_futbol`` — el fútbol de las últimas 48 h, con lo que trae
   Strava (duración, pulso medio, "esfuerzo relativo"), comparado con tus
   partidos de los últimos 120 días. Un partido suave no rebaja la pierna.

La voz es la de un entrenador: frases sencillas, el estado claro ("hoy vas
justo", "estás fresco") y el dato dicho en palabras normales. Si no hay
dato, no hay frase.
"""

from datetime import timedelta
from statistics import median

VENTANA_BASE_DIAS = 28
MIN_DIAS_BASE = 5
HRV_BAJO = 0.15          # −15 % de tu media
HRV_MUY_BAJO = 0.25      # −25 %: por sí sola ya es rojo
PULSO_ALTO_LPM = 5
SUENO_MINIMO_H = 6.0
SUENO_MENOS_QUE_MEDIA_H = 1.25

FUTBOL_VENTANA_DIAS = 120
FUTBOL_MIN_PARTIDOS = 3


# ── Utilidades de texto ──────────────────────────────────────────────────────

def horas_texto(horas):
    """7.5 → '7 h 30'; 6.0 → '6 h'."""
    total = int(round(float(horas) * 60))
    h, m = divmod(total, 60)
    return f'{h} h {m:02d}' if m else f'{h} h'


def _f(valor):
    try:
        return None if valor is None else float(valor)
    except (TypeError, ValueError):
        return None


# ── 1. Recuperación (reloj) ──────────────────────────────────────────────────

def _medias_base(cliente, hoy):
    from clientes.models import BitacoraDiaria

    filas = BitacoraDiaria.objects.filter(
        cliente=cliente, fecha__lt=hoy, fecha__gte=hoy - timedelta(days=VENTANA_BASE_DIAS),
    ).values('fecha', 'hrv_ms', 'fc_reposo', 'horas_sueno')
    por_campo = {'hrv_ms': {}, 'fc_reposo': {}, 'horas_sueno': {}}
    for fila in filas:  # una por día (si hubiera dos, vale la última)
        # 26-oct-2026: solo los días con datos del reloj (variabilidad o pulso).
        # El sueño apuntado a mano en check-ins antiguos daba una "media" de
        # 8 h 07 cuando el reloj solo llevaba dos noches; el panel decía a la
        # vez "te estoy conociendo".
        if not (_f(fila['hrv_ms']) or _f(fila['fc_reposo'])):
            continue
        for campo in por_campo:
            v = _f(fila[campo])
            if v:
                por_campo[campo][fila['fecha']] = v
    medias = {}
    for campo, valores in por_campo.items():
        if len(valores) >= MIN_DIAS_BASE:
            medias[campo] = sum(valores.values()) / len(valores)
    return medias


def _datos_hoy(cliente, hoy):
    from clientes.models import BitacoraDiaria

    datos = {}
    for fila in BitacoraDiaria.objects.filter(cliente=cliente, fecha=hoy).order_by('pk'):
        for campo in ('hrv_ms', 'fc_reposo', 'horas_sueno', 'energia_subjetiva'):
            v = _f(getattr(fila, campo, None))
            if v is not None:
                datos[campo] = v
    return datos


def lectura_recuperacion(cliente, hoy):
    """{'nivel', 'frase', 'senales', 'datos', 'medias'} o None si hoy no hay datos del reloj.

    Todo lo que devuelve es serializable (va al snapshot de la decisión).
    """
    hoy_datos = _datos_hoy(cliente, hoy)
    if not any(k in hoy_datos for k in ('hrv_ms', 'fc_reposo', 'horas_sueno')):
        return None
    medias = _medias_base(cliente, hoy)

    senales = []          # cada una: {'tipo', 'texto'}
    buenas = []
    hrv, media_hrv = hoy_datos.get('hrv_ms'), medias.get('hrv_ms')
    hrv_muy_baja = False
    if hrv and media_hrv:
        caida = (media_hrv - hrv) / media_hrv
        pct = round(abs(caida) * 100)
        if caida >= HRV_BAJO:
            hrv_muy_baja = caida >= HRV_MUY_BAJO
            senales.append({'tipo': 'hrv', 'texto': (
                f'el reloj dice que tu cuerpo aún no se ha recuperado del todo '
                f'(tu variabilidad cardiaca está un {pct} % por debajo de lo normal en ti)')})
        elif caida <= -0.05:
            buenas.append('el reloj te ve bien recuperado')

    fc, media_fc = hoy_datos.get('fc_reposo'), medias.get('fc_reposo')
    if fc and media_fc:
        diferencia = round(fc - media_fc)
        if diferencia >= PULSO_ALTO_LPM:
            senales.append({'tipo': 'pulso', 'texto': (
                f'tu pulso en reposo está {diferencia} pulsaciones más alto de lo habitual '
                f'({int(fc)} frente a {round(media_fc)})')})
        elif diferencia <= -2:
            buenas.append('tienes el pulso en reposo tranquilo')

    sueno, media_sueno = hoy_datos.get('horas_sueno'), medias.get('horas_sueno')
    if sueno:
        corto = sueno < SUENO_MINIMO_H or (media_sueno and sueno <= media_sueno - SUENO_MENOS_QUE_MEDIA_H)
        if corto:
            if media_sueno and sueno <= media_sueno - SUENO_MENOS_QUE_MEDIA_H:
                texto = f'has dormido {horas_texto(sueno)}, bastante menos de lo que sueles ({horas_texto(media_sueno)})'
            else:
                texto = f'has dormido solo {horas_texto(sueno)}'
            senales.append({'tipo': 'sueno', 'texto': texto})
        elif sueno >= 7:
            buenas.append(f'has dormido {horas_texto(sueno)}')

    if len(senales) >= 2 or hrv_muy_baja:
        nivel = 'rojo'
    elif senales:
        nivel = 'ambar'
    elif buenas and medias:
        # 27-oct-2026: sin media no hay "fresco". El 27 salía en verde solo por
        # dormir 7 h 52, con la variabilidad en 32 ms (55 y 81 los días antes).
        nivel = 'verde'
    elif medias:
        nivel = 'normal'  # 25-oct-2026: hay media y nada se sale de lo normal en ti
    else:
        nivel = 'sin_referencia'  # hay datos, pero aún no hay media para compararlos

    return {
        'nivel': nivel,
        'senales': [s['tipo'] for s in senales],
        'frase': _frase_recuperacion(nivel, senales, buenas, hoy_datos),
        'datos': {k: v for k, v in hoy_datos.items()},
        'medias': {k: round(v, 1) for k, v in medias.items()},
    }


def _unir(partes):
    if len(partes) <= 1:
        return ''.join(partes)
    return ', '.join(partes[:-1]) + ' y ' + partes[-1]


def _frase_recuperacion(nivel, senales, buenas, datos):
    textos = [s['texto'] for s in senales]
    if nivel == 'rojo':
        return (f'Hoy vas justo: {_unir(textos)}. Entrenamos, pero los principales sin apretar '
                f'y los accesorios quedan para otro día. Hoy sumar es descansar bien.')
    if nivel == 'ambar':
        # 26-oct-2026: también lo bueno (el 26 dormiste poco, pero la variabilidad
        # era la mejor de la semana y la frase solo hablaba del sueño).
        bueno = f' Lo bueno: {_unir(buenas)}.' if buenas else ''
        return (f'Hoy no estás al cien: {textos[0]}.{bueno} Entrenamos normal; si en la primera serie '
                f'notas que no tira, quita una repetición y no pasa nada.')
    if nivel == 'verde':
        return f'Hoy estás fresco: {_unir(buenas)}. Día para apretar.'
    if nivel == 'normal':
        return 'Llegas como siempre: ni el sueño, ni el pulso, ni la variabilidad se salen de lo normal en ti.'
    if datos.get('horas_sueno'):
        return (f'Has dormido {horas_texto(datos["horas_sueno"])}. En unos días tendré tu media '
                f'y te podré decir cómo llegas comparado con lo normal en ti.')
    return None


# ── 2. Esfuerzo del fútbol (Strava) ──────────────────────────────────────────

def _datos_partido(act):
    """{'fecha', 'minutos', 'pulso_medio', 'esfuerzo'} de una ActividadRealizada de fútbol."""
    raw = {}
    try:
        fuente = act.strava_source
        raw = getattr(fuente, 'raw_json', None) or {}
        if isinstance(raw, str):  # algunas filas antiguas lo guardan como texto
            import json
            raw = json.loads(raw)
    except Exception:  # noqa: BLE001 — sin Strava vinculado
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    minutos = act.duracion_minutos or (round((raw.get('moving_time') or 0) / 60) or None)
    pulso = act.hr_media or (round(raw['average_heartrate']) if raw.get('average_heartrate') else None)
    esfuerzo = raw.get('suffer_score') or raw.get('relative_effort')
    try:
        esfuerzo = float(esfuerzo) if esfuerzo else None
    except (TypeError, ValueError):
        esfuerzo = None
    return {
        'fecha': (act.fecha_realizado or act.fecha).isoformat(),
        'minutos': int(minutos) if minutos else None,
        'pulso_medio': int(pulso) if pulso else None,
        'esfuerzo': esfuerzo,
    }


def _carga(p):
    """Esfuerzo relativo de Strava si está; si no, minutos × pulso (comparable entre partidos)."""
    if p.get('esfuerzo'):
        return ('esfuerzo', p['esfuerzo'])
    if p.get('minutos') and p.get('pulso_medio'):
        return ('min_pulso', p['minutos'] * p['pulso_medio'])
    return (None, None)


def esfuerzo_futbol(cliente, hoy):
    """Lectura del fútbol de ayer o anteayer, o None si no hubo.

    {'nivel': 'alto'|'normal'|'suave'|'sin_datos', 'frase', 'partido'}.
    """
    from entrenos.models import ActividadRealizada

    def _fecha_real(a):
        return a.fecha_realizado or a.fecha

    recientes = [
        a for a in ActividadRealizada.objects.filter(
            cliente=cliente, tipo='futbol',
            fecha__gte=hoy - timedelta(days=FUTBOL_VENTANA_DIAS), fecha__lte=hoy,
        ).order_by('fecha', 'id')
    ]
    ultimos = [a for a in recientes if hoy - timedelta(days=2) <= _fecha_real(a) < hoy]
    if not ultimos:
        return None
    act = max(ultimos, key=lambda a: (_fecha_real(a), a.id))
    partido = _datos_partido(act)
    cuando = 'Ayer' if _fecha_real(act) == hoy - timedelta(days=1) else 'Anteayer'

    tipo, carga = _carga(partido)
    previas = []
    for a in recientes:
        if a.id == act.id or _fecha_real(a) >= _fecha_real(act):
            continue
        t, c = _carga(_datos_partido(a))
        if t == tipo and c:
            previas.append(c)

    detalle = []
    if partido['minutos']:
        detalle.append(f"{partido['minutos']} min")
    if partido['pulso_medio']:
        detalle.append(f"pulso medio {partido['pulso_medio']}")
    detalle_txt = f" ({', '.join(detalle)})" if detalle else ''

    if carga is None or len(previas) < FUTBOL_MIN_PARTIDOS:
        nivel = 'sin_datos'
        if partido['minutos'] and partido['minutos'] < 40:
            nivel = 'suave'
            frase = (f'{cuando} jugaste un rato corto de fútbol{detalle_txt}. '
                     f'Las piernas están bien: hoy pierna normal.')
        else:
            frase = (f'{cuando} jugaste al fútbol{detalle_txt}. Tus piernas ya han trabajado: '
                     f'hoy pierna en versión suave.')
        return {'nivel': nivel, 'frase': frase, 'partido': partido}

    referencia = median(previas)
    ratio = carga / referencia if referencia else 1
    if ratio >= 1.2:
        nivel = 'alto'
        frase = (f'{cuando} el fútbol fue de los duros para ti{detalle_txt}, '
                 f'más que un partido normal tuyo. Las piernas aún lo notan: hoy pierna en versión suave.')
    elif ratio <= 0.6:
        nivel = 'suave'
        frase = (f'{cuando} el fútbol fue tranquilo{detalle_txt}, bastante menos que un partido normal tuyo. '
                 f'Las piernas están bien: hoy pierna normal.')
    else:
        nivel = 'normal'
        frase = (f'{cuando} jugaste un partido normal para ti{detalle_txt}. '
                 f'Tus piernas ya han trabajado: hoy pierna en versión suave.')
    partido['comparado_con'] = round(referencia, 1)
    return {'nivel': nivel, 'frase': frase, 'partido': partido}


# ── 3. Comprobar si acertó (cierre) ──────────────────────────────────────────

def comprobacion_cierre(cliente, entreno):
    """Si la sesión se rebajó por recuperación o fútbol: ¿cómo te fue? Frase o None.

    Compara el esfuerzo medio (RPE) de hoy con el de tus sesiones de las 4
    semanas anteriores.
    """
    from django.db.models import Avg

    from entrenos.models import EjercicioRealizado

    version = getattr(entreno, 'gym_decision_version', None)
    snapshot = getattr(version, 'snapshot', None) or {}
    causa = snapshot.get('causa_principal')
    if causa not in ('recuperacion_baja', 'futbol_reciente'):
        return None
    rpe_hoy = EjercicioRealizado.objects.filter(
        entreno=entreno, completado=True, rpe__isnull=False,
    ).aggregate(m=Avg('rpe'))['m']
    rpe_antes = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, completado=True, rpe__isnull=False,
        entreno__fecha__lt=entreno.fecha, entreno__fecha__gte=entreno.fecha - timedelta(days=28),
    ).aggregate(m=Avg('rpe'))['m']
    if rpe_hoy is None or rpe_antes is None:
        return None
    motivo = 'llegabas cansado' if causa == 'recuperacion_baja' else 'venías del fútbol'
    hoy_txt = f'{rpe_hoy:.1f}'.replace('.', ',')
    antes_txt = f'{rpe_antes:.1f}'.replace('.', ',')
    if rpe_hoy >= rpe_antes + 0.5:
        return (f'Hoy te bajé la sesión porque {motivo}, y aun así te costó más de lo normal '
                f'(esfuerzo {hoy_txt} sobre 10; sueles estar en {antes_txt}). Bien hecho no forzar: '
                f'mañana descansa bien.')
    return (f'Hoy te bajé la sesión porque {motivo}. Te costó lo normal (esfuerzo {hoy_txt} sobre 10, '
            f'como tus {antes_txt} de siempre): la rebaja fue justa y no pierdes nada.')
