"""
Vitalidad JOI — eje de constancia (independiente del estado de atención).

Este módulo NO toca ni depende de determinar_estado_habitacion_joi
(SILENCIO/OBSERVANDO/PRESENTE/PROTEGIENDO, en services.py). Es un eje
puramente visual y aparte: cuánto "brilla" JOI según la constancia de
entrenamiento reciente del usuario, al estilo Tamagotchi pero sin castigo
— JOI nunca "muere", solo hiberna.

Fuente base: core.context.actividad_context.get_actividad_context, la misma
fuente única que ya usa build_activity_context y el semáforo, para no
introducir un segundo cálculo de racha_dias/última actividad "actuales".

Nota de diseño importante: racha_dias (tal y como lo define
core.context.actividad_context) cuenta días consecutivos CON HOY incluido,
así que en cuanto el usuario lleva un día sin entrenar, racha_dias ya es 0
— es exactamente el momento en que este módulo empieza a importar. Por eso,
para la "gracia extendida por constancia previa" no podemos usar racha_dias
tal cual: calculamos aparte cuán larga fue la racha que terminó en la fecha
de la última actividad (_racha_previa_a), que sí sobrevive al paso de los
días sin depender de que "ayer" hubiera actividad.

Diseño:
- Periodo de gracia: los primeros días sin entrenar no penalizan nada.
  Se alarga un poco si la racha que tenías al parar era larga (recompensa
  la constancia con más colchón antes de empezar a decaer).
- Pasado el periodo de gracia, decae linealmente hasta un suelo mínimo
  (nunca cero) en ~12 días — "hibernación", no castigo.
- Al registrar actividad nueva, la vitalidad vuelve de golpe al máximo.
"""
from datetime import date, timedelta

VITALIDAD_MINIMA = 25
VITALIDAD_MAXIMA = 100

GRACIA_BASE_DIAS = 2
GRACIA_EXTRA_POR_SEMANA_RACHA = 1
GRACIA_EXTRA_TOPE_DIAS = 5

DIAS_HASTA_SUELO = 12

NIVELES_VISUALES = ('plena', 'estable', 'bajando', 'hibernando')

_TIPOS_ACTIVIDAD = ['gym', 'hyrox', 'carrera']


def _racha_previa_a(cliente, fecha) -> int:
    """Días consecutivos con actividad terminando en `fecha` (inclusive),
    caminando hacia atrás. A diferencia de racha_dias (que exige actividad
    HOY), esto responde "cuán consistente venía el usuario justo antes de
    parar", sin importar cuántos días hayan pasado desde entonces.
    """
    from entrenos.models import ActividadRealizada
    from django.db.models.functions import Coalesce

    dias = 0
    dia = fecha
    while (
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=_TIPOS_ACTIVIDAD)
        .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
        .filter(fecha_ef=dia)
        .exists()
    ):
        dias += 1
        dia -= timedelta(days=1)
    return dias


def _gracia_dias(racha_referencia: int) -> int:
    """Días de gracia antes de empezar a decaer, según la mejor racha
    relevante disponible (la actual si sigue viva, o la que tenías al
    parar)."""
    semanas_completas = max(racha_referencia, 0) // 7
    extra = min(semanas_completas * GRACIA_EXTRA_POR_SEMANA_RACHA, GRACIA_EXTRA_TOPE_DIAS)
    return GRACIA_BASE_DIAS + extra


def _nivel_visual(valor: int) -> str:
    if valor >= 85:
        return 'plena'
    if valor >= 55:
        return 'estable'
    if valor > VITALIDAD_MINIMA:
        return 'bajando'
    return 'hibernando'


def calcular_vitalidad_joi(cliente, hoy: date | None = None) -> dict:
    """
    Devuelve:
        {
            'valor':          int (VITALIDAD_MINIMA..VITALIDAD_MAXIMA),
            'nivel_visual':   'plena' | 'estable' | 'bajando' | 'hibernando',
            'dias_inactivo':  int | None,  # None si nunca hubo actividad
            'racha_dias':     int,  # racha ACTUAL (0 si no hay actividad hoy)
            'racha_referencia': int,  # racha usada para calcular la gracia
            'en_gracia':      bool,
        }
    Nunca lanza: ante cualquier fallo al leer el contexto de actividad,
    devuelve un estado neutro ('estable') en vez de romper la Habitación.
    """
    if hoy is None:
        hoy = date.today()

    try:
        from core.context.actividad_context import get_actividad_context
        ctx = get_actividad_context(cliente, hoy)
        racha_dias = ctx.get('racha_dias') or 0
        ultima = ctx.get('ultima_actividad')
        dias_inactivo = ultima.get('dias_hace') if ultima else None
    except Exception:
        racha_dias = 0
        dias_inactivo = None

    if dias_inactivo is None:
        # Nunca se registró actividad: ni "hibernando" (no hubo abandono)
        # ni "plena" (todavía no hay nada que celebrar). Punto de partida neutro.
        return {
            'valor': 60,
            'nivel_visual': 'estable',
            'dias_inactivo': None,
            'racha_dias': racha_dias,
            'racha_referencia': 0,
            'en_gracia': True,
        }

    if racha_dias > 0:
        racha_referencia = racha_dias
    else:
        try:
            fecha_ultima = hoy - timedelta(days=dias_inactivo)
            racha_referencia = _racha_previa_a(cliente, fecha_ultima)
        except Exception:
            racha_referencia = 0

    gracia = _gracia_dias(racha_referencia)

    if dias_inactivo <= gracia:
        valor = VITALIDAD_MAXIMA
        en_gracia = True
    else:
        dias_decayendo = dias_inactivo - gracia
        proporcion = min(dias_decayendo / DIAS_HASTA_SUELO, 1.0)
        valor = round(VITALIDAD_MAXIMA - proporcion * (VITALIDAD_MAXIMA - VITALIDAD_MINIMA))
        en_gracia = False

    return {
        'valor': valor,
        'nivel_visual': _nivel_visual(valor),
        'dias_inactivo': dias_inactivo,
        'racha_dias': racha_dias,
        'racha_referencia': racha_referencia,
        'en_gracia': en_gracia,
    }
