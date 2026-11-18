"""Marcador semanal por músculo (26-oct-2026; rehecho el 18-nov-2026).

Un solo periodo para todo: la semana de calendario en curso (lunes a domingo).

- **Hechas**: series de trabajo reales desde el lunes hasta hoy. Las
  indirectas cuentan la mitad (un press de pecho es medio tríceps; un remo,
  medio bíceps).
- **Pendientes**: lo que aportan de verdad las sesiones de la semana que aún
  no has hecho (series de cada una para ese músculo), no solo si lo tocan.
- **Plan**: la referencia es lo que pide el planificador para esa misma
  semana, contado igual. Se dice de dónde sale. Ya no hay un mínimo de 10 ni
  un máximo de «plan + 4»: no estaban justificados.
- **Frase**: solo hechos (llevas X, las pendientes aportan Y, el plan pide Z).

7-nov-2026: el plan y lo hecho se cuentan igual. El Farmer Walk cuenta como
antebrazo y medio trapecio, en el plan y en lo hecho.
"""

from collections import Counter, defaultdict
from datetime import timedelta
import unicodedata

# 18-nov-2026: a partir de cuántas series sobre el plan se avisa de que se supera.
# Solo informa; no es una norma de entrenamiento ni propone nada por sí sola.
MARGEN_SOBRE_PLAN = 4

# (palabras del ejercicio, grupo directo, grupo que recibe media serie)
INDIRECTOS = (
    (('press', 'fondos', 'dips', 'convergent', 'flexion'), 'pecho', 'tríceps'),
    (('jalon', 'remo', 'dominada', 'pull'), 'espalda', 'bíceps'),
    (('sentadilla', 'prensa', 'hack', 'zancada', 'bulgara', 'lunge', 'step'), 'cuádriceps', 'glúteos'),
    (('peso muerto', 'rumano', 'buenos dias'), 'isquios', 'glúteos'),
    (('press', 'arnold'), 'hombros', 'tríceps'),
)
NO_INDIRECTO = ('press frances', 'cable fly', 'aperturas', 'pull-over', 'pullover', 'brazos rectos')

NOMBRES = {'core': 'Core', 'trapecio': 'Trapecio'}


def _limpio(texto):
    texto = unicodedata.normalize('NFD', str(texto or '').casefold())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def _canon(grupo, nombre=''):
    from entrenos.services.criterios_entrenador_service import grupo_de
    return grupo_de(grupo) or grupo_de(nombre) or (_limpio(grupo).strip() or None)


def _indirecto(nombre, directo):
    n = _limpio(nombre)
    if any(x in n for x in NO_INDIRECTO):
        return None
    for palabras, grupo, recibe in INDIRECTOS:
        if grupo == directo and any(p in n for p in palabras):
            return recibe
    return None


def es_farmer(nombre):
    n = _limpio(nombre)
    return 'farmer' in n or 'granjero' in n


def grupos_de_serie(nombre, grupo):
    """[(grupo, peso)]: el directo cuenta 1 y el indirecto 0,5 (7-nov-2026)."""
    if es_farmer(nombre):
        return [('antebrazos', 1.0), ('trapecio', 0.5)]
    g = _canon(grupo, nombre)
    if not g:
        return []
    out = [(g, 1.0)]
    recibe = _indirecto(nombre, g)
    if recibe:
        out.append((recibe, 0.5))
    return out


def _visible(grupo):
    return NOMBRES.get(grupo, grupo[:1].upper() + grupo[1:])


def _grupos_catalogo(nombres):
    """{nombre limpio: grupo_muscular} del catálogo (EjercicioBase) para esos nombres."""
    from rutinas.models import EjercicioBase
    nombres = {n for n in nombres if n}
    if not nombres:
        return {}
    limpios = {_limpio(n) for n in nombres}
    out = {}
    for nombre, grupo in EjercicioBase.objects.filter(nombre__in=nombres).values_list('nombre', 'grupo_muscular'):
        if grupo and _limpio(nombre) in limpios:
            out[_limpio(nombre)] = grupo
    return out


