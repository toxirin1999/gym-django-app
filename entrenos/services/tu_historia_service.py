"""Tu historia en el gym (14-nov-2026).

Panel provisional al estilo de un resumen anual: lo acumulado, no lo que falta.
Idea de David: "no soy consciente del trabajo que hago; ¿ese esfuerzo se pierde
en el olvido?". Todo sale de los entrenos registrados; si un dato no existe, la
pantalla correspondiente no aparece.

Limpieza (la misma que se usó al contarlo a mano el 14-nov):
- Solo entrenos con volumen registrado (> 0 kg).
- Días con 3 registros o más se tratan como pruebas de la app (agosto de 2025).
- Duplicados del mismo día con el mismo volumen cuentan una vez.
- Duraciones fuera de 5-180 min se tratan como desconocidas; las horas de esas
  sesiones se estiman con la media de las conocidas.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta

DUR_MIN, DUR_MAX = 5, 180
REGISTROS_DIA_PRUEBA = 3
KG_COCHE = 1500  # coche medio, para la equivalencia

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago',
                'sep', 'oct', 'nov', 'dic']


@dataclass(frozen=True)
class Sesion:
    id: int
    fecha: date
    kg: float
    minutos: int | None
    nombre: str


def _num(valor, decimales=0):
    """Número a la española: 1.914 · 7,9."""
    texto = f'{valor:,.{decimales}f}'
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def _fecha_larga(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def _mes_txt(anio, mes):
    return f'{MESES[mes - 1].capitalize()} {anio}'


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
        if kg <= 0 or por_dia[f['fecha']] >= REGISTROS_DIA_PRUEBA:
            continue
        clave = (f['fecha'], round(kg))
        if clave in vistos:
            continue
        vistos.add(clave)
        minutos = f['duracion_minutos']
        if not minutos or not (DUR_MIN <= minutos <= DUR_MAX):
            minutos = None
        nombre = (f['nombre_rutina_liftin'] or f['rutina__nombre'] or 'Entreno').strip()
        sesiones.append(Sesion(f['id'], f['fecha'], kg, minutos, nombre))
    return sesiones


def _meses(sesiones, hasta):
    primero = sesiones[0].fecha
    meses = OrderedDict()
    anio, mes = primero.year, primero.month
    while (anio, mes) <= (hasta.year, hasta.month):
        meses[(anio, mes)] = {'sesiones': 0, 'kg': 0.0}
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    for s in sesiones:
        m = meses[(s.fecha.year, s.fecha.month)]
        m['sesiones'] += 1
        m['kg'] += s.kg
    return meses


def _racha_semanas(sesiones):
    semanas = sorted({s.fecha - timedelta(days=s.fecha.weekday()) for s in sesiones})
    mejor = actual = 1 if semanas else 0
    for previa, siguiente in zip(semanas, semanas[1:]):
        actual = actual + 1 if (siguiente - previa).days == 7 else 1
        mejor = max(mejor, actual)
    return mejor


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


def _ejercicio_mas_repetido(ids):
    from entrenos.models import EjercicioRealizado
    from entrenos.services.nombres_visibles import nombre_visible

    filas = EjercicioRealizado.objects.filter(entreno_id__in=ids).values_list(
        'entreno_id', 'nombre_ejercicio', 'series')
    entrenos, series, grafias = {}, Counter(), {}
    for entreno_id, nombre, n_series in filas:
        clave = (nombre or '').strip().casefold()
        if not clave:
            continue
        entrenos.setdefault(clave, set()).add(entreno_id)
        series[clave] += n_series or 0
        grafias.setdefault(clave, Counter())[nombre.strip()] += 1
    if not entrenos:
        return None
    clave = max(entrenos, key=lambda c: (len(entrenos[c]), series[c]))
    return {
        # La grafía más usada; a igualdad, la que lleva mayúsculas (la del catálogo).
        'nombre': nombre_visible(max(
            grafias[clave].items(), key=lambda kv: (kv[1], kv[0] != kv[0].lower(), kv[0])
        )[0]),
        'entrenos': len(entrenos[clave]),
        'series': series[clave],
    }


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
    max_ses = max(m['sesiones'] for m in valores) or 1
    barras = [
        {'etiqueta': MESES_CORTOS[mes - 1], 'anio': anio, 'sesiones': m['sesiones'],
         'alto': round(100 * m['sesiones'] / max_ses), 'enero': mes == 1}
        for (anio, mes), m in meses.items()
    ]

    mayor = max(sesiones, key=lambda s: s.kg)

    return {
        'desde': _fecha_larga(primera.fecha),
        'primera': {
            'fecha': _fecha_larga(primera.fecha),
            'nombre': primera.nombre,
            'minutos': primera.minutos,
            'kg': _num(primera.kg),
        },
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
        'barras': barras,
        'racha_semanas': _racha_semanas(sesiones),
        'comparacion': _comparacion_anual(meses, hasta),
        'mayor': {
            'fecha': _fecha_larga(mayor.fecha),
            'nombre': mayor.nombre,
            't': _num(mayor.kg / 1000, 1),
        },
        'ejercicio': _ejercicio_mas_repetido([s.id for s in sesiones]),
    }
