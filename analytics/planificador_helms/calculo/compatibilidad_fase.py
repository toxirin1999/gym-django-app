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

FUERA DE ALCANCE: suavizado de e1RM a través de múltiples sesiones
históricas. Esta función usa solo la última sesión real como evidencia.
"""

from typing import Optional

from analytics.utils import estimar_1rm_con_rpe

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
      'motivo_tipo':  'recalculado_fase' | 'recalculado_descarga' | None.
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
    # Brzycki inverso: peso_rpe10 = e1RM * (1.0278 - 0.0278 * reps)
    factor_brzycki = max(0.01, 1.0278 - 0.0278 * reps_objetivo_hoy)
    peso_rpe_10 = e1rm * factor_brzycki
    reduccion_por_rpe = max(0.0, (10 - rpe_objetivo_hoy)) * 0.03
    peso_calculado = peso_rpe_10 * (1 - reduccion_por_rpe)

    if redondear_fn:
        peso_final = redondear_fn(peso_calculado)
    else:
        peso_final = round(round(peso_calculado / 2.5) * 2.5, 1)

    motivo_tipo = 'recalculado_descarga' if es_descarga_hoy else 'recalculado_fase'
    return {'aplica': True, 'peso': peso_final, 'motivo_tipo': motivo_tipo}
