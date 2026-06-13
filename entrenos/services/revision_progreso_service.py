"""
Phase 63 — Revisión de progreso (peso/cintura/rendimiento).

Lectura on-demand que combina tres señales que hasta ahora vivían aisladas:
peso (PesoDiario), medidas corporales (RevisionProgreso) y rendimiento
(RecordPersonal + volumen de entrenamiento). Cuando hay al menos dos de estas
señales con datos suficientes, antepone una lectura cruzada prudente; si no,
sólo devuelve los items individuales disponibles.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from entrenos.services.resumen_semanal_service import _tipo_record_label

UMBRAL_PESO_KG = Decimal('0.5')      # mismo umbral que AnalizadorPeso mensual
UMBRAL_CINTURA_CM = Decimal('0.5')   # mismo orden de magnitud, sin precedente exacto
UMBRAL_VOLUMEN_PCT = 10              # % cambio para considerar "subiendo"/"bajando"

_ETIQUETAS_MEDIDAS = {
    'cintura': ('cintura', 'cm'),
    'peso_corporal': ('peso corporal', 'kg'),
    'grasa_corporal': ('grasa corporal', '%'),
}


def get_revision_progreso(cliente, hoy=None):
    """
    Lectura de progreso a más plazo: combina peso, medidas y rendimiento
    del último mes. Si hay al menos 2 ejes con datos, antepone una lectura
    cruzada prudente. Devuelve [] si no hay datos en ninguna señal.
    """
    hoy = hoy or date.today()

    senal_peso = _calcular_senal_peso(cliente, hoy)
    senal_medidas = _calcular_senal_medidas(cliente)
    senal_rendimiento = _calcular_senal_rendimiento(cliente, hoy)

    items = []

    lectura = _lectura_cruzada(senal_peso, senal_medidas, senal_rendimiento)
    if lectura:
        items.append(lectura)

    items += _item_peso(senal_peso)
    items += _item_medidas(senal_medidas)
    items += _items_rendimiento(senal_rendimiento)

    return items


# ── Señales internas ────────────────────────────────────────────────────

def _calcular_senal_peso(cliente, hoy):
    """{'direccion': 'subiendo'|'bajando'|'estable', 'cambio': Decimal} o None."""
    from clientes.models import PesoDiario

    hace_30 = hoy - timedelta(days=30)
    registros = list(
        PesoDiario.objects.filter(cliente=cliente, fecha__gte=hace_30, fecha__lte=hoy)
        .order_by('fecha')
    )
    if len(registros) < 2:
        return None

    cambio = registros[-1].peso_kg - registros[0].peso_kg
    if abs(cambio) < UMBRAL_PESO_KG:
        direccion = 'estable'
    else:
        direccion = 'subiendo' if cambio > 0 else 'bajando'

    return {'direccion': direccion, 'cambio': cambio}


def _calcular_senal_medidas(cliente):
    """{'deltas': {campo: Decimal}, 'dias': int, 'cintura_direccion': str|None} o None."""
    from clientes.models import RevisionProgreso

    revisiones = list(RevisionProgreso.objects.filter(cliente=cliente).order_by('-fecha')[:2])
    if len(revisiones) < 2:
        return None

    latest, previous = revisiones
    dias = (latest.fecha - previous.fecha).days

    deltas = {}
    for campo in ('cintura', 'peso_corporal', 'grasa_corporal'):
        actual, anterior = getattr(latest, campo), getattr(previous, campo)
        if actual is not None and anterior is not None:
            delta = actual - anterior
            if delta != 0:
                deltas[campo] = delta

    if not deltas:
        return None

    cintura_delta = deltas.get('cintura')
    if cintura_delta is None:
        cintura_direccion = None
    elif abs(cintura_delta) < UMBRAL_CINTURA_CM:
        cintura_direccion = 'estable'
    else:
        cintura_direccion = 'subiendo' if cintura_delta > 0 else 'bajando'

    return {'deltas': deltas, 'dias': dias, 'cintura_direccion': cintura_direccion}


def _calcular_senal_rendimiento(cliente, hoy):
    """{'records': list, 'volumen_direccion': str|None, 'volumen_reciente': Decimal,
        'volumen_anterior': Decimal} o None."""
    from entrenos.models import RecordPersonal, EntrenoRealizado

    hace_30 = hoy - timedelta(days=30)
    records = list(
        RecordPersonal.objects.filter(
            cliente=cliente, fecha_logrado__gte=hace_30, fecha_logrado__lte=hoy,
        ).order_by('ejercicio_nombre', 'tipo_record')
    )

    hace_14, hace_28 = hoy - timedelta(days=14), hoy - timedelta(days=28)

    vol_reciente = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__gt=hace_14, fecha__lte=hoy,
    ).aggregate(t=Sum('volumen_total_kg'))['t'] or Decimal('0')

    vol_anterior = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__gt=hace_28, fecha__lte=hace_14,
    ).aggregate(t=Sum('volumen_total_kg'))['t'] or Decimal('0')

    volumen_direccion = None
    if vol_anterior > 0:
        cambio_pct = (vol_reciente - vol_anterior) / vol_anterior * 100
        if cambio_pct > UMBRAL_VOLUMEN_PCT:
            volumen_direccion = 'subiendo'
        elif cambio_pct < -UMBRAL_VOLUMEN_PCT:
            volumen_direccion = 'bajando'
        else:
            volumen_direccion = 'estable'

    if not records and volumen_direccion is None:
        return None

    return {
        'records': records,
        'volumen_direccion': volumen_direccion,
        'volumen_reciente': vol_reciente,
        'volumen_anterior': vol_anterior,
    }


# ── Lectura cruzada ─────────────────────────────────────────────────────

def _lectura_cruzada(senal_peso, senal_medidas, senal_rendimiento):
    """
    Sólo emite item si hay al menos 2 de los 3 ejes con datos. Cubre 4 casos
    con conclusión; si no matchea ninguno (o falta cintura, o señales no
    cubiertas), no fuerza ninguna lectura de composición.
    """
    ejes = sum(s is not None for s in (senal_peso, senal_medidas, senal_rendimiento))
    if ejes < 2:
        return None

    peso_dir = senal_peso['direccion'] if senal_peso else None
    cintura_dir = senal_medidas['cintura_direccion'] if senal_medidas else None

    rendimiento_resumen = None
    if senal_rendimiento:
        if senal_rendimiento['records'] or senal_rendimiento['volumen_direccion'] == 'subiendo':
            rendimiento_resumen = 'mejora'
        elif senal_rendimiento['volumen_direccion'] == 'bajando':
            rendimiento_resumen = 'empeora'
        else:
            rendimiento_resumen = 'estable'

    texto = None

    # 1) Recomposición: peso estable + cintura bajando + rendimiento no cae
    if peso_dir == 'estable' and cintura_dir == 'bajando' and rendimiento_resumen != 'empeora':
        texto = (
            'Peso estable y cintura bajando: podría tratarse de recomposición '
            'corporal — no parece necesario hacer cambios.'
        )

    # 2) Ganancia útil: peso sube + cintura estable + rendimiento mejora
    elif peso_dir == 'subiendo' and cintura_dir == 'estable' and rendimiento_resumen == 'mejora':
        texto = (
            'Peso subiendo con cintura estable y rendimiento al alza: la subida '
            'parece acompañar una mejora real — vale la pena seguir observando.'
        )

    # 3) Alerta suave: peso sube + cintura sube + rendimiento no mejora
    elif peso_dir == 'subiendo' and cintura_dir == 'subiendo' and rendimiento_resumen != 'mejora':
        texto = (
            'Peso y cintura suben sin que el rendimiento muestre mejora clara: '
            'puede valer la pena revisar adherencia o nutrición.'
        )

    # 4) Déficit/fatiga: peso baja + rendimiento cae (no requiere medidas)
    elif peso_dir == 'bajando' and rendimiento_resumen == 'empeora':
        texto = (
            'Peso bajando junto con caída de rendimiento: conviene vigilar si '
            'el déficit actual es demasiado agresivo o si hay fatiga acumulada.'
        )

    if texto is None:
        return None

    return {'tipo': 'lectura_cruzada', 'icono': '🧭', 'color': 'info', 'texto': texto}


# ── Items individuales por señal ───────────────────────────────────────

def _item_peso(senal):
    if senal is None:
        return []
    if senal['direccion'] == 'estable':
        texto = f"Peso: estable en el último mes ({senal['cambio']:+.1f} kg)."
        icono = '⚖️'
    else:
        verbo = 'subiendo' if senal['direccion'] == 'subiendo' else 'bajando'
        texto = f"Peso: {verbo} {abs(senal['cambio']):.1f} kg en el último mes."
        icono = '📈' if senal['direccion'] == 'subiendo' else '📉'
    return [{'tipo': 'peso', 'icono': icono, 'texto': texto, 'color': 'info'}]


def _item_medidas(senal):
    if senal is None:
        return []
    partes = [
        f'{_ETIQUETAS_MEDIDAS[campo][0]} {delta:+.1f} {_ETIQUETAS_MEDIDAS[campo][1]}'
        for campo, delta in senal['deltas'].items()
    ]
    texto = f"Medidas: {', '.join(partes)} desde la última revisión (hace {senal['dias']} días)."
    return [{'tipo': 'medidas', 'icono': '📏', 'color': 'info', 'texto': texto}]


def _items_rendimiento(senal):
    if senal is None:
        return []
    items = []

    if senal['records']:
        por_ejercicio = {}
        for r in senal['records']:
            por_ejercicio.setdefault(r.ejercicio_nombre, []).append(_tipo_record_label(r.tipo_record))
        resumen = '; '.join(
            f'{ej} ({", ".join(tipos)})' for ej, tipos in list(por_ejercicio.items())[:3]
        )
        n = len(senal['records'])
        plural = 'récords' if n != 1 else 'récord'
        items.append({
            'tipo': 'rendimiento', 'icono': '🏆', 'color': 'info',
            'texto': f'{n} {plural} personal{"es" if n != 1 else ""} en el último mes: {resumen}.',
        })

    if senal['volumen_direccion'] is not None:
        icono = {'subiendo': '📈', 'bajando': '📉', 'estable': '➡️'}[senal['volumen_direccion']]
        items.append({
            'tipo': 'rendimiento', 'icono': icono, 'color': 'info',
            'texto': (
                f"Volumen de entrenamiento {senal['volumen_direccion']} "
                f"({round(senal['volumen_reciente']):,} kg últimas 2 semanas "
                f"vs {round(senal['volumen_anterior']):,} kg anteriores)."
            ),
        })

    return items
