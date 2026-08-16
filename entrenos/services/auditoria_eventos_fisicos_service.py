"""Auditoría pasiva de la identidad de eventos físicos.

No deduplica ni decide que dos filas sean el mismo esfuerzo. Expone grupos que
podrían estar sumando dos veces y pérdidas de trazabilidad con Strava para que
las reglas se calibren contra datos reales antes de mutar el histórico.
"""

from collections import defaultdict

from django.db.models import Q

from entrenos.models import ActividadRealizada
from hyrox.models import StravaActivityRaw


MAX_LIMIT = 1000


def _effective_date(activity):
    return activity.fecha_realizado or activity.fecha


def _event_payload(activity):
    return {
        "id": activity.pk,
        "titulo": activity.titulo,
        "fuente": activity.fuente,
        "fecha_planificada": activity.fecha.isoformat(),
        "fecha_realizada": (
            activity.fecha_realizado.isoformat() if activity.fecha_realizado else None
        ),
        "duracion_minutos": activity.duracion_minutos,
        "carga_ua": (
            float(activity.carga_ua) if activity.carga_ua is not None else None
        ),
        "rpe": float(activity.rpe_medio) if activity.rpe_medio is not None else None,
        "entreno_gym_id": activity.entreno_gym_id,
        "sesion_hyrox_id": activity.sesion_hyrox_id,
    }


def auditar_eventos_fisicos(*, cliente_id, desde, hasta, limit=MAX_LIMIT):
    activities = list(
        ActividadRealizada.objects.filter(cliente_id=cliente_id)
        .filter(
            Q(fecha_realizado__range=(desde, hasta))
            | Q(fecha_realizado__isnull=True, fecha__range=(desde, hasta))
        )
        .select_related("entreno_gym", "sesion_hyrox")
        .order_by("pk")[:limit]
    )

    grouped = defaultdict(list)
    for activity in activities:
        grouped[(_effective_date(activity), activity.tipo)].append(activity)

    findings = []
    for (effective_date, activity_type), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        events = [_event_payload(activity) for activity in group]
        sources = {event["fuente"] for event in events}
        durations = [
            event["duracion_minutos"]
            for event in events
            if event["duracion_minutos"] is not None
        ]
        mixed_sources_close_duration = (
            len(sources) > 1
            and len(durations) == len(events)
            and max(durations) - min(durations) <= 10
        )
        normalized_titles = {
            " ".join((event["titulo"] or "").casefold().split()) for event in events
        }
        same_manual_title = sources == {"manual"} and len(normalized_titles) == 1
        if not (mixed_sources_close_duration or same_manual_title):
            continue
        loads = [event["carga_ua"] for event in events if event["carga_ua"] is not None]
        findings.append({
            "tipo_registro": "hallazgo",
            "code": "duplicado_probable",
            "confidence": "alta",
            "cliente_id": cliente_id,
            "fecha_efectiva": effective_date.isoformat(),
            "tipo": activity_type,
            "event_ids": [event["id"] for event in events],
            "fuentes": sorted(sources),
            "carga_ua_sumada": round(sum(loads), 2) if loads else None,
            "eventos": events,
            "aplicar_automaticamente": False,
        })

    strava_without_link = list(
        StravaActivityRaw.objects.filter(
            cliente_id=cliente_id,
            fecha_actividad__range=(desde, hasta),
            estado__in=("merged", "created"),
            entreno_gym__isnull=True,
            hyrox_session__isnull=True,
            actividad_hub__isnull=True,
        ).order_by("fecha_actividad", "pk")[:limit]
    )
    for raw in strava_without_link:
        is_legacy_created = raw.estado == "created"
        findings.append({
            "tipo_registro": "hallazgo",
            "code": (
                "strava_legacy_sin_vinculo_hub"
                if is_legacy_created
                else "strava_procesado_sin_vinculo"
            ),
            "confidence": "media" if is_legacy_created else "alta",
            "cliente_id": cliente_id,
            "fecha_efectiva": raw.fecha_actividad.isoformat(),
            "strava_raw_id": raw.pk,
            "strava_id": raw.strava_id,
            "estado": raw.estado,
            "tipo_strava": raw.tipo_strava,
            "nombre": raw.nombre_strava,
            "duracion_minutos": raw.duracion_minutos(),
            "aplicar_automaticamente": False,
        })

    findings.sort(key=lambda row: (
        row["fecha_efectiva"], row["code"],
        row.get("event_ids", [row.get("strava_raw_id")]),
    ))
    summary = {
        "tipo_registro": "resumen",
        "cliente_id": cliente_id,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "eventos_evaluados": len(activities),
        "strava_procesados_sin_vinculo": len(strava_without_link),
        "grupos_candidatos": sum(
            finding["code"] == "duplicado_probable" for finding in findings
        ),
        "hallazgos": len(findings),
        "limit": limit,
        "truncado": len(activities) == limit or len(strava_without_link) == limit,
        "solo_lectura": True,
    }
    return {"findings": findings, "summary": summary}
