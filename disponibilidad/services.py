from datetime import datetime, timedelta, time

from django.db.models import DateTimeField
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import RegistroDisponibilidad

# ── Constantes calibrables ─────────────────────────────────────────────────────
BASELINE = 55.0  # score neutro de partida — banda "Suficiente" baja

# Techo por nivel: cada evento se aproxima asintóticamente a su techo, con
# retornos decrecientes — evita que repetir "Suficiente" sature a 100 sin
# ninguna ingesta "Completa" reciente (visto con datos reales en producción).
TECHO_NIVEL = {
    'A': 100.0,  # Completa — única capaz de consolidar la banda Alta
    'B': 70.0,   # Suficiente
    'C': 45.0,   # Recurso — deliberadamente bajo: autoridad mínima, pendiente de refinar
}

FACTOR_APROXIMACION = 0.5  # cada evento recorre la mitad de la distancia a su techo

DEDUP_VENTANA_MINUTOS = 5  # ingestas del mismo cliente más cerca que esto se tratan como corrección (prevalece la última)

DELTA_ENTRENO = -20.0

UMBRAL_HORAS_ESTABLE = 4.0      # antes de esto, el tiempo no erosiona nada
EROSION_POR_HORA_DIA = 3.0
EROSION_POR_HORA_NOCHE = 1.0    # erosión reducida en horario de sueño — evolución nocturna, no congelada

HORA_INICIO_NOCHE = 23          # 23:00
HORA_FIN_NOCHE = 7              # 07:00

VENTANA_LOOKBACK_HORAS = 72     # más allá de esto se parte de BASELINE, da persistencia acotada sin recorrer todo el historial


def _es_hora_nocturna(dt):
    """True si la hora de dt cae dentro del rango de sueño (23:00–07:00)."""
    h = dt.hour
    return h >= HORA_INICIO_NOCHE or h < HORA_FIN_NOCHE


def _aplicar_erosion(score, desde, hasta):
    """Erosiona score según el gap entre dos datetimes. Devuelve el nuevo score."""
    gap_horas = (hasta - desde).total_seconds() / 3600
    if gap_horas <= UMBRAL_HORAS_ESTABLE:
        return score

    horas_erosionables = gap_horas - UMBRAL_HORAS_ESTABLE
    # Punto medio del tramo erosionable para decidir tasa diurna/nocturna
    punto_medio = desde + timedelta(hours=UMBRAL_HORAS_ESTABLE) + timedelta(hours=horas_erosionables / 2)
    tasa = EROSION_POR_HORA_NOCHE if _es_hora_nocturna(punto_medio) else EROSION_POR_HORA_DIA
    return max(0.0, score - horas_erosionables * tasa)


def _aplicar_ingesta(score, nivel):
    """Aproxima score hacia el techo del nivel, con retornos decrecientes.

    Si score ya está en o por encima del techo de ese nivel, el evento no lo
    mueve — evita saturación por repetir el mismo nivel sin variar.
    """
    techo = TECHO_NIVEL.get(nivel)
    if techo is None or score >= techo:
        return score
    return score + (techo - score) * FACTOR_APROXIMACION


def _deduplicar_ingestas(ingestas):
    """Colapsa ingestas del mismo cliente a <5 min de *momento_efectivo* entre sí: prevalece la última (corrección), no se suman ambas.

    Se ordena explícitamente por momento_efectivo (no por el orden de llegada del
    queryset) porque dos registros pueden compartir timestamp de guardado pero
    corresponder a momentos reales distintos.
    """
    ingestas = sorted(ingestas, key=lambda r: (r.momento_efectivo, r.pk))
    resultado = []
    for r in ingestas:
        if resultado and (r.momento_efectivo - resultado[-1].momento_efectivo) < timedelta(minutes=DEDUP_VENTANA_MINUTOS):
            resultado[-1] = r
        else:
            resultado.append(r)
    return resultado