def series_plan_semana(cliente, hoy):
    """{grupo: series} que pide el plan de la semana de ``hoy`` (lunes a domingo)."""
    from entrenos.services.sesion_recomendada import _build_planificador, _es_descanso, _normalizar_entrenamiento

    planificador = _build_planificador(cliente)
    lunes = hoy - timedelta(days=hoy.weekday())
    plan = Counter()
    sesiones = []
    entrenos = []
    for i in range(7):
        ent = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(lunes + timedelta(days=i)))
        if not ent or _es_descanso(ent):
            continue
        entrenos.append(ent)
    # 8-nov-2026: el grupo de cada ejercicio sale de donde sale en lo hecho (el
    # catálogo de ejercicios); el planificador puede tenerlo en otro (búlgara:
    # glúteo en el plan y cuádriceps al registrarla).
    grupo_catalogo = _grupos_catalogo(
        {ej.get('nombre') for ent in entrenos for ej in (ent.get('ejercicios') or [])})
    for ent in entrenos:
        grupos = set()
        series = Counter()
        por_ejercicio = defaultdict(list)
        for ej in ent.get('ejercicios') or []:
            try:
                n = int(ej.get('series') or 0)
            except (TypeError, ValueError):
                n = 0
            grupo = grupo_catalogo.get(_limpio(ej.get('nombre'))) or ej.get('grupo_muscular')
            for g, peso in grupos_de_serie(ej.get('nombre'), grupo):
                plan[g] += n * peso
                series[g] += n * peso
                por_ejercicio[g].append((ej.get('nombre'), n * peso))
                if peso == 1.0:
                    grupos.add(g)
        # 18-nov-2026: las series que aporta cada sesión a cada músculo (no solo si lo toca).
        sesiones.append({'nombre': (ent.get('rutina_nombre') or '').strip(), 'grupos': grupos,
                         'series': dict(series), 'ejercicios': dict(por_ejercicio)})
    return plan, sesiones


def _fecha_real_entre(desde, hasta, prefijo='entreno__'):
    """Filtro por el día en que se hizo la sesión (``fecha_ejecucion``; si no consta, ``fecha``).

    ``fecha`` es el día del plan al que pertenece la rutina; una sesión movida se hizo otro día.
    Lo hecho y lo pendiente de la semana cuentan por el día real (18-nov-2026).
    """
    from django.db.models import Q
    return (Q(**{f'{prefijo}fecha_ejecucion__gte': desde, f'{prefijo}fecha_ejecucion__lte': hasta})
            | Q(**{f'{prefijo}fecha_ejecucion__isnull': True, f'{prefijo}fecha__gte': desde,
                   f'{prefijo}fecha__lte': hasta}))


def series_hechas_detalle(cliente, desde, hasta):
    """(total, directas, indirectas) por grupo entre ``desde`` y ``hasta``, ambos incluidos.

    Series de trabajo confirmadas; las indirectas ya van a la mitad.
    """
    from entrenos.models import SerieRealizada

    total, directas, indirectas = Counter(), Counter(), Counter()
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, completado=True, es_aproximacion=False,
    ).filter(_fecha_real_entre(desde, hasta)).select_related('ejercicio'):
        for g, peso in grupos_de_serie(s.ejercicio.nombre, s.ejercicio.grupo_muscular):
            total[g] += peso
            (directas if peso == 1.0 else indirectas)[g] += peso
    return total, directas, indirectas


def series_hechas_por_sesion(cliente, desde, hasta):
    """{grupo: [{'dia', 'fecha', 'series'}]} de las series hechas, por sesión (18-nov-2026)."""
    from entrenos.models import SerieRealizada

    acumulado = {}
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, completado=True, es_aproximacion=False,
    ).filter(_fecha_real_entre(desde, hasta)).select_related('ejercicio', 'entreno', 'entreno__rutina'):
        rutina = getattr(s.entreno, 'rutina', None)
        dia = _dia(rutina.nombre) if rutina is not None else 'Sesión'
        for g, peso in grupos_de_serie(s.ejercicio.nombre, s.ejercicio.grupo_muscular):
            clave = (g, s.entreno_id)
            fila = acumulado.setdefault(clave, {'dia': dia, 'fecha': s.entreno.fecha, 'series': 0})
            fila['series'] += peso
    out = defaultdict(list)
    for (g, _eid), fila in acumulado.items():
        out[g].append(fila)
    for g in out:
        out[g].sort(key=lambda f: f['fecha'])
    return dict(out)


