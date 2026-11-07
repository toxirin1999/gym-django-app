"""Marcador semanal por músculo (26-oct-2026, semana adaptativa, paso 2).

Solo muestra: series de los últimos 7 días por músculo frente a su objetivo.

- **Objetivo**: un margen, no un número. El mínimo es 10 series (evidencia)
  o lo que pide tu plan si es menos (core, trapecio…); el máximo, lo que pide
  tu plan con 4 de margen, sin pasar de 20.
- **Hechas**: series de trabajo reales de los últimos 7 días. Las indirectas
  cuentan la mitad (un press de pecho es medio tríceps; un remo, medio bíceps).
- **Frase**: solo si hay algo que decir (falta llegar al mínimo, o te pasas).

7-nov-2026: el plan y lo hecho se cuentan igual (antes el plan solo contaba
directas y lo hecho sumaba las indirectas: tríceps "17 de 9–14" con 9
directas). Cada fila dice cuántas son directas y cuántas indirectas. El
Farmer Walk cuenta como antebrazo y medio trapecio, en el plan y en lo hecho
(antes el plan lo ponía en trapecio un día y lo hecho, en antebrazo).
"""

from collections import Counter, defaultdict
from datetime import timedelta
import unicodedata

MINIMO_EVIDENCIA = 10
MAXIMO_EVIDENCIA = 20
MARGEN = 4

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
        for ej in ent.get('ejercicios') or []:
            try:
                n = int(ej.get('series') or 0)
            except (TypeError, ValueError):
                n = 0
            grupo = grupo_catalogo.get(_limpio(ej.get('nombre'))) or ej.get('grupo_muscular')
            for g, peso in grupos_de_serie(ej.get('nombre'), grupo):
                plan[g] += n * peso
                if peso == 1.0:
                    grupos.add(g)
        sesiones.append({'nombre': (ent.get('rutina_nombre') or '').strip(), 'grupos': grupos})
    return plan, sesiones


