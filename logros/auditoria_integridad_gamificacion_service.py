"""Auditoría pasiva del ledger histórico de gamificación."""

import hashlib
import json
from collections import Counter

from django.db.models import Count, Q, Sum

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from logros.models import HistorialPuntos, PerfilGamificacion, PruebaUsuario


SCHEMA_VERSION = 1
MAX_LIMIT = 10_000


def _fingerprint(payload):
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _finding(code, cliente_id, **evidence):
    row = {
        "tipo_registro": "hallazgo",
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "code": code,
        **evidence,
    }
    return {**row, "fingerprint": _fingerprint(row)}


def auditar_integridad_gamificacion(*, cliente_id, limit=1000):
    """Clasifica divergencias sin escribir ni recomendar una reparación."""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")
    if not Cliente.objects.filter(pk=cliente_id).exists():
        raise ValueError("cliente inexistente")

    profiles = list(PerfilGamificacion.objects.filter(cliente_id=cliente_id).order_by("pk"))
    profile_ids = [profile.pk for profile in profiles]
    trainings = list(
        EntrenoRealizado.objects.filter(cliente_id=cliente_id)
        .only("pk", "procesado_gamificacion")
        .order_by("pk")
    )
    training_ids = [training.pk for training in trainings]
    own_history = HistorialPuntos.objects.filter(perfil_id__in=profile_ids)
    relevant_history = list(
        HistorialPuntos.objects.filter(
            Q(perfil_id__in=profile_ids) | Q(entreno_id__in=training_ids)
        ).select_related("perfil", "entreno").only(
            "pk", "perfil_id", "perfil__cliente_id", "entreno_id",
            "entreno__cliente_id", "prueba_legendaria_id", "quest_id", "puntos",
        )
        .order_by("pk")
    )
    own_rows = [row for row in relevant_history if row.perfil_id in profile_ids]
    own_by_training = Counter(row.entreno_id for row in own_rows if row.entreno_id is not None)
    all_by_training = Counter(row.entreno_id for row in relevant_history if row.entreno_id is not None)
    base_by_training = Counter(
        row.entreno_id for row in relevant_history
        if row.entreno_id is not None
        and row.prueba_legendaria_id is None
        and row.quest_id is None
    )
    findings = []

    if len(profiles) == 0:
        findings.append(_finding("missing_gamification_profile", cliente_id, actual=0, expected=1))
    elif len(profiles) > 1:  # Defensa para esquemas legacy sin OneToOne efectivo.
        findings.append(_finding(
            "multiple_gamification_profiles", cliente_id, actual=len(profiles), expected=1,
        ))

    real_count = len(trainings)
    history_aggregate = own_history.aggregate(count=Count("pk"), points=Sum("puntos"))
    history_count = history_aggregate["count"] or 0
    history_sum = history_aggregate["points"] or 0
    if len(profiles) == 1:
        profile = profiles[0]
        if profile.entrenos_totales != real_count:
            findings.append(_finding(
                "training_total_mismatch", cliente_id,
                expected=real_count, actual=profile.entrenos_totales,
                classification=(
                    "profile_greater_than_training_records"
                    if profile.entrenos_totales > real_count
                    else "training_records_greater_than_profile"
                ),
            ))
        if profile.puntos_totales != history_sum:
            findings.append(_finding(
                "point_total_mismatch", cliente_id,
                expected=history_sum, actual=profile.puntos_totales,
                classification=(
                    "profile_greater_than_ledger"
                    if profile.puntos_totales > history_sum
                    else "ledger_greater_than_profile"
                ),
            ))

    for training in trainings:
        if base_by_training[training.pk] > 1:
            findings.append(_finding(
                "multiple_base_events_for_training", cliente_id,
                entreno_id=training.pk, actual=base_by_training[training.pk], expected=1,
            ))
        if training.procesado_gamificacion and own_by_training[training.pk] == 0:
            findings.append(_finding(
                "processed_training_without_own_history", cliente_id,
                entreno_id=training.pk,
            ))
        if not training.procesado_gamificacion and all_by_training[training.pk] > 0:
            findings.append(_finding(
                "unprocessed_training_with_history", cliente_id,
                entreno_id=training.pk,
                classification="legacy_or_inconsistent",
            ))

    for history in relevant_history:
        if history.entreno_id is not None:
            training_client_id = history.entreno.cliente_id
            profile_client_id = history.perfil.cliente_id
            if training_client_id != profile_client_id:
                findings.append(_finding(
                    "cross_client_training_history", cliente_id,
                    historial_id=history.pk, entreno_id=history.entreno_id,
                    perfil_cliente_id=profile_client_id,
                    entreno_cliente_id=training_client_id,
                ))
        elif history.perfil_id in profile_ids:
            findings.append(_finding(
                "history_without_training", cliente_id,
                historial_id=history.pk,
                classification="non_training_event_unknown_origin",
            ))

    duplicate_tests = (
        PruebaUsuario.objects.filter(perfil_id__in=profile_ids)
        .values("perfil_id", "prueba_id")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .order_by("perfil_id", "prueba_id")
    )
    for group in duplicate_tests:
        findings.append(_finding(
            "duplicate_user_test", cliente_id,
            perfil_id=group["perfil_id"], prueba_id=group["prueba_id"],
            actual=group["total"], expected=1,
        ))

    findings.sort(key=lambda row: (
        row["code"], row.get("entreno_id") or 0,
        row.get("historial_id") or 0, row["fingerprint"],
    ))
    counts = dict(sorted(Counter(row["code"] for row in findings).items()))
    visible = findings[:limit]
    summary = {
        "tipo_registro": "resumen",
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "limit": limit,
        "counts_by_code": counts,
        "totals": {
            "perfiles": len(profiles),
            "entrenos_reales": real_count,
            "historial_count": history_count,
            "historial_sum": history_sum,
            "historial_sin_entreno": sum(
                1 for row in own_rows if row.entreno_id is None
            ),
            "hallazgos": len(findings),
            "emitidos": len(visible),
        },
        "truncados": len(findings) - len(visible),
        "solo_lectura": True,
    }
    signed_summary = {
        **summary,
        "fingerprint": _fingerprint({"findings": visible, "summary": summary}),
    }
    return {"findings": visible, "summary": signed_summary}
