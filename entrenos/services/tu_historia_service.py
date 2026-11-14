"""Tu historia en el gym (14-nov-2026).

Panel al estilo de un resumen anual: lo acumulado, no lo que falta. Idea de
David: "no soy consciente del trabajo que hago; ¿ese esfuerzo se pierde en el
olvido?". Todo sale de los entrenos registrados; si un dato no existe, la
pantalla correspondiente no aparece.

Versión 2 (14-nov): mosaico de días, la vuelta, un entreno por etapa, la
descarga respetada, la serie que hoy es normal, el ejercicio que ha estado ahí
(primera y última vez) y nombres de ejercicio agrupados sin tildes ni mayúsculas.
Las toneladas pierden protagonismo (sin "día más grande").

Limpieza:
- Entrenos con volumen registrado (> 0 kg) o, sin volumen, con una duración
  creíble (hay sesiones reales de mayo de 2026 sin kg apuntados).
- Días con 3 registros o más se tratan como pruebas de la app (agosto de 2025).
- Duplicados del mismo día con el mismo volumen cuentan una vez.
- Duraciones fuera de 5-180 min se tratan como desconocidas; las horas de esas
  sesiones se estiman con la media de las conocidas.
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta

DUR_MIN, DUR_MAX = 5, 180
REGISTROS_DIA_PRUEBA = 3
KG_COCHE = 1500  # coche medio, para la equivalencia

# La serie que hoy es normal
SERIE_ANTIGUA_MIN_DIAS = 42   # la exigente, de hace al menos 6 semanas
SERIE_RECIENTE_DIAS = 35      # la de ahora, de las últimas 5 semanas
SERIE_ANTIGUA_RPE_MIN = 9
SERIE_MARGEN_RPE = 1.5        # al menos 1,5 puntos menos de RPE
SERIE_PESO_MAX = 1.25         # la reciente, como mucho un 25 % más pesada (misma serie, no otra máquina)

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago',
                'sep', 'oct', 'nov', 'dic']

_RE_FASE = re.compile(r'^\s*d[ií]a\s*\d+\s*[-—–]+\s*(.+?)\s*$', re.IGNORECASE)


@dataclass(frozen=True)
class Sesion:
    id: int
    fecha: date
    kg: float
    minutos: int | None
    nombre: str


# ── utilidades de texto ──────────────────────────────────────────────────────

def _num(valor, decimales=0):
    """Número a la española: 1.914 · 7,9."""
    texto = f'{valor:,.{decimales}f}'
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def _peso(valor):
    """62,5 · 60 (sin ",0")."""
    return _num(float(valor), 1).removesuffix(',0')


def _fecha_larga(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def _fecha_corta(d):
    return f'{d.day} de {MESES[d.month - 1]}'


def _mes_txt(anio, mes):
    return f'{MESES[mes - 1].capitalize()} {anio}'


def _mes_anio_corto(d):
    return f'{MESES_CORTOS[d.month - 1]} {str(d.year)[2:]}'


def clave_nombre(nombre):
    """Agrupa variantes de escritura: sin tildes, sin mayúsculas, espacios simples."""
    texto = unicodedata.normalize('NFKD', str(nombre or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.casefold().split())


def fase_de(nombre_rutina):
    """'Dia 3 - Hipertrofia — Metabólica' → 'Hipertrofia — Metabólica'."""
    m = _RE_FASE.match(nombre_rutina or '')
    if not m:
        return None
    return ' '.join(m.group(1).replace('_', ' ').split())


def _es_descarga(fase):
    return bool(fase) and 'descarga' in clave_nombre(fase)


# ── sesiones ─────────────────────────────────────────────────────────────────

def sesiones_limpias(cliente, hasta=None):
    from entrenos.models import EntrenoRealizado

    hasta = hasta or date.today()
    filas = list(
        EntrenoRealizado.objects.filter(cliente=cliente, fecha__lte=hasta)
        .order_by('fecha', 'id')
        .values('id', 'fecha', 'volumen_total_kg', 'duracion_minutos',
                'nombre_rutina_liftin', 'rutina__nombre')
    )
    por_dia = Counter(f['fecha'] for f in filas)
    vistos, sesiones = set(), []
    for f in filas:
        kg = float(f['volumen_total_kg'] or 0)
        minutos = f['duracion_minutos']
        if not minutos or not (DUR_MIN <= minutos <= DUR_MAX):
            minutos = None
        if (kg <= 0 and not minutos) or por_dia[f['fecha']] >= REGISTROS_DIA_PRUEBA:
            continue
        clave = (f['fecha'], round(kg))
        if clave in vistos:
            continue
        vistos.add(clave)
        nombre = (f['nombre_rutina_liftin'] or f['rutina__nombre'] or 'Entreno').strip()
        sesiones.append(Sesion(f['id'], f['fecha'], kg, minutos, nombre))
    return sesiones


def _ref(s):
    """Lo mínimo para enlazar una sesión desde la historia."""
    return {'id': s.id, 'fecha': _fecha_larga(s.fecha), 'nombre': s.nombre}


# ── constancia ───────────────────────────────────────────────────────────────

def _meses(sesiones, hasta):
    primero = sesiones[0].fecha
    meses = OrderedDict()
    anio, mes = primero.year, primero.month
    while (anio, mes) <= (hasta.year, hasta.month):
        meses[(anio, mes)] = {'sesiones': 0, 'kg': 0.0, 'dias': set()}
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    for s in sesiones:
        m = meses[(s.fecha.year, s.fecha.month)]
        m['sesiones'] += 1
        m['kg'] += s.kg
        m['dias'].add(s.fecha.day)
    return meses


def _mosaico(meses, primero, hasta):
    """Un punto por día: entrenado, sin entreno, antes del primero o futuro."""
    filas = []
    for (anio, mes), m in meses.items():
        puntos = []
        for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
            d = date(anio, mes, dia)
            if d < primero or d > hasta:
                estado = 'fuera'
            elif dia in m['dias']:
                estado = 'si'
            else:
                estado = 'no'
            puntos.append(estado)
        filas.append({
            'etiqueta': f'{MESES_CORTOS[mes - 1]} {str(anio)[2:]}',
            'mes': _mes_txt(anio, mes),
            'puntos': puntos,
            'dias': len(m['dias']),
            'lista': ', '.join(str(d) for d in sorted(m['dias'])),
        })
    return filas


def _racha_semanas(sesiones):
    semanas = sorted({s.fecha - timedelta(days=s.fecha.weekday()) for s in sesiones})
    mejor = actual = 1 if semanas else 0
    for previa, siguiente in zip(semanas, semanas[1:]):
        actual = actual + 1 if (siguiente - previa).days == 7 else 1
        mejor = max(mejor, actual)
    return mejor


def _la_vuelta(sesiones):
    """La pausa más larga entre dos días de gym y el entreno con el que volviste."""
    dias = sorted({s.fecha for s in sesiones})
    if len(dias) < 2:
        return None
    mejor = max(zip(dias, dias[1:]), key=lambda par: ((par[1] - par[0]).days, par[1]))
    sin_entrenar = (mejor[1] - mejor[0]).days - 1
    if sin_entrenar < 1:
        return None
    vuelta = next(s for s in sesiones if s.fecha == mejor[1])
    return {
        'dias': sin_entrenar,
        'desde': _fecha_corta(mejor[0] + timedelta(days=1)),
        'hasta': _fecha_corta(mejor[1] - timedelta(days=1)),
        'anio': mejor[1].year,
        'vuelta': _ref(vuelta) | {'minutos': vuelta.minutos},
        'larga': sin_entrenar >= 7,
    }


def _comparacion_anual(meses, hasta):
    """Último mes completo frente al mismo mes del año anterior."""
    anio, mes = (hasta.year - 1, 12) if hasta.month == 1 else (hasta.year, hasta.month - 1)
    ahora = meses.get((anio, mes))
    antes = meses.get((anio - 1, mes))
    if not ahora or not antes or not antes['sesiones'] or not ahora['sesiones']:
        return None
    factor = ahora['kg'] / antes['kg'] if antes['kg'] else None
    return {
        'antes_mes': _mes_txt(anio - 1, mes),
        'ahora_mes': _mes_txt(anio, mes),
        'antes_sesiones': antes['sesiones'],
        'ahora_sesiones': ahora['sesiones'],
        'antes_t': _num(antes['kg'] / 1000),
        'ahora_t': _num(ahora['kg'] / 1000),
        'factor': _num(factor, 1) if factor else None,
        'sube': bool(factor and factor > 1),
    }


# ── etapas ───────────────────────────────────────────────────────────────────

def _etapas(sesiones):
    """Tramos seguidos con la misma fase en el nombre de la rutina."""
    etapas = []
    for s in sesiones:
        fase = fase_de(s.nombre)
        if not fase:
            continue
        if etapas and clave_nombre(etapas[-1]['fase']) == clave_nombre(fase):
            etapas[-1]['sesiones'].append(s)
        else:
            etapas.append({'fase': fase, 'sesiones': [s]})
    return etapas


def _ejercicios_de(entreno_id, limite=6):
    from entrenos.models import EjercicioRealizado
    from entrenos.services.nombres_visibles import nombre_visible

    filas = list(EjercicioRealizado.objects.filter(entreno_id=entreno_id).order_by('orden', 'id')[:limite])
    catalogo = _nombre_catalogo({clave_nombre(f.nombre_ejercicio) for f in filas})
    return [
        {'nombre': nombre_visible(catalogo.get(clave_nombre(f.nombre_ejercicio)) or f.nombre_ejercicio),
         'series': f.series}
        for f in filas
    ]


def _entreno_tipico(etapa):
    """La sesión mediana en volumen de la etapa: ni la más floja ni la más bestia."""
    con_volumen = [s for s in etapa['sesiones'] if s.kg > 0] or etapa['sesiones']
    ordenadas = sorted(con_volumen, key=lambda s: s.kg)
    s = ordenadas[len(ordenadas) // 2]
    inicio, fin = etapa['sesiones'][0].fecha, etapa['sesiones'][-1].fecha
    return {
        'fase': etapa['fase'],
        'periodo': (_mes_anio_corto(inicio) if (inicio.year, inicio.month) == (fin.year, fin.month)
                    else f'{_mes_anio_corto(inicio)} – {_mes_anio_corto(fin)}'),
        'sesiones': len(etapa['sesiones']),
        'entreno': _ref(s) | {'minutos': s.minutos},
        'ejercicios': _ejercicios_de(s.id),
    }


def _entrenos_por_etapa(etapas):
    """La primera etapa larga y la actual (sin contar descargas)."""
    normales = [e for e in etapas if not _es_descarga(e['fase'])]
    primera = next((e for e in normales if len(e['sesiones']) >= 4), None)
    actual = normales[-1] if normales else None
    if not primera or not actual or primera is actual:
        return None
    # Lista (no dict): el JSON de MySQL reordena las claves al congelar la edición.
    return [_entreno_tipico(primera) | {'ahora': False}, _entreno_tipico(actual) | {'ahora': True}]


def _descarga_respetada(etapas, sesiones):
    """La última descarga completa: cuánto bajaste y con qué volviste."""
    for i in range(len(etapas) - 1, -1, -1):
        etapa = etapas[i]
        if not _es_descarga(etapa['fase']):
            continue
        inicio, fin = etapa['sesiones'][0].fecha, etapa['sesiones'][-1].fecha
        antes = [s for s in sesiones if s.fecha < inicio and s.kg > 0][-5:]
        despues = [s for s in sesiones
                   if s.fecha > fin and s.kg > 0 and not _es_descarga(fase_de(s.nombre))]
        en_descarga = [s for s in etapa['sesiones'] if s.kg > 0]
        if len(antes) < 3 or not despues or not en_descarga:
            continue
        media_antes = sum(s.kg for s in antes) / len(antes)
        media_descarga = sum(s.kg for s in en_descarga) / len(en_descarga)
        if media_antes <= 0 or media_descarga >= media_antes:
            continue
        vuelta = despues[0]
        return {
            'desde': _fecha_corta(inicio),
            'hasta': _fecha_corta(fin),
            'sesiones': len(etapa['sesiones']),
            'bajada': round(100 * (1 - media_descarga / media_antes)),
            'vuelta': _ref(vuelta),
            'vuelta_t': _num(vuelta.kg / 1000, 1),
            'antes_t': _num(media_antes / 1000, 1),
        }
    return None


# ── ejercicios ───────────────────────────────────────────────────────────────

def _nombre_catalogo(claves):
    """Nombre del catálogo para cada clave normalizada (si existe)."""
    from rutinas.models import EjercicioBase

    catalogo = {}
    for nombre in EjercicioBase.objects.values_list('nombre', flat=True):
        clave = clave_nombre(nombre)
        if clave in claves and clave not in catalogo:
            catalogo[clave] = nombre
    return catalogo


def _ejercicio_de_siempre(sesiones):
    """El ejercicio en más entrenos, con su primera y última vez."""
    from entrenos.models import EjercicioRealizado
    from entrenos.services.nombres_visibles import nombre_visible

    por_id = {s.id: s for s in sesiones}
    filas = EjercicioRealizado.objects.filter(entreno_id__in=list(por_id)).values_list(
        'entreno_id', 'nombre_ejercicio', 'series')
    entrenos, series, grafias = {}, Counter(), {}
    for entreno_id, nombre, n_series in filas:
        clave = clave_nombre(nombre)
        if not clave:
            continue
        entrenos.setdefault(clave, set()).add(entreno_id)
        series[clave] += n_series or 0
        grafias.setdefault(clave, Counter())[nombre.strip()] += 1
    if not entrenos:
        return None
    clave = max(entrenos, key=lambda c: (len(entrenos[c]), series[c]))
    nombre = _nombre_catalogo({clave}).get(clave) or max(
        grafias[clave].items(), key=lambda kv: (kv[1], kv[0] != kv[0].lower(), kv[0]))[0]
    ses = sorted((por_id[i] for i in entrenos[clave]), key=lambda s: (s.fecha, s.id))
    return {
        'nombre': nombre_visible(nombre),
        'entrenos': len(entrenos[clave]),
        'series': series[clave],
        'primera': _ref(ses[0]),
        'ultima': _ref(ses[-1]),
    }


def _serie_que_hoy_es_normal(sesiones, hasta):
    """Una serie antigua que costó mucho y una reciente igual o mayor con más margen."""
    from entrenos.models import SerieRealizada
    from entrenos.services.nombres_visibles import nombre_visible

    por_id = {s.id: s for s in sesiones}
    filas = (
        SerieRealizada.objects.filter(
            entreno_id__in=list(por_id), completado=True, es_aproximacion=False,
            rpe_real__isnull=False, peso_kg__gt=0, distancia_metros__isnull=True,
        )
        .values_list('entreno_id', 'ejercicio__nombre', 'peso_kg', 'repeticiones', 'rpe_real')
    )
    por_ejercicio = {}
    for entreno_id, nombre, peso, reps, rpe in filas:
        s = por_id[entreno_id]
        por_ejercicio.setdefault(clave_nombre(nombre), []).append(
            (s, nombre, float(peso), reps, float(rpe)))

    limite_antigua = hasta - timedelta(days=SERIE_ANTIGUA_MIN_DIAS)
    desde_reciente = hasta - timedelta(days=SERIE_RECIENTE_DIAS)
    mejor, mejor_puntos = None, None
    for series in por_ejercicio.values():
        antiguas = [x for x in series if x[0].fecha <= limite_antigua and x[4] >= SERIE_ANTIGUA_RPE_MIN]
        recientes = [x for x in series if x[0].fecha >= desde_reciente]
        for a in antiguas:
            for r in recientes:
                if r[2] < a[2] or r[2] > a[2] * SERIE_PESO_MAX or r[3] < a[3]:
                    continue
                if r[4] > a[4] - SERIE_MARGEN_RPE:
                    continue
                puntos = (a[4] - r[4], r[2] / a[2], (r[0].fecha - a[0].fecha).days)
                if mejor_puntos is None or puntos > mejor_puntos:
                    mejor, mejor_puntos = (a, r), puntos
    if not mejor:
        return None
    a, r = mejor

    def _serie(x):
        return _ref(x[0]) | {'peso': _peso(x[2]), 'reps': x[3], 'rpe': _peso(x[4])}

    return {'ejercicio': nombre_visible(a[1]), 'antes': _serie(a), 'ahora': _serie(r)}


# ── historia completa ────────────────────────────────────────────────────────

def calcular_historia(cliente, hasta=None):
    hasta = hasta or date.today()
    sesiones = sesiones_limpias(cliente, hasta)
    if not sesiones:
        return None

    primera = sesiones[0]
    dias = len({s.fecha for s in sesiones})
    semanas = max(1.0, ((hasta - primera.fecha).days + 1) / 7)
    kg_total = sum(s.kg for s in sesiones)

    con_duracion = [s.minutos for s in sesiones if s.minutos]
    media_min = sum(con_duracion) / len(con_duracion) if con_duracion else None
    sin_duracion = len(sesiones) - len(con_duracion)
    horas = None
    if media_min:
        horas = (sum(con_duracion) + sin_duracion * media_min) / 60

    meses = _meses(sesiones, hasta)
    valores = list(meses.values())
    # El primer mes y el actual pueden estar a medias: no cuentan para el "mes más flojo".
    completos = valores[1:-1] if len(valores) > 2 else []
    etapas = _etapas(sesiones)

    return {
        'hasta': hasta.isoformat(),
        'desde': _fecha_larga(primera.fecha),
        'primera': _ref(primera) | {'minutos': primera.minutos, 'kg': _num(primera.kg)},
        'sesiones': len(sesiones),
        'dias': dias,
        'semanas': round(semanas),
        'por_semana': _num(len(sesiones) / semanas, 1),
        'horas': round(horas) if horas else None,
        'horas_estimadas': sin_duracion if horas else 0,
        'media_min': round(media_min) if media_min else None,
        'dias_enteros': _num(horas / 24, 1).removesuffix(',0') if horas else None,
        'toneladas': _num(kg_total / 1000),
        'coches': _num(kg_total / KG_COCHE),
        'meses_total': len(valores),
        'meses_con_entreno': sum(1 for m in valores if m['sesiones']),
        'mes_minimo': min((m['sesiones'] for m in completos), default=None),
        'mosaico': _mosaico(meses, primera.fecha, hasta),
        'racha_semanas': _racha_semanas(sesiones),
        'vuelta': _la_vuelta(sesiones),
        'comparacion': _comparacion_anual(meses, hasta),
        'etapas': _entrenos_por_etapa(etapas),
        'descarga': _descarga_respetada(etapas, sesiones),
        'serie_normal': _serie_que_hoy_es_normal(sesiones, hasta),
        'ejercicio': _ejercicio_de_siempre(sesiones),
    }


def cifras_del_momento(h):
    """Lo que se guarda con una carta para compararlo cuando se abra."""
    return {'fecha': h['hasta'], 'dias': h['dias'], 'horas': h['horas'], 'toneladas': h['toneladas']}
