"""Contrato read-only para preparar y validar revisiones epistemológicas."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json

from core.services.epistemic_review_queue import planificar_revision_memoria


SCHEMA_VERSION = 1
MAX_BATCH_ITEMS = 8
ALLOWED_ACTIONS = {'mantener', 'debilitar', 'cuestionar', 'descartar'}
MAX_REASON_LENGTH = 240


def traducir_accion_a_revision_humana(action: str) -> str:
    """Puente futuro explícito; no convierte debilitar en acción humana."""
    mapping = {
        'mantener': 'confirmar',
        'cuestionar': 'cuestionar',
        'descartar': 'descartar',
    }
    if action == 'debilitar':
        raise ValueError('debilitar no es una acción humana del ledger')
    try:
        return mapping[action]
    except KeyError as exc:
        raise ValueError('acción de propuesta no traducible') from exc


def _parse_ref(raw: str) -> tuple[int, str]:
    try:
        raw_id, fingerprint = raw.split(':', 1)
        item_id = int(raw_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('item inválido; use id:fingerprint') from exc
    if item_id <= 0 or len(fingerprint) != 64:
        raise ValueError('item inválido; use id:fingerprint')
    try:
        int(fingerprint, 16)
    except ValueError as exc:
        raise ValueError('fingerprint inválido') from exc
    return item_id, fingerprint.lower()


def preparar_lote_revision(*, cliente_id: int, as_of, item_refs: list[str]) -> dict:
    refs = list(item_refs or [])
    if not refs:
        raise ValueError('se requiere al menos un item')
    if len(refs) > MAX_BATCH_ITEMS:
        raise ValueError(f'el lote admite un máximo de {MAX_BATCH_ITEMS} items')
    parsed = [_parse_ref(raw) for raw in refs]
    ids = [item_id for item_id, _ in parsed]
    if len(ids) != len(set(ids)):
        raise ValueError('item duplicado')

    queue = planificar_revision_memoria(
        cliente_id=cliente_id, as_of=as_of, limit=100000,
    )
    by_id = {item['id']: item for item in queue['items']}
    for item_id, fingerprint in parsed:
        item = by_id.get(item_id)
        if item is None:
            raise ValueError(f'item {item_id} no elegible en la cola actual')
        if item['fingerprint'] != fingerprint:
            raise ValueError(f'fingerprint stale para item {item_id}')

    selected_ids = set(ids)
    items = [item for item in queue['items'] if item['id'] in selected_ids]
    manifest_source = '|'.join(f"{item['id']}:{item['fingerprint']}" for item in items)
    return {
        'schema_version': SCHEMA_VERSION,
        'cliente_id': cliente_id,
        'as_of': queue['as_of'],
        'items': items,
        'item_count': len(items),
        'manifest_fingerprint': hashlib.sha256(manifest_source.encode('utf-8')).hexdigest(),
        'execution_enabled': False,
        'solo_lectura': True,
    }


def _construir_payload_privado(*, cliente_id: int, item_ids: list[int]) -> list[dict]:
    """Carga privada para una integración futura; nunca se usa en la salida CLI."""
    from clientes.models import Cliente
    from joi.models import ManualDavid

    cliente = Cliente.objects.only('user_id').get(pk=cliente_id)
    rows = ManualDavid.objects.filter(
        user_id=cliente.user_id, pk__in=item_ids,
    ).order_by('pk')
    return [{
        'id': row.pk,
        'entrada': row.entrada,
        'notas_revision': row.notas_revision,
        'hipotesis_contraria': row.hipotesis_contraria,
    } for row in rows]


def _load_proposal(payload):
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError('JSON inválido') from exc
    if not isinstance(payload, dict):
        raise ValueError('la propuesta debe ser un objeto JSON')
    return payload


def validar_propuesta_revision(payload, manifest: dict) -> dict:
    proposal = _load_proposal(payload)
    if set(proposal) != {'schema_version', 'items'} or proposal.get('schema_version') != 1:
        raise ValueError('contrato o schema_version inválido')
    items = proposal.get('items')
    if not isinstance(items, list):
        raise ValueError('items debe ser una lista')

    expected = {item['id']: item['fingerprint'] for item in manifest.get('items', [])}
    seen = set()
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('cada item debe ser un objeto')
        action = item.get('action')
        allowed_fields = {'id', 'fingerprint', 'action', 'motivo'}
        if action != 'descartar':
            allowed_fields.add('confidence_delta')
        if set(item) != allowed_fields:
            raise ValueError('campos extra, ausentes o delta no permitido')
        item_id = item.get('id')
        if item_id in seen:
            raise ValueError('ID duplicado')
        seen.add(item_id)
        if item_id not in expected:
            raise ValueError('ID ajeno al manifiesto')
        if item.get('fingerprint') != expected[item_id]:
            raise ValueError('fingerprint no coincide')
        if action not in ALLOWED_ACTIONS:
            raise ValueError('acción no permitida')
        reason = item.get('motivo')
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > MAX_REASON_LENGTH:
            raise ValueError('motivo vacío o demasiado largo')
        if action != 'descartar':
            delta = item.get('confidence_delta')
            if isinstance(delta, bool) or not isinstance(delta, (int, float)):
                raise ValueError('confidence_delta inválido')
            valid_delta = (
                0 <= delta <= 0.05 if action == 'mantener'
                else delta == -0.10 if action == 'debilitar'
                else delta == -0.20
            )
            if not valid_delta:
                raise ValueError('confidence_delta fuera de contrato')
        normalized.append(dict(item))

    if seen != set(expected):
        raise ValueError('la cobertura debe ser exacta 1:1')
    return {'schema_version': SCHEMA_VERSION, 'items': normalized}
