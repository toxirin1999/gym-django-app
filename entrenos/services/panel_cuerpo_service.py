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
    texto = f'{cabeza}: {unidas}.'
    # 13-nov-2026 (mejora 5): si la bajada viene de una semana de descarga, se dice.
    if pct <= -10 and _dias_en_descarga(cliente, corte, hoy) >= 3:
        texto += ' Es semana de descarga: que baje es lo previsto.'
    return texto


def _dias_en_descarga(cliente, desde, hasta):
    """Cuántos días de [desde, hasta] caen en una semana de descarga del plan."""
    try:
        from entrenos.services.sesion_descarga_service import fecha_en_descarga, periodos_descarga
        periodos = periodos_descarga(cliente.id)
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for i in range((hasta - desde).days + 1)
               if fecha_en_descarga(desde + timedelta(days=i), periodos))


def _n0(v):
    return str(round(v))


def _serie_manana(cliente, hoy, campo, dias, franja, malo, lectura=None, fmt=None):
    """Puntos de una medida de cada mañana y su franja normal alrededor de tu media.

    ``franja(media)`` → (abajo, arriba); ``malo(valor, media)`` → punto en rojo.
    ``lectura(valor, media)`` → frase corta ("un 37 % por debajo de lo normal").
    3-nov-2026: también la línea de tendencia (media de 7 días) y la frase de
    hoy y de la tendencia: con un valor suelto que sube y baja 40 ms de un día a
    otro, el gráfico solo no se entendía.
    """
    from clientes.models import BitacoraDiaria
    from entrenos.services.recuperacion_service import _medias_base

    # 13-nov-2026: ``fmt`` da el valor que se enseña (sueño: «6,7»); por defecto, el entero.
    fmt = fmt or (lambda v: round(v))
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
    margen = max((tope - suelo) * 0.15, 3 if (media or max(valores.values())) > 20 else 0.4)  # 13-nov: el sueño va en horas
    suelo, tope = suelo - margen, tope + margen
    puntos = []
    for i in range(dias):
        d = desde + timedelta(days=i)
        if d in valores:
            puntos.append({'x': _x(i, dias), 'y': _y(valores[d], tope, suelo), 'valor': fmt(valores[d]),
                           'fecha': f'{d:%d/%m}', 'bajo': bool(media and malo(valores[d], media)),
                           'hoy': d == hoy})
    # 27-oct-2026: las últimas mañanas, escritas (con 3 puntos en 30 días no se leían).
    ultimos = [p for p in puntos][-7:]
    marcas = [{'x': _x(i, dias), 'texto': f'{desde + timedelta(days=i):%d/%m}'} for i in (0, dias // 2)]
    marcas.append({'x': _x(dias - 1, dias), 'texto': 'hoy'})
    out = {'puntos': puntos, 'media': fmt(media) if media else None, 'ancho': ANCHO, 'alto': ALTO,
           'base_y': ALTO - MARGEN_ABA, 'texto_y': ALTO - 6,
           # 13-nov-2026 (mejora 17): valores en el eje y cuánto oscila, para no leer cada punto «a ojo».
           'eje_max': fmt(tope), 'eje_min': fmt(suelo), 'eje_max_y': MARGEN_ARR + 4, 'eje_min_y': ALTO - MARGEN_ABA - 4,
           'hoy_num': valores.get(hoy), 'media_num': media, 'tendencia_num': tendencias.get(dias - 1),
           'suelo_num': suelo, 'tope_num': tope, 'banda_num': banda,
           'serie_nums': [valores[desde + timedelta(days=i)] for i in range(dias) if desde + timedelta(days=i) in valores],
           'minimo': fmt(min(valores.values())), 'maximo': fmt(max(valores.values())),
           'oscila': bool(media and (max(valores.values()) - min(valores.values())) / media >= 0.4),
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
                out['hoy_valor'] = fmt(valores[hoy])
                out['hoy_lectura'] = lectura(valores[hoy], media)
            t = tendencias.get(dias - 1)
            if t is not None:
                out['tendencia_valor'] = fmt(t)
                out['tendencia_lectura'] = lectura(t, media)
    return out


def _lectura_variabilidad(v, media):
    pct = round((v / media - 1) * 100)
    if v < media * 0.85:
        return f'un {-pct} % por debajo de lo habitual en ti'
    if v > media * 1.15:
        return f'un {pct} % por encima de lo habitual: bien recuperado'
    return 'dentro de lo habitual en ti'


def _lectura_pulso(v, media):
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM
    dif = round(v - media)
    if dif >= PULSO_ALTO_LPM:
        return f'{dif} pulsaciones más de lo habitual en ti'
    if dif <= -2:
        return f'{-dif} menos de lo habitual: tranquilo'
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


def _horas(v):
    """6.73 → '6 h 44' (el mismo formato en la cabecera y en la pestaña del sueño)."""
    from entrenos.services.recuperacion_service import horas_texto
    return horas_texto(v)


def _lectura_sueno(v, media):
    from entrenos.services.recuperacion_service import SUENO_MENOS_QUE_MEDIA_H, SUENO_MINIMO_H
    if v < SUENO_MINIMO_H:
        return 'poco: menos de 6 h'
    if v <= media - SUENO_MENOS_QUE_MEDIA_H:
        return 'bastante menos de lo que sueles'
    if v < media - 0.4:
        return 'algo menos de lo que sueles'
    return 'como sueles'


def sueno(cliente, hoy, dias=DIAS_MANANAS):
    """13-nov-2026: horas dormidas cada mañana; franja ±1 h 15 de tu media. Rojo: menos de 6 h o 1 h 15 menos."""
    from entrenos.services.recuperacion_service import SUENO_MENOS_QUE_MEDIA_H, SUENO_MINIMO_H
    return _serie_manana(
        cliente, hoy, 'horas_sueno', dias,
        franja=lambda m: (m - SUENO_MENOS_QUE_MEDIA_H, m + SUENO_MENOS_QUE_MEDIA_H),
        malo=lambda v, m: v < SUENO_MINIMO_H or v <= m - SUENO_MENOS_QUE_MEDIA_H,
        lectura=_lectura_sueno, fmt=_horas)


def _detalle_dia(lec):
    """13-nov-2026: qué datos marcaron la mañana, cortos y con cifras (sin consejos de entreno)."""
    if not lec:
        return ''
    from entrenos.services.recuperacion_service import (
        PULSO_ALTO_LPM, SUENO_MENOS_QUE_MEDIA_H, SUENO_MINIMO_H, horas_texto)
    d, m = lec.get('datos') or {}, lec.get('medias') or {}
    partes = []
    if d.get('hrv_ms') and m.get('hrv_ms'):
        pct = round((d['hrv_ms'] / m['hrv_ms'] - 1) * 100)
        partes.append(f'variabilidad {round(d["hrv_ms"])} ms ({abs(pct)} % {"por encima" if pct > 0 else "por debajo"} de lo habitual)')
    elif d.get('hrv_ms'):
        partes.append(f'variabilidad {round(d["hrv_ms"])} ms')
    if d.get('fc_reposo'):
        dif = round(d['fc_reposo'] - m['fc_reposo']) if m.get('fc_reposo') else None
        extra = '' if dif is None else (f' ({abs(dif)} {"por encima" if dif > 0 else "por debajo"} de lo habitual)' if dif else '')
        partes.append(f'pulso {round(d["fc_reposo"])}{extra}')
    if d.get('horas_sueno'):
        partes.append(f'sueño {horas_texto(d["horas_sueno"])}')
    if not partes:
        return ''
    marcadas = [n for n in lec.get('senales') or []]
    nombres = {'hrv': 'la variabilidad', 'pulso': 'el pulso', 'sueno': 'el sueño'}
    marca = (' Lo que la marcó: ' + ' y '.join(nombres[x] for x in marcadas if x in nombres) + '.') if marcadas else ''
    return 'Ese día: ' + ', '.join(partes) + '.' + marca


def dias_recientes(estado, cliente=None):
    """Los últimos 14 días, del más antiguo al de hoy: letra del día y nivel.

    13-nov-2026 (mejoras 8 y 12): con ``cliente``, cada día lleva ``detalle`` (qué señales lo marcaron)
    y ``hoy`` para pintarlo y poder tocarlo.
    """
    from datetime import date

    out = []
    for d in reversed(estado['cuerpo']):
        f = date.fromisoformat(d['fecha'])
        dia = {'letra': LETRAS_DIA[f.weekday()], 'fecha': f'{f:%d/%m}', 'nivel': d['nivel'] or 'sin',
               'nombre': NOMBRES_NIVEL.get(d['nivel'], 'Sin dato'),                'detalle': ''}
        if cliente is not None and d['nivel'] not in (None, 'parada'):
            try:
                from entrenos.services.recuperacion_service import lectura_recuperacion
                dia['detalle'] = _detalle_dia(lectura_recuperacion(cliente, f))
            except Exception:  # noqa: BLE001
                dia['detalle'] = ''
        # 31-oct-2026: la energía baja al empezar también pinta el día (ámbar).
        if d.get('energia_baja') and d['nivel'] not in ('ambar', 'rojo', 'parada'):
            e, h = d['energia_baja']
            dia['nivel'] = 'ambar'
            dia['nombre'] = f'Energía {e} al empezar (sueles {str(h).replace(".", ",")})'
            dia['detalle'] = (dia['detalle'] + ' ' if dia['detalle'] else '') + (
                f'Marcaste energía {e} al empezar el entreno (lo habitual en ti es {str(h).replace(".", ",")}).')
        out.append(dia)
    if out:
        out[-1]['hoy'] = True
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
    from entrenos.services.estado_carga_service import DAR_MAS_BUENOS, DAR_MAS_RATIO, PASAS_RATIO
    DAR_MAS_RATIO_MIN = DAR_MAS_RATIO[0]

    r = estado['respuesta']
    ratio = estado['carga']['ratio']
    malos, dias5 = estado['malos_5'], estado['dias_5']
    buenos, dias14 = estado['buenos_14'], estado['dias_14']
    conociendo = r == 'conociendote'
    pct = round((ratio - 1) * 100) if ratio is not None else None

    if r == 'parada':
        return [{'pregunta': p, 'respuesta': 'En pausa', 'tono': 'neutro',
                 'porque': 'Estás de parada: no juzgo nada hasta que vuelvas.'}
                for p in ('¿Hace falta descanso extra?', '¿Me estoy pasando?', '¿Puedo dar más?')]

    # 8-nov-2026: cuántas mañanas cuentan, en qué periodo y si deben ser seguidas.
    mananas5 = f'{malos} de {_mananas(dias5)} con dato de los últimos 5 días'
    descanso = {'pregunta': '¿Hace falta descanso extra?'}
    if r == 'descansa':
        descanso.update(respuesta='Sí', tono='alerta',
                        porque=f'Tus señales piden descanso: {mananas5} por debajo de lo normal en ti.')
    elif conociendo:
        descanso.update(respuesta='Aún no lo sé', tono='neutro',
                        porque=f'Me faltan mañanas comparadas con tu media ({dias14} de 5).')
    else:
        descanso.update(respuesta='Hoy no', tono='bien',
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
        if ratio is not None and ratio < DAR_MAS_RATIO_MIN:
            motivos.append(f'la carga de la semana va un {abs(pct)} % por debajo de tu media: '
                           f'hace falta una semana en lo tuyo para saber si aguantarías más')
        if estado['esfuerzo']['subiendo']:
            motivos.append('tu esfuerzo medio está subiendo')
        if estado['molestias']:
            motivos.append('molestias en ' + ', '.join(estado['molestias']))
        # 13-nov-2026: «pendiente» (gris), no el azul de «En pausa»; y siempre con el motivo.
        sin_valorar = ratio is not None and ratio < DAR_MAS_RATIO_MIN
        mas.update(respuesta='Aún no se puede valorar' if sin_valorar else 'Todavía no', tono='pendiente',
                   porque=(('; '.join(motivos))[0].upper() + '; '.join(motivos)[1:] + '.') if motivos
                   else 'Todavía no se cumple alguna de las condiciones; mira el «i» para ver cuáles.')
    descanso['cambia'], pasas['cambia'], mas['cambia'] = _que_cambiaria(estado, pct, conociendo)
    return [descanso, pasas, mas]


def _pct_txt(pct):
    return f'{"+" if pct > 0 else "−" if pct < 0 else ""}{abs(pct)} %'


def _que_cambiaria(estado, pct, conociendo):
    """13-nov-2026 (idea 5): la regla actual de cada respuesta y, si faltan datos, cuáles."""
    from entrenos.services.estado_carga_service import (
        DAR_MAS_BUENOS, DESCANSA_MALOS, DESCANSA_VENTANA, PASAS_MALOS, PASAS_RATIO)

    ratio = estado['carga']['ratio']
    malos, dias5 = estado['malos_5'], estado['dias_5']
    buenos, dias14 = estado['buenos_14'], estado['dias_14']
    ahora = _pct_txt(pct) if pct is not None else 'sin dato'

    if conociendo:
        falta = (f'Me faltan mañanas del reloj comparadas con tu media: llevo {dias14} de 5. '
                 f'Hasta entonces no saco conclusiones.')
        return falta, falta, falta

    descanso = (f'Pasaría a «Sí» si {DESCANSA_MALOS} de las últimas {DESCANSA_VENTANA} mañanas con dato '
                f'salen por debajo de lo habitual (ahora {malos} de {dias5}) y tu carga no ha bajado más '
                f'de un 20 % respecto a tu media')
    if ratio is not None and ratio < 0.8:
        descanso += f' (ahora {ahora}: con una carga tan baja esta regla no se activa)'
    descanso += '.'

    if ratio is None:
        pasas = 'Falta historial de carga (4 semanas) para compararla con tu media.'
    else:
        pasas = (f'Pasaría a «Sí» si tus últimos 7 días llegan a un {round((PASAS_RATIO - 1) * 100)} % o más '
                 f'por encima de tu media (ahora {ahora}) y {PASAS_MALOS} de las últimas {DESCANSA_VENTANA} '
                 f'mañanas salen por debajo (ahora {malos}).')

    faltan = []
    if buenos < DAR_MAS_BUENOS:
        faltan.append(f'{DAR_MAS_BUENOS} mañanas buenas en 14 días, seguidas o no (llevas {buenos})')
    if dias14 < 14:
        faltan.append(f'datos del reloj de más días: solo pude comparar {dias14} de los 14')
    if ratio is not None and not (0.8 <= ratio <= 1.3):
        faltan.append(f'carga entre −20 % y +30 % de tu media (ahora {ahora})')
    if estado['esfuerzo']['subiendo']:
        faltan.append('que tu esfuerzo medio deje de subir')
    if estado['molestias']:
        faltan.append('sin molestias (hay en ' + ', '.join(estado['molestias']) + ')')
    if estado['respuesta'] == 'dar_mas':
        mas = 'Se mantiene mientras sigas con 10 mañanas buenas en 14 días, la carga en tu zona y sin molestias.'
    elif faltan:
        mas = 'Para valorarlo falta: ' + '; '.join(faltan) + '.'
    else:
        mas = 'Se cumplen las condiciones salvo que cambie alguna; mira el «i» para verlas.'
    return descanso, pasas, mas


DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre')


def fecha_texto(d):
    """'domingo 25 de octubre', sin depender del idioma del servidor."""
    return f'{DIAS_SEMANA[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def _spark(nums, suelo, tope, w=96, h=28, pad=3):
    """Mini línea de las 14 mañanas para la tarjeta (puntos con punto decimal, como el resto de SVG)."""
    if len(nums) < 2 or tope <= suelo:
        return '', None, None
    n = len(nums)
    pts = [((i / (n - 1)) * (w - 6) + 3, h - pad - ((v - suelo) / (tope - suelo)) * (h - 2 * pad))
           for i, v in enumerate(nums)]
    return ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts), round(pts[-1][0], 1), round(pts[-1][1], 1)


def tarjetas_senales(variab, pul, sue):
    """14-nov-2026: variabilidad, pulso y sueño como tarjetas: número, barra de tu rango y mini línea.

    Todo sale de las mismas series del panel; no hay puntuación inventada.
    """
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM, SUENO_MENOS_QUE_MEDIA_H, SUENO_MINIMO_H

    def _base(clave, nombre, serie, unidad, rango_fmt):
        hoy, media = serie.get('hoy_num'), serie.get('media_num')
        t = {'clave': clave, 'nombre': nombre, 'unidad': unidad, 'ok': None, 'estado': 'Sin dato de hoy',
             'valor': '—', 'hay_dato': hoy is not None and bool(media)}
        banda = serie.get('banda_num')
        if banda and serie.get('tope_num') is not None:
            suelo, tope = serie['suelo_num'], serie['tope_num']
            pc = lambda v: max(2.0, min(98.0, (v - suelo) / (tope - suelo) * 100))  # noqa: E731
            t.update(banda_ini=round(pc(banda[0]), 1), banda_ancho=round(pc(banda[1]) - pc(banda[0]), 1),
                     punto=round(pc(hoy), 1) if hoy is not None else None,
                     rango=rango_fmt(banda), minimo=serie['eje_min'], maximo=serie['eje_max'])
        sp, sx, sy = _spark(serie.get('serie_nums') or [], serie.get('suelo_num', 0), serie.get('tope_num', 0))
        t.update(spark=sp, sx=sx, sy=sy)
        tv, tl = serie.get('tendencia_valor'), serie.get('tendencia_lectura')
        t['linea'] = f'Tendencia 7 días: {tv}{(" " + unidad) if unidad else ""} · {tl}' if tv is not None and tl else ''
        return t, hoy, media

    t1, hoy, media = _base('variabilidad', 'Variabilidad cardiaca', variab, 'ms',
                           lambda b: f'{round(b[0])}–{round(b[1])}')
    if t1['hay_dato']:
        pct = round((hoy / media - 1) * 100)
        t1['valor'] = str(variab['hoy_valor'])
        t1['ok'] = hoy >= media * 0.85
        t1['estado'] = (f'▼ {-pct} % bajo' if hoy < media * 0.85 else f'▲ {pct} % alto' if hoy > media * 1.15
                        else 'En tu rango')
    t2, hoy, media = _base('pulso', 'Pulso en reposo', pul, 'lpm', lambda b: f'{round(b[0])}–{round(b[1])}')
    if t2['hay_dato']:
        dif = round(hoy - media)
        t2['valor'] = str(pul['hoy_valor'])
        t2['ok'] = dif < PULSO_ALTO_LPM
        t2['estado'] = (f'▲ {dif} alto' if dif >= PULSO_ALTO_LPM else f'▼ {-dif} · tranquilo' if dif <= -2
                        else 'En tu rango')
    t3, hoy, media = _base('sueno', 'Sueño', sue, '', lambda b: f'{_horas(b[0])}–{_horas(b[1])}')
    if t3['hay_dato']:
        t3['valor'] = str(sue['hoy_valor'])
        corto = hoy < SUENO_MINIMO_H or hoy <= media - SUENO_MENOS_QUE_MEDIA_H
        t3['ok'] = not corto
        t3['estado'] = ('▼ corto' if corto else '▼ algo menos' if hoy < media - 0.4 else 'Como sueles')
    return [t1, t2, t3]


def medidor_carga(cliente, hoy):
    """14-nov-2026: la carga de 7 días como medidor (40–160 % de tu media; zona normal 80–130 %)."""
    import math

    from entrenos.services.estado_carga_service import DIAS_AGUDA, lectura_carga

    carga = lectura_carga(cliente, hoy)
    if not carga['normal'] or carga['ratio'] is None:
        return None
    pct = round(carga['ratio'] * 100)
    ang = lambda pc: math.pi - ((max(40, min(160, pc)) - 40) / 120) * math.pi  # noqa: E731
    pt = lambda pc: (75 + 60 * math.cos(ang(pc)), 80 - 60 * math.sin(ang(pc)))  # noqa: E731
    a, b, m = pt(80), pt(130), pt(pct)
    ratio = round(pct - 100)
    return {
        'texto': f'{"+" if ratio > 0 else "−" if ratio < 0 else ""}{abs(ratio)} %',
        'banda': f'M {a[0]:.1f} {a[1]:.1f} A 60 60 0 0 1 {b[0]:.1f} {b[1]:.1f}',
        'x': round(m[0], 1), 'y': round(m[1], 1),
        'en_zona': 80 <= pct <= 130,
        'descarga': ratio <= -10 and _dias_en_descarga(cliente, hoy - timedelta(days=DIAS_AGUDA - 1), hoy) >= 3,
    }


def chips_de_cambios(cambios):
    """Los cambios del briefing en chips cortos (el texto completo queda al tocar)."""
    import re
    chips, otros = [], 0
    for c in cambios or []:
        if c.startswith('La sesión va en versión reducida'):
            chips.append('Versión reducida')
        elif (m := re.match(r'RPE objetivo un punto menos en (\d+)', c)):
            chips.append(f'RPE −1 · {m.group(1)} ejerc.')
        elif c.startswith(('La sesión va tal como', 'Hoy no hay sesión')):
            continue
        else:
            otros += 1
    if otros:
        chips.append(f'{otros} cambio{"s" if otros != 1 else ""} más' if chips else
                     f'{otros} cambio{"s" if otros != 1 else ""}')
    return chips


def decision_de_hoy(cliente, usuario, hoy):
    """13-nov-2026: la MISMA decisión efectiva que enseña Ahora (no una lectura propia).

    Reutiliza lo que usa ``dashboard_silencioso_preview``: la autoridad diaria de gym, el estado del
    sistema (organismo) y el porqué. Devuelve None si algo falla (la página cae a su titular de siempre).
    """
    import logging
    try:
        from core.organismo import estado_operativo_visible, resolver_estado_sistema_hoy
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym
        from entrenos.services.porque_decision_service import construir_porque

        decision_gym = resolver_autoridad_diaria_gym(cliente, hoy) or {}
        estado_sistema = resolver_estado_sistema_hoy(usuario, decision_gym=decision_gym) or {}
        operativo = estado_operativo_visible(estado_sistema.get('estado'), estado_sistema.get('motivo'))
        frase = estado_sistema.get('texto') or decision_gym.get('mensaje') or ''
        porque = None
        if operativo not in ('DESCANSAR', 'HECHO'):
            porque = construir_porque(decision_gym)
            if porque and porque.strip() == frase.strip():
                porque = None
        return {
            'estado': operativo, 'titulo': operativo.capitalize(), 'frase': frase, 'porque': porque,
            'cambios': (cambios := que_cambio(decision_gym, operativo)),
            'chips': chips_de_cambios(cambios),
            'tono': {'ENTRENAR': 'bien', 'HECHO': 'bien', 'AJUSTAR': 'aviso'}.get(operativo, 'aviso'),
        }
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception('panel cuerpo: no se pudo leer la decisión de hoy')
        return None


_TIPOS_AJUSTE = {
    'criterio_entrenador', 'deload', 'molestia_reciente', 'sustitucion_molestia',
    'sustitucion_estancamiento', 'intervencion_molestia_pospuesta', 'progresion_pospuesta',
}


def que_cambio(decision_gym, operativo=None):
    """13-nov-2026 (idea 1): solo ajustes ya aplicados en el briefing (``cambios_materializados``).

    Una frase por motivo (el RPE un punto menos en varios ejercicios cuenta una vez).
    """
    import re
    decision_gym = decision_gym or {}
    cambios = [c for c in (decision_gym.get('cambios_materializados') or []) if c.get('tipo') in _TIPOS_AJUSTE]
    items = []
    if decision_gym.get('estado') == 'version_reducida' or decision_gym.get('modo_reducido'):
        items.append('La sesión va en versión reducida.')
    por_motivo = {}
    ultimo_motivo = ''
    for c in cambios:
        razon = (c.get('razon') or '').strip()
        if c['tipo'] == 'criterio_entrenador':
            m = re.search(r'en vez de [\d.,]+: (.+?)\. Deja', razon)
            corta = re.match(r'^Hoy RPE [\d.,]+ en vez de [\d.,]+\.$', razon)
            if m:
                ultimo_motivo = m.group(1)
                por_motivo.setdefault(ultimo_motivo, []).append(c.get('ejercicio_original'))
            elif corta:  # mismo porqué que la primera tarjeta (se cuenta una vez)
                por_motivo.setdefault(ultimo_motivo, []).append(c.get('ejercicio_original'))
            else:  # víspera/día de fútbol u otro criterio: su frase tal cual, una vez
                if razon and razon not in items:
                    items.append(razon)
        elif c['tipo'] == 'deload':
            items.append(razon)
        else:
            nombre = c.get('ejercicio_original')
            items.append(f'{nombre}: {razon}' if nombre else razon)
    for motivo, ejercicios in por_motivo.items():
        n = len({e for e in ejercicios if e}) or len(ejercicios)
        cuando = f': {motivo}' if motivo else ''
        items.append(f'RPE objetivo un punto menos en {n} {"ejercicio" if n == 1 else "ejercicios"}{cuando}.')
    if len(items) > 6:
        items = items[:6] + [f'… y {len(items) - 6} ajustes más.']
    if items:
        return items
    if operativo in ('DESCANSAR', 'HECHO') or not decision_gym.get('sesion_materializada'):
        return ['Hoy no hay sesión que ajustar.']
    return ['La sesión va tal como está en el plan: el briefing no ha aplicado ajustes.']


def frase_reloj(variab, pul, sue):
    """Qué vio el reloj ESTA mañana (solo hoy; la tendencia va en «últimos días»)."""
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM

    partes = []
    hv, mv = variab.get('hoy_num'), variab.get('media_num')
    if hv is not None and mv:
        if hv < mv * 0.85:
            partes.append(f'Variabilidad por debajo de tu rango hoy ({round(hv)} ms; lo habitual, unos {round(mv)})')
        elif hv > mv * 1.15:
            partes.append(f'Variabilidad por encima de tu rango hoy ({round(hv)} ms; lo habitual, unos {round(mv)})')
        else:
            partes.append(f'Variabilidad dentro de lo habitual hoy ({round(hv)} ms)')
    hp, mp = pul.get('hoy_num'), pul.get('media_num')
    if hp is not None and mp:
        dif = round(hp - mp)
        if dif >= PULSO_ALTO_LPM:
            partes.append(f'Pulso por encima de tu rango ({round(hp)}; lo habitual, unos {round(mp)})')
        elif dif <= -2:
            partes.append(f'Pulso tranquilo ({round(hp)}, {-dif} por debajo de lo habitual)')
        else:
            partes.append(f'Pulso dentro de lo habitual ({round(hp)})')
    hs, ms = sue.get('hoy_num'), sue.get('media_num')
    if hs is not None:
        txt = _horas(hs)
        if ms and hs <= ms - 1.25 or hs < 6:
            partes.append(f'Sueño corto ({txt})')
        elif ms and hs < ms - 0.4:
            partes.append(f'Sueño algo por debajo de lo habitual ({txt})')
        else:
            partes.append(f'Sueño {txt}')
    if not partes:
        return 'El reloj aún no ha mandado datos de esta mañana.'
    return '. '.join(partes) + '.'


def frase_ultimos_dias(estado, variab, pul, sue):
    """Qué muestran los últimos días: tendencia de siete días de cada señal y mañanas malas."""
    partes = []
    if variab.get('tendencia_valor') is not None:
        partes.append(f'variabilidad {variab["tendencia_valor"]} ms, {variab["tendencia_lectura"]}')
    if pul.get('tendencia_valor') is not None:
        partes.append(f'pulso {pul["tendencia_valor"]}, {pul["tendencia_lectura"]}')
    if sue.get('tendencia_valor') is not None:
        partes.append(f'sueño {sue["tendencia_valor"]}, {sue["tendencia_lectura"]}')
    out = ''
    if partes:
        out = 'Tendencia de 7 días: ' + '; '.join(partes) + '.'
    if estado.get('dias_5'):
        out += (f' {estado["malos_5"]} de las últimas {estado["dias_5"]} mañanas con dato '
                f'por debajo de lo habitual.')
    return out.strip()


def sello_reloj(cliente, hoy):
    """13-nov-2026 (idea 4): hora de importación y fecha de las mediciones, por separado.

    ``{'importacion': 'hoy 07:42' | None, 'mediciones': str, 'atraso': bool}``. Una sincronización de hoy
    con datos de ayer se dice como tal.
    """
    from datetime import timedelta
    from django.utils import timezone

    from clientes.models import BitacoraDiaria

    filas = list(BitacoraDiaria.objects.filter(cliente=cliente, fecha__gte=hoy - timedelta(days=6), fecha__lte=hoy)
                 .values('fecha', 'hrv_ms', 'fc_reposo', 'horas_sueno', 'salud_importado_en'))
    if not filas:
        return None

    def _dia(f):
        return 'hoy' if f == hoy else 'ayer' if f == hoy - timedelta(days=1) else f'{f:%d/%m}'

    nombres = {'hrv_ms': 'variabilidad', 'fc_reposo': 'pulso', 'horas_sueno': 'sueño'}
    ultimo = {}
    for campo in nombres:
        fechas = [f['fecha'] for f in filas if f[campo] is not None]
        if fechas:
            ultimo[campo] = max(fechas)
    if not ultimo:
        return None
    de_hoy = [n for c, n in nombres.items() if ultimo.get(c) == hoy]
    atrasadas = [(n, ultimo[c]) for c, n in nombres.items() if c in ultimo and ultimo[c] != hoy]
    faltan = [n for c, n in nombres.items() if c not in ultimo]
    if de_hoy and not atrasadas and not faltan:
        mediciones = 'las tres señales son de esta mañana'
    else:
        partes = []
        if de_hoy:
            partes.append(', '.join(de_hoy) + ' de esta mañana')
        for n, f in atrasadas:
            partes.append(f'{n} de {_dia(f)}')
        if faltan:
            partes.append('sin ' + ', '.join(faltan))
        mediciones = '; '.join(partes)
    importaciones = [f['salud_importado_en'] for f in filas if f['salud_importado_en']]
    importacion = None
    if importaciones:
        cuando = timezone.localtime(max(importaciones))
        importacion = f'{_dia(cuando.date())} {cuando:%H:%M}'
    return {'importacion': importacion, 'mediciones': mediciones, 'atraso': bool(atrasadas or faltan)}


def contexto_panel(cliente, hoy, usuario=None):
    from entrenos.services.estado_carga_service import TITULOS, estado_carga, parada_en

    estado = estado_carga(cliente, hoy)
    dias = dias_recientes(estado, cliente)
    variab, pul, sue = variabilidad(cliente, hoy), pulso(cliente, hoy), sueno(cliente, hoy)
    return {
        'estado': estado,
        'titulo': TITULOS[estado['respuesta']],
        'decision': decision_de_hoy(cliente, usuario or cliente.user, hoy),
        'tarjetas': tarjetas_senales(variab, pul, sue),
        'medidor': medidor_carga(cliente, hoy),
        'bloque_reloj': frase_reloj(variab, pul, sue),
        'bloque_ultimos': frase_ultimos_dias(estado, variab, pul, sue),
        'sello_reloj': sello_reloj(cliente, hoy),
        'preguntas': tres_preguntas(estado),
        'descanso_plan': descanso_del_plan(cliente, hoy),
        'camino': camino(cliente, hoy),
        'variabilidad': variab,
        'pulso': pul,
        'sueno': sue,
        'dias_energia': [d for d in dias if d['nombre'].startswith('Energía')],
        'frase_camino': frase_camino(cliente, hoy),
        'dias': dias,
        'parada': parada_en(cliente, hoy),
        'fecha_texto': fecha_texto(hoy),
    }