def series_hechas_detalle(cliente, desde, hasta):
    """(total, directas, indirectas) por grupo entre ``desde`` y ``hasta``, ambos incluidos.

    Series de trabajo confirmadas; las indirectas ya van a la mitad.
    """
    from entrenos.models import SerieRealizada

    total, directas, indirectas = Counter(), Counter(), Counter()
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, completado=True, es_aproximacion=False,
        entreno__fecha__gte=desde, entreno__fecha__lte=hasta,
    ).select_related('ejercicio'):
        for g, peso in grupos_de_serie(s.ejercicio.nombre, s.ejercicio.grupo_muscular):
            total[g] += peso
            (directas if peso == 1.0 else indirectas)[g] += peso
    return total, directas, indirectas


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
        for e in EntrenoRealizado.objects.filter(cliente=cliente, rutina__isnull=False).filter(
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


def marcador_semanal(cliente, hoy):
    """{'filas': [...], 'frase': str|None}. Filas ordenadas por series del plan."""
    plan, sesiones = series_plan_semana(cliente, hoy)
    if not plan:
        return {'filas': [], 'frase': None}
    # 2-nov-2026: en la semana de descarga se cuenta desde el lunes y contra la
    # descarga; los últimos 7 días eran la semana normal anterior y el mínimo
    # de una semana normal ("te faltan 7 de pecho") no tiene sentido aquí.
    descarga = False
    try:
        from entrenos.services.sesion_descarga_service import semana_plan_descarga
        descarga = semana_plan_descarga(cliente.id, hoy)
    except Exception:  # noqa: BLE001
        pass
    dias = hoy.weekday() + 1 if descarga else 7
    desde = hoy - timedelta(days=dias - 1)
    hechas, directas, indirectas = series_hechas_detalle(cliente, desde, hoy)
    pendientes = _pendientes(cliente, hoy, sesiones)

    filas = []
    for grupo, en_plan in sorted(plan.items(), key=lambda kv: (-kv[1], kv[0])):
        ref = int(en_plan + 0.5)  # el margen, en series enteras
        minimo = min(MINIMO_EVIDENCIA, ref)
        maximo = min(MAXIMO_EVIDENCIA, max(ref, MINIMO_EVIDENCIA) + MARGEN)
        if descarga:
            minimo, maximo = 0, ref + 2
        h = hechas.get(grupo, 0)
        estado = 'bajo' if h < minimo else ('alto' if h > maximo else 'ok')
        cubren = [_dia(s['nombre']) for s in pendientes if grupo in s['grupos']]
        filas.append({
            'grupo': _visible(grupo), 'clave': grupo, 'hechas': h, 'minimo': minimo, 'maximo': maximo,
            'directas': directas.get(grupo, 0), 'indirectas': indirectas.get(grupo, 0),
            'plan': en_plan, 'estado': estado, 'cubren': cubren,
            'pct': min(100, round(h / maximo * 100)) if maximo else 0,
            'pct_min': min(100, round(minimo / maximo * 100)) if maximo else 0,
        })
    if descarga:
        sobra = _frase_sobra(filas)
        frase = ('Semana de descarga: aquí no hay mínimos que cumplir, se cuenta desde el lunes '
                 'frente a lo que pide la descarga.' + (f' {sobra}' if sobra else ''))
        return {'filas': filas, 'frase': frase, 'descarga': True, 'sobra': sobra,
                'periodo': f'Esta semana (descarga) · {_rango(desde, hoy)}'}
    return {'filas': filas, 'frase': _frase(filas), 'descarga': False,
            'periodo': f'Últimos 7 días · {_rango(desde, hoy)}'}


def _rango(desde, hasta):
    return f'{desde:%d/%m}–{hasta:%d/%m}'


def _num(valor):
    return str(int(valor)) if float(valor).is_integer() else f'{valor:g}'.replace('.', ',')


def _frase(filas):
    """Lo que hay que decir de la semana, o None si va bien.

    31-oct-2026: lo que falta y, además, lo que ya sobra (tríceps 17 de 9–14
    con el Día 5 por delante). Solo avisa; no cambia la sesión.
    """
    falta = _frase_falta(filas)
    sobra = _frase_sobra(filas)
    if falta and sobra:
        return f'{falta} {sobra}'
    return falta or sobra


def _frase_sobra(filas):
    altos = sorted((f for f in filas if f['estado'] == 'alto'),
                   key=lambda x: x['hechas'] - x['maximo'], reverse=True)
    if not altos:
        return None
    con_dia = [f for f in altos if f['cubren']]
    if con_dia:
        nombres = [f"{f['grupo'].lower()} ({_num(f['hechas'])} de {f['minimo']}–{f['maximo']})" for f in con_dia[:3]]
        lista = nombres[0] if len(nombres) == 1 else ', '.join(nombres[:-1]) + ' y ' + nombres[-1]
        dias = ' y el '.join(sorted({d for f in con_dia[:3] for d in f['cubren']})[:2])
        verbo = 'va' if len(nombres) == 1 else 'van'
        return (f"Ya {verbo} por encima del máximo {lista}, y el {dias} lo vuelve a cargar: "
                f"esas series no suman, solo cansan.")
    f = altos[0]
    return (f"{f['grupo']} va por encima ({_num(f['hechas'])} de {f['minimo']}–{f['maximo']}): "
            f"más series no suman, solo cansan.")


def _frase_falta(filas):
    sin_cubrir = [f for f in filas if f['estado'] == 'bajo' and not f['cubren']]
    if sin_cubrir:
        f = sin_cubrir[0]
        return (f"{f['grupo']} se queda en {_num(f['hechas'])} series de {f['minimo']}–{f['maximo']} "
                f"y no quedan días esta semana que lo trabajen.")
    bajos = [f for f in filas if f['estado'] == 'bajo']
    if bajos:
        f = max(bajos, key=lambda x: x['minimo'] - x['hechas'])
        falta = f['minimo'] - f['hechas']
        dias = ' y el '.join(f['cubren'][:2])
        verbo = 'las cubren' if len(f['cubren'][:2]) > 1 else 'las cubre'
        return f"Te faltan {_num(falta)} series de {f['grupo'].lower()} para el mínimo: el {dias} {verbo}."
    return None


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
