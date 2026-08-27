"""Frontera/outbox entre decisiones ejecutivas de Gym y la voz JOI."""

from datetime import datetime, timedelta

from django.core.cache import cache
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


def resolver_apertura_diaria_entrenador(cliente, fecha_ref=None):
    """Resuelve una vez la apertura diaria para web y tareas programadas.

    Una apertura existente es inmutable. Los hechos que llegan después se
    publican mediante la voz ejecutiva normal, sin reescribir el inicio del día.
    """
    from joi.models import MensajeJOI

    fecha = fecha_ref or timezone.localdate()
    apertura_existente = MensajeJOI.objects.filter(
        user=cliente.user,
        trigger="apertura_manana",
        creado_en__date=fecha,
    ).exists()
    if apertura_existente:
        return procesar_eventos_entrenador_pendientes(cliente, limite=20)

    lock_key = f"joi_apertura_lock_{cliente.user_id}_{fecha}"
    if not cache.add(lock_key, True, 600):
        return None
    try:
        mensaje, habia_eventos = reconciliar_eventos_en_apertura(
            cliente, limite=20, ventana_horas=48,
        )
        if habia_eventos:
            # En fallo la transacción dejó los recibos pendientes. No se crea
            # una apertura limpia que esconda el lote del siguiente intento.
            if mensaje is None:
                cache.delete(lock_key)
            return mensaje

        from joi.services import generar_mensaje_joi
        return generar_mensaje_joi(cliente, "apertura_manana")
    except Exception:
        cache.delete(lock_key)
        return None


_PAYLOAD_KEYS = frozenset({
    "schema_version", "event_type", "source_model", "source_id",
    "occurred_at", "epistemic_level", "status", "facts",
})


def _parse_as_of(as_of):
    if isinstance(as_of, datetime):
        corte = as_of
    else:
        if hasattr(as_of, "isoformat") and not isinstance(as_of, str):
            valor = as_of.isoformat()
        else:
            valor = str(as_of)
        try:
            corte = datetime.fromisoformat(valor)
        except ValueError as exc:
            raise ValueError("as_of debe ser ISO-8601") from exc
        if len(valor) <= 10:
            corte = datetime.combine(corte.date(), datetime.max.time())
    if timezone.is_naive(corte):
        corte = timezone.make_aware(corte, timezone.get_current_timezone())
    return corte


def auditar_outbox_entrenador_joi(*, as_of, cliente_id=None, limit=500):
    """Audita el outbox en lectura estricta y devuelve datos JSONL seguros."""
    from collections import Counter, defaultdict

    from clientes.models import Cliente
    from joi.models import EventoEntrenadorJOI

    corte = _parse_as_of(as_of)
    limit = max(1, min(int(limit), 5000))
    queryset = EventoEntrenadorJOI.objects.select_related("mensaje").order_by("id")
    if cliente_id is not None:
        user_id = Cliente.objects.only("user_id").get(pk=cliente_id).user_id
        queryset = queryset.filter(user_id=user_id)
    eventos = list(queryset[:limit])
    findings = []

    def add(code, evento, **evidence):
        item = {
            "tipo_registro": "hallazgo",
            "code": code,
            "evento_id": evento.pk,
            "user_id": evento.user_id,
            "event_type": evento.event_type,
            "source_model": evento.source_model,
            "source_id": evento.source_id,
        }
        if evidence:
            item["evidence"] = evidence
        findings.append(item)

    semantic = defaultdict(list)
    for evento in eventos:
        payload = evento.payload if isinstance(evento.payload, dict) else {}
        ocurrido = _ocurrido_en(evento)
        semantic[(evento.event_type, evento.source_model, evento.source_id)].append(evento)

        if evento.estado == EventoEntrenadorJOI.ESTADO_PENDIENTE and ocurrido < corte - timedelta(hours=48):
            add("pending_over_48h", evento)
        if (
            evento.estado == EventoEntrenadorJOI.ESTADO_PROCESANDO
            and evento.reclamado_en
            and evento.reclamado_en < corte - timedelta(minutes=5)
        ):
            add("processing_stale_over_5m", evento)
        if evento.estado == EventoEntrenadorJOI.ESTADO_PUBLICADO and not evento.mensaje_id:
            add("published_without_message", evento)
        if evento.mensaje_id and evento.mensaje is None:
            add("published_message_missing", evento)
        if evento.mensaje_id and evento.mensaje and evento.mensaje.user_id != evento.user_id:
            add("message_user_mismatch", evento)

        source_fields = {
            "event_type": evento.event_type,
            "source_model": evento.source_model,
            "source_id": evento.source_id,
            "status": evento.status,
        }
        mismatches = sorted(
            key for key, expected in source_fields.items()
            if payload.get(key) != expected
        )
        if mismatches:
            add("payload_source_mismatch", evento, fields=mismatches)

        facts = payload.get("facts") if isinstance(payload.get("facts"), dict) else {}
        allowed_facts = {"accion", "ejercicio", "confianza", "motivo_codigo"}
        if evento.event_type == EVENT_TYPE:
            allowed_facts.update({"peso_anterior", "rpe_anterior", "valor_cambio"})
        elif evento.event_type == OUTCOME_EVENT_TYPE:
            allowed_facts.update({"resultado", "fecha_evaluacion"})
        extra_top = sorted(set(payload) - _PAYLOAD_KEYS)
        extra_facts = sorted(set(facts) - allowed_facts)
        if extra_top or extra_facts or not isinstance(payload.get("facts"), dict):
            add(
                "payload_not_allowlisted", evento,
                extra_payload_keys=extra_top, extra_fact_keys=extra_facts,
            )
        if ocurrido > corte:
            add("future_occurred_at", evento)
        if (
            evento.intentos > 0
            and evento.estado != EventoEntrenadorJOI.ESTADO_PUBLICADO
            and not evento.ultimo_error
        ):
            add("attempts_without_error_context", evento, attempts=evento.intentos)

    for key in sorted(semantic, key=lambda item: (item[0], item[1], item[2])):
        duplicados = semantic[key]
        if len(duplicados) > 1:
            for evento in duplicados:
                add(
                    "duplicate_semantic_receipt", evento,
                    duplicate_count=len(duplicados),
                )

    findings.sort(key=lambda item: (item["evento_id"], item["code"]))
    counts = Counter(item["code"] for item in findings)
    estados = Counter(evento.estado for evento in eventos)
    summary = {
        "tipo_registro": "resumen",
        "schema_version": 1,
        "as_of": corte.isoformat(),
        "cliente_id": cliente_id,
        "evaluados": len(eventos),
        "limit": limit,
        "truncados": max(queryset.count() - len(eventos), 0),
        "estados": dict(sorted(estados.items())),
        "backlog": {
            "pendiente": estados.get(EventoEntrenadorJOI.ESTADO_PENDIENTE, 0),
            "procesando": estados.get(EventoEntrenadorJOI.ESTADO_PROCESANDO, 0),
        },
        "counts_by_code": dict(sorted(counts.items())),
        "hallazgos": len(findings),
        "contract_ok": not findings,
        "solo_lectura": True,
    }
    return {"findings": findings, "summary": summary}


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
