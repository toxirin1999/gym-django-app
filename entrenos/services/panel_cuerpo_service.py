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
        lectura=_lectura_sueno, fmt=lambda v: _n1(v))


def lectura_cruzada(variab, pul):
    """13-nov-2026 (mejora 7): variabilidad y pulso de hoy leídos juntos, solo si dicen algo."""
    from entrenos.services.recuperacion_service import PULSO_ALTO_LPM

    def _num(x):
        return x if isinstance(x, (int, float)) else None
    hv, mv = _num(variab.get('hoy_valor')), _num(variab.get('media'))
    hp, mp = _num(pul.get('hoy_valor')), _num(pul.get('media'))
    if None in (hv, mv, hp, mp):
        return None
    hrv_baja = hv < mv * 0.85
    pulso_alto = hp - mp >= PULSO_ALTO_LPM
    pulso_bajo = hp - mp <= -2
    if hrv_baja and pulso_alto:
        return 'Las dos señales apuntan a cansancio: variabilidad baja y pulso alto.'
    if hrv_baja and pulso_bajo:
        return ('Hoy la variabilidad está baja pero el pulso en reposo está tranquilo: las dos señales se '
                'compensan, así que no lo leo como cansancio acumulado. Mira si mañana se repite.')
    if hrv_baja:
        return 'Hoy la variabilidad está baja y el pulso normal: una señal suelta, no un patrón.'
    return None


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
        partes.append(f'variabilidad {round(d["hrv_ms"])} ms ({"+" if pct > 0 else "−"}{abs(pct)} % sobre lo normal)')
    elif d.get('hrv_ms'):
        partes.append(f'variabilidad {round(d["hrv_ms"])} ms')
    if d.get('fc_reposo'):
        dif = round(d['fc_reposo'] - m['fc_reposo']) if m.get('fc_reposo') else None
        extra = '' if dif is None else (f' ({dif:+d} sobre lo normal)'.replace('-', '−'))
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
        if ratio is not None and ratio < DAR_MAS_RATIO_MIN:
            motivos.append(f'la carga de la semana va un {abs(pct)} % por debajo de tu media: '
                           f'hace falta una semana en lo tuyo para saber si aguantarías más')
        if estado['esfuerzo']['subiendo']:
            motivos.append('tu esfuerzo medio está subiendo')
        if estado['molestias']:
            motivos.append('molestias en ' + ', '.join(estado['molestias']))
        # 13-nov-2026: «pendiente» (gris), no el azul de «En pausa»; y siempre con el motivo.
        mas.update(respuesta='Todavía no', tono='pendiente',
                   porque=(('; '.join(motivos))[0].upper() + '; '.join(motivos)[1:] + '.') if motivos
                   else 'Todavía no se cumple alguna de las condiciones; mira el «i» para ver cuáles.')
    return [descanso, pasas, mas]


DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre')


def aviso_hoy(estado, dias):
    """13-nov-2026 (mejora 1): si hoy amaneces por debajo y el titular dice «Vas bien», que lo diga.

    El titular mira los últimos 5 días; la decisión de hoy en Ahora mira esta mañana.
    """
    if not dias or estado['respuesta'] in ('parada', 'descansa', 'te_pasas'):
        return None
    hoy_d = dias[-1]
    if hoy_d['nivel'] not in ('rojo', 'ambar'):
        return None
    detalle = (hoy_d.get('detalle') or '').replace('Ese día: ', '', 1)
    base = f'Esta mañana amaneces {hoy_d["nombre"].lower()}'
    return f'{base}: {detalle}' if detalle else f'{base}.'


def fecha_texto(d):
    """'domingo 25 de octubre', sin depender del idioma del servidor."""
    return f'{DIAS_SEMANA[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def contexto_panel(cliente, hoy):
    from entrenos.services.estado_carga_service import TITULOS, estado_carga, parada_en

    estado = estado_carga(cliente, hoy)
    dias = dias_recientes(estado, cliente)
    variab, pul = variabilidad(cliente, hoy), pulso(cliente, hoy)
    return {
        'estado': estado,
        'titulo': TITULOS[estado['respuesta']],
        'preguntas': tres_preguntas(estado),
        'descanso_plan': descanso_del_plan(cliente, hoy),
        'camino': camino(cliente, hoy),
        'variabilidad': variab,
        'pulso': pul,
        'sueno': sueno(cliente, hoy),
        'lectura_cruzada': lectura_cruzada(variab, pul),
        'aviso_hoy': aviso_hoy(estado, dias),
        'dias_energia': [d for d in dias if d['nombre'].startswith('Energía')],
        'frase_camino': frase_camino(cliente, hoy),
        'dias': dias,
        'parada': parada_en(cliente, hoy),
        'fecha_texto': fecha_texto(hoy),
    }