def _hecho_por_ejercicio(cliente, desde, hasta):
    """{(clave de rutina, ejercicio limpio): {grupo: series}} de lo hecho entre ``desde`` y ``hasta``."""
    from entrenos.models import SerieRealizada
    from entrenos.services.nombre_rutina import clave_rutina

    out = defaultdict(Counter)
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, completado=True, es_aproximacion=False,
    ).filter(_fecha_real_entre(desde, hasta)).select_related('ejercicio', 'entreno__rutina'):
        rutina = getattr(s.entreno, 'rutina', None)
        clave = clave_rutina(rutina.nombre) if rutina is not None else ''
        for g, peso in grupos_de_serie(s.ejercicio.nombre, s.ejercicio.grupo_muscular):
            out[(clave, _limpio(s.ejercicio.nombre))][g] += peso
    return out


def _desvios(sesiones, pendientes, hecho, grupo):
    """Dónde lo hecho de las sesiones YA hechas se separa de lo que el plan pedía para ese músculo.

    [{'dia', 'ejercicio', 'plan', 'hecho'}]: faltó (hecho < plan) o se hizo de más / otro ejercicio
    (plan 0). Explica por qué el plan de la semana y lo hecho más lo pendiente no coinciden.
    """
    from entrenos.services.nombre_rutina import clave_rutina

    pendientes_ids = {id(s) for s in pendientes}
    out = []
    for s in sesiones:
        if id(s) in pendientes_ids:
            continue
        clave = clave_rutina(s['nombre'])
        previstos = set()
        for nombre, series in (s.get('ejercicios') or {}).get(grupo, []):
            limpio = _limpio(nombre)
            previstos.add(limpio)
            hecho_aqui = hecho.get((clave, limpio), {}).get(grupo, 0)
            if abs(series - hecho_aqui) > 1e-9:
                out.append({'dia': _dia(s['nombre']), 'ejercicio': nombre, 'plan': series, 'hecho': hecho_aqui})
        for (c, limpio), grupos in hecho.items():
            if c == clave and limpio not in previstos and grupos.get(grupo, 0) > 0:
                out.append({'dia': _dia(s['nombre']), 'ejercicio': limpio.title(), 'plan': 0,
                            'hecho': grupos[grupo]})
    return out


# ─────────────────────────────────────────────────────────────
# Referencia seguida (18-nov-2026): cada sesión hecha se mide contra la versión
# que mostró la app ese día, no contra el planificador de hoy.
# ─────────────────────────────────────────────────────────────

DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
# Ejercicios cuya presencia en una versión sigue sin explicarse (18-nov-2026, repaso del Día 3).
CAUSA_PENDIENTE = ('machine shoulder press', 'press arnold')


def _series_ejercicio(ej):
    try:
        return int(ej.get('series') or 0)
    except (TypeError, ValueError):
        return 0


def _prescrito_de_version(snapshot, sustituciones, grupo_catalogo):
    """[(nombre, grupo, series)] que pedía la versión seguida, con las sustituciones aplicadas.

    Un ejercicio sustituido se cambia por el sustituto con las mismas series.
    """
    cambio = {_limpio(orig): nuevo for orig, nuevo in sustituciones}
    out = []
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        nombre = ej.get('nombre')
        n = _series_ejercicio(ej)
        if not nombre or not n:
            continue
        sustituto = cambio.get(_limpio(nombre))
        if sustituto:
            out.append((sustituto, grupo_catalogo.get(_limpio(sustituto)), n))
        else:
            out.append((nombre, grupo_catalogo.get(_limpio(nombre)) or ej.get('grupo_muscular'), n))
    return out


