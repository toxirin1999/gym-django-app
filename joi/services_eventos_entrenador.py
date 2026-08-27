"""Frontera/outbox entre decisiones ejecutivas de Gym y la voz JOI."""

from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

SCHEMA_VERSION = 1
SOURCE_MODEL = "entrenos.GymDecisionLog"
EVENT_TYPE = "gym_decision_application"
OUTCOME_EVENT_TYPE = "gym_decision_outcome"
ACCIONES_VERBALIZABLES = frozenset({
    "cambiar_variante", "bajar_peso", "deload", "mantener",
})
MOTIVOS_CODIGO_PERMITIDOS = frozenset({
    "tecnica_comprometida", "tope_maquina", "tope_maquina_sin_margen",
    "fallo_intencional", "fallo_no_controlado",
    "fallo_repetido_no_controlado", "rpe_alto_sostenido", "rpe_extremo",
    "molestia_reciente", "progresion_peso", "progresion_reps",
})


def construir_evento_decision_aplicada(decision):
    """Construye un DTO allowlisted; nunca copia campos narrativos libres."""
    facts = {
        "accion": decision.accion,
        "ejercicio": decision.ejercicio,
        "confianza": decision.confianza,
    }
    if decision.motivo_codigo in MOTIVOS_CODIGO_PERMITIDOS:
        facts["motivo_codigo"] = decision.motivo_codigo
    for nombre in ("peso_anterior", "rpe_anterior", "valor_cambio"):
        valor = getattr(decision, nombre, None)
        if valor is not None:
            facts[nombre] = valor
    ocurrido = decision.fecha_aplicacion or timezone.now()
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "source_model": SOURCE_MODEL,
        "source_id": decision.pk,
        "occurred_at": ocurrido.isoformat(),
        "epistemic_level": "applied",
        "status": "aplicada",
        "facts": facts,
    }


def publicar_evento_decision_aplicada(decision):
    """Encola una aplicación confirmada; nunca invoca IA en esta ruta."""
    if decision.estado_aplicacion != "aplicada":
        return None
    if decision.accion not in ACCIONES_VERBALIZABLES:
        return None
    payload = construir_evento_decision_aplicada(decision)
    from joi.models import EventoEntrenadorJOI
    evento, _ = EventoEntrenadorJOI.objects.get_or_create(
        event_type=payload["event_type"],
        source_model=payload["source_model"],
        source_id=payload["source_id"],
        status=payload["status"],
        defaults={"user": decision.cliente.user, "payload": payload},
    )
    return evento


encolar_evento_decision_aplicada = publicar_evento_decision_aplicada


def construir_evento_resultado_decision(decision):
    """DTO evaluado y allowlisted; excluye toda explicación narrativa libre."""
    facts = {
        "resultado": decision.resultado,
        "accion": decision.accion,
        "ejercicio": decision.ejercicio,
        "confianza": decision.confianza,
        "fecha_evaluacion": decision.fecha_evaluacion.isoformat(),
    }
    if decision.motivo_codigo in MOTIVOS_CODIGO_PERMITIDOS:
        facts["motivo_codigo"] = decision.motivo_codigo
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": OUTCOME_EVENT_TYPE,
        "source_model": SOURCE_MODEL,
        "source_id": decision.pk,
        "occurred_at": decision.fecha_evaluacion.isoformat(),
        "epistemic_level": "evaluated",
        "status": decision.resultado,
        "facts": facts,
    }


def publicar_evento_resultado_decision(decision):
    """Encola únicamente cierres evaluados del productor canónico."""
    if decision.resultado not in {"validada", "fallida", "neutra"}:
        return None
    if decision.fecha_evaluacion is None:
        return None
    payload = construir_evento_resultado_decision(decision)
    from joi.models import EventoEntrenadorJOI
    evento, _ = EventoEntrenadorJOI.objects.get_or_create(
        event_type=payload["event_type"],
        source_model=payload["source_model"],
        source_id=payload["source_id"],
        status=payload["status"],
        defaults={"user": decision.cliente.user, "payload": payload},
    )
    return evento


