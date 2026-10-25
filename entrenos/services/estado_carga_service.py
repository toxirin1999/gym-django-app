"""Estado de carga: un solo cálculo de cómo responde tu cuerpo a lo que entrenas.

25-oct-2026, paso 1 del panel «Cómo responde tu cuerpo» (a la sombra: de
momento no cambia nada de la app; lo lee el comando ``ver_estado_carga``).

Junta dos lecturas y contesta cada día una de estas respuestas:

- **Tu carga**: la suma de los últimos 7 días (esfuerzo × minutos de cada
  actividad: gimnasio, fútbol, Hyrox…) frente a tu semana normal, que es la
  media de las 4 semanas anteriores.
- **Tu cuerpo**: cómo amaneciste cada día según el reloj (variabilidad, pulso
  en reposo y sueño frente a tu media de 28 días, ``recuperacion_service``).

Respuestas (umbrales de partida, se ajustan viendo qué habrían dicho):

- ``parada``: has dicho que estás enfermo o de parada. No se juzga nada.
- ``descansa``: el cuerpo por debajo de lo normal en 3 de los últimos 5 días
  con dato, y la carga normal o alta.
- ``te_pasas``: la carga un 30 % o más por encima de tu semana normal y el
  cuerpo empezando a bajar (2 de los últimos 5 días).
- ``dar_mas``: el cuerpo normal o mejor en 10 de los últimos 14 días, la carga
  dentro de lo normal, el esfuerzo (RPE) estable o bajando y sin molestias.
- ``conociendote``: aún no hay datos del reloj suficientes (menos de 5 días).
- ``vas_bien``: nada de lo anterior.

Los días de una parada declarada no cuentan como días malos ni buenos.
"""

from datetime import timedelta

DIAS_AGUDA = 7
SEMANAS_NORMAL = 4
DESCANSA_MALOS, DESCANSA_VENTANA = 3, 5
PASAS_RATIO, PASAS_MALOS = 1.3, 2
DAR_MAS_BUENOS, DAR_MAS_VENTANA = 10, 14
DAR_MAS_RATIO = (0.8, 1.3)
MIN_DIAS_RELOJ = 5
DURACION_MAX_MIN = 240  # una "sesión" de más de 4 h es un cronómetro olvidado

NIVELES_MALOS = ('ambar', 'rojo')
NIVELES_BUENOS = ('verde', 'normal')

TITULOS = {
    'parada': 'De parada',
    'descansa': 'Descansa',
    'te_pasas': 'Te estás pasando',
    'dar_mas': 'Puedes dar más',
    'vas_bien': 'Vas bien',
    'conociendote': 'Te estoy conociendo',
}


# ── Piezas ──────────────────────────────────────────────────────────────────

def parada_en(cliente, dia):
    """La parada declarada que cubre ese día, o None."""
    from django.db.models import Q
    from entrenos.models import ParadaDeclarada

    return (
        ParadaDeclarada.objects.filter(cliente=cliente, inicio__lte=dia)
        .filter(Q(fin__isnull=True) | Q(fin__gte=dia))
        .order_by('-inicio').first()
    )


def _dias_en_parada(cliente, desde, hasta):
    from django.db.models import Q
    from entrenos.models import ParadaDeclarada

    dias = set()
    for p in ParadaDeclarada.objects.filter(cliente=cliente, inicio__lte=hasta).filter(
        Q(fin__isnull=True) | Q(fin__gte=desde)
    ):
        d = max(p.inicio, desde)
        fin = min(p.fin or hasta, hasta)
        while d <= fin:
            dias.add(d)
            d += timedelta(days=1)
    return dias


def carga_por_dia(cliente, desde, hasta):
    """{fecha: carga} con la carga de cada día (el día en que se hizo, no el del plan)."""
    from django.db.models.functions import Coalesce
    from entrenos.models import ActividadRealizada

    por_dia = {}
    for a in (
        ActividadRealizada.objects.filter(cliente=cliente, carga_ua__isnull=False)
        .annotate(fecha_carga=Coalesce('fecha_realizado', 'fecha'))
        .filter(fecha_carga__gte=desde, fecha_carga__lte=hasta)
        .values('fecha_carga', 'carga_ua', 'duracion_minutos')
    ):
        if (a['duracion_minutos'] or 0) > DURACION_MAX_MIN:
            continue
        por_dia[a['fecha_carga']] = por_dia.get(a['fecha_carga'], 0.0) + float(a['carga_ua'] or 0)
    return por_dia


