"""Panel «Cómo responde tu cuerpo» (25-oct-2026, paso 2).

Todo lo que pinta la página sale de aquí, ya calculado: la respuesta del día
(``estado_carga_service``), las tres preguntas, el camino de 30 días (carga de
7 días frente a tu franja normal) y la variabilidad de cada mañana. La página
solo dibuja; no decide nada.
"""

from datetime import timedelta

DIAS_CAMINO = 30
ANCHO, ALTO = 340, 170
MARGEN_IZQ, MARGEN_DER, MARGEN_ARR, MARGEN_ABA = 8, 8, 16, 22
FRANJA = (0.8, 1.3)  # tu zona normal: de un 20 % menos a un 30 % más que tu semana normal

LETRAS_DIA = ('L', 'M', 'X', 'J', 'V', 'S', 'D')
NOMBRES_NIVEL = {
    'rojo': 'Por debajo', 'ambar': 'Algo por debajo', 'verde': 'Fresco', 'normal': 'Normal',
    'sin_referencia': 'Sin media aún', 'parada': 'De parada', None: 'Sin dato',
}


def _x(i, n):
    util = ANCHO - MARGEN_IZQ - MARGEN_DER
    return round(MARGEN_IZQ + (util * i / (n - 1) if n > 1 else util / 2), 1)


def _y(valor, tope, suelo=0):
    util = ALTO - MARGEN_ARR - MARGEN_ABA
    rango = tope - suelo
    return round(MARGEN_ARR + util * (1 - ((valor - suelo) / rango if rango else 0)), 1)