def _construir_lote(eventos):
    tipos = {evento.payload.get("event_type") for evento in eventos}
    if tipos == {EVENT_TYPE}:
        event_type = "gym_decision_application_batch"
        epistemic_level = "applied"
        status = "aplicada"
    elif tipos == {OUTCOME_EVENT_TYPE}:
        event_type = "gym_decision_event_batch"
        epistemic_level = "evaluated"
        estados = {evento.payload.get("status") for evento in eventos}
        status = estados.pop() if len(estados) == 1 else "mixed"
    else:
        event_type = "gym_decision_event_batch"
        epistemic_level = "mixed"
        status = "mixed"
    return {
        "schema_version": 2,
        "event_type": event_type,
        "epistemic_level": epistemic_level,
        "status": status,
        "events": [_serializar_evento_para_voz(evento) for evento in eventos],
    }


def _serializar_evento_para_voz(evento):
    """Reconstruye el recibo desde una allowlist aunque la fila sea manipulada."""
    payload = evento.payload or {}
    facts = payload.get("facts") or {}
    permitidos = {"accion", "ejercicio", "confianza", "motivo_codigo"}
    if evento.event_type == EVENT_TYPE:
        permitidos.update({"peso_anterior", "rpe_anterior", "valor_cambio"})
    elif evento.event_type == OUTCOME_EVENT_TYPE:
        permitidos.update({"resultado", "fecha_evaluacion"})
    facts_limpios = {clave: facts[clave] for clave in permitidos if clave in facts}
    if facts_limpios.get("motivo_codigo") not in MOTIVOS_CODIGO_PERMITIDOS:
        facts_limpios.pop("motivo_codigo", None)
    return {
        "schema_version": payload.get("schema_version", SCHEMA_VERSION),
        "event_type": evento.event_type,
        "source_model": evento.source_model,
        "source_id": evento.source_id,
        "occurred_at": payload.get("occurred_at"),
        "epistemic_level": (
            "evaluated" if evento.event_type == OUTCOME_EVENT_TYPE else "applied"
        ),
        "status": evento.status,
        "facts": facts_limpios,
    }


def _ocurrido_en(evento):
    valor = (evento.payload or {}).get("occurred_at")
    try:
        ocurrido = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return evento.creado_en
    if timezone.is_naive(ocurrido):
        ocurrido = timezone.make_aware(ocurrido, timezone.get_current_timezone())
    return ocurrido


def _prioridad_evento(evento):
    return 0 if evento.event_type == EVENT_TYPE else 1


