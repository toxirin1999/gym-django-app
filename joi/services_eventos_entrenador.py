"""Frontera/outbox entre decisiones ejecutivas de Gym y la voz JOI."""

from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

SCHEMA_VERSION = 1
SOURCE_MODEL = "entrenos.GymDecisionLog"
EVENT_TYPE = "gym_decision_application"
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


def _construir_lote(eventos):
    return {
        "schema_version": 2,
        "event_type": "gym_decision_application_batch",
        "epistemic_level": "applied",
        "status": "aplicada",
        "events": [evento.payload for evento in eventos],
    }


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