def camino(cliente, hoy, dias=DIAS_CAMINO):
    """Puntos del gráfico: carga de 7 días y franja normal, día a día."""
    from entrenos.services.estado_carga_service import lectura_carga

    serie = []
    for i in range(dias - 1, -1, -1):
        d = hoy - timedelta(days=i)
        c = lectura_carga(cliente, d)
        serie.append({'fecha': d, 'semana': c['semana'], 'normal': c['normal']})
    tope = max([s['semana'] for s in serie] + [s['normal'] * FRANJA[1] for s in serie] + [1]) * 1.08
    n = len(serie)
    arriba = [(_x(i, n), _y(s['normal'] * FRANJA[1], tope)) for i, s in enumerate(serie)]
    abajo = [(_x(i, n), _y(s['normal'] * FRANJA[0], tope)) for i, s in enumerate(serie)]
    franja = ' '.join(f'{x},{y}' for x, y in arriba + list(reversed(abajo)))
    linea = ' '.join(f'{_x(i, n)},{_y(s["semana"], tope)}' for i, s in enumerate(serie))
    ultimo = serie[-1]
    marcas = [
        {'x': _x(i, n), 'texto': f'{s["fecha"]:%d/%m}'}
        for i, s in enumerate(serie) if i in (0, n // 2, n - 1)
    ]
    hay_carga = any(s['semana'] for s in serie)
    return {
        'franja': franja, 'linea': linea, 'marcas': marcas, 'hay_carga': hay_carga,
        'hoy_x': _x(n - 1, n), 'hoy_y': _y(ultimo['semana'], tope),
        'semana': ultimo['semana'], 'normal': ultimo['normal'],
        'ancho': ANCHO, 'alto': ALTO, 'base_y': ALTO - MARGEN_ABA, 'texto_y': ALTO - 6,
    }


def _sesiones_y_rpe(cliente, desde, hasta):
    """(nº de sesiones, esfuerzo medio) de las actividades con carga en ese tramo."""
    from django.db.models.functions import Coalesce
    from entrenos.models import ActividadRealizada
    from entrenos.services.estado_carga_service import DURACION_MAX_MIN

    filas = [
        a for a in ActividadRealizada.objects.filter(cliente=cliente, carga_ua__isnull=False)
        .annotate(fecha_carga=Coalesce('fecha_realizado', 'fecha'))
        .filter(fecha_carga__gte=desde, fecha_carga__lte=hasta)
        .values('rpe_medio', 'duracion_minutos')
        if (a['duracion_minutos'] or 0) <= DURACION_MAX_MIN
    ]
    rpes = [float(a['rpe_medio']) for a in filas if a['rpe_medio']]
    return len(filas), (sum(rpes) / len(rpes) if rpes else None)


def _n1(x):
    return f'{x:.1f}'.replace('.', ',')


def frase_camino(cliente, hoy):
    """25-oct-2026: la carga de la semana contada con sesiones e intensidad, no con puntos.

    'Esta semana has acumulado un 75 % más de esfuerzo que en una semana normal tuya:
    más sesiones (6 frente a 4) y más intensas (esfuerzo medio 7,9 frente a 7,3).'
    """
    from entrenos.services.estado_carga_service import DIAS_AGUDA, SEMANAS_NORMAL, lectura_carga

    carga = lectura_carga(cliente, hoy)
    if not carga['normal']:
        return None
    corte = hoy - timedelta(days=DIAS_AGUDA - 1)
    n_sem, rpe_sem = _sesiones_y_rpe(cliente, corte, hoy)
    n_ant, rpe_ant = _sesiones_y_rpe(cliente, hoy - timedelta(days=DIAS_AGUDA * (SEMANAS_NORMAL + 1) - 1),
                                     corte - timedelta(days=1))
    n_normal = round(n_ant / SEMANAS_NORMAL)
    pct = round((carga['ratio'] - 1) * 100)

    if abs(pct) < 10:
        cabeza = 'Esta semana llevas un esfuerzo parecido al de una semana normal tuya'
    elif pct > 0:
        cabeza = f'Esta semana has acumulado un {pct} % más de esfuerzo que en una semana normal tuya'
    else:
        cabeza = f'Esta semana llevas un {-pct} % menos de esfuerzo que en una semana normal tuya'

    partes = []
    if n_sem != n_normal:
        partes.append(f'{"más" if n_sem > n_normal else "menos"} sesiones ({n_sem} frente a {n_normal})')
    else:
        partes.append(f'las mismas sesiones ({n_sem})')
    if rpe_sem is not None and rpe_ant is not None:
        if rpe_sem >= rpe_ant + 0.3:
            partes.append(f'más intensas (esfuerzo medio {_n1(rpe_sem)} frente a {_n1(rpe_ant)})')
        elif rpe_sem <= rpe_ant - 0.3:
            partes.append(f'más suaves (esfuerzo medio {_n1(rpe_sem)} frente a {_n1(rpe_ant)})')
        else:
            partes.append(f'con la intensidad de siempre (esfuerzo medio {_n1(rpe_sem)})')
    unidas = partes[0] if len(partes) == 1 else f'{partes[0]} y {partes[1]}'
    if partes[0].startswith('las mismas') and len(partes) == 2:
        unidas = f'{partes[0]}, {partes[1]}'
    return f'{cabeza}: {unidas}.'


def variabilidad(cliente, hoy, dias=DIAS_CAMINO):
    """Puntos de variabilidad de cada mañana y tu franja normal (±15 % de tu media)."""
    from clientes.models import BitacoraDiaria
    from entrenos.services.recuperacion_service import _medias_base

    desde = hoy - timedelta(days=dias - 1)
    valores = {}
    for fecha, hrv in BitacoraDiaria.objects.filter(
        cliente=cliente, fecha__gte=desde, fecha__lte=hoy, hrv_ms__isnull=False,
    ).values_list('fecha', 'hrv_ms'):
        valores[fecha] = hrv
    media = _medias_base(cliente, hoy + timedelta(days=1)).get('hrv_ms')
    if not valores:
        return {'puntos': [], 'media': None}
    # El eje va del valor más bajo al más alto (con la franja normal dentro), no desde cero:
    # desde cero, todas las mañanas salían en una línea plana.
    referencia = list(valores.values()) + ([media * 0.85, media * 1.15] if media else [])
    suelo, tope = min(referencia), max(referencia)
    margen = max((tope - suelo) * 0.15, 3)
    suelo, tope = suelo - margen, tope + margen
    puntos = []
    for i in range(dias):
        d = desde + timedelta(days=i)
        if d in valores:
            puntos.append({'x': _x(i, dias), 'y': _y(valores[d], tope, suelo), 'valor': valores[d],
                           'fecha': f'{d:%d/%m}', 'bajo': bool(media and valores[d] < media * 0.85)})
    out = {'puntos': puntos, 'media': round(media) if media else None, 'ancho': ANCHO, 'alto': ALTO,
           'base_y': ALTO - MARGEN_ABA, 'texto_y': ALTO - 6,
           'marcas': [{'x': _x(i, dias), 'texto': f'{desde + timedelta(days=i):%d/%m}'} for i in (0, dias // 2, dias - 1)]}
    if media:
        out['franja_y1'] = _y(media * 1.15, tope, suelo)
        out['franja_y2'] = _y(media * 0.85, tope, suelo)
        out['media_y'] = _y(media, tope, suelo)
        out['franja_alto'] = round(out['franja_y2'] - out['franja_y1'], 1)
    return out


def dias_recientes(estado):
    """Los últimos 14 días, del más antiguo al de hoy: letra del día y nivel."""
    from datetime import date

    out = []
    for d in reversed(estado['cuerpo']):
        f = date.fromisoformat(d['fecha'])
        out.append({'letra': LETRAS_DIA[f.weekday()], 'fecha': f'{f:%d/%m}', 'nivel': d['nivel'] or 'sin',
                    'nombre': NOMBRES_NIVEL.get(d['nivel'], 'Sin dato')})
    return out


def tres_preguntas(estado):
    """¿Descanso? ¿Me paso? ¿Puedo dar más? Respuesta corta + por qué, con el dato."""
    from entrenos.services.estado_carga_service import DAR_MAS_BUENOS, PASAS_RATIO

    r = estado['respuesta']
    ratio = estado['carga']['ratio']
    malos, dias5 = estado['malos_5'], estado['dias_5']
    buenos, dias14 = estado['buenos_14'], estado['dias_14']
    conociendo = r == 'conociendote'
    pct = round((ratio - 1) * 100) if ratio is not None else None

    if r == 'parada':
        return [{'pregunta': p, 'respuesta': 'En pausa', 'tono': 'neutro',
                 'porque': 'Estás de parada: no juzgo nada hasta que vuelvas.'}
                for p in ('¿Necesito descansar?', '¿Me estoy pasando?', '¿Puedo dar más?')]

    descanso = {'pregunta': '¿Necesito descansar?'}
    if r == 'descansa':
        descanso.update(respuesta='Sí', tono='alerta',
                        porque=f'{malos} de los últimos {dias5} días por debajo de lo normal en ti.')
    elif conociendo:
        descanso.update(respuesta='Aún no lo sé', tono='neutro',
                        porque=f'Me faltan días de reloj ({dias14} de 5).')
    else:
        descanso.update(respuesta='No', tono='bien',
                        porque=f'{malos} de los últimos {dias5} días por debajo de lo normal (salta con 3).')

    pasas = {'pregunta': '¿Me estoy pasando?'}
    if r == 'te_pasas':
        pasas.update(respuesta='Sí', tono='alerta',
                     porque=f'{pct} % más de carga que tu semana normal y el cuerpo empieza a notarlo.')
    elif ratio is not None and ratio >= PASAS_RATIO:
        pasas.update(respuesta='Carga alta', tono='aviso',
                     porque=f'{pct} % más que tu semana normal. '
                            + ('Aún no sé cómo lo lleva tu cuerpo.' if conociendo else 'De momento tu cuerpo lo aguanta.'))
    elif ratio is None:
        pasas.update(respuesta='Aún no lo sé', tono='neutro', porque='Me falta historial de carga.')
    else:
        pasas.update(respuesta='No', tono='bien',
                     porque=('Carga como en tus semanas normales.' if abs(pct) < 10 else
                             f'Carga un {abs(pct)} % {"por encima" if pct > 0 else "por debajo"} de tu semana normal.'))

    mas = {'pregunta': '¿Puedo dar más?'}
    if r == 'dar_mas':
        mas.update(respuesta='Sí', tono='bien',
                   porque=f'{buenos} de {dias14} días recuperándote bien y la carga en lo tuyo.')
    elif conociendo:
        mas.update(respuesta='Aún no lo sé', tono='neutro',
                   porque='Necesito un par de semanas viéndote recuperar.')
    else:
        motivos = []
        if buenos < DAR_MAS_BUENOS:
            motivos.append(f'{buenos} de {dias14} días buenos (pido 10)')
        if ratio is not None and ratio > 1.3:
            motivos.append('la carga ya va alta')
        if estado['esfuerzo']['subiendo']:
            motivos.append('tu esfuerzo medio está subiendo')
        if estado['molestias']:
            motivos.append('molestias en ' + ', '.join(estado['molestias']))
        mas.update(respuesta='Todavía no', tono='neutro',
                   porque=(motivos[0][0].upper() + '; '.join(motivos)[1:] + '.') if motivos else 'Aún no.')
    return [descanso, pasas, mas]


DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre')


def fecha_texto(d):
    """'domingo 25 de octubre', sin depender del idioma del servidor."""
    return f'{DIAS_SEMANA[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def contexto_panel(cliente, hoy):
    from entrenos.services.estado_carga_service import TITULOS, estado_carga, parada_en

    estado = estado_carga(cliente, hoy)
    return {
        'estado': estado,
        'titulo': TITULOS[estado['respuesta']],
        'preguntas': tres_preguntas(estado),
        'camino': camino(cliente, hoy),
        'variabilidad': variabilidad(cliente, hoy),
        'frase_camino': frase_camino(cliente, hoy),
        'dias': dias_recientes(estado),
        'parada': parada_en(cliente, hoy),
        'fecha_texto': fecha_texto(hoy),
    }
