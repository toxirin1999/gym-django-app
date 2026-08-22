"""Ejecución humana transaccional sobre ManualDavid con ledger reversible."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import transaction

from core.services.epistemic_registry import clasificar_revision_manual
from core.services.epistemic_review_queue import fingerprint_manual


SCHEMA_VERSION = 1
HUMAN_ACTIONS = {'confirmar', 'cuestionar', 'descartar', 'posponer'}


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _snapshot(manual, *, operation_as_of) -> dict:
    return {
        'schema_version': SCHEMA_VERSION,
        'estado': manual.estado,
        'activa': manual.activa,
        'confianza': float(manual.confianza),
        'ultima_evidencia': manual.ultima_evidencia.isoformat() if manual.ultima_evidencia else None,
        'fingerprint': fingerprint_manual(manual),
        'operation_as_of': operation_as_of.isoformat(),
    }


def _restore(manual, snapshot):
    manual.estado = snapshot['estado']
    manual.activa = snapshot['activa']
    manual.confianza = snapshot['confianza']
    raw_date = snapshot.get('ultima_evidencia')
    manual.ultima_evidencia = date.fromisoformat(raw_date) if raw_date else None


def _same_request(operation, *, manual_id, actor_id, accion, fingerprint, motivo, as_of, reversa_de_id=None):
    return (
        operation.manual_id == manual_id
        and operation.actor_id == actor_id
        and operation.accion == accion
        and operation.expected_fingerprint == fingerprint
        and operation.motivo == motivo
        and operation.reversa_de_id == reversa_de_id
        and operation.after_snapshot.get('operation_as_of') == as_of.isoformat()
    )


def _existing_or_collision(*, key, **request):
    from joi.models import RevisionManualDavidOperacion
    existing = RevisionManualDavidOperacion.objects.filter(idempotency_key=key).first()
    if not existing:
        return None
    if not _same_request(existing, **request):
        raise ValueError('colisión de idempotencia')
    return existing


@transaction.atomic
def aplicar_revision_memoria(
    *, cliente, actor, manual_id, accion, expected_fingerprint,
    idempotency_key, as_of, motivo='',
):
    from joi.models import ManualDavid, RevisionManualDavidOperacion

    cutoff = _as_date(as_of)
    motivo = (motivo or '').strip()
    if accion not in HUMAN_ACTIONS:
        raise ValueError('acción humana no permitida')
    if len(motivo) > 240:
        raise ValueError('motivo demasiado largo')
    existing = _existing_or_collision(
        key=idempotency_key, manual_id=manual_id, actor_id=actor.pk,
        accion=accion, fingerprint=expected_fingerprint, motivo=motivo,
        as_of=cutoff,
    )
    if existing:
        return existing
    if actor.pk != cliente.user_id:
        raise ValueError('actor no autorizado para el cliente')

    try:
        manual = ManualDavid.objects.select_for_update().get(pk=manual_id)
    except ManualDavid.DoesNotExist as exc:
        raise ValueError('la memoria no existe o no pertenece al cliente') from exc
    if manual.user_id != cliente.user_id:
        raise ValueError('la memoria no pertenece al cliente')
    # Relectura tras el lock: un retry concurrente pudo completar mientras
    # esperábamos por esta misma memoria.
    existing = _existing_or_collision(
        key=idempotency_key, manual_id=manual_id, actor_id=actor.pk,
        accion=accion, fingerprint=expected_fingerprint, motivo=motivo,
        as_of=cutoff,
    )
    if existing:
        return existing
    latest_effective_operation = (
        RevisionManualDavidOperacion.objects.select_for_update()
        .filter(
            manual_id=manual.pk,
            reversa_de__isnull=True,
            reversion__isnull=True,
        )
        .exclude(accion='deshacer')
        .order_by('-created_at', '-pk')
        .first()
    )
    if (
        latest_effective_operation
        and latest_effective_operation.accion in {'cuestionar', 'posponer'}
        and latest_effective_operation.aplazada_hasta
        and cutoff < latest_effective_operation.aplazada_hasta
    ):
        raise ValueError(
            'la revisión humana está aplazada hasta '
            f'{latest_effective_operation.aplazada_hasta.isoformat()}'
        )
    current_fingerprint = fingerprint_manual(manual)
    if current_fingerprint != expected_fingerprint:
        raise ValueError('fingerprint actual no coincide')
    eligible = clasificar_revision_manual(
        origen=manual.origen, tipo=manual.tipo, estado=manual.estado,
        activa=manual.activa, creado_en=manual.creado_en,
        ultima_evidencia=manual.ultima_evidencia, as_of=cutoff,
    )
    if not eligible:
        raise ValueError('la memoria ya no es elegible para revisión')

    before = _snapshot(manual, operation_as_of=cutoff)
    aplazada_hasta = None
    update_fields = []
    if accion == 'confirmar':
        manual.estado, manual.activa = 'activa', True
        manual.confianza = round(min(1.0, float(manual.confianza) + 0.05), 6)
        manual.ultima_evidencia = cutoff
        update_fields = ['estado', 'activa', 'confianza', 'ultima_evidencia']
    elif accion == 'cuestionar':
        manual.estado, manual.activa = 'cuestionada', True
        manual.confianza = round(max(0.0, float(manual.confianza) - 0.20), 6)
        aplazada_hasta = cutoff + timedelta(days=14)
        update_fields = ['estado', 'activa', 'confianza']
    elif accion == 'descartar':
        manual.estado, manual.activa, manual.confianza = 'descartada', False, 0.0
        manual.ultima_evidencia = cutoff
        update_fields = ['estado', 'activa', 'confianza', 'ultima_evidencia']
    else:
        aplazada_hasta = cutoff + timedelta(days=14)

    if update_fields:
        manual.save(update_fields=update_fields)
    after = _snapshot(manual, operation_as_of=cutoff)
    return RevisionManualDavidOperacion.objects.create(
        manual=manual, actor=actor, accion=accion,
        idempotency_key=idempotency_key,
        expected_fingerprint=expected_fingerprint,
        before_snapshot=before, after_snapshot=after,
        aplazada_hasta=aplazada_hasta, motivo=motivo,
        schema_version=SCHEMA_VERSION,
    )


@transaction.atomic
def deshacer_revision_memoria(
    *, cliente, actor, operacion_id, idempotency_key, as_of,
):
    from joi.models import ManualDavid, RevisionManualDavidOperacion

    cutoff = _as_date(as_of)
    if actor.pk != cliente.user_id:
        raise ValueError('actor no autorizado')
    try:
        original = RevisionManualDavidOperacion.objects.select_for_update().get(pk=operacion_id)
    except RevisionManualDavidOperacion.DoesNotExist as exc:
        raise ValueError('operación original no existe') from exc
    expected_current = original.after_snapshot.get('fingerprint', '')
    existing = _existing_or_collision(
        key=idempotency_key, manual_id=original.manual_id, actor_id=actor.pk,
        accion='deshacer', fingerprint=expected_current, motivo='',
        as_of=cutoff, reversa_de_id=original.pk,
    )
    if existing:
        return existing
    # Igual que en aplicar: cubrir el retry que terminó mientras se esperaba
    # el lock de la operación original.
    existing = _existing_or_collision(
        key=idempotency_key, manual_id=original.manual_id, actor_id=actor.pk,
        accion='deshacer', fingerprint=expected_current, motivo='',
        as_of=cutoff, reversa_de_id=original.pk,
    )
    if existing:
        return existing
    if original.actor_id != actor.pk or original.manual.user_id != cliente.user_id:
        raise ValueError('actor no autorizado para deshacer')
    if original.accion == 'deshacer':
        raise ValueError('no se puede deshacer una reversión')
    if RevisionManualDavidOperacion.objects.filter(reversa_de=original).exists():
        raise ValueError('la operación ya fue deshecha')
    if RevisionManualDavidOperacion.objects.filter(
        manual_id=original.manual_id, pk__gt=original.pk, reversa_de__isnull=True,
    ).exists():
        raise ValueError('la memoria cambió después de la operación')

    manual = ManualDavid.objects.select_for_update().get(pk=original.manual_id)
    if fingerprint_manual(manual) != expected_current:
        raise ValueError('la memoria cambió desde la operación')
    before_undo = _snapshot(manual, operation_as_of=cutoff)
    _restore(manual, original.before_snapshot)
    manual.save(update_fields=['estado', 'activa', 'confianza', 'ultima_evidencia'])
    after_undo = _snapshot(manual, operation_as_of=cutoff)
    return RevisionManualDavidOperacion.objects.create(
        manual=manual, actor=actor, accion='deshacer',
        idempotency_key=idempotency_key,
        expected_fingerprint=expected_current,
        before_snapshot=before_undo, after_snapshot=after_undo,
        motivo='', reversa_de=original, schema_version=SCHEMA_VERSION,
    )