def _sesiones_seguidas(cliente, lunes, hoy, sesiones_plan):
    """Una entrada por sesión hecha esta semana, con la versión que se siguió.

    {'entreno_id','dia','fecha','sin_version','reducida','hora_version','regenerada',
     'prescrito': [(nombre, grupo, series)], 'hechos': {nombre limpio: {grupo: series}},
     'hechos_nombres': set, 'sustituciones': [(orig, nuevo)], 'completa': bool}
    """
    from django.db.models import Q
    from django.utils import timezone
    from entrenos.models import EntrenoRealizado, GymDecisionVersion, SerieRealizada
    from entrenos.services.nombre_rutina import clave_rutina

    entrenos = list(
        EntrenoRealizado.objects.filter(cliente=cliente, rutina__isnull=False).filter(
            Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=hoy)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=hoy)
        ).select_related('rutina', 'gym_decision_version').order_by('fecha_ejecucion', 'fecha', 'id')
    )
    if not entrenos:
        return []
    ids = [e.id for e in entrenos]
    nombres = set()
    hechos = defaultdict(lambda: defaultdict(Counter))
    for sr in SerieRealizada.objects.filter(entreno_id__in=ids, completado=True, es_aproximacion=False
                                            ).select_related('ejercicio'):
        nombres.add(sr.ejercicio.nombre)
        for g, peso in grupos_de_serie(sr.ejercicio.nombre, sr.ejercicio.grupo_muscular):
            hechos[sr.entreno_id][_limpio(sr.ejercicio.nombre)][g] += peso
    sustit = defaultdict(list)
    hechos_nombres = defaultdict(set)
    from entrenos.models import EjercicioRealizado
    for er in EjercicioRealizado.objects.filter(entreno_id__in=ids, completado=True):
        hechos_nombres[er.entreno_id].add(_limpio(er.nombre_ejercicio))
        if (er.sustituye_a or '').strip():
            sustit[er.entreno_id].append((er.sustituye_a.strip(), er.nombre_ejercicio))
    versiones = defaultdict(list)
    for v in GymDecisionVersion.objects.filter(cliente=cliente, fecha__in={e.fecha for e in entrenos}).order_by('version'):
        versiones[v.fecha].append(v)

    out = []
    for e in entrenos:
        v = e.gym_decision_version
        snap = (getattr(v, 'snapshot', None) or {}) if v else {}
        ejercicios_snap = (snap.get('entrenamiento') or {}).get('ejercicios') or []
        sin_version = not ejercicios_snap
        grupo_catalogo = _grupos_catalogo(
            {ej.get('nombre') for ej in ejercicios_snap} | {n for _o, n in sustit[e.id]})
        prescrito = [] if sin_version else _prescrito_de_version(snap, sustit[e.id], grupo_catalogo)
        completa = (not sin_version) and all(_limpio(n) in hechos_nombres[e.id] for n, _g, _s in prescrito)
        otras = [x for x in versiones.get(e.fecha, []) if v is None or x.pk != v.pk]
        regenerada = None
        if otras:
            ultima = max(otras, key=lambda x: x.version)
            if v is None or ultima.version > v.version:
                n_ej = len((ultima.snapshot.get('entrenamiento') or {}).get('ejercicios') or [])
                regenerada = {'hora': timezone.localtime(ultima.creado_en).strftime('%H:%M'), 'ejercicios': n_ej}
        fecha = e.fecha_ejecucion or e.fecha
        out.append({
            'entreno_id': e.id, 'dia': _dia(e.rutina.nombre), 'clave': clave_rutina(e.rutina.nombre),
            'fecha': fecha, 'sin_version': sin_version,
            'reducida': snap.get('estado') == 'version_reducida',
            'hora_version': timezone.localtime(v.creado_en).strftime('%H:%M') if v else None,
            'regenerada': regenerada, 'prescrito': prescrito, 'sustituciones': sustit[e.id],
            'hechos': {k: dict(c) for k, c in hechos[e.id].items()}, 'completa': completa,
            'n_prescritos': len(prescrito), 'n_hechos_prescritos': sum(
                1 for n, _g, _s in prescrito if _limpio(n) in hechos_nombres[e.id]),
        })
    return out


