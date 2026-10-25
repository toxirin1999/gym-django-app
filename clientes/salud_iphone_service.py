"""Check-in automático desde la app Salud del iPhone vía Health Auto Export.

Health Auto Export (iOS) puede enviar por la noche/mañana, con una automatización
"REST API", un JSON con las métricas de Salud:

    {"data": {"metrics": [
        {"name": "sleep_analysis", "units": "hr", "data": [
            {"date": "2026-10-15", "totalSleep": 7.2, "asleep": 7.2, "sleepEnd": "2026-10-15 07:01:00 +0200", ...}]},
        {"name": "resting_heart_rate", "units": "count/min", "data": [{"date": "2026-10-15 00:00:00 +0200", "qty": 52}]},
        {"name": "heart_rate_variability", "units": "ms", "data": [{"date": "...", "qty": 48.3}]}
    ]}}

De ahí sale el check-in de la mañana: horas de sueño, FC en reposo y HRV, en
la ``BitacoraDiaria`` del día en que te despiertas (la misma fila que rellena
el check-in a mano). La energía no está en Salud: se sigue preguntando al
empezar el entreno.

Si llega el peso (``weight_body_mass``), va a ``PesoDiario``.

Solo se aceptan los últimos ``DIAS_VENTANA`` días: es un check-in, no una
importación de histórico.

24-oct-2026: también acepta el formato sencillo del Atajo de iOS (gratis,
sin Health Auto Export), un diccionario plano del día de hoy:

    {"hrv": 48, "pulso_reposo": 52, "sueno": 432, "fecha": "2026-10-25"}

Los valores pueden llegar como número o como texto ("48,3", "52 lpm", o
varios números si el Atajo manda la lista de muestras): se hace la media
para la variabilidad y el pulso, y la suma para el sueño. El sueño se
interpreta por tamaño: hasta 24 son horas, hasta 1440 minutos y más,
segundos. ``fecha`` es opcional (por defecto, hoy).
"""
import re

from collections import defaultdict
from datetime import date, timedelta

DIAS_VENTANA = 7
NOMBRES_HRV = ('heart_rate_variability', 'heart_rate_variability_sdnn')
NOMBRES_PESO = ('weight_body_mass', 'body_mass')
VALORES_NO_SUENO = {'awake', 'in bed', 'inbed', 'despierto', 'en cama'}


def _fecha(texto):
    """'2026-10-15 07:01:00 +0200' o '2026-10-15' → date (día local del iPhone)."""
    try:
        return date.fromisoformat(str(texto).strip()[:10])
    except (TypeError, ValueError):
        return None


def _numero(valor):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # descarta NaN


def _horas(valor, unidades):
    n = _numero(valor)
    if n is None:
        return None
    return n / 60 if (unidades or '').lower().startswith('min') else n


_NUMERO = re.compile(r'-?\d+(?:[.,]\d+)?')
CLAVES_ATAJO = {
    'hrv_ms': ('hrv', 'hrv_ms', 'variabilidad'),
    'fc_reposo': ('pulso_reposo', 'fc_reposo', 'resting_heart_rate', 'pulso'),
    'horas_sueno': ('sueno', 'sueno_horas', 'sueno_minutos', 'horas_sueno', 'sleep'),
}


def _numeros(valor):
    """48 / '48,3' / '52 lpm' / '41\n55' / [41, 55] → [floats]."""
    if valor is None or isinstance(valor, bool):
        return []
    if isinstance(valor, (int, float)):
        return [float(valor)] if valor == valor else []
    if isinstance(valor, (list, tuple)):
        return [n for v in valor for n in _numeros(v)]
    return [float(t.replace(',', '.')) for t in _NUMERO.findall(str(valor))]


_HMS = re.compile(r'(\d+):(\d{1,2})(?::(\d{1,2}))?')


_CON_UNIDAD = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(horas?|hrs?|h|minutos?|mins?|m|segundos?|segs?|s)\b', re.IGNORECASE)
_MS = re.compile(r'(\d+(?:[.,]\d+)?)\s*ms\b', re.IGNORECASE)
_PULSO = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:lpm|bpm|ppm|latidos|count/min|cpm)', re.IGNORECASE)


def _valores_con_unidad(valor, patron):
    """Si el texto trae la unidad ("45 ms", "59 lpm"), solo esos números (no fechas ni horas)."""
    if isinstance(valor, (list, tuple)):
        valor = '\n'.join(str(v) for v in valor)
    if not isinstance(valor, str):
        return None
    encontrados = [float(n.replace(',', '.')) for n in patron.findall(valor)]
    return encontrados or None