def _timestamp_entreno(entreno):
    """Construye un datetime aware a partir de fecha + hora_inicio/hora_fin del EntrenoRealizado.

    Sin hora registrada, se posiciona al final del día (23:59) en vez de
    inventar mediodía — no fabrica una cronología falsa frente a las
    ingestas del mismo día.
    """
    if entreno.hora_inicio:
        t = entreno.hora_inicio
    elif entreno.hora_fin:
        t = entreno.hora_fin
    else:
        t = time(23, 59)
    naive = datetime.combine(entreno.fecha, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


RECURSOS_DISPONIBLES_CACHE_TTL = 300  # 5 min — techo de frescura; se invalida antes en disponibilidad/views.py::registrar


def calcular_recursos_disponibles(cliente):
    """
    Cachea el resultado (ver _calcular_recursos_disponibles_calc para el
    cálculo real). Se invalida explícitamente al registrar una ingesta nueva
    (disponibilidad/views.py::registrar) — el TTL de 5 min es solo un techo
    de seguridad, no la vía normal de frescura.
    """
    from django.core.cache import cache
    cache_key = f'recursos_disponibles_{cliente.id}'
    resultado = cache.get(cache_key)
    if resultado is None:
        resultado = _calcular_recursos_disponibles_calc(cliente)
        cache.set(cache_key, resultado, RECURSOS_DISPONIBLES_CACHE_TTL)
    return resultado


def _calcular_recursos_disponibles_calc(cliente):
    """
    Replay secuencial con memoria — cada ingesta/entreno modifica un score acumulado.

    Devuelve {'score': int|None, 'banda': str|None, 'motivo': str|None}.
    El campo 'banda' es lo que debe mostrarse en UI; 'score' solo para calibración interna.
    """
    # importación local para evitar ciclo si en el futuro entrenos importa de disponibilidad
    from entrenos.models import EntrenoRealizado

    ahora = timezone.now()
    ventana_inicio = ahora - timedelta(hours=VENTANA_LOOKBACK_HORAS)

    # ── Eventos de ingesta ────────────────────────────────────────────────────
    # momento_efectivo (Coalesce) en vez de timestamp: filtra/ordena por cuándo
    # ocurrió realmente la ingesta, no por cuándo se guardó el registro.
    ingestas_qs = RegistroDisponibilidad.objects.filter(cliente=cliente).annotate(
        _momento_efectivo=Coalesce('momento_ingesta', 'timestamp', output_field=DateTimeField()),
    ).filter(_momento_efectivo__gte=ventana_inicio).order_by('_momento_efectivo')
    ingestas = _deduplicar_ingestas(ingestas_qs)

    # ── Eventos de entreno (excluye sesiones incompletas) ─────────────────────
    entrenos_qs = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=ventana_inicio.date(),
    ).exclude(
        numero_ejercicios=0,
        volumen_total_kg=0,
    ).order_by('fecha')

    # Construimos listas de eventos: cada elemento es (timestamp, tipo, payload)
    eventos = []
    for r in ingestas:
        eventos.append((r.momento_efectivo, 'ingesta', r.nivel))
    for e in entrenos_qs:
        ts = _timestamp_entreno(e)
        if ts >= ventana_inicio:
            eventos.append((ts, 'entreno', None))

    eventos.sort(key=lambda ev: ev[0])

    # ── Sin ningún registro histórico ─────────────────────────────────────────
    if not RegistroDisponibilidad.objects.filter(cliente=cliente).exists():
        return {'score': None, 'banda': None, 'motivo': 'sin_datos'}

    # ── Sin eventos dentro de la ventana → rescatar el más reciente fuera ─────
    if not eventos:
        ultimo = (
            RegistroDisponibilidad.objects.filter(cliente=cliente).annotate(
                _momento_efectivo=Coalesce('momento_ingesta', 'timestamp', output_field=DateTimeField()),
            ).order_by('-_momento_efectivo').first()
        )
        # Tratar como si hubiera pasado 1 h antes de su momento_efectivo (cursor = ts - 1h)
        eventos = [(ultimo.momento_efectivo, 'ingesta', ultimo.nivel)]
        cursor = ultimo.momento_efectivo - timedelta(hours=1)
    else:
        cursor = ventana_inicio

    # ── Replay ───────────────────────────────────────────────────────────────
    score = BASELINE

    for ts, tipo, payload in eventos:
        score = _aplicar_erosion(score, cursor, ts)

        if tipo == 'ingesta':
            score = min(100.0, max(0.0, _aplicar_ingesta(score, payload)))
        elif tipo == 'entreno':
            score = min(100.0, max(0.0, score + DELTA_ENTRENO))

        cursor = ts

    # Erosión final hasta ahora
    score = _aplicar_erosion(score, cursor, ahora)

    score = round(max(0.0, min(100.0, score)))

    # ── Banda de representación ────────────────────────────────────────────────
    if score >= 75:
        banda = 'Alta'
    elif score >= 50:
        banda = 'Suficiente'
    elif score >= 25:
        banda = 'Baja'
    else:
        banda = 'Crítica'

    return {
        'score': score,
        'banda': banda,
        'motivo': None,
    }
