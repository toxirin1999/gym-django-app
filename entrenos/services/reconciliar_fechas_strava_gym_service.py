"""Reconciliación explícita de fecha efectiva Gym desde evidencia Strava."""

from collections import defaultdict

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
        ).select_related("entreno_gym", "actividad_hub").order_by("fecha_actividad", "pk")
    )
    candidates = []
    ambiguous = []

    grouped_raws = defaultdict(list)
    for raw in raws:
        grouped_raws[raw.entreno_gym_id].append(raw)
    selected_raws = []
    for workout_raws in grouped_raws.values():
        if len(workout_raws) == 1:
            selected_raws.extend(workout_raws)
            continue
        workout = workout_raws[0].entreno_gym
        current_date = workout.fecha_ejecucion or workout.fecha
        exact = [raw for raw in workout_raws if raw.fecha_actividad == current_date]
        if len(exact) == 1:
            selected_raws.append(exact[0])
            discarded = [raw for raw in workout_raws if raw.pk != exact[0].pk]
        else:
            discarded = workout_raws
        for raw in discarded:
            ambiguous.append({
                "tipo_registro": "ambiguo",
                "code": "varios_strava_mismo_entreno",
                "strava_raw_id": raw.pk,
                "entreno_gym_id": workout.pk,
                "fecha_strava": raw.fecha_actividad.isoformat(),
            })

    for raw in selected_raws:
        workout = raw.entreno_gym
        activity = raw.actividad_hub
        derived_legacy_hub = activity is None
        if activity is None:
            try:
                activity = workout.hub_actividad
            except ActividadRealizada.DoesNotExist:
                ambiguous.append({
                    "tipo_registro": "ambiguo",
                    "code": "entreno_gym_sin_hub",
                    "strava_raw_id": raw.pk,
                    "entreno_gym_id": workout.pk,
                })
                continue
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
        if workout_date == raw.fecha_actividad and not derived_legacy_hub:
            continue
        difference = abs((raw.fecha_actividad - workout_date).days)
        if difference not in (0, 1):
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
            "actualizar_fecha": difference == 1,
            "vincular_hub_legacy": derived_legacy_hub,
        })

    applied = 0
    if apply and candidates:
        with transaction.atomic():
            for candidate in candidates:
                raw = StravaActivityRaw.objects.select_for_update().get(
                    pk=candidate["strava_raw_id"]
                )
                if candidate["actualizar_fecha"]:
                    updated_workout = EntrenoRealizado.objects.filter(
                        pk=candidate["entreno_gym_id"],
                        fecha_ejecucion=candidate["fecha_actual"],
                    ).update(fecha_ejecucion=raw.fecha_actividad)
                    updated_activity = ActividadRealizada.objects.filter(
                        pk=candidate["actividad_hub_id"],
                        fecha_realizado=candidate["fecha_actual"],
                    ).update(fecha_realizado=raw.fecha_actividad)
                    if updated_workout != updated_activity or updated_workout != 1:
                        raise RuntimeError("No se pudo reconciliar Gym y hub de forma atómica")
                if candidate["vincular_hub_legacy"]:
                    raw.actividad_hub_id = candidate["actividad_hub_id"]
                    raw.save(update_fields=["actividad_hub"])
                applied += 1

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