def _horas_con_unidades(valor):
    """'1 h 23 min', '83 min', '7 hr', '3600 s' (uno o varios tramos) → horas, o None."""
    if isinstance(valor, (list, tuple)):
        valor = '\n'.join(str(v) for v in valor)
    if not isinstance(valor, str):
        return None
    total = 0.0
    for numero, unidad in _CON_UNIDAD.findall(valor):
        n = float(numero.replace(',', '.'))
        u = unidad.lower()
        if u.startswith('h'):
            total += n
        elif u.startswith('m'):
            total += n / 60
        else:
            total += n / 3600
    return total or None


def _horas_sueno_atajo(clave, valor):
    if isinstance(valor, (list, tuple)) and all(isinstance(v, str) for v in valor):
        valor = '\n'.join(valor)
    # "7:12:00" o "7:12" (duración en formato reloj) → horas.
    if isinstance(valor, str) and _HMS.search(valor):
        total = 0.0
        for h, m, seg in _HMS.findall(valor):
            total += int(h) + int(m) / 60 + (int(seg) / 3600 if seg else 0)
        return total or None
    con_unidades = _horas_con_unidades(valor)
    if con_unidades:
        return con_unidades
    ns = [n for n in _numeros(valor) if n > 0]
    if not ns:
        return None
    total = sum(ns)
    if clave == 'sueno_minutos':
        return total / 60
    if total <= 24:
        return total
    if total <= 1440:
        return total / 60
    return total / 3600


FASES_NO_SUENO = ('despierto', 'awake', 'en cama', 'in bed', 'inbed')


def _lineas(valor):
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return [t.strip() for t in str(valor or '').splitlines() if t.strip()]


def _segundos_reloj(texto):
    """Duración de un tramo como la da Atajos: '16:24' (min:s), '1:13:06' (h:min:s), '59' (s)."""
    partes = texto.replace(',', '.').split(':')
    try:
        numeros = [float(p) for p in partes]
    except ValueError:
        return None
    if len(numeros) == 3:
        return numeros[0] * 3600 + numeros[1] * 60 + numeros[2]
    if len(numeros) == 2:
        return numeros[0] * 60 + numeros[1]
    if len(numeros) == 1:
        return numeros[0]
    return None


def _horas_por_tramos(duraciones, fases=None):
    """Suma los tramos de sueño (formato reloj), quitando los 'Despierto' / 'En cama' si llega la fase.

    Devuelve None si no es una lista de tramos en formato reloj.
    """
    lineas = _lineas(duraciones)
    if len(lineas) < 2 or not any(':' in l for l in lineas):
        return None
    fases_l = _lineas(fases) if fases is not None else []
    usar_fases = len(fases_l) == len(lineas)
    total = 0.0
    for i, linea in enumerate(lineas):
        if usar_fases and any(f in fases_l[i].lower() for f in FASES_NO_SUENO):
            continue
        seg = _segundos_reloj(linea)
        if seg is None:
            return None
        total += seg
    return total / 3600


def leer_atajo(payload, hoy):
    """Formato plano del Atajo → {fecha: {...}} (mismo formato que ``leer_metricas``)."""
    if not isinstance(payload, dict):
        return {}
    dia = _fecha(payload.get('fecha')) if payload.get('fecha') else hoy
    if dia is None:
        return {}
    valores = {}
    for campo, claves in CLAVES_ATAJO.items():
        for clave in claves:
            if clave not in payload:
                continue
            if campo == 'horas_sueno':
                horas = _horas_por_tramos(payload[clave], payload.get('fases'))
                if horas is None:
                    horas = _horas_sueno_atajo(clave, payload[clave])
                if horas and 0 < horas <= 16:
                    valores[campo] = round(horas, 2)
            else:
                patron = _MS if campo == 'hrv_ms' else _PULSO
                ns = _valores_con_unidad(payload[clave], patron) or [n for n in _numeros(payload[clave]) if n > 0]
                if ns:
                    media = round(sum(ns) / len(ns))
                    rango = (1, 300) if campo == 'hrv_ms' else (30, 200)
                    if rango[0] <= media <= rango[1]:
                        valores[campo] = media
            break
    return {dia: valores} if valores else {}


