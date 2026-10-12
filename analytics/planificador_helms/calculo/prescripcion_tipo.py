"""Prescripción según el tipo de ejercicio (decisiones del 12-oct-2026).

Dos reglas, puras y sin acceso a BD:

1. RPE por tipo de ejercicio. Los multiarticulares cansan mucho y fallar una
   serie pesada sale caro: RPE 7–8 (2–3 reps en reserva). Los aislamientos
   generan poca fatiga y para hipertrofia compensa acercarse al fallo: RPE 8–9.
   En descarga no se toca nada: su RPE bajo es intencional.

2. Unidad real en los ejercicios que no se miden en kg × reps. El plan anual
   los generaba como un press normal ("Dead Hang 32,5 kg", "Farmer Walk
   2,5 kg × 15", "Sissy Squat 27,5 kg"). La pantalla de entrenamiento ya
   interpreta ``repeticiones`` como segundos (tiempo) o metros (distancia);
   aquí se le da un rango y una carga coherentes con esa unidad.
"""

COMPUESTOS = frozenset({'compuesto_principal', 'compuesto_secundario'})

RPE_COMPUESTO = (7, 8)
RPE_AISLAMIENTO = (8, 9)

# Rangos en la unidad real del ejercicio (segundos o metros).
RANGO_TIEMPO_SEG = '20-40'
RANGO_TIEMPO_SEG_DESCARGA = '15-25'
RANGO_DISTANCIA_M = '20-30'
RANGO_DISTANCIA_M_DESCARGA = '15-20'

# Carga contractual del Farmer Walk por mano: la misma que fija el servidor al
# ejecutar y guardar la sesión (entrenos/views.py). Plan y ejecución coinciden.
FARMER_KG_POR_MANO = 36.0

TIPOS_SIN_CARGA = frozenset({'progresion_tiempo', 'progresion_reps', 'progresion_variante'})


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def rpe_por_tipo(rpe_objetivo, tipo_ejercicio, es_descarga=False):
    """RPE objetivo según sea multiarticular o aislamiento."""
    if es_descarga or rpe_objetivo is None:
        return rpe_objetivo
    if tipo_ejercicio in COMPUESTOS:
        return _acotar(rpe_objetivo, *RPE_COMPUESTO)
    return _acotar(rpe_objetivo + 1, *RPE_AISLAMIENTO)


def es_farmer(nombre):
    nombre = ' '.join(str(nombre or '').casefold().split())
    return 'farmer' in nombre or 'granjero' in nombre


def rango_por_tipo(tipo_progresion, rep_range, es_descarga=False):
    """Rango en la unidad real: segundos, metros o el rango de reps de siempre."""
    if tipo_progresion == 'progresion_tiempo':
        return RANGO_TIEMPO_SEG_DESCARGA if es_descarga else RANGO_TIEMPO_SEG
    if tipo_progresion == 'progresion_distancia':
        return RANGO_DISTANCIA_M_DESCARGA if es_descarga else RANGO_DISTANCIA_M
    return rep_range


def unidad_por_tipo(tipo_progresion):
    if tipo_progresion == 'progresion_tiempo':
        return 's'
    if tipo_progresion == 'progresion_distancia':
        return 'm'
    return 'reps'


def carga_por_tipo(tipo_progresion, nombre, peso_calculado, peso_historico=None):
    """Carga coherente con el tipo, o ``peso_calculado`` si es un ejercicio con kg.

    - Tiempo y progresión por reps/variante: sin carga externa (0).
    - Distancia: Farmer Walk a su carga contractual por mano; otros, la última
      carga real registrada si la hay, y si no, sin carga (no se inventa).
    - Resto (kg × reps y lastre): el peso que ya calculó el planificador.
    """
    if tipo_progresion in TIPOS_SIN_CARGA:
        return 0.0
    if tipo_progresion == 'progresion_distancia':
        if es_farmer(nombre):
            return FARMER_KG_POR_MANO
        try:
            historico = float(peso_historico or 0)
        except (TypeError, ValueError):
            historico = 0.0
        return historico if historico > 0 else 0.0
    return peso_calculado
