"""Auditoría read-only del ledger humano de ManualDavid (F1/F2/G)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import re

from django.db.models import Q

from core.services.epistemic_registry import clasificar_revision_manual
from core.services.epistemic_review_queue import (
    fingerprint_manual,
    planificar_revision_memoria,
)
from joi.services_manual_authority import resolver_autoridad_manual


SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_FIELDS = {
    'schema_version', 'estado', 'activa', 'confianza', 'ultima_evidencia',
    'fingerprint', 'operation_as_of',
}
SEMANTIC_FIELDS = {
    'estado', 'activa', 'confianza', 'ultima_evidencia', 'fingerprint',
}
HEX_64 = re.compile(r'^[0-9a-f]{64}$')


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _finding(code, *, manual_id=None, operation_id=None, field=None):
    item = {
        'tipo_registro': 'hallazgo',
        'schema_version': SCHEMA_VERSION,
        'code': code,
        'manual_id': manual_id,
        'operation_id': operation_id,
    }
    if field:
        item['field'] = field
    return item


def _snapshot_valid(snapshot):
    return (
        isinstance(snapshot, dict)
        and SNAPSHOT_FIELDS.issubset(snapshot)
        and snapshot.get('schema_version') == SNAPSHOT_SCHEMA_VERSION
        and isinstance(snapshot.get('activa'), bool)
        and isinstance(snapshot.get('confianza'), (int, float))
        and isinstance(snapshot.get('estado'), str)
        and isinstance(snapshot.get('operation_as_of'), str)
    )


def _semantic(snapshot):
    return {key: snapshot.get(key) for key in SEMANTIC_FIELDS}


def _same_number(left, right):
    try:
        return abs(float(left) - float(right)) < 0.000001
    except (TypeError, ValueError):
        return False


def _expected_semantics(operation, before, after):
    """Comprueba únicamente la transición declarada; no reconstruye texto privado."""
    try:
        operation_date = date.fromisoformat(after['operation_as_of'])
    except (TypeError, ValueError):
        return False
    if before.get('operation_as_of') != after.get('operation_as_of'):
        return False

    action = operation.accion
    if action == 'confirmar':
        return (
            after['estado'] == 'activa'
            and after['activa'] is True
            and _same_number(after['confianza'], min(1.0, float(before['confianza']) + 0.05))
            and after['ultima_evidencia'] == operation_date.isoformat()
            and operation.aplazada_hasta is None
        )
    if action == 'cuestionar':
        return (
            after['estado'] == 'cuestionada'
            and after['activa'] is True
            and _same_number(after['confianza'], max(0.0, float(before['confianza']) - 0.20))
            and after['ultima_evidencia'] == before['ultima_evidencia']
            and operation.aplazada_hasta == operation_date + timedelta(days=14)
        )
    if action == 'descartar':
        return (
            after['estado'] == 'descartada'
            and after['activa'] is False
            and _same_number(after['confianza'], 0.0)
            and after['ultima_evidencia'] == operation_date.isoformat()
            and operation.aplazada_hasta is None
        )
    if action == 'posponer':
        return (
            _semantic(after) == _semantic(before)
            and operation.aplazada_hasta == operation_date + timedelta(days=14)
        )
    return action == 'deshacer'


def auditar_revision_memoria(*, cliente_id, as_of, limit=500):
    """Devuelve hallazgos estructurados y resumen sin modificar ningún modelo."""
    from clientes.models import Cliente
    from joi.models import ManualDavid, RevisionManualDavidOperacion

    cutoff = _as_date(as_of)
    cliente = Cliente.objects.only('pk', 'user_id').get(pk=cliente_id)
    manuals = list(ManualDavid.objects.filter(user_id=cliente.user_id).order_by('pk'))
    manual_by_id = {manual.pk: manual for manual in manuals}
    operations = list(
        RevisionManualDavidOperacion.objects.filter(
            Q(manual__user_id=cliente.user_id) | Q(actor_id=cliente.user_id),
        ).select_related('manual').order_by('created_at', 'pk')
    )
    operation_by_id = {operation.pk: operation for operation in operations}
    reversals_by_original = {}
    for operation in operations:
        if operation.reversa_de_id:
            reversals_by_original.setdefault(operation.reversa_de_id, []).append(operation)

    findings = []
    structurally_valid = set()
    for operation in operations:
        manual_id = operation.manual_id
        operation_id = operation.pk
        valid = True
        if operation.manual.user_id != cliente.user_id:
            findings.append(_finding(
                'operation_manual_not_owned', manual_id=manual_id,
                operation_id=operation_id,
            ))
            valid = False
        if operation.actor_id != cliente.user_id:
            findings.append(_finding(
                'operation_actor_mismatch', manual_id=manual_id,
                operation_id=operation_id,
            ))
            valid = False
        if operation.schema_version != SCHEMA_VERSION:
            findings.append(_finding(
                'operation_schema_invalid', manual_id=manual_id,
                operation_id=operation_id, field='schema_version',
            ))
            valid = False
        if not HEX_64.fullmatch(operation.expected_fingerprint or ''):
            findings.append(_finding(
                'expected_fingerprint_invalid', manual_id=manual_id,
                operation_id=operation_id, field='expected_fingerprint',
            ))
            valid = False

        before_ok = _snapshot_valid(operation.before_snapshot)
        after_ok = _snapshot_valid(operation.after_snapshot)
        for field, snapshot, snapshot_ok in (
            ('before', operation.before_snapshot, before_ok),
            ('after', operation.after_snapshot, after_ok),
        ):
            if not snapshot_ok:
                findings.append(_finding(
                    'snapshot_schema_invalid', manual_id=manual_id,
                    operation_id=operation_id, field=field,
                ))
                valid = False
            elif not HEX_64.fullmatch(snapshot.get('fingerprint') or ''):
                findings.append(_finding(
                    'snapshot_fingerprint_invalid', manual_id=manual_id,
                    operation_id=operation_id, field=field,
                ))
                valid = False

        if before_ok and after_ok:
            if operation.expected_fingerprint != operation.before_snapshot['fingerprint']:
                findings.append(_finding(
                    'expected_fingerprint_mismatch', manual_id=manual_id,
                    operation_id=operation_id,
                ))
                valid = False
            if not _expected_semantics(
                operation, operation.before_snapshot, operation.after_snapshot,
            ):
                findings.append(_finding(
                    'action_semantics_mismatch', manual_id=manual_id,
                    operation_id=operation_id,
                ))
                valid = False

        if operation.accion == 'deshacer':
            original = operation_by_id.get(operation.reversa_de_id)
            if (
                original is None
                or original.accion == 'deshacer'
                or original.manual_id != operation.manual_id
                or original.actor_id != operation.actor_id
            ):
                findings.append(_finding(
                    'undo_reference_invalid', manual_id=manual_id,
                    operation_id=operation_id,
                ))
                valid = False
            elif before_ok and after_ok:
                if (
                    _semantic(operation.before_snapshot) != _semantic(original.after_snapshot)
                    or _semantic(operation.after_snapshot) != _semantic(original.before_snapshot)
                ):
                    findings.append(_finding(
                        'undo_semantics_mismatch', manual_id=manual_id,
                        operation_id=operation_id,
                    ))
                    valid = False
        elif operation.reversa_de_id is not None:
            findings.append(_finding(
                'non_undo_has_reverse_reference', manual_id=manual_id,
                operation_id=operation_id,
            ))
            valid = False
        if len(reversals_by_original.get(operation.pk, [])) > 1:
            findings.append(_finding(
                'multiple_undo_operations', manual_id=manual_id,
                operation_id=operation_id,
            ))
            valid = False
        if valid:
            structurally_valid.add(operation.pk)

    effective = [
        operation for operation in operations
        if operation.accion != 'deshacer'
        and operation.pk not in reversals_by_original
    ]
    latest_effective = {}
    for operation in effective:
        latest_effective[operation.manual_id] = operation

    queue_result = planificar_revision_memoria(
        cliente_id=cliente_id, as_of=cutoff, limit=max(1, len(manuals) + 1),
    )
    queue_ids = {item['id'] for item in queue_result['items']}
    authority_items = resolver_autoridad_manual(cliente.user, as_of=cutoff)
    authority_by_id = {item['id']: item for item in authority_items}
    allowed_authorities = {
        'explicit_correction', 'user_confirmed', 'stable_manual',
        'automatic_hypothesis', 'uncertain_hypothesis',
    }
    for item in authority_items:
        if item['authority'] not in allowed_authorities:
            findings.append(_finding(
                'authority_not_permitted', manual_id=item['id'],
            ))

    for manual_id, operation in latest_effective.items():
        manual = manual_by_id.get(manual_id)
        if manual is None or operation.pk not in structurally_valid:
            if manual_id in authority_by_id:
                findings.append(_finding(
                    'authority_from_invalid_operation', manual_id=manual_id,
                    operation_id=operation.pk,
                ))
            continue
        if fingerprint_manual(manual) != operation.after_snapshot.get('fingerprint'):
            findings.append(_finding(
                'current_state_stale_external', manual_id=manual_id,
                operation_id=operation.pk,
            ))

        in_queue = manual_id in queue_ids
        authority = authority_by_id.get(manual_id)
        action = operation.accion
        if action == 'confirmar':
            if in_queue:
                findings.append(_finding(
                    'confirmed_present_in_queue', manual_id=manual_id,
                    operation_id=operation.pk,
                ))
            if not authority or authority['authority'] != 'user_confirmed':
                findings.append(_finding(
                    'confirmed_authority_mismatch', manual_id=manual_id,
                    operation_id=operation.pk,
                ))
        elif action == 'descartar':
            if manual.activa or in_queue or authority:
                findings.append(_finding(
                    'discarded_still_visible', manual_id=manual_id,
                    operation_id=operation.pk,
                ))
        elif action in {'posponer', 'cuestionar'}:
            cooling_down = bool(
                operation.aplazada_hasta and cutoff < operation.aplazada_hasta
            )
            if cooling_down:
                if in_queue or authority:
                    findings.append(_finding(
                        'cooldown_visibility_mismatch', manual_id=manual_id,
                        operation_id=operation.pk,
                    ))
            else:
                eligible = clasificar_revision_manual(
                    origen=manual.origen, tipo=manual.tipo,
                    estado=manual.estado, activa=manual.activa,
                    creado_en=manual.creado_en,
                    ultima_evidencia=manual.ultima_evidencia,
                    as_of=cutoff,
                )
                if bool(eligible) != in_queue:
                    findings.append(_finding(
                        'queue_eligibility_mismatch', manual_id=manual_id,
                        operation_id=operation.pk,
                    ))
                expected_authority = (
                    'uncertain_hypothesis' if action == 'cuestionar'
                    else 'automatic_hypothesis'
                )
                if not authority or authority['authority'] != expected_authority:
                    findings.append(_finding(
                        'cooldown_authority_mismatch', manual_id=manual_id,
                        operation_id=operation.pk,
                    ))

    findings.sort(key=lambda item: (
        item['code'], item.get('manual_id') or 0,
        item.get('operation_id') or 0, item.get('field', ''),
    ))
    counts = Counter(item['code'] for item in findings)
    safe_limit = max(0, int(limit))
    emitted = findings[:safe_limit]
    summary = {
        'tipo_registro': 'resumen',
        'schema_version': SCHEMA_VERSION,
        'cliente_id': cliente_id,
        'as_of': cutoff.isoformat(),
        'limit': safe_limit,
        'hallazgos_total': len(findings),
        'emitidos': len(emitted),
        'truncados': max(0, len(findings) - len(emitted)),
        'counts_by_code': dict(sorted(counts.items())),
        'totals': {
            'manuals': len(manuals),
            'operations': len(operations),
            'effective': len(effective),
            'queue': len(queue_ids),
            'authority': len(authority_items),
        },
        'solo_lectura': True,
    }
    return {'findings': emitted, 'summary': summary}

