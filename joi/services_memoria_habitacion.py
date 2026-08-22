"""Proyección read-only de una memoria revisable para la habitación JOI."""

from __future__ import annotations

from datetime import date, datetime

from core.services.epistemic_review_queue import planificar_revision_memoria


_LABELS = {
    'revision_vencida': 'Necesita una nueva mirada',
    'pendiente_revision': 'Pendiente de primera revisión',
}

_ESTADO_LABELS = {
    'activa': 'En uso',
    'cuestionada': 'Cuestionada',
    'debilitada': 'Con reservas',
}


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value[:10]) if value else None


def construir_memoria_habitacion(*, cliente, as_of, requested_id=None):
    """Devuelve una sola candidata propia; no muta ni consulta IA/caché."""
    cutoff = _date(as_of)
    queue = planificar_revision_memoria(
        cliente_id=cliente.pk, as_of=cutoff, limit=100000,
    )
    items = queue['items']
    if not items:
        return None

    try:
        requested_id = int(requested_id) if requested_id not in (None, '') else None
    except (TypeError, ValueError):
        requested_id = None
    index_by_id = {item['id']: index for index, item in enumerate(items)}
    index = index_by_id.get(requested_id, 0)
    queue_item = items[index]

    from joi.models import ManualDavid
    manual = ManualDavid.objects.only('pk', 'user_id', 'entrada', 'estado').get(
        pk=queue_item['id'], user_id=cliente.user_id,
    )
    base = _date(queue_item['ultima_evidencia']) or _date(queue_item['creado_en'])
    age_days = max(0, (cutoff - base).days) if base else 0
    current = {
        'id': manual.pk,
        'texto': manual.entrada,
        'estado': manual.estado,
        'estado_label': _ESTADO_LABELS.get(manual.estado, 'En revisión'),
        'classification': queue_item['classification'],
        'classification_label': _LABELS[queue_item['classification']],
        'age_days': age_days,
        'ordinal': index + 1,
        'total': len(items),
    }
    return {
        'count': len(items),
        'current': current,
        'previous_id': items[index - 1]['id'] if index > 0 else None,
        'next_id': items[index + 1]['id'] if index + 1 < len(items) else None,
    }
