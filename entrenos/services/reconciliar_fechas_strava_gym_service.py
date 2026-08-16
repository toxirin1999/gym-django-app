"""Reconciliación explícita de fecha efectiva Gym desde evidencia Strava."""

from django.db import transaction

from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.models import StravaActivityRaw


def reconciliar_fechas_strava_gym(*, cliente_id, desde, hasta, apply=False):
    raws = list(
        StravaActivityRaw.objects.filter(
            cliente_id=cliente_id,
            fecha_actividad__range=(desde, hasta),
            estado="merged",
            entreno_gym__isnull=False,
            actividad_hub__isnull=False,
        ).select_related("entreno_gym", "actividad_hub").order_by("fecha_actividad", "pk")
    )
    candidates = []
    ambiguous = []

    for raw in raws:
        workout = raw.entreno_gym
        activity = raw.actividad_hub
        workout_date = workout.fecha_ejecucion or workout.fecha
        activity_date = activity.fecha_realizado or activity.fecha
        if workout_date != activity_date:
            ambiguous.append({
                "tipo_registro": "ambiguo",
                "code": "fechas_gym_hub_divergentes",
                "strava_raw_id": raw.pk,
                "entreno_gym_id": workout.pk,
                "actividad_hub_id": activity.pk,
            })
            continue
        if workout_date == raw.fecha_actividad:
            continue
        difference = abs((raw.fecha_actividad - workout_date).days)
        if difference != 1:
            ambiguous.append({
                "tipo_registro": "ambiguo",
                "code": "salto_fecha_fuera_de_margen",
                "strava_raw_id": raw.pk,
                "entreno_gym_id": workout.pk,
                "actividad_hub_id": activity.pk,
                "dias_diferencia": difference,
            })
            continue
        candidates.append({
            "tipo_registro": "candidato",
            "strava_raw_id": raw.pk,
            "strava_id": raw.strava_id,
            "entreno_gym_id": workout.pk,
            "actividad_hub_id": activity.pk,
            "fecha_planificada": workout.fecha.isoformat(),
            "fecha_actual": workout_date.isoformat(),
            "fecha_strava": raw.fecha_actividad.isoformat(),
            "dias_diferencia": difference,
        })

    applied = 0
    if apply and candidates:
        with transaction.atomic():
            for candidate in candidates:
                raw = StravaActivityRaw.objects.select_for_update().get(
                    pk=candidate["strava_raw_id"]
                )
                updated_workout = EntrenoRealizado.objects.filter(
                    pk=candidate["entreno_gym_id"],
                    fecha_ejecucion=candidate["fecha_actual"],
                ).update(fecha_ejecucion=raw.fecha_actividad)
                updated_activity = ActividadRealizada.objects.filter(
                    pk=candidate["actividad_hub_id"],
                    fecha_realizado=candidate["fecha_actual"],
                ).update(fecha_realizado=raw.fecha_actividad)
                if updated_workout != updated_activity:
                    raise RuntimeError("No se pudo reconciliar Gym y hub de forma atómica")
                applied += updated_workout

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

