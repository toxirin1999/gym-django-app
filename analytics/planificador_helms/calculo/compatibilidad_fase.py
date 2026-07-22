"""
Phase Gym Peso 2 — Carga dependiente de fase.

Regla madre: el último peso no es la recomendación, es evidencia para
estimar capacidad (e1RM). Esta capacidad solo se traduce directamente en
"peso_anterior ± incremento fijo" cuando el rango de reps de la sesión
anterior y el de hoy pertenecen a la misma familia de estímulo (mismo
"bucket"). Si la familia cambia (p.ej. potencia 3 reps → descarga 10 reps),
el incremento fijo no tiene sentido: hay que recalcular desde e1RM con el
rango y RPE objetivo de HOY.

Una sola función de decisión, reutilizada por los tres sitios donde hoy se
decide el peso:
  1. analytics/planificador_helms/core.py        (generación del plan)
  2. entrenos/models.py GymDecisionLog            (peso_sugerido downstream)
  3. entrenos/views.py vista_entrenamiento_activo (lo que ve el usuario)

Phase Gym Peso 2.2 — X.0: resolver_ancla_historica()
Suaviza la ancla de e1RM ponderando las sesiones dentro de una ventana de
42 días (máximo 3, pesos 0.5/0.3/0.2 con renormalización). El caller ya
filtra por bucket; este módulo solo promedia lo que recibe.
"""

from datetime import date as _date
from typing import Optional

from analytics.utils import estimar_1rm_con_rpe

# ── Constantes de ancla histórica (Phase Gym Peso 2.2 X.0) ───────────────────
VENTANA_ANCLA_DIAS = 42
PESOS_ANCLA = [0.5, 0.3, 0.2]

# ── Constantes de guard de reps altas (Phase Gym Peso 2.2 X.1) ───────────────
# Brzycki es poco fiable a partir de UMBRAL_REPS_ALTO reps (relación no lineal
# entre reps y % de 1RM en ese tramo). Se proyecta a REPS_REF_ALTO (punto fiable)
# y se aplica un step-down plano; el derate por RPE objetivo NO se aplica aquí.
UMBRAL_REPS_ALTO = 15   # reps objetivo >= 15 → tramo poco fiable para Brzycki/RPE directo
REPS_REF_ALTO = 10      # proyectar primero a un equivalente-10RM fiable
STEP_DOWN_ALTO = 0.175  # -17.5% plano sobre ese equivalente-10RM

# ── Buckets de fase por rango de reps ────────────────────────────────────────
# Basados en los rep_range reales usados en periodizacion/generador.py:
#   potencia:                  '2-4', '3-5'
#   fuerza:                     '3-5', '4-6'
#   hipertrofia (acumulación):  '10-12'
#   hipertrofia (intensific.):  '8-10'
#   hipertrofia_especifica:     '8-12'
#   hipertrofia_metabolica:     '12-15'
#   descarga:                   '10-15'
#
# Fuerza y potencia comparten rango bajo (2-6 reps): es la misma familia de
# estímulo de cara a "¿puedo seguir progresando el mismo peso?" — un cambio
# de potencia a fuerza (o viceversa) no exige recalcular desde e1RM.
# Hipertrofia/descarga comparten rango alto (8-15 reps): misma familia.
BUCKET_FUERZA_POTENCIA = 'fuerza_potencia'
BUCKET_HIPERTROFIA = 'hipertrofia'

_UMBRAL_REPS_BUCKET = 7  # reps <= 7 → fuerza_potencia; reps >= 8 → hipertrofia


def _bucket_desde_reps(reps: int) -> str:
    return BUCKET_FUERZA_POTENCIA if reps <= _UMBRAL_REPS_BUCKET else BUCKET_HIPERTROFIA


def _primer_numero(rango_str) -> int:
    """Extrae el primer entero de un rango '8-12', '3-5' o '10'."""
    try:
        return int(str(rango_str).split('-')[0].strip())
    except (ValueError, AttributeError, IndexError):
        return 8


def son_rangos_compatibles(reps_anteriores, rep_range_hoy) -> bool:
    """
    True si las reps reales de la última sesión y el rango objetivo de hoy
    pertenecen al mismo bucket de fase (misma familia de estímulo).
    """
    if reps_anteriores is None:
        return False
    bucket_anterior = _bucket_desde_reps(int(reps_anteriores))
    bucket_hoy = _bucket_desde_reps(_primer_numero(rep_range_hoy))
    return bucket_anterior == bucket_hoy


