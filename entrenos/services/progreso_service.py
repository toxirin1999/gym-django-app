"""
Phase 64D — memoria compacta de progreso por ejercicio.

Extrae lógica ya existente en `vista_entrenamiento_activo`
(detección de tope de máquina y de estancamiento) y añade el cálculo
de comparación de peso entre lo recomendado hoy y la última vez.
No cambia el comportamiento existente, solo lo centraliza.
"""
from datetime import timedelta


def calcular_sugerencia_tope(datos_anterior):
    """
    Réplica de la detección de "tope de máquina" de vista_entrenamiento_activo:
    si la última vez se marcó es_tope_maquina con peso > 0, se sugiere mantener
    el peso y subir una repetición.

    Devuelve (sugerencia_tope: bool, reps_sugeridas_tope: int | None).
    """
    if not datos_anterior:
        return False, None

    try:
        peso_ant = float(datos_anterior.get('peso') or 0)
    except (TypeError, ValueError):
        peso_ant = 0.0

    if datos_anterior.get('es_tope_maquina') and peso_ant > 0:
        reps_ant = datos_anterior.get('repeticiones') or 0
        return True, int(reps_ant) + 1

    return False, None


def detectar_estancamiento(cliente, nombre_ejercicio, fecha_actual):
    """
    Réplica de la detección de estancamiento de vista_entrenamiento_activo:
    True si existe un GymDecisionLog activo de tipo `cambiar_variante` por
    "Sin progresión" en los últimos 21 días para este ejercicio.
    """
    from entrenos.models import GymDecisionLog

    try:
        return GymDecisionLog.objects.filter(
            cliente=cliente,
            ejercicio__iexact=nombre_ejercicio,
            accion='cambiar_variante',
            fecha_creacion__date__gte=fecha_actual - timedelta(days=21),
            motivo__icontains='Sin progresión',
        ).exists()
    except Exception:
        return False


def calcular_comparacion_peso(peso_recomendado_kg, peso_anterior_kg):
    """
    Compara el peso recomendado para hoy con el de la última vez.

    Devuelve None si no hay histórico (peso_anterior_kg vacío o <= 0).
    En otro caso, devuelve {'direccion': 'subida'|'bajada'|'igual', 'delta': float}.
    """
    try:
        peso_anterior = float(peso_anterior_kg or 0)
    except (TypeError, ValueError):
        peso_anterior = 0.0

    if peso_anterior <= 0:
        return None

    try:
        peso_actual = float(peso_recomendado_kg or 0)
    except (TypeError, ValueError):
        peso_actual = 0.0

    delta = round(peso_actual - peso_anterior, 2)
    if delta > 0:
        direccion = 'subida'
    elif delta < 0:
        direccion = 'bajada'
    else:
        direccion = 'igual'

    return {'direccion': direccion, 'delta': delta}
