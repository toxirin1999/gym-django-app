"""Sesiones de descarga: no sirven de "la última vez" (31-oct-2026).

En una descarga el peso se baja a propósito (semana de descarga del bloque,
``recalculado_descarga``) o se limita el esfuerzo (ciclo de deload: una serie
menos y RPE 7 como máximo). Si esa sesión se lee como "la última vez", la
semana siguiente el techo del peso (que solo baja o limita) deja al ejercicio
en el peso de descarga más un salto de máquina, y se tarda varias sesiones en
volver sin ningún motivo real. Lo mismo con el ancla del planificador.

Una sesión cuenta como descarga si:
- el ejercicio venía marcado así en el snapshot de esa sesión (``deload``,
  ``_deload_aplicado`` o ``motivo_peso = recalculado_descarga``), o
- su fecha cae en una semana de descarga del plan (``SemanaPlanGym``) o en un
  ciclo de deload (``CicloDeload``) vigente ese día.
"""

from datetime import timedelta


def periodos_descarga(cliente_id):
    """Lista de (inicio, fin) con las fechas de descarga del cliente."""
    from entrenos.models import CicloDeload, SemanaPlanGym

    periodos = [
        (lunes, lunes + timedelta(days=6))
        for lunes in SemanaPlanGym.objects.filter(
            cliente_id=cliente_id, descarga=True,
        ).values_list('lunes', flat=True)
    ]
    for inicio, fin, cierre in CicloDeload.objects.filter(cliente_id=cliente_id).values_list(
        'fecha_inicio', 'fecha_fin_prevista', 'fecha_cierre',
    ):
        if cierre and cierre <= fin:
            # Cerrado antes de tiempo: desde el día del cierre ya no es descarga.
            fin = cierre - timedelta(days=1)
        if fin >= inicio:
            periodos.append((inicio, fin))
    return periodos


def fecha_en_descarga(fecha, periodos):
    return any(inicio <= fecha <= fin for inicio, fin in periodos or ())


def ejercicio_marcado_descarga(entreno, nombre):
    """¿El snapshot de esa sesión prescribió el ejercicio como descarga?"""
    from entrenos.services.decision_log_service import normalizar_ejercicio

    version = getattr(entreno, 'gym_decision_version', None)
    snapshot = getattr(version, 'snapshot', None) or {}
    clave = normalizar_ejercicio(nombre)
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) != clave:
            continue
        motivo = ej.get('motivo_peso') or {}
        return bool(
            ej.get('deload') or ej.get('_deload_aplicado')
            or (isinstance(motivo, dict) and motivo.get('tipo') == 'recalculado_descarga')
        )
    return False


def es_sesion_descarga(entreno, nombre, periodos=None):
    """True si en esa sesión el ejercicio se hizo en descarga."""
    try:
        if ejercicio_marcado_descarga(entreno, nombre):
            return True
    except Exception:
        pass
    if periodos is None:
        periodos = periodos_descarga(entreno.cliente_id)
    return fecha_en_descarga(entreno.fecha, periodos)
