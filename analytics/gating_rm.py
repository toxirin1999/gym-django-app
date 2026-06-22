"""
Phase Gym Peso 2.1 — Actualización prudente del RM único (one_rm_data).

Bug cerrado: estimar_1rm_con_rpe (Epley+RIR) extrapola mal cuando el RPE
objetivo es bajo y las reps son altas. RIR = 10 - rpe; reps_teoricas =
reps + RIR. Con RPE bajo y reps altas, RIR es grande y las reps teóricas
al fallo quedan muy infladas, disparando el e1RM aunque el cliente solo
haya obedecido exactamente la descarga prescrita.

Regla madre: en descarga, hacer el peso prescrito con el RPE objetivo no
debería disparar el 1RM histórico. Debería confirmar que la descarga está
bien calibrada, no demostrar una mejora de fuerza.

decidir_actualizacion_rm() es la única función que decide si una serie
puede subir cliente.one_rm_data, y con qué tope. Reutiliza
estimar_1rm_con_rpe (analytics/utils.py) — no duplica la fórmula.
"""

from analytics.utils import estimar_1rm_con_rpe

# Tope de subida por sesión para fases no-descarga con evidencia normal
# (RPE real registrado). 3% por sesión es conservador frente a progresiones
# de fuerza típicas (2.5kg sobre cargas medias suele rondar 2-5%) pero evita
# que una sola serie con RIR amplio dispare el histórico en un solo golpe,
# como pasaba con el trinquete directo al e1RM observado.
FACTOR_SUAVIZADO_RM = 1.03


def decidir_actualizacion_rm(*, rm_actual, peso, reps, rpe_real, es_descarga):
    """
    Decide si una serie debe actualizar cliente.one_rm_data y a qué valor.

    Devuelve dict con:
      'actualiza':     bool
      'rm_resultante':  float — rm_actual si no actualiza, nuevo valor si sí.
      'motivo':        uno de:
          'rm_actualizado'                 — (reservado, no usado en v1: todo
                                               lo que sube pasa por suavizado)
          'rm_actualizado_suavizado'       — sube, topado a rm_actual * FACTOR
          'rm_no_actualizado_descarga'     — fase descarga, nunca sube
          'rm_no_actualizado_rpe_incompatible' — (reservado para futuras
                                               reglas de RPE vs objetivo)
          'rm_sin_rpe_confianza_baja'      — sin RPE real, confianza baja
    """
    rm_actual = float(rm_actual or 0)

    if es_descarga:
        return {'actualiza': False, 'rm_resultante': rm_actual, 'motivo': 'rm_no_actualizado_descarga'}

    if rpe_real is None:
        return {'actualiza': False, 'rm_resultante': rm_actual, 'motivo': 'rm_sin_rpe_confianza_baja'}

    e1rm_observado = estimar_1rm_con_rpe(float(peso), int(reps), float(rpe_real))
    if not e1rm_observado or e1rm_observado <= rm_actual:
        return {'actualiza': False, 'rm_resultante': rm_actual, 'motivo': 'rm_no_actualizado_rpe_incompatible' if rm_actual else 'rm_sin_rpe_confianza_baja'}

    if rm_actual <= 0:
        # Primera carga registrada para este ejercicio: no hay base sobre la
        # que aplicar un tope relativo, se acepta el e1RM observado.
        return {'actualiza': True, 'rm_resultante': round(e1rm_observado, 2), 'motivo': 'rm_actualizado_suavizado'}

    tope = rm_actual * FACTOR_SUAVIZADO_RM
    rm_resultante = round(min(e1rm_observado, tope), 2)
    return {'actualiza': True, 'rm_resultante': rm_resultante, 'motivo': 'rm_actualizado_suavizado'}
