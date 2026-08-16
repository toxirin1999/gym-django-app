"""Partición pasiva de la identidad Strava → Gym → hub canónico."""

from collections import Counter

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count

from hyrox.models import StravaActivityRaw

SCHEMA_VERSION = 1
MAX_LIMIT = 500


def _reverse_hub(gym):
    if gym is None:
        return None
    try:
        return gym.hub_actividad
    except ObjectDoesNotExist:
        return None


def _conflicts(raw, gym, hub, reverse_hub):
    conflicts = []
    if gym is not None and gym.cliente_id != raw.cliente_id:
        conflicts.append("raw_gym_cross_client")
    if hub is not None and hub.cliente_id != raw.cliente_id:
        conflicts.append("raw_hub_cross_client")
    if hub is not None and gym is None:
        conflicts.append("hub_without_raw_gym_fk")
    if hub is not None and gym is not None and hub.entreno_gym_id != gym.pk:
        conflicts.append("hub_gym_fk_mismatch")
    if hub is not None and hub.tipo != "gym":
        conflicts.append("hub_not_gym")
    if hub is not None and reverse_hub is not None and hub.pk != reverse_hub.pk:
        conflicts.append("raw_hub_reverse_hub_mismatch")
    if hub is None and reverse_hub is not None:
        if reverse_hub.cliente_id != raw.cliente_id:
            conflicts.append("reverse_hub_cross_client")
        if reverse_hub.tipo != "gym":
            conflicts.append("reverse_hub_not_gym")
    if raw.hyrox_session_id is not None:
        hyrox_cliente_id = raw.hyrox_session.objective.cliente_id
        if hyrox_cliente_id != raw.cliente_id:
            conflicts.append("raw_hyrox_cross_client")
    return conflicts


def _non_gym_classification(raw):
    kind = raw.tipo_hyrox()
    if raw.hyrox_session_id is not None:
        return f"hyrox_session:{raw.estado}:{kind}"
    return f"{raw.estado}:{kind}"


def _effective_date(obj, effective_field, planned_field):
    if obj is None:
        return None
    return getattr(obj, effective_field) or getattr(obj, planned_field)


def _iso(value):
    return value.isoformat() if value is not None else None


def clasificar_identidad_strava_gym(*, cliente_id, desde, hasta, limit=MAX_LIMIT):
    """Clasifica cada raw del cliente/rango una sola vez, sin realizar escrituras.

    Se incluyen raws ``merged`` por defecto. ``limit`` limita únicamente las
    filas emitidas; el total y la multiplicidad por Gym se calculan globalmente.
    """
    if desde > hasta:
        raise ValueError("desde no puede ser posterior a hasta")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")

    base = StravaActivityRaw.objects.filter(
        cliente_id=cliente_id, estado="merged", fecha_actividad__range=(desde, hasta),
    )
    total = base.count()
    raw_counts = dict(
        base.exclude(entreno_gym_id=None)
        .values("entreno_gym_id")
        .annotate(total=Count("pk"))
        .values_list("entreno_gym_id", "total")
    )
    raws = list(
        base.select_related(
            "entreno_gym", "actividad_hub", "hyrox_session__objective",
        ).order_by("fecha_actividad", "pk")[:limit]
    )

    rows = []
    for raw in raws:
        gym, hub = raw.entreno_gym, raw.actividad_hub
        reverse_hub = _reverse_hub(gym)
        reverse_hub_id = reverse_hub.pk if reverse_hub is not None else None
        gym_raw_count = raw_counts.get(raw.entreno_gym_id, 0)
        conflicts = _conflicts(raw, gym, hub, reverse_hub)
        gym_effective = _effective_date(gym, "fecha_ejecucion", "fecha")
        # El hub directo es la identidad declarada; si falta, se expone el
        # canónico inverso que se está evaluando como posible recuperación.
        date_hub = hub or reverse_hub
        hub_effective = _effective_date(date_hub, "fecha_realizado", "fecha")
        delta_days = abs((raw.fecha_actividad - gym_effective).days) if gym_effective else None
        date_conflict = (
            reverse_hub is not None
            and (gym_effective != hub_effective or delta_days is None or delta_days > 1)
        )

        if conflicts:
            category = "identity_conflict"
        elif gym is None:
            category = "non_gym_out_of_scope"
        elif hub is not None:
            category = "gym_complete"
        elif gym_raw_count > 1:
            category = "gym_missing_hub_multiple_raw"
        elif reverse_hub_id is None:
            category = "gym_missing_hub_no_canonical_hub"
        elif date_conflict:
            category = "gym_missing_hub_date_conflict"
        else:
            category = "gym_missing_hub_recoverable"

        row = {
            "tipo_registro": "clasificacion",
            "schema_version": SCHEMA_VERSION,
            "cliente_id": raw.cliente_id,
            "fecha": raw.fecha_actividad.isoformat(),
            "strava_raw_id": raw.pk,
            "strava_id": raw.strava_id,
            "tipo_strava": raw.tipo_strava,
            "estado": raw.estado,
            "entreno_gym_id": raw.entreno_gym_id,
            "actividad_hub_id": raw.actividad_hub_id,
            "reverse_actividad_hub_id": reverse_hub_id,
            "hyrox_session_id": raw.hyrox_session_id,
            "gym_raw_count": gym_raw_count,
            "fecha_gym_planificada": _iso(gym.fecha) if gym is not None else None,
            "fecha_gym_efectiva": _iso(gym_effective),
            "fecha_hub_planificada": _iso(date_hub.fecha) if date_hub is not None else None,
            "fecha_hub_efectiva": _iso(hub_effective),
            "delta_dias_strava_gym": delta_days,
            "category": category,
        }
        if conflicts:
            row["conflicts"] = conflicts
        if category == "non_gym_out_of_scope":
            row["non_gym_classification"] = _non_gym_classification(raw)
        rows.append(row)

    counts = dict(sorted(Counter(row["category"] for row in rows).items()))
    evaluated = len(rows)
    partition_count = sum(counts.values())
    summary = {
        "tipo_registro": "resumen",
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "limit": limit,
        "state": "merged",
        "total": total,
        "evaluated": evaluated,
        "truncated": total - evaluated,
        "counts_by_category": counts,
        "partition_count": partition_count,
        "partition_complete": partition_count == evaluated,
        "solo_lectura": True,
    }
    return {"classifications": rows, "summary": summary}
