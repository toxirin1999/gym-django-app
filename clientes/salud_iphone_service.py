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
"""

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
    for dia, valores in sorted(leer_metricas(payload).items()):
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