def _linea_entrenador(seguidas):
    """Un ajuste prescrito (versión reducida, sustitución) o un hueco de datos; None si no hay nada que contar."""
    if not seguidas:
        return None
    ajustes = []
    for s in seguidas:
        dia = DIAS_SEMANA[s['fecha'].weekday()]
        if s['reducida']:
            ajustes.append(f"la versión reducida del {dia}")
        for orig, nuevo in s['sustituciones']:
            ajustes.append(f"la sustitución {_corto(orig)} → {_corto(nuevo)} del {dia}")
    sin = [s for s in seguidas if s['sin_version']]
    partes = []
    n = len(seguidas)
    todas = all(s['completa'] for s in seguidas)
    if ajustes:
        if todas:
            numero = {1: 'la sesión', 2: 'las dos sesiones', 3: 'las tres sesiones', 4: 'las cuatro sesiones',
                      5: 'las cinco sesiones'}.get(n, f'las {n} sesiones')
            partes.append(f"Completaste {numero} con {_unir(ajustes)}.")
        else:
            partes.append(f"Esta semana hubo {_unir(ajustes)}.")
    if sin:
        partes.append("Sin versión histórica para comprobar " + _unir(
            [f"el {DIAS_SEMANA[s['fecha'].weekday()]}" for s in sin]) + '.')
    return ' '.join(partes) or None


def _corto(nombre):
    """«Sissy Squat» → «Sissy»; «Sentadilla Hack» → «Hack» (para la línea del entrenador)."""
    palabras = [w for w in str(nombre or '').split() if _limpio(w) not in ('squat', 'sentadilla')]
    return ' '.join(palabras) or str(nombre or '')


def _unir(items):
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' y ' + items[-1]


def _contrib(nombre, grupo_ej, n, grupo):
    """Lo que aporta ``n`` series de ese ejercicio al músculo ``grupo`` (directa 1, indirecta 0,5)."""
    return sum(p for g, p in grupos_de_serie(nombre, grupo_ej) if g == grupo) * n


def _detalle_musculo(grupo, seguidas, sesiones, pendientes):
    """Desglose por sesión y ejercicio de un músculo y su objetivo aplicable (18-nov-2026).

    Las sesiones hechas se miden contra la versión que se siguió; las pendientes, contra el plan
    vigente (provisional). Si una sesión no tiene versión guardada no se comprueba nada.
    """
    sesiones_hechas = []
    objetivo_hecho = 0.0
    hechas_total = 0.0
    diferencias = []
    plan_por_clave = defaultdict(list)
    pendientes_ids = {id(x) for x in pendientes}
    for sp in sesiones:
        if id(sp) not in pendientes_ids:
            plan_por_clave[_clave(sp['nombre'])].append(sp)

    for sg in seguidas:
        hecho_sesion = sum(c.get(grupo, 0) for c in sg['hechos'].values())
        hechas_total += hecho_sesion
        fila = {'dia': sg['dia'], 'fecha': sg['fecha'], 'hechas': hecho_sesion,
                'sin_version': sg['sin_version'], 'reducida': sg['reducida'],
                'sustituciones': [(o, n) for o, n in sg['sustituciones']], 'ejercicios': []}
        if sg['sin_version']:
            objetivo_hecho += hecho_sesion
            fila['ejercicios'] = [{'nombre': n.title(), 'hecho': c[grupo]}
                                  for n, c in sg['hechos'].items() if c.get(grupo)]
            if hecho_sesion or fila['ejercicios']:
                sesiones_hechas.append(fila)
            continue
        previsto_ids = set()
        for nombre, grupo_ej, n in sg['prescrito']:
            aporte = _contrib(nombre, grupo_ej, n, grupo)
            if not aporte:
                continue
            previsto_ids.add(_limpio(nombre))
            fila['ejercicios'].append({
                'nombre': nombre, 'series': n, 'previsto': aporte,
                'hecho': sg['hechos'].get(_limpio(nombre), {}).get(grupo, 0)})
            objetivo_hecho += aporte
        for limpio, c in sg['hechos'].items():
            if limpio not in previsto_ids and c.get(grupo):
                fila['ejercicios'].append({'nombre': limpio.title(), 'series': None, 'previsto': 0,
                                           'hecho': c[grupo], 'de_mas': True})
        if fila['ejercicios'] or hecho_sesion:
            sesiones_hechas.append(fila)
        # Diferencia con el plan vigente de esa misma sesión (solo informa).
        candidatas = plan_por_clave.get(sg['clave']) or []
        plan_sesion = candidatas.pop(0) if candidatas else None
        if plan_sesion is None:
            continue
        plan_ej = {_limpio(nom): v for nom, v in (plan_sesion.get('ejercicios') or {}).get(grupo, [])}
        cambio = {_limpio(o): n for o, n in sg['sustituciones']}
        usados = set()
        for nombre, grupo_ej, n in sg['prescrito']:
            aporte = _contrib(nombre, grupo_ej, n, grupo)
            limpio = _limpio(nombre)
            origen = next((o for o, nuevo in cambio.items() if _limpio(nuevo) == limpio), None)
            ref = plan_ej.get(origen if origen in plan_ej else limpio, 0)
            usados.add(origen if origen in plan_ej else limpio)
            if abs(aporte - ref) < 1e-9:
                continue
            if origen is not None:
                texto = f'sustitución: {nombre}'
            elif ref == 0:
                texto = f'la versión que seguiste traía {nombre} ({n}) y el plan actual no'
            elif sg['reducida']:
                texto = 'versión reducida por la app'
            else:
                texto = f'{nombre}: {_num(aporte)} frente a {_num(ref)}'
            diferencias.append({'dia': sg['dia'], 'texto': texto, 'valor': aporte - ref,
                                'causa_pendiente': ref == 0 and _limpio(nombre) in CAUSA_PENDIENTE})
        for limpio, v in plan_ej.items():
            if limpio not in usados and v:
                nombre = next((nom for nom, _v in plan_sesion['ejercicios'][grupo] if _limpio(nom) == limpio), limpio)
                diferencias.append({'dia': sg['dia'], 'texto': f'la versión que seguiste no traía {nombre} ({_num(v)})',
                                    'valor': -v, 'causa_pendiente': False})

    pend_detalle = []
    pend_total = 0.0
    for sp in pendientes:
        ejercicios = [{'nombre': nom, 'valor': v} for nom, v in (sp.get('ejercicios') or {}).get(grupo, []) if v]
        total = sp['series'].get(grupo, 0)
        if total:
            pend_total += total
            pend_detalle.append({'dia': _dia(sp['nombre']), 'series': total, 'ejercicios': ejercicios})
    return {
        'hechas': hechas_total, 'pendientes': pend_total, 'objetivo': objetivo_hecho + pend_total,
        'sesiones_hechas': sesiones_hechas, 'pendientes_detalle': pend_detalle, 'diferencias': diferencias,
    }