def lectura_carga(cliente, hoy):
    """{'semana', 'normal', 'ratio'}: últimos 7 días frente a la media de las 4 semanas anteriores."""
    inicio_normal = hoy - timedelta(days=DIAS_AGUDA * (SEMANAS_NORMAL + 1) - 1)
    por_dia = carga_por_dia(cliente, inicio_normal, hoy)
    corte = hoy - timedelta(days=DIAS_AGUDA - 1)
    semana = sum(c for d, c in por_dia.items() if d >= corte)
    anteriores = sum(c for d, c in por_dia.items() if d < corte)
    normal = anteriores / SEMANAS_NORMAL
    return {
        'semana': round(semana),
        'normal': round(normal),
        'ratio': round(semana / normal, 2) if normal > 0 else None,
    }


def lectura_cuerpo(cliente, hoy):
    """Cómo amaneciste en los últimos 14 días: [{'fecha', 'nivel'}] (más reciente primero)."""
    from entrenos.services.recuperacion_service import lectura_recuperacion

    parada = _dias_en_parada(cliente, hoy - timedelta(days=DAR_MAS_VENTANA - 1), hoy)
    dias = []
    for i in range(DAR_MAS_VENTANA):
        d = hoy - timedelta(days=i)
        if d in parada:
            dias.append({'fecha': d.isoformat(), 'nivel': 'parada'})
            continue
        lectura = lectura_recuperacion(cliente, d)
        dias.append({'fecha': d.isoformat(), 'nivel': lectura['nivel'] if lectura else None})
    return dias


def _rpe_medio(cliente, desde, hasta):
    from django.db.models import Avg
    from entrenos.models import EjercicioRealizado

    return EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, completado=True, rpe__isnull=False,
        entreno__fecha__gte=desde, entreno__fecha__lte=hasta,
    ).aggregate(m=Avg('rpe'))['m']


def lectura_esfuerzo(cliente, hoy):
    """RPE medio de las últimas 2 semanas frente a las 2 anteriores."""
    ahora = _rpe_medio(cliente, hoy - timedelta(days=13), hoy)
    antes = _rpe_medio(cliente, hoy - timedelta(days=27), hoy - timedelta(days=14))
    return {
        'ahora': round(ahora, 1) if ahora is not None else None,
        'antes': round(antes, 1) if antes is not None else None,
        'subiendo': ahora is not None and antes is not None and ahora > antes + 0.3,
    }


def molestias_recientes(cliente, hoy):
    """Zonas con molestia marcada en el cierre en los últimos 14 días."""
    from entrenos.models import SensacionZonaGym

    return sorted(set(SensacionZonaGym.objects.filter(
        cliente=cliente, molestia__gte=1,
        entreno__fecha__gte=hoy - timedelta(days=13), entreno__fecha__lte=hoy,
    ).values_list('zona', flat=True)))


# ── El cálculo ─────────────────────────────────────────────────────────────

def _pct(ratio):
    return round((ratio - 1) * 100)