def leer_metricas(payload):
    """{fecha: {'horas_sueno', 'fc_reposo', 'hrv_ms'}} con lo que traiga el JSON."""
    data = (payload or {}).get('data') or {}
    metricas = data.get('metrics') if isinstance(data, dict) else None
    por_dia = defaultdict(dict)
    if not isinstance(metricas, list):
        return {}

    for metrica in metricas:
        if not isinstance(metrica, dict):
            continue
        nombre = (metrica.get('name') or '').strip().lower()
        unidades = metrica.get('units') or ''
        puntos = [p for p in (metrica.get('data') or []) if isinstance(p, dict)]

        if nombre == 'sleep_analysis':
            sueno = defaultdict(float)
            for p in puntos:
                if 'totalSleep' in p or 'asleep' in p:  # agregado: una fila por noche
                    dia = _fecha(p.get('sleepEnd') or p.get('date'))
                    horas = _horas(p.get('totalSleep') if p.get('totalSleep') is not None else p.get('asleep'), unidades)
                    if dia and horas:
                        sueno[dia] = max(sueno[dia], horas)
                elif str(p.get('value') or '').strip().lower() not in VALORES_NO_SUENO:  # tramos sueltos
                    dia = _fecha(p.get('sleepEnd') or p.get('endDate') or p.get('date'))
                    horas = _horas(p.get('qty'), unidades)
                    if dia and horas:
                        sueno[dia] += horas
            for dia, horas in sueno.items():
                if 0 < horas <= 16:
                    por_dia[dia]['horas_sueno'] = round(horas, 2)

        elif nombre == 'resting_heart_rate':
            valores = defaultdict(list)
            for p in puntos:
                dia, n = _fecha(p.get('date')), _numero(p.get('qty') if p.get('qty') is not None else p.get('Avg'))
                if dia and n:
                    valores[dia].append(n)
            for dia, ns in valores.items():
                fc = round(sum(ns) / len(ns))
                if 30 <= fc <= 200:
                    por_dia[dia]['fc_reposo'] = fc

        elif nombre in NOMBRES_HRV:
            valores = defaultdict(list)
            for p in puntos:
                dia, n = _fecha(p.get('date')), _numero(p.get('qty') if p.get('qty') is not None else p.get('Avg'))
                if dia and n:
                    valores[dia].append(n)
            for dia, ns in valores.items():
                hrv = round(sum(ns) / len(ns))
                if 1 <= hrv <= 300:
                    por_dia[dia]['hrv_ms'] = hrv
        elif nombre in NOMBRES_PESO:
            por_libras = (unidades or '').lower().startswith('lb')
            ultimos = {}
            for p in puntos:  # el último peso del día
                dia, n = _fecha(p.get('date')), _numero(p.get('qty'))
                if dia and n:
                    ultimos[dia] = n * 0.45359237 if por_libras else n
            for dia, kg in ultimos.items():
                if 30 <= kg <= 250:
                    por_dia[dia]['peso_kg'] = round(kg, 1)
    return dict(por_dia)


def _guardar_peso(cliente, dia, kg):
    """El peso va a ``PesoDiario`` (la serie que leen Memoria y el control de peso)."""
    from django.db import IntegrityError, transaction
    from clientes.models import PesoDiario

    fila = PesoDiario.objects.filter(cliente=cliente, fecha=dia).first()
    if fila is not None:
        if float(fila.peso_kg) != kg:
            fila.peso_kg = kg
            fila.save(update_fields=['peso_kg'])
        return
    try:
        with transaction.atomic():
            fila = PesoDiario.objects.create(cliente=cliente, peso_kg=kg)
            if fila.fecha != dia:  # ``fecha`` es auto_now_add
                PesoDiario.objects.filter(pk=fila.pk).update(fecha=dia)
    except IntegrityError:
        pass


def guardar_checkin_iphone(cliente, payload, hoy=None):
    """Guarda en BitacoraDiaria lo recibido. Devuelve {fecha_iso: campos guardados}."""
    from django.core.cache import cache
    from django.db import transaction
    from django.utils import timezone
    from clientes.models import BitacoraDiaria

    hoy = hoy or timezone.localdate()
    guardado = {}
    metricas = leer_metricas(payload) or leer_atajo(payload, hoy)
    for dia, valores in sorted(metricas.items()):
        if not valores or dia > hoy or dia < hoy - timedelta(days=DIAS_VENTANA):
            continue
        peso = valores.pop('peso_kg', None)
        if peso is not None:
            _guardar_peso(cliente, dia, peso)
        if not valores:
            guardado[dia.isoformat()] = {'peso_kg': peso}
            continue
        with transaction.atomic():
            fila = (
                BitacoraDiaria.objects.select_for_update()
                .filter(cliente=cliente, fecha=dia).order_by('pk').first()
            )
            if fila is None:
                fila = BitacoraDiaria.objects.create(cliente=cliente, **valores)
                if fila.fecha != dia:  # ``fecha`` es auto_now_add: se corrige al día real
                    BitacoraDiaria.objects.filter(pk=fila.pk).update(fecha=dia)
            else:
                for campo, valor in valores.items():
                    setattr(fila, campo, valor)
                fila.save(update_fields=list(valores))
        guardado[dia.isoformat()] = {**valores, **({'peso_kg': peso} if peso is not None else {})}
    cache.set(f'salud_iphone_ultimo_{cliente.id}',
              {'cuando': timezone.now().isoformat(), 'guardado': guardado}, 60 * 60 * 24 * 30)
    if guardado:
        cache.delete(f'bio_ctx_{cliente.id}')
        cache.delete(f'dashboard_acwr_unificado_{cliente.id}')
    return guardado
