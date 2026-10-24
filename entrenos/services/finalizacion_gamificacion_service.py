"""Cierre explícito, transaccional e idempotente de la gamificación."""

from django.db import transaction

from entrenos.models import EntrenoRealizado


@transaction.atomic
def finalizar_gamificacion_entreno(entreno):
    """Procesa una sesión completa exactamente una vez.

    El llamador debe invocar este cierre después de persistir hijos y métricas.
    El bloqueo del padre convierte ``procesado_gamificacion`` en el latch de
    autoridad; cualquier excepción revierte tanto premios como latch.
    """
    entreno_id = getattr(entreno, "pk", entreno)
    if not entreno_id:
        raise ValueError("El entrenamiento debe estar persistido antes de finalizarlo")

    bloqueado = (
        EntrenoRealizado.objects.select_for_update()
        .select_related("cliente", "rutina")
        .get(pk=entreno_id)
    )
    if bloqueado.procesado_gamificacion:
        return {"already_processed": True}

    from django.conf import settings
    from logros.services import CodiceService

    if not getattr(settings, 'GAMIFICACION_ACTIVA', False):
        # 24-oct-2026 (poda): sin puntos, pruebas, misiones ni notificaciones.
        # Se conserva lo que usan otras pantallas: la sesión del panel y los
        # récords personales.
        bloqueado._defer_cierre_aprendizaje_gym = True
        CodiceService._asegurar_sesion_entrenamiento(bloqueado)
        try:
            from entrenos.services.records_service import RecordsService
            RecordsService.detectar_records_sesion(bloqueado)
        except Exception:
            pass
        bloqueado.procesado_gamificacion = True
        bloqueado.save(update_fields=["procesado_gamificacion"])
        return {"already_processed": False, "gamificacion_apagada": True}

    # Codice actualiza métricas del padre y el latch. Esos saves internos no
    # constituyen otro cierre causal de aprendizaje.
    bloqueado._defer_cierre_aprendizaje_gym = True
    resultado = CodiceService.procesar_entreno_completo(bloqueado)
    bloqueado.procesado_gamificacion = True
    bloqueado.save(update_fields=["procesado_gamificacion"])
    return {"already_processed": False, **resultado}