def _clave(nombre):
    from entrenos.services.nombre_rutina import clave_rutina
    return clave_rutina(nombre)


def series_hechas(cliente, hoy, dias=7):
    return series_hechas_detalle(cliente, hoy - timedelta(days=dias - 1), hoy)[0]


def _pendientes(cliente, hoy, sesiones):
    """Nombres de las sesiones de la semana que aún no has hecho, con sus grupos."""
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado

    lunes = hoy - timedelta(days=hoy.weekday())
    from entrenos.services.nombre_rutina import clave_rutina
    hechas = Counter(
        clave_rutina(e.rutina.nombre)
        for e in EntrenoRealizado.objects.filter(
            cliente=cliente, rutina__isnull=False,
            # Una sesión del plan de la semana pasada hecha hoy suma sus series, pero no cubre
            # una sesión pendiente de esta semana aunque se llame igual.
            fecha__gte=lunes,
        ).filter(
            Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=hoy)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=hoy)
        ).select_related('rutina')
    )
    pendientes = []
    for s in sesiones:
        clave = clave_rutina(s['nombre'])
        if hechas[clave] > 0:
            hechas[clave] -= 1
            continue
        pendientes.append(s)
    return pendientes


def _dia(nombre):
    from entrenos.services.sesion_recomendada import _etiqueta_dia
    return _etiqueta_dia(nombre) or nombre


def _estado_fila(hechas, plan, proyectadas):
    if proyectadas > plan + MARGEN_SOBRE_PLAN:
        return 'supera'
    if hechas >= plan:
        return 'completo'
    if proyectadas >= plan:
        return 'cubierto'
    return 'falta'


