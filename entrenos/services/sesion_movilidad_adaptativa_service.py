"""Cierre transaccional de movilidad y resolución explícita del plan Gym."""

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from entrenos.models import (
    ActividadRealizada,
    SesionMovilidadAdaptativa,
    SesionProgramada,
)


def _validar_metricas(duracion_minutos, rpe):
    if duracion_minutos is None or int(duracion_minutos) <= 0:
        raise ValueError("La duración real debe ser mayor que cero.")
    if rpe is None or not 1 <= float(rpe) <= 10:
        raise ValueError("El RPE real debe estar entre 1 y 10.")


def _validar_resolucion(cliente, sesion, resolucion, fecha, fecha_destino):
    permitidas = {valor for valor, _ in SesionMovilidadAdaptativa.RESOLUCIONES}
    if resolucion not in permitidas:
        raise ValueError("Resolución de movilidad no válida.")
    if sesion is not None and sesion.cliente_id != cliente.id:
        raise ValueError("La sesión programada pertenece a otro cliente.")
    if resolucion in {"posponer", "sustituir"} and sesion is None:
        raise ValueError("La resolución requiere una sesión programada pendiente.")
    if sesion is not None and sesion.estado != SesionProgramada.ESTADO_PENDIENTE:
        raise ValueError("La sesión programada debe estar pendiente.")
    if resolucion == "posponer":
        if fecha_destino is None or fecha_destino <= fecha:
            raise ValueError("La fecha destino debe ser posterior a la sesión de movilidad.")
        colision = SesionProgramada.objects.filter(
            cliente=cliente,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        ).exclude(pk=sesion.pk).filter(
            Q(fecha_prevista=fecha_destino) | Q(pospuesta_hasta=fecha_destino)
        ).exists()
        if colision:
            raise ValueError("La fecha destino está ocupada por otro entrenamiento.")


@transaction.atomic
def completar_sesion_movilidad(
    *, cliente, plan, fecha, duracion_minutos, rpe, resolucion,
    idempotency_key, sesion_programada=None, fecha_destino=None,
):
    """Persiste movilidad real y aplica una sola resolución sobre el Gym."""
    if getattr(plan, "modalidad", None) != "movilidad":
        raise ValueError("El plan seleccionado no es una sesión de movilidad.")
    if not idempotency_key or not str(idempotency_key).strip():
        raise ValueError("La clave de idempotencia es obligatoria.")
    if sesion_programada is not None and sesion_programada.cliente_id != cliente.id:
        raise ValueError("La sesión programada pertenece a otro cliente.")

    existente = SesionMovilidadAdaptativa.objects.select_related("actividad").filter(
        cliente=cliente, idempotency_key=str(idempotency_key).strip(),
    ).first()
    if existente:
        comando_original = (
            existente.plan_id,
            existente.sesion_programada_id,
            existente.fecha,
            existente.duracion_minutos,
            float(existente.rpe),
            existente.resolucion,
            existente.fecha_destino,
        )
        comando_recibido = (
            plan.pk,
            sesion_programada.pk if sesion_programada is not None else None,
            fecha,
            int(duracion_minutos),
            float(rpe),
            resolucion,
            fecha_destino if resolucion == "posponer" else None,
        )
        if comando_original != comando_recibido:
            raise ValueError(
                "La clave de idempotencia ya se usó para otra sesión de movilidad."
            )
        return existente

    if sesion_programada is not None:
        sesion_programada = SesionProgramada.objects.select_for_update().get(
            pk=sesion_programada.pk,
        )

    _validar_metricas(duracion_minutos, rpe)
    _validar_resolucion(
        cliente, sesion_programada, resolucion, fecha, fecha_destino,
    )

    duracion = int(duracion_minutos)
    rpe_real = float(rpe)
    actividad = ActividadRealizada.objects.create(
        cliente=cliente,
        tipo="movilidad",
        titulo=f"Movilidad · {plan.nombre}",
        fecha=fecha,
        fecha_realizado=fecha,
        duracion_minutos=duracion,
        rpe_medio=rpe_real,
        carga_ua=round(duracion * rpe_real, 1),
        fuente="manual",
        notas=f"Sesión adaptativa de movilidad · resolución: {resolucion}",
    )
    registro = SesionMovilidadAdaptativa.objects.create(
        cliente=cliente,
        plan=plan,
        sesion_programada=sesion_programada,
        actividad=actividad,
        resolucion=resolucion,
        fecha=fecha,
        fecha_destino=fecha_destino if resolucion == "posponer" else None,
        duracion_minutos=duracion,
        rpe=rpe_real,
        idempotency_key=str(idempotency_key).strip(),
    )

    if sesion_programada is not None and resolucion == "posponer":
        sesion_programada.pospuesta_hasta = fecha_destino
        sesion_programada.motivo_estado = (
            "Movilidad completada; entrenamiento pospuesto conscientemente."
        )
        sesion_programada.save(update_fields=[
            "pospuesta_hasta", "motivo_estado", "actualizada_en",
        ])
    elif sesion_programada is not None and resolucion == "sustituir":
        sesion_programada.estado = SesionProgramada.ESTADO_SUSTITUIDA_RECUPERACION
        sesion_programada.pospuesta_hasta = None
        sesion_programada.motivo_estado = (
            "Movilidad completada: sustitución de recuperación sin deuda."
        )
        sesion_programada.save(update_fields=[
            "estado", "pospuesta_hasta", "motivo_estado", "actualizada_en",
        ])

    transaction.on_commit(
        lambda: (
            cache.delete(f"dashboard_acwr_unificado_{cliente.id}"),
            cache.delete(f"dashboard_carga_total_{cliente.id}"),
            cache.delete(f"dashboard_resumen_gym_{cliente.id}"),
        )
    )
    return registro
