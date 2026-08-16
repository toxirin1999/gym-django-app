"""Recupera vínculos inequívocos StravaRaw → ActividadRealizada legacy."""

from django.db import transaction
from django.db.models import Q

from entrenos.models import ActividadRealizada
from hyrox.models import StravaActivityRaw


def _normalize(value):
    return " ".join((value or "").casefold().split())


def _effective_filter(target_date):
    return (
        Q(fecha_realizado=target_date)
        | Q(fecha_realizado__isnull=True, fecha=target_date)
    )


def vincular_strava_hub_legacy(*, cliente_id, desde, hasta, apply=False):
    raws = list(
        StravaActivityRaw.objects.filter(
            cliente_id=cliente_id,
            fecha_actividad__range=(desde, hasta),
            estado__in=("created", "merged"),
            actividad_hub__isnull=True,
        ).order_by("fecha_actividad", "pk")
    )
    candidates = []
    ambiguous = []
    claimed_activity_ids = set()

    for raw in raws:
        # `merged` debería conservar un vínculo Gym/Hyrox. Sin él no es seguro
        # reconstruir identidad mediante semejanza superficial.
        if raw.estado != "created":
            if raw.entreno_gym_id is None and raw.hyrox_session_id is None:
                ambiguous.append({
                    "tipo_registro": "ambiguo",
                    "code": "strava_merged_sin_autoridad",
                    "strava_raw_id": raw.pk,
                    "fecha": raw.fecha_actividad.isoformat(),
                })
            continue

        possible = []
        for activity in ActividadRealizada.objects.filter(
            Q(cliente_id=cliente_id, fuente="strava")
            & _effective_filter(raw.fecha_actividad)
        ).order_by("pk"):
            if activity.pk in claimed_activity_ids:
                continue
            if _normalize(activity.titulo) != _normalize(raw.nombre_strava):
                continue
            if activity.duracion_minutos is None:
                continue
            delta = abs(float(activity.duracion_minutos) - raw.duracion_minutos())
            if delta <= 2:
                possible.append((delta, activity))

        possible.sort(key=lambda item: (item[0], item[1].pk))
        if not possible:
            ambiguous.append({
                "tipo_registro": "ambiguo",
                "code": "sin_candidato_inequivoco",
                "strava_raw_id": raw.pk,
                "fecha": raw.fecha_actividad.isoformat(),
            })
            continue
        if len(possible) > 1 and possible[0][0] == possible[1][0]:
            ambiguous.append({
                "tipo_registro": "ambiguo",
                "code": "varios_candidatos_equivalentes",
                "strava_raw_id": raw.pk,
                "fecha": raw.fecha_actividad.isoformat(),
            })
            continue

        delta, activity = possible[0]
        claimed_activity_ids.add(activity.pk)
        candidates.append({
            "tipo_registro": "candidato",
            "strava_raw_id": raw.pk,
            "strava_id": raw.strava_id,
            "actividad_hub_id": activity.pk,
            "fecha": raw.fecha_actividad.isoformat(),
            "delta_minutos": round(delta, 2),
        })

    applied = 0
    if apply and candidates:
        with transaction.atomic():
            for candidate in candidates:
                updated = StravaActivityRaw.objects.filter(
                    pk=candidate["strava_raw_id"],
                    actividad_hub__isnull=True,
                ).update(actividad_hub_id=candidate["actividad_hub_id"])
                applied += updated

    summary = {
        "tipo_registro": "resumen",
        "cliente_id": cliente_id,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "modo": "apply" if apply else "dry-run",
        "evaluados": len(raws),
        "candidatos": len(candidates),
        "ambiguos": len(ambiguous),
        "aplicados": applied,
        "solo_lectura": not apply,
    }
    return {"candidates": candidates, "ambiguous": ambiguous, "summary": summary}