def marcador_semanal(cliente, hoy):
    """{'filas': [...], 'frase': str|None, 'periodo', 'referencia'}. Filas por series del plan."""
    plan, sesiones = series_plan_semana(cliente, hoy)
    if not plan:
        return {'filas': [], 'frase': None}
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    descarga = False
    try:
        from entrenos.services.sesion_descarga_service import semana_plan_descarga
        descarga = semana_plan_descarga(cliente.id, hoy)
    except Exception:  # noqa: BLE001
        pass
    hechas, directas, indirectas = series_hechas_detalle(cliente, lunes, hoy)
    por_sesion = series_hechas_por_sesion(cliente, lunes, hoy)
    pendientes = _pendientes(cliente, hoy, sesiones)
    hecho_ej = _hecho_por_ejercicio(cliente, lunes, hoy)
    seguidas = _sesiones_seguidas(cliente, lunes, hoy, sesiones)

    filas = []
    for grupo, en_plan in sorted(plan.items(), key=lambda kv: (-kv[1], kv[0])):
        h = hechas.get(grupo, 0)
        aportan = [{'dia': _dia(s['nombre']), 'series': s['series'].get(grupo, 0)}
                   for s in pendientes if s['series'].get(grupo, 0) > 0]
        pend = sum(a['series'] for a in aportan)
        proyectadas = h + pend
        escala = max(en_plan, proyectadas, 1)
        filas.append({
            'grupo': _visible(grupo), 'clave': grupo, 'hechas': h, 'plan': en_plan,
            'pendientes': pend, 'proyectadas': proyectadas,
            'directas': directas.get(grupo, 0), 'indirectas': indirectas.get(grupo, 0),
            'estado': _estado_fila(h, en_plan, proyectadas),
            'aportan': aportan, 'hechas_por_sesion': por_sesion.get(grupo, []),
            'desvios': _desvios(sesiones, pendientes, hecho_ej, grupo),
            'cubren': [a['dia'] for a in aportan],
            'pct': round(h / escala * 100),
            'pct_pend': round(min(pend, escala - min(h, escala)) / escala * 100),
            'pct_plan': round(en_plan / escala * 100),
        })
        # Vista móvil (18-nov-2026): barra a escala propia del músculo sobre su objetivo aplicable.
        det = _detalle_musculo(grupo, seguidas, sesiones, pendientes)
        esc = max(det['objetivo'], det['hechas'] + det['pendientes'], 1)
        filas[-1].update({
            'objetivo': det['objetivo'], 'detalle': det,
            'bar_hechas': round(det['hechas'] / esc * 100, 1),
            'bar_pend': round(det['pendientes'] / esc * 100, 1),
            'diferencia_plan': det['objetivo'] - en_plan,
        })
    dias_pend = [_dia(s['nombre']) for s in pendientes]
    referencia = {
        'texto': (f'Plan de la semana {_rango(lunes, domingo)} según el planificador: '
                  f'{len(sesiones)} sesiones, {len(pendientes)} sin hacer'
                  + (f' ({", ".join(dias_pend)})' if dias_pend else '')),
        'sesiones_plan': len(sesiones), 'sesiones_pendientes': dias_pend,
    }
    etiqueta = 'Semana de descarga' if descarga else 'Semana'
    sesiones_detalle = [{
        'dia': sg['dia'], 'fecha': sg['fecha'], 'estado': 'hecha', 'sin_version': sg['sin_version'],
        'reducida': sg['reducida'], 'hora_version': sg['hora_version'], 'regenerada': sg['regenerada'],
        'sustituciones': sg['sustituciones'], 'n_prescritos': sg['n_prescritos'],
        'n_hechos': sg['n_hechos_prescritos'],
    } for sg in seguidas] + [{
        'dia': _dia(sp['nombre']), 'estado': 'pendiente',
    } for sp in pendientes]
    return {'filas': filas, 'frase': _frase(filas), 'descarga': descarga, 'referencia': referencia,
            'linea_entrenador': _linea_entrenador(seguidas), 'sesiones_detalle': sesiones_detalle,
            'semana_rango': _rango(lunes, domingo), 'hasta_hoy': f'{DIAS_SEMANA[hoy.weekday()]} {hoy:%d/%m}',
            'periodo': f'{etiqueta} {_rango(lunes, domingo)} · hecho hasta hoy ({hoy:%d/%m})'}


def _rango(desde, hasta):
    return f'{desde:%d/%m}–{hasta:%d/%m}'


def _num(valor):
    return str(int(valor)) if float(valor).is_integer() else f'{valor:g}'.replace('.', ',')