def estado_carga(cliente, hoy):
    """La lectura del día. Todo serializable (irá al panel y al snapshot)."""
    carga = lectura_carga(cliente, hoy)
    cuerpo = lectura_cuerpo(cliente, hoy)
    esfuerzo = lectura_esfuerzo(cliente, hoy)
    molestias = molestias_recientes(cliente, hoy)

    parada = parada_en(cliente, hoy)
    ultimos5 = [d['nivel'] for d in cuerpo[:DESCANSA_VENTANA] if d['nivel'] not in (None, 'parada')]
    ultimos14 = [d['nivel'] for d in cuerpo if d['nivel'] not in (None, 'parada')]
    malos5 = sum(1 for n in ultimos5 if n in NIVELES_MALOS)
    buenos14 = sum(1 for n in ultimos14 if n in NIVELES_BUENOS)
    ratio = carga['ratio']

    base = {'carga': carga, 'cuerpo': cuerpo, 'esfuerzo': esfuerzo, 'molestias': molestias,
            'malos_5': malos5, 'dias_5': len(ultimos5), 'buenos_14': buenos14, 'dias_14': len(ultimos14)}

    if parada:
        que = 'enfermo' if parada.tipo == parada.TIPO_ENFERMO else 'de parada'
        return {**base, 'respuesta': 'parada', 'frase': (
            f'Estás {que} desde el {parada.inicio:%d/%m}. Estos días no cuentan: ni como mala '
            f'recuperación ni como falta de constancia. Cuando vuelvas, empezamos suave.')}

    if len(ultimos14) < MIN_DIAS_RELOJ:
        frase = (f'Te estoy conociendo: llevo {len(ultimos14)} '
                 f'{"día" if len(ultimos14) == 1 else "días"} con datos del reloj y necesito '
                 f'{MIN_DIAS_RELOJ} para saber qué es lo normal en ti.')
        if ratio is not None:
            frase += f' Tu carga de esta semana va {_texto_ratio(ratio)}.'
        return {**base, 'respuesta': 'conociendote', 'frase': frase}

    if malos5 >= DESCANSA_MALOS and (ratio is None or ratio >= 0.8):
        return {**base, 'respuesta': 'descansa', 'frase': (
            f'Llevas {malos5} de los últimos {len(ultimos5)} días amaneciendo por debajo de lo normal '
            f'en ti, y la carga sigue {_texto_ratio(ratio) if ratio is not None else "como siempre"}. '
            f'Hoy descansa o haz algo suave: mañana rendirás más.')}

    if ratio is not None and ratio >= PASAS_RATIO and malos5 >= PASAS_MALOS:
        return {**base, 'respuesta': 'te_pasas', 'frase': (
            f'Esta semana llevas un {_pct(ratio)} % más de carga que en tus semanas normales y tu cuerpo '
            f'empieza a notarlo ({malos5} de los últimos {len(ultimos5)} días por debajo de lo normal). '
            f'Aflojamos un par de días.')}

    if (buenos14 >= DAR_MAS_BUENOS and ratio is not None
            and DAR_MAS_RATIO[0] <= ratio <= DAR_MAS_RATIO[1]
            and not esfuerzo['subiendo'] and not molestias):
        detalle = ''
        if esfuerzo['ahora'] is not None and esfuerzo['antes'] is not None:
            detalle = f' y tu esfuerzo medio va en {_n(esfuerzo["ahora"])} (antes {_n(esfuerzo["antes"])})'
        return {**base, 'respuesta': 'dar_mas', 'frase': (
            f'{buenos14} de los últimos {len(ultimos14)} días recuperándote bien, la carga en lo tuyo'
            f'{detalle}. Te veo para más: es buen momento para subir un poco el volumen.')}

    frase = 'Vas bien: tu cuerpo y tu carga están donde deben.'
    if ratio is not None:
        frase = f'Vas bien: carga {_texto_ratio(ratio)} y tu cuerpo respondiendo como siempre.'
    return {**base, 'respuesta': 'vas_bien', 'frase': frase}


def _n(x):
    return f'{x:.1f}'.replace('.', ',')


def _texto_ratio(ratio):
    pct = _pct(ratio)
    if abs(pct) < 10:
        return 'como en tus semanas normales'
    if pct > 0:
        return f'un {pct} % por encima de tus semanas normales'
    return f'un {-pct} % por debajo de tus semanas normales'


# ── Parada declarada ───────────────────────────────────────────────────────

def declarar_parada(cliente, tipo, hoy):
    """Abre una parada (o cambia el tipo de la abierta). Devuelve la parada."""
    from entrenos.models import ParadaDeclarada

    if tipo not in dict(ParadaDeclarada.TIPOS):
        raise ValueError('tipo no válido')
    abierta = ParadaDeclarada.objects.filter(cliente=cliente, fin__isnull=True).first()
    if abierta:
        abierta.tipo = tipo
        abierta.save(update_fields=['tipo'])
        return abierta
    return ParadaDeclarada.objects.create(cliente=cliente, tipo=tipo, inicio=hoy)


def terminar_parada(cliente, hoy):
    """Cierra la parada abierta: el último día de parada fue ayer (o hoy, si empezó hoy)."""
    from entrenos.models import ParadaDeclarada

    abierta = ParadaDeclarada.objects.filter(cliente=cliente, fin__isnull=True).first()
    if not abierta:
        return None
    if abierta.inicio >= hoy:  # marcada y desmarcada el mismo día: como si no hubiera pasado
        abierta.delete()
        return None
    abierta.fin = hoy - timedelta(days=1)
    abierta.save(update_fields=['fin'])
    return abierta