def reconciliar_eventos_en_apertura(cliente, *, limite=20, ventana_horas=48):
    """Integra hechos recientes en una única apertura y publica sus recibos.

    Retorna ``(mensaje, habia_eventos_elegibles)`` para que el llamador pueda
    distinguir una cola vacía de un fallo y no crear una apertura parcial.
    """
    from joi.models import EventoEntrenadorJOI

    limite = max(1, min(int(limite), 20))
    ahora = timezone.now()
    umbral = ahora - timedelta(hours=ventana_horas)

    try:
        with transaction.atomic():
            EventoEntrenadorJOI.objects.select_for_update().filter(
                user=cliente.user,
                estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
                reclamado_en__lt=ahora - timedelta(minutes=5),
            ).update(
                estado=EventoEntrenadorJOI.ESTADO_PENDIENTE,
                reclamado_en=None,
                ultimo_error="stale_claim_recovered",
            )

            pendientes = list(
                EventoEntrenadorJOI.objects.select_for_update(skip_locked=True)
                .filter(user=cliente.user, estado=EventoEntrenadorJOI.ESTADO_PENDIENTE)
            )
            elegibles = [
                evento for evento in pendientes
                if evento.source_model == SOURCE_MODEL
                and evento.event_type in {EVENT_TYPE, OUTCOME_EVENT_TYPE}
                and _ocurrido_en(evento) >= umbral
            ]
            elegibles.sort(key=lambda evento: (
                _ocurrido_en(evento), _prioridad_evento(evento), evento.pk,
            ))
            candidatos = elegibles[:limite]
            if not candidatos:
                return None, False

            ids = [evento.pk for evento in candidatos]
            EventoEntrenadorJOI.objects.filter(pk__in=ids).update(
                estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
                intentos=F("intentos") + 1,
                reclamado_en=ahora,
                ultimo_error="",
            )

            lote = _construir_lote(candidatos)
            from joi.services import generar_mensaje_joi
            mensaje = generar_mensaje_joi(
                cliente,
                "apertura_manana",
                {"_evento_entrenador": lote},
            )
            if mensaje is None:
                # Fuerza rollback del claim y de cualquier escritura parcial
                # que el generador hubiera alcanzado antes de devolver None.
                raise RuntimeError("message_not_created")

            EventoEntrenadorJOI.objects.filter(pk__in=ids).update(
                estado=EventoEntrenadorJOI.ESTADO_PUBLICADO,
                mensaje=mensaje,
                reclamado_en=None,
                procesado_en=timezone.now(),
                ultimo_error="",
            )
            return mensaje, True
    except Exception:
        # La transacción revierte claim, apertura y recibos como una unidad.
        return None, True


def procesar_eventos_entrenador_pendientes(cliente, *, limite=20):
    """Publica un lote ordenado de un cliente como un único mensaje JOI.

    El claim se persiste antes de invocar al proveedor. Un fallo devuelve el
    lote a pendiente, mientras que el éxito enlaza cada recibo solo después de
    que ``MensajeJOI`` exista.
    """
    from joi.models import EventoEntrenadorJOI

    limite = max(1, min(int(limite), 100))
    with transaction.atomic():
        ahora = timezone.now()
        # Un worker puede morir después del claim. Las reclamaciones antiguas
        # vuelven a la cola y conservan el contador de intentos.
        EventoEntrenadorJOI.objects.select_for_update().filter(
            user=cliente.user,
            estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
            reclamado_en__lt=ahora - timedelta(minutes=5),
        ).update(
            estado=EventoEntrenadorJOI.ESTADO_PENDIENTE,
            reclamado_en=None,
            ultimo_error="stale_claim_recovered",
        )
        candidatos = list(
            EventoEntrenadorJOI.objects.select_for_update(skip_locked=True)
            .filter(user=cliente.user, estado=EventoEntrenadorJOI.ESTADO_PENDIENTE)
            .order_by("creado_en", "id")[:limite]
        )
        if not candidatos:
            return None
        ids = [evento.pk for evento in candidatos]
        EventoEntrenadorJOI.objects.filter(pk__in=ids).update(
            estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
            intentos=F("intentos") + 1,
            reclamado_en=ahora,
            ultimo_error="",
        )

    lote = _construir_lote(candidatos)
    try:
        from joi.services import generar_mensaje_joi
        mensaje = generar_mensaje_joi(
            cliente,
            "decision_plan",
            {"_evento_entrenador": lote, "_contexto_minimo": True},
        )
    except Exception:
        mensaje = None

    if mensaje is None:
        with transaction.atomic():
            EventoEntrenadorJOI.objects.select_for_update().filter(
                pk__in=ids,
                estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
            ).update(
                estado=EventoEntrenadorJOI.ESTADO_PENDIENTE,
                reclamado_en=None,
                ultimo_error="message_not_created",
            )
        return None

    with transaction.atomic():
        EventoEntrenadorJOI.objects.select_for_update().filter(
            pk__in=ids,
            estado=EventoEntrenadorJOI.ESTADO_PROCESANDO,
        ).update(
            estado=EventoEntrenadorJOI.ESTADO_PUBLICADO,
            mensaje=mensaje,
            procesado_en=timezone.now(),
            ultimo_error="",
        )
    return mensaje