def _frase(filas):
    """Solo hechos de la semana (llevas, aportan las pendientes, pide el plan), o None.

    18-nov-2026: sin juicios sobre si las series valen o no: el panel dice cuántas series hay,
    cuántas aportan de verdad las sesiones que quedan y qué pide el plan.
    """
    partes = []
    falta = [f for f in filas if f['estado'] == 'falta']
    if falta:
        f = max(falta, key=lambda x: x['plan'] - x['proyectadas'])
        partes.append(
            f"{f['grupo']}: llevas {_num(f['hechas'])} de {_num(f['plan'])} que pide el plan; "
            + (f"las sesiones pendientes ({' y '.join(f['cubren'])}) aportan {_num(f['pendientes'])}"
               if f['cubren'] else 'ninguna sesión pendiente lo trabaja')
            + f" y quedarías en {_num(f['proyectadas'])}.")
    supera = sorted((f for f in filas if f['estado'] == 'supera'),
                    key=lambda x: x['proyectadas'] - x['plan'], reverse=True)
    for f in supera[:2]:
        partes.append(
            f"{f['grupo']}: llevas {_num(f['hechas'])} y las pendientes suman {_num(f['pendientes'])} "
            f"({_num(f['proyectadas'])}); el plan de la semana pide {_num(f['plan'])}.")
    return ' '.join(partes) or None


from core.perfil_tramos import tramo_de


@tramo_de('marcador_semanal')
def marcador_cacheado(cliente, hoy):
    """El marcador, cacheado 10 minutos (genera la semana del plan)."""
    from django.core.cache import cache
    from entrenos.models import SerieRealizada

    ultima = SerieRealizada.objects.filter(entreno__cliente=cliente).order_by('-id').values_list('id', flat=True).first()
    clave = f'marcador_semanal_{cliente.id}_{hoy.isoformat()}_{ultima or 0}'
    datos = cache.get(clave)
    if datos is None:
        try:
            datos = marcador_semanal(cliente, hoy)
        except Exception:  # noqa: BLE001 — es un panel, no debe tumbar la página
            import logging
            logging.getLogger(__name__).exception('marcador_semanal falló')
            datos = {'filas': [], 'frase': None}
        cache.set(clave, datos, 600)
    return datos


SEMANAS_MEDIA = 4


def media_semanal_series(cliente, hoy, semanas=SEMANAS_MEDIA):
    """Media semanal de series por grupo en las últimas semanas completas sin descarga (7-nov-2026).

    Memoria enseñaba "series/sem" con las directas de los últimos 28 días
    divididas entre 4, con la descarga y las semanas a medias dentro (tríceps
    4,2 cuando una semana completa del bloque llevaba 9-10 directas). Ahora:
    semanas de lunes a domingo ya cerradas, sin las de descarga, contadas como
    el marcador de Plan (directas enteras, indirectas a la mitad).

    Devuelve {'grupos': {grupo: {'total', 'directas', 'indirectas'}},
              'semanas': n, 'desde': date, 'hasta': date} o None sin semanas.
    """
    from entrenos.models import SemanaPlanGym

    lunes_actual = hoy - timedelta(days=hoy.weekday())
    descarga = set(SemanaPlanGym.objects.filter(
        cliente=cliente, descarga=True, lunes__lt=lunes_actual,
    ).values_list('lunes', flat=True))
    lunes = []
    k = 1
    while len(lunes) < semanas and k <= semanas * 3:
        candidato = lunes_actual - timedelta(days=7 * k)
        if candidato not in descarga:
            lunes.append(candidato)
        k += 1
    if not lunes:
        return None
    total, directas, indirectas = Counter(), Counter(), Counter()
    for l in lunes:
        t, d, i = series_hechas_detalle(cliente, l, l + timedelta(days=6))
        total.update(t)
        directas.update(d)
        indirectas.update(i)
    n = len(lunes)
    grupos = {
        g: {'total': round(total[g] / n, 1), 'directas': round(directas[g] / n, 1),
            'indirectas': round(indirectas[g] / n, 1)}
        for g in total
    }
    return {'grupos': grupos, 'semanas': n, 'desde': min(lunes), 'hasta': max(lunes) + timedelta(days=6)}