def resolver_peso_objetivo(
    *,
    peso_anterior: Optional[float],
    reps_anteriores: Optional[int],
    rpe_anterior: Optional[float],
    rep_range_hoy: str,
    rpe_objetivo_hoy: int,
    es_descarga_hoy: bool = False,
    redondear_fn=None,
) -> dict:
    """
    Decide el peso de trabajo para HOY a partir de la evidencia disponible.

    Jerarquía (ver Phase Gym Peso 2):
      A. Sin historial real           → None (el caller debe usar el cálculo
                                          por e1RM puro, p.ej. CalculadorPeso).
      B. Historial + bucket compatible → None (el caller debe aplicar su
                                          incremento normal: peso_anterior ±
                                          ajuste por RPE, como ya hace).
      C. Historial + bucket incompatible → recalcula desde e1RM (Epley+RIR)
                                          sobre la última sesión real.
      D. Descarga                      → recalcula desde e1RM con reducción
                                          explícita de descarga (RPE objetivo
                                          bajo ya lo refleja en la fórmula).

    Devuelve dict con:
      'aplica':       bool — True si esta función decidió el peso (casos C/D).
                       False si el caller debe seguir su propio camino (A/B).
      'peso':         float|None — peso resultante si aplica=True.
      'motivo_tipo':  'recalculado_fase' | 'recalculado_descarga'
                      | 'recalculado_alto' | None.
    """
    sin_datos = peso_anterior is None or not peso_anterior or reps_anteriores is None or not rpe_anterior
    if sin_datos:
        return {'aplica': False, 'peso': None, 'motivo_tipo': None}

    compatible = son_rangos_compatibles(reps_anteriores, rep_range_hoy)

    if compatible and not es_descarga_hoy:
        return {'aplica': False, 'peso': None, 'motivo_tipo': None}

    # Caso C (bucket incompatible) o D (descarga): recalcular desde e1RM
    # usando la última sesión real como evidencia de capacidad.
    e1rm = estimar_1rm_con_rpe(float(peso_anterior), int(reps_anteriores), float(rpe_anterior))
    if not e1rm:
        return {'aplica': False, 'peso': None, 'motivo_tipo': None}

    reps_objetivo_hoy = _primer_numero(rep_range_hoy)

    if reps_objetivo_hoy >= UMBRAL_REPS_ALTO:
        # Guard X.1: rango >= 15 reps — Brzycki es poco fiable en este tramo
        # (infraestima la carga real). Se proyecta al equivalente-10RM y se aplica
        # un step-down plano. Sin derate adicional por RPE: el step-down ya es la
        # prescripción completa. Si coincide con es_descarga_hoy, el motivo sigue
        # siendo 'recalculado_alto' — el rango es la razón del camino especial.
        factor_10rm = max(0.01, 1.0278 - 0.0278 * REPS_REF_ALTO)
        peso_10rm_equiv = e1rm * factor_10rm
        peso_calculado = peso_10rm_equiv * (1 - STEP_DOWN_ALTO)
        motivo_tipo = 'recalculado_alto'
    else:
        # Camino normal: Brzycki inverso directo a reps_objetivo_hoy + derate por RPE
        factor_brzycki = max(0.01, 1.0278 - 0.0278 * reps_objetivo_hoy)
        peso_rpe_10 = e1rm * factor_brzycki
        reduccion_por_rpe = max(0.0, (10 - rpe_objetivo_hoy)) * 0.03
        peso_calculado = peso_rpe_10 * (1 - reduccion_por_rpe)
        motivo_tipo = 'recalculado_descarga' if es_descarga_hoy else 'recalculado_fase'

    if redondear_fn:
        peso_final = redondear_fn(peso_calculado)
    else:
        peso_final = round(round(peso_calculado / 2.5) * 2.5, 1)

    return {'aplica': True, 'peso': peso_final, 'motivo_tipo': motivo_tipo}


def resolver_ancla_historica(sesiones, *, ahora=None):
    """
    Calcula un ancla de capacidad suavizada ponderando las sesiones más recientes
    dentro de una ventana de VENTANA_ANCLA_DIAS días.

    El caller ya filtra sesiones por bucket (mismo estímulo que la sesión actual);
    este helper solo promedia lo que recibe.

    Args:
        sesiones: lista de dicts {'peso', 'reps', 'rpe', 'fecha'}, ordenada
                  de más reciente a más antigua.
        ahora:    date de referencia para la ventana (None → date.today()).

    Devuelve:
        dict {'peso': float, 'reps': int, 'rpe': float}
        o None si sesiones está vacía (el caller no tiene base de estimación).
    """
    if not sesiones:
        return None

    hoy = ahora if ahora is not None else _date.today()

    dentro = [s for s in sesiones if (hoy - s['fecha']).days <= VENTANA_ANCLA_DIAS]

    # Si ninguna sesión cae en ventana, usar solo la más reciente disponible.
    # Garantía: nunca peor que "solo la última sesión" (comportamiento pre-X.0).
    candidatas = dentro if dentro else [sesiones[0]]

    usadas = candidatas[:3]
    n = len(usadas)

    pesos_raw = PESOS_ANCLA[:n]
    suma = sum(pesos_raw)
    pesos = [p / suma for p in pesos_raw]

    e1rms = [
        estimar_1rm_con_rpe(float(s['peso']), int(s['reps']), float(s['rpe']))
        for s in usadas
    ]
    e1rm_suave = sum(w * e for w, e in zip(pesos, e1rms))
    rpe_ref = sum(w * float(s['rpe']) for w, s in zip(pesos, usadas))
    reps_ref = int(usadas[0]['reps'])

    # Inversa de Epley+RIR (misma fórmula que estimar_1rm_con_rpe) para que el
    # round-trip N=1 sea matemáticamente exacto sin introducir sesgo de fórmula.
    divisor = 1.0 + (reps_ref + (10.0 - rpe_ref)) / 30.0
    peso_suave = e1rm_suave / divisor

    return {'peso': peso_suave, 'reps': reps_ref, 'rpe': rpe_ref}
