"""Política determinista de autoridad humana para el Manual de David."""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone


STABLE_TYPES = {'dato_usuario', 'preferencia', 'limite'}
REVISABLE_TYPES = {'patron', 'hipotesis', 'contradiccion'}


def _as_date(value):
    if value is None:
        return timezone.localdate()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def resolver_autoridad_manual(user, *, as_of=None, incluir_contenido=True):
    """Selecciona y ordena memoria usable en voz sin N+1 ni datos del ledger."""
    from joi.models import ManualDavid, RevisionManualDavidOperacion

    cutoff = _as_date(as_of)
    manuals = list(
        ManualDavid.objects.filter(user=user, activa=True)
        .exclude(estado='descartada')
        .values(
            'id', 'entrada', 'origen', 'tipo', 'confianza', 'estado',
            'hipotesis_contraria', 'creado_en',
            'ultima_evidencia',
        )
    )
    if not manuals:
        return []

    operations = (
        RevisionManualDavidOperacion.objects
        .filter(
            manual_id__in=[manual['id'] for manual in manuals],
            reversa_de__isnull=True,
            reversion__isnull=True,
        )
        .exclude(accion='deshacer')
        .order_by('manual_id', '-created_at', '-pk')
        .values('id', 'manual_id', 'accion', 'aplazada_hasta')
    )
    latest_by_manual = {}
    for operation in operations:
        latest_by_manual.setdefault(operation['manual_id'], operation)

    result = []
    for manual in manuals:
        operation = latest_by_manual.get(manual['id'])
        if (
            operation
            and operation['accion'] in {'cuestionar', 'posponer'}
            and operation['aplazada_hasta']
            and cutoff < operation['aplazada_hasta']
        ):
            continue

        if manual['origen'] == 'feedback_error':
            authority, priority = 'explicit_correction', 0
            provenance = {'source': 'explicit_correction', 'operation_id': None}
        elif operation and operation['accion'] == 'confirmar':
            authority, priority = 'user_confirmed', 10
            provenance = {'source': 'human_review', 'operation_id': operation['id']}
        elif manual['estado'] in {'cuestionada', 'debilitada'}:
            authority, priority = 'uncertain_hypothesis', 40
            provenance = {
                'source': 'human_review' if operation else 'manual_state',
                'operation_id': operation['id'] if operation else None,
            }
        elif manual['tipo'] in STABLE_TYPES:
            authority, priority = 'stable_manual', 20
            provenance = {'source': 'manual_state', 'operation_id': None}
        else:
            authority, priority = 'automatic_hypothesis', 30
            provenance = {'source': 'automatic_pattern', 'operation_id': None}

        item = {
            'id': manual['id'],
            'authority': authority,
            'confidence': float(manual['confianza']),
            'tipo': manual['tipo'],
            'estado': manual['estado'],
            'priority': priority,
            'provenance': provenance,
            'creado_en': manual['creado_en'],
            'ultima_evidencia': manual['ultima_evidencia'],
        }
        if incluir_contenido:
            item['entrada'] = manual['entrada']
            item['hipotesis_contraria'] = manual['hipotesis_contraria']
        result.append(item)

    return sorted(result, key=lambda item: (item['priority'], item['creado_en'], item['id']))


def construir_contexto_autoridad_manual(user, *, as_of=None):
    """Provenance mínima serializable; nunca incluye contenido o snapshots."""
    items = resolver_autoridad_manual(
        user, as_of=as_of, incluir_contenido=False,
    )
    return {
        'schema_version': 1,
        'items': [
            {
                'manual_id': item['id'],
                'authority': item['authority'],
                'provenance': item['provenance'],
            }
            for item in items
        ],
    }


def formatear_manual_para_prompt(items):
    if not items:
        return ''
    groups = {
        'explicit_correction': [], 'user_confirmed': [], 'stable_manual': [],
        'automatic_hypothesis': [], 'uncertain_hypothesis': [],
    }
    for item in items:
        groups[item['authority']].append(item)

    lines = ['MANUAL DE DAVID (autoridad calibrada; no es conocimiento consolidado):']
    headings = (
        ('explicit_correction', 'CORRECCIONES EXPLÍCITAS DEL USUARIO — máxima prioridad:'),
        ('user_confirmed', 'CONFIRMACIÓN EXPLÍCITA DEL USUARIO — prioritaria, pero no es verdad absoluta ni conocimiento consolidado:'),
        ('stable_manual', 'DATOS, PREFERENCIAS Y LÍMITES EN USO:'),
        ('automatic_hypothesis', 'HIPÓTESIS AUTOMÁTICAS — usa lenguaje provisional:'),
        ('uncertain_hypothesis', 'HIPÓTESIS EXPLÍCITAMENTE INCIERTAS — Nunca las redactes como hechos ni instrucciones:'),
    )
    for authority, heading in headings:
        if not groups[authority]:
            continue
        lines.append(f'  {heading}')
        for item in groups[authority]:
            prefix = '[?]' if authority == 'uncertain_hypothesis' else f"[{int(item['confidence'] * 100)}%]"
            line = f"  - {prefix} {item['entrada']}"
            if item.get('hipotesis_contraria') and authority in {
                'automatic_hypothesis', 'uncertain_hypothesis',
            }:
                line += f" (alternativa posible: {item['hipotesis_contraria']})"
            lines.append(line)
    return '\n'.join(lines) + '\n'
