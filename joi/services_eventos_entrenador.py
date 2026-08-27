"""Frontera entre decisiones ejecutivas de Gym y la voz JOI."""

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


def _mensaje_existente(evento):
    from joi.models import MensajeJOI

    for mensaje in MensajeJOI.objects.filter(trigger="decision_plan").only("id", "contexto"):
        contexto = mensaje.contexto or {}
        if (
            contexto.get("source_model") == evento["source_model"]
            and contexto.get("source_id") == evento["source_id"]
            and contexto.get("status") == evento["status"]
        ):
            return mensaje
    return None


def publicar_evento_decision_aplicada(decision):
    """Verbaliza una aplicación confirmada, idempotente y reintentable."""
    if decision.estado_aplicacion != "aplicada":
        return None
    if decision.accion not in ACCIONES_VERBALIZABLES:
        return None
    evento = construir_evento_decision_aplicada(decision)
    existente = _mensaje_existente(evento)
    if existente:
        return existente
    from joi.services import generar_mensaje_joi
    return generar_mensaje_joi(
        decision.cliente, "decision_plan", {"_evento_entrenador": evento},
    )
