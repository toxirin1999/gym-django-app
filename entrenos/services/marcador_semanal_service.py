"""Marcador semanal por músculo (26-oct-2026, semana adaptativa, paso 2).

Solo muestra: series de los últimos 7 días por músculo frente a su objetivo.

- **Objetivo**: un margen, no un número. El mínimo es 10 series (evidencia)
  o lo que pide tu plan si es menos (core, trapecio…); el máximo, lo que pide
  tu plan con 4 de margen, sin pasar de 20.
- **Hechas**: series de trabajo reales de los últimos 7 días. Las indirectas
  cuentan la mitad (un press de pecho es medio tríceps; un remo, medio bíceps).
- **Frase**: solo si hay algo que decir (falta llegar al mínimo, o te pasas).
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


def _visible(grupo):
    return NOMBRES.get(grupo, grupo[:1].upper() + grupo[1:])


def series_plan_semana(cliente, hoy):
    """{grupo: series} que pide el plan de la semana de ``hoy`` (lunes a domingo)."""
    from entrenos.services.sesion_recomendada import _build_planificador, _es_descanso, _normalizar_entrenamiento

    planificador = _build_planificador(cliente)
    lunes = hoy - timedelta(days=hoy.weekday())
    plan = Counter()
    sesiones = []
    for i in range(7):
        ent = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(lunes + timedelta(days=i)))
        if not ent or _es_descanso(ent):
            continue
        grupos = set()
        for ej in ent.get('ejercicios') or []:
            g = _canon(ej.get('grupo_muscular'), ej.get('nombre'))
            if g:
                plan[g] += int(ej.get('series') or 0)
                grupos.add(g)
        sesiones.append({'nombre': (ent.get('rutina_nombre') or '').strip(), 'grupos': grupos})
    return plan, sesiones


def series_hechas(cliente, hoy, dias=7):
    from entrenos.models import SerieRealizada

    hechas = Counter()
    for s in SerieRealizada.objects.filter(
        entreno__cliente=cliente, completado=True, es_aproximacion=False,
        entreno__fecha__gte=hoy - timedelta(days=dias - 1), entreno__fecha__lte=hoy,
    ).select_related('ejercicio'):
        g = _canon(s.ejercicio.grupo_muscular, s.ejercicio.nombre)
        if not g:
            continue
        hechas[g] += 1
        recibe = _indirecto(s.ejercicio.nombre, g)
        if recibe:
            hechas[recibe] += 0.5
    return hechas


def _pendientes(cliente, hoy, sesiones):
    """Nombres de las sesiones de la semana que aún no has hecho, con sus grupos."""
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado

    lunes = hoy - timedelta(days=hoy.weekday())
    hechas = Counter(
        (e.rutina.nombre or '').strip().casefold()
        for e in EntrenoRealizado.objects.filter(cliente=cliente, rutina__isnull=False).filter(
            Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=hoy)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=hoy)
        ).select_related('rutina')
    )
    pendientes = []
    for s in sesiones:
        clave = s['nombre'].casefold()
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
    hechas = series_hechas(cliente, hoy)
    pendientes = _pendientes(cliente, hoy, sesiones)

    filas = []
    for grupo, en_plan in sorted(plan.items(), key=lambda kv: (-kv[1], kv[0])):
        minimo = min(MINIMO_EVIDENCIA, en_plan)
        maximo = min(MAXIMO_EVIDENCIA, max(en_plan, MINIMO_EVIDENCIA) + MARGEN)
        h = hechas.get(grupo, 0)
        estado = 'bajo' if h < minimo else ('alto' if h > maximo else 'ok')
        cubren = [_dia(s['nombre']) for s in pendientes if grupo in s['grupos']]
        filas.append({
            'grupo': _visible(grupo), 'clave': grupo, 'hechas': h, 'minimo': minimo, 'maximo': maximo,
            'plan': en_plan, 'estado': estado, 'cubren': cubren,
            'pct': min(100, round(h / maximo * 100)) if maximo else 0,
            'pct_min': min(100, round(minimo / maximo * 100)) if maximo else 0,
        })
    return {'filas': filas, 'frase': _frase(filas)}


def _num(valor):
    return str(int(valor)) if float(valor).is_integer() else f'{valor:g}'.replace('.', ',')


def _frase(filas):
    """Lo que hay que decir de la semana, o None si va bien."""
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
        return f"Te faltan {_num(falta)} series de {f['grupo'].lower()} para el mínimo: el {dias} las cubre."
    altos = [f for f in filas if f['estado'] == 'alto']
    if altos:
        f = altos[0]
        return (f"{f['grupo']} va por encima ({_num(f['hechas'])} de {f['minimo']}–{f['maximo']}): "
                f"más series no suman, solo cansan.")
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
