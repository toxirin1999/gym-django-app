"""Cola determinista y de solo lectura para revisar memoria epistemológica."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import hashlib
import json

from core.services.epistemic_registry import clasificar_revision_manual


SCHEMA_VERSION = 1


def _iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _fingerprint(manual) -> str:
    # Los textos privados participan en la huella para detectar cambios, pero
    # nunca forman parte del registro emitido.
    payload = {
        'id': manual.pk,
        'entrada': manual.entrada,
        'notas_revision': manual.notas_revision,
        'hipotesis_contraria': manual.hipotesis_contraria,
        'origen': manual.origen,
        'tipo': manual.tipo,
        'estado': manual.estado,
        'activa': manual.activa,
        'confianza': manual.confianza,
        'fuente_mensaje_id': manual.fuente_mensaje_id,
        'creado_en': _iso(manual.creado_en),
        'ultima_evidencia': _iso(manual.ultima_evidencia),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def planificar_revision_memoria(*, cliente_id: int, as_of, limit: int = 500) -> dict:
    from clientes.models import Cliente
    from joi.models import ManualDavid

    cutoff = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    if isinstance(cutoff, datetime):
        cutoff = cutoff.date()
    cliente = Cliente.objects.only('user_id').get(pk=cliente_id)
    candidates = list(ManualDavid.objects.filter(
        user_id=cliente.user_id,
        activa=True,
        origen='patron_detectado',
        tipo__in=('patron', 'hipotesis', 'contradiccion'),
    ).exclude(estado='descartada').order_by('pk'))

    queued = []
    for manual in candidates:
        revision = clasificar_revision_manual(
            origen=manual.origen, tipo=manual.tipo, estado=manual.estado,
            activa=manual.activa, creado_en=manual.creado_en,
            ultima_evidencia=manual.ultima_evidencia, as_of=cutoff,
        )
        if not revision:
            continue
        priority = (
            0 if revision['classification'] == 'revision_vencida' and manual.estado == 'cuestionada'
            else 1 if revision['classification'] == 'revision_vencida'
            else 2
        )
        queued.append((priority, revision['base_date'], manual.pk, manual, revision))

    queued.sort(key=lambda item: (item[0], item[1], item[2]))
    all_items = []
    for ordinal, (_, _, _, manual, revision) in enumerate(queued, start=1):
        all_items.append({
            'schema_version': SCHEMA_VERSION,
            'record_id': f'joi.manualdavid:{manual.pk}',
            'id': manual.pk,
            'classification': revision['classification'],
            'estado': manual.estado,
            'origen': manual.origen,
            'confianza': manual.confianza,
            'creado_en': _iso(manual.creado_en),
            'ultima_evidencia': _iso(manual.ultima_evidencia),
            'has_source_message': manual.fuente_mensaje_id is not None,
            'has_revision_notes': bool(manual.notas_revision),
            'has_opposing_hypothesis': bool(manual.hipotesis_contraria),
            'ordinal': ordinal,
            'as_of': cutoff.isoformat(),
            'fingerprint': _fingerprint(manual),
        })

    safe_limit = max(0, limit)
    items = all_items[:safe_limit]
    counts = Counter(item['classification'] for item in all_items)
    return {
        'items': items,
        'counts_by_classification': dict(sorted(counts.items())),
        'total': len(all_items),
        'evaluados': len(candidates),
        'emitidos': len(items),
        'truncados': max(0, len(all_items) - len(items)),
        'cliente_id': cliente_id,
        'as_of': cutoff.isoformat(),
        'limit': safe_limit,
        'schema_version': SCHEMA_VERSION,
        'solo_lectura': True,
    }
