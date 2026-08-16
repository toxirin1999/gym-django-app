"""Auditoría pasiva de métricas para identidades Strava → Gym → hub."""

from collections import Counter

from hyrox.models import StravaActivityRaw

AUDIT_SCHEMA_VERSION = 1
MAX_LIMIT = 500


def _finding(raw, code, *, field=None, expected=None, actual=None, classification=None):
    row = {"tipo_registro": "hallazgo", "schema_version": AUDIT_SCHEMA_VERSION,
           "cliente_id": raw.cliente_id, "fecha": raw.fecha_actividad.isoformat(),
           "strava_raw_id": raw.pk, "strava_id": raw.strava_id,
           "entreno_gym_id": raw.entreno_gym_id, "actividad_hub_id": raw.actividad_hub_id,
           "code": code, "field": field, "expected": expected, "actual": actual}
    if classification is not None:
        row["classification"] = classification
    return row


def auditar_metricas_strava_gym(*, cliente_id, desde, hasta, limit=MAX_LIMIT):
    if desde > hasta:
        raise ValueError("desde no puede ser posterior a hasta")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")
    base_query = StravaActivityRaw.objects.filter(
        cliente_id=cliente_id, estado="merged", fecha_actividad__range=(desde, hasta),
    )
    total_candidates = base_query.count()
    # La unicidad no depende del límite de presentación de la auditoría.
    raw_counts = Counter(base_query.exclude(entreno_gym_id=None).values_list(
        "entreno_gym_id", flat=True,
    ))
    raws = list(base_query.select_related("entreno_gym", "actividad_hub").order_by(
        "fecha_actividad", "pk",
    )[:limit])
    findings, comparable, duration_truncations_tolerated = [], 0, 0
    identity_codes = {"multiple_strava_raws_for_entreno", "cross_client_identity",
                      "missing_entreno_gym_link", "missing_actividad_hub_link"}
    for raw in raws:
        rows = []
        gym, hub = raw.entreno_gym, raw.actividad_hub
        if gym is None:
            rows.append(_finding(raw, "missing_entreno_gym_link"))
        if hub is None:
            rows.append(_finding(raw, "missing_actividad_hub_link"))
        if gym is not None and raw_counts[gym.pk] > 1:
            rows.append(_finding(raw, "multiple_strava_raws_for_entreno"))
        if gym is not None and hub is not None and not (
            raw.cliente_id == gym.cliente_id == hub.cliente_id and hub.entreno_gym_id == gym.pk
        ):
            rows.append(_finding(raw, "cross_client_identity"))
        valid = gym is not None and hub is not None and not any(r["code"] in identity_codes for r in rows)
        if valid:
            complete = True
            if gym.duracion_minutos != hub.duracion_minutos:
                rows.append(_finding(raw, "gym_hub_duration_mismatch", field="duracion_minutos",
                                     expected=gym.duracion_minutos, actual=hub.duracion_minutos))
            if gym.duracion_minutos is None or hub.duracion_minutos is None:
                complete = False
            else:
                minutes = raw.duracion_segundos / 60
                delta = abs(minutes - gym.duracion_minutos)
                if delta >= 1:
                    rows.append(_finding(raw, "strava_gym_duration_mismatch", field="duracion_minutos",
                                         expected=gym.duracion_minutos, actual=round(minutes, 4),
                                         classification="provenance_unknown"))
                elif delta > 0:
                    duration_truncations_tolerated += 1
            if hub.carga_ua is not None and hub.duracion_minutos is None:
                rows.append(_finding(raw, "load_without_duration", field="carga_ua", actual=hub.carga_ua,
                                     classification="informative_fallback_possible"))
                complete = False
            if hub.carga_ua is not None and hub.rpe_medio is None:
                rows.append(_finding(raw, "load_without_rpe", field="carga_ua", actual=hub.carga_ua,
                                     classification="informative_fallback_possible"))
                complete = False
            if hub.duracion_minutos is not None and hub.rpe_medio is not None:
                expected = round(hub.rpe_medio * hub.duracion_minutos, 1)
                if hub.carga_ua is None or round(abs(hub.carga_ua - expected), 10) > 0.1:
                    rows.append(_finding(raw, "hub_load_mismatch", field="carga_ua",
                                         expected=expected, actual=hub.carga_ua))
            else:
                complete = False
            comparable += int(complete)
        findings.extend(rows)
    findings.sort(key=lambda r: (r["fecha"], r["strava_raw_id"], r["code"], r["field"] or ""))
    counts = dict(sorted(Counter(r["code"] for r in findings).items()))
    summary = {"tipo_registro": "resumen", "schema_version": AUDIT_SCHEMA_VERSION,
               "cliente_id": cliente_id, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
               "limit": limit, "total_candidates": total_candidates,
               "evaluated": len(raws), "counts_by_code": counts,
               "comparable": comparable,
               "classified_without_comparison": len(raws) - comparable,
               "truncated": total_candidates - len(raws),
               "duration_truncations_tolerated": duration_truncations_tolerated,
               "coverage": {"comparable": comparable,
                            "classified_without_comparison": len(raws) - comparable,
                            "duration_truncations_tolerated": duration_truncations_tolerated},
               "solo_lectura": True}
    return {"findings": findings, "summary": summary}
