"""Panel «Cómo responde tu cuerpo» (25-oct-2026, paso 2).

Todo lo que pinta la página sale de aquí, ya calculado: la respuesta del día
(``estado_carga_service``), las tres preguntas, el camino de 30 días (carga de
7 días frente a tu franja normal) y la variabilidad de cada mañana. La página
solo dibuja; no decide nada.
"""

from datetime import timedelta

DIAS_CAMINO = 30
# 3-nov-2026: variabilidad y pulso, 14 mañanas como «Cómo amaneces» (con 30 días
# y datos desde el 24-oct todo se apelotonaba a la derecha).
DIAS_MANANAS = 14
DIAS_TENDENCIA = 7
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


def _n0(v):
    return str(round(v))


def _serie_manana(cliente, hoy, campo, dias, franja, malo, lectura=None):
    """Puntos de una medida de cada mañana y su franja normal alrededor de tu media.

    ``franja(media)`` → (abajo, arriba); ``malo(valor, media)`` → punto en rojo.
    ``lectura(valor, media)`` → frase corta ("un 37 % por debajo de lo normal").
    3-nov-2026: también la línea de tendencia (media de 7 días) y la frase de
    hoy y de la tendencia: con un valor suelto que sube y baja 40 ms de un día a
    otro, el gráfico solo no se entendía.
    """
    from clientes.models import BitacoraDiaria
    from entrenos.services.recuperacion_service import _medias_base

    desde = hoy - timedelta(days=dias - 1)
    valores = {}
    for fecha, v in BitacoraDiaria.objects.filter(
        cliente=cliente, fecha__gte=desde - timedelta(days=DIAS_TENDENCIA - 1), fecha__lte=hoy,
        **{f'{campo}__isnull': False},
    ).values_list('fecha', campo):
        valores[fecha] = float(v)
    previos = {f: v for f, v in valores.items() if f < desde}
    valores = {f: v for f, v in valores.items() if f >= desde}
    # 28-oct-2026 (nota 9): la misma media que usan los días (sin la mañana de hoy).
    media = _medias_base(cliente, hoy).get(campo)
    if not valores:
        return {'puntos': [], 'media': None}

    todos = {**previos, **valores}

    def _tendencia(d):
        ventana = [todos[f] for f in todos if d - timedelta(days=DIAS_TENDENCIA - 1) <= f <= d]
        return sum(ventana) / len(ventana) if len(ventana) >= 3 else None

    tendencias = {}
    for i in range(dias):
        d = desde + timedelta(days=i)
        t = _tendencia(d)
        if t is not None and (d in valores or d == hoy):
            tendencias[i] = t

    # El eje va del valor más bajo al más alto (con la franja normal dentro), no desde cero:
    # desde cero, todas las mañanas salían en una línea plana.
    banda = franja(media) if media else None
    referencia = list(valores.values()) + (list(banda) if banda else [])
    suelo, tope = min(referencia), max(referencia)
    margen = max((tope - suelo) * 0.15, 3)
    suelo, tope = suelo - margen, tope + margen
    puntos = []
    for i in range(dias):
        d = desde + timedelta(days=i)
        if d in valores:
            puntos.append({'x': _x(i, dias), 'y': _y(valores[d], tope, suelo), 'valor': round(valores[d]),
                           'fecha': f'{d:%d/%m}', 'bajo': bool(media and malo(valores[d], media)),
                           'hoy': d == hoy})
    # 27-oct-2026: las últimas mañanas, escritas (con 3 puntos en 30 días no se leían).
    ultimos = [p for p in puntos][-7:]
    marcas = [{'x': _x(i, dias), 'texto': f'{desde + timedelta(days=i):%d/%m}'} for i in (0, dias // 2)]
    marcas.append({'x': _x(dias - 1, dias), 'texto': 'hoy'})
    out = {'puntos': puntos, 'media': round(media) if media else None, 'ancho': ANCHO, 'alto': ALTO,
           'base_y': ALTO - MARGEN_ABA, 'texto_y': ALTO - 6,
           'ultimos': ' · '.join(str(p['valor']) for p in ultimos),
           # 31-oct-2026: las mañanas que cuentan para la media (sin la de hoy):
           # decía "llevo 5" con 4 en la media.
           'dias_con_dato': sum(1 for f in valores if f < hoy),
           'marcas': marcas,
           # Puntos como texto con punto decimal: la página está en español y
           # Django escribía "231,4", que el SVG no entiende (los puntos se iban a x=0).
           'linea': ' '.join(f"{p['x']},{p['y']}" for p in puntos),
           'tendencia': ' '.join(f'{_x(i, dias)},{_y(t, tope, suelo)}' for i, t in sorted(tendencias.items()))
           if len(tendencias) >= 2 else ''}
    if banda:
        out['franja_y1'] = _y(banda[1], tope, suelo)
        out['franja_y2'] = _y(banda[0], tope, suelo)
        out['media_y'] = _y(media, tope, suelo)
        out['franja_alto'] = round(out['franja_y2'] - out['franja_y1'], 1)
        out['media_texto_y'] = round(out['media_y'] - 4, 1)
        if lectura:
            if hoy in valores:
                out['hoy_valor'] = round(valores[hoy])
                out['hoy_lectura'] = lectura(valores[hoy], media)
            t = tendencias.get(dias - 1)
            if t is not None:
                out['tendencia_valor'] = round(t)
                out['tendencia_lectura'] = lectura(t, media)
    return out


def _lectura_variabilidad(v, media):
    pct = round((v / media - 1) * 100)
    if v < media * 0.85:
        return f'un {-pct} % por debajo de lo normal en ti'
    if v > media * 1.15:
        return f'un {pct} % por encima de lo normal: bien recuperado'
    return 'dentro de lo normal en ti'


def _lectura_pulso(v, media):
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM
    dif = round(v - media)
    if dif >= PULSO_ALTO_LPM:
        return f'{dif} pulsaciones más de lo normal en ti'
    if dif <= -2:
        return f'{-dif} menos de lo normal: tranquilo'
    return 'como siempre'


def variabilidad(cliente, hoy, dias=DIAS_MANANAS):
    """Variabilidad de cada mañana; franja normal ±15 % de tu media. Rojo: 15 % o más por debajo."""
    return _serie_manana(cliente, hoy, 'hrv_ms', dias,
                         franja=lambda m: (m * 0.85, m * 1.15), malo=lambda v, m: v < m * 0.85,
                         lectura=_lectura_variabilidad)


def pulso(cliente, hoy, dias=DIAS_MANANAS):
    """27-oct-2026: pulso en reposo de cada mañana; franja ±5 de tu media. Rojo: 5 o más por encima."""
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM
    return _serie_manana(cliente, hoy, 'fc_reposo', dias,
                         franja=lambda m: (m - PULSO_ALTO_LPM, m + PULSO_ALTO_LPM),
                         malo=lambda v, m: v >= m + PULSO_ALTO_LPM,
                         lectura=_lectura_pulso)


def dias_recientes(estado):
    """Los últimos 14 días, del más antiguo al de hoy: letra del día y nivel."""
    from datetime import date

    out = []
    for d in reversed(estado['cuerpo']):
        f = date.fromisoformat(d['fecha'])
        dia = {'letra': LETRAS_DIA[f.weekday()], 'fecha': f'{f:%d/%m}', 'nivel': d['nivel'] or 'sin',
               'nombre': NOMBRES_NIVEL.get(d['nivel'], 'Sin dato')}
        # 31-oct-2026: la energía baja al empezar también pinta el día (ámbar).
        if d.get('energia_baja') and d['nivel'] not in ('ambar', 'rojo', 'parada'):
            e, h = d['energia_baja']
            dia['nivel'] = 'ambar'
            dia['nombre'] = f'Energía {e} al empezar (sueles {str(h).replace(".", ",")})'
        out.append(dia)
    return out


def _mananas(n):
    return f'{n} mañana' if n == 1 else f'{n} mañanas'


def descanso_del_plan(cliente, hoy):
    """8-nov-2026: True si hoy el plan marca descanso (no tus señales)."""
    try:
        from entrenos.services.semana_rutina_service import semana_segun_cola
        dia = semana_segun_cola(cliente, hoy)['dias'].get(hoy) or {}
    except Exception:  # noqa: BLE001
        return False
    return dia.get('tipo') == 'descanso' and not dia.get('aplazada')


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

    # 8-nov-2026: cuántas mañanas cuentan, en qué periodo y si deben ser seguidas.
    mananas5 = f'{malos} de {_mananas(dias5)} con dato de los últimos 5 días'
    descanso = {'pregunta': '¿Necesito descansar?'}
    if r == 'descansa':
        descanso.update(respuesta='Sí', tono='alerta',
                        porque=f'Tus señales piden descanso: {mananas5} por debajo de lo normal en ti.')
    elif conociendo:
        descanso.update(respuesta='Aún no lo sé', tono='neutro',
                        porque=f'Me faltan mañanas comparadas con tu media ({dias14} de 5).')
    else:
        descanso.update(respuesta='No', tono='bien',
                        porque=(f'Tus señales no piden descanso extra: {mananas5} por debajo de lo normal. '
                                f'Lo pediría con 3, seguidas o no.'))

    pasas = {'pregunta': '¿Me estoy pasando?'}
    if r == 'te_pasas':
        pasas.update(respuesta='Sí', tono='alerta',
                     porque=(f'Últimos 7 días: un {pct} % más que tu media de las 4 semanas anteriores, '
                             f'y el cuerpo empieza a notarlo.'))
    elif ratio is not None and ratio >= PASAS_RATIO:
        pasas.update(respuesta='Carga alta', tono='aviso',
                     porque=f'Últimos 7 días: un {pct} % más que tu media de las 4 semanas anteriores. '
                            + ('Aún no sé cómo lo lleva tu cuerpo.' if conociendo else 'De momento tu cuerpo lo aguanta.'))
    elif ratio is None:
        pasas.update(respuesta='Aún no lo sé', tono='neutro', porque='Me falta historial de carga.')
    else:
        pasas.update(respuesta='No', tono='bien',
                     porque=('Últimos 7 días: como tu media de las 4 semanas anteriores.' if abs(pct) < 10 else
                             f'Últimos 7 días: un {abs(pct)} % {"por encima" if pct > 0 else "por debajo"} '
                             f'de tu media de las 4 semanas anteriores.'))

    mas = {'pregunta': '¿Puedo dar más?'}
    if r == 'dar_mas':
        mas.update(respuesta='Sí', tono='bien',
                   porque=(f'{buenos} mañanas buenas en los últimos 14 días (hacían falta 10, seguidas o no) '
                           f'y la carga en lo tuyo.'))
    elif conociendo:
        mas.update(respuesta='Aún no lo sé', tono='neutro',
                   porque='Necesito un par de semanas viéndote recuperar.')
    else:
        motivos = []
        if buenos < DAR_MAS_BUENOS:
            sin_dato = f'; el reloj solo pudo comparar {dias14} de los 14' if dias14 < 14 else ''
            motivos.append(f'{buenos} mañanas buenas en los últimos 14 días; hacen falta 10, '
                           f'seguidas o no{sin_dato}')
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
        'descanso_plan': descanso_del_plan(cliente, hoy),
        'camino': camino(cliente, hoy),
        'variabilidad': variabilidad(cliente, hoy),
        'pulso': pulso(cliente, hoy),
        'frase_camino': frase_camino(cliente, hoy),
        'dias': dias_recientes(estado),
        'parada': parada_en(cliente, hoy),
        'fecha_texto': fecha_texto(hoy),
    }
