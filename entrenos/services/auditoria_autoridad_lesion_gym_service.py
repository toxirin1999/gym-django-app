"""Auditoria pasiva de propagacion y alineacion de autoridad de lesion Gym."""

from __future__ import annotations

from collections import Counter
import re
import unicodedata

from django.db.models import Q

from entrenos.models import GymDecisionVersion, IntervencionMolestiaGym
from hyrox.models import UserInjury
from rehab.models import EpisodioRehab


SCHEMA_VERSION = 1
MAX_LIMIT = 500
BLOCKING_PHASES = {"AGUDA", "SUB_AGUDA"}
RETURN_PHASE = "RETORNO"
SIDE_ALIASES = {
    "izq": "izquierda", "izquierda": "izquierda",
    "der": "derecha", "derecha": "derecha",
    "ambas": "bilateral", "ambos": "bilateral", "bilateral": "bilateral",
}


def _normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _select_versions(*, cliente_id, desde, hasta, limit):
    query = GymDecisionVersion.objects.filter(
        vigente=True,
        fecha__range=(desde, hasta),
    )
    if cliente_id is not None:
        query = query.filter(cliente_id=cliente_id)
    selected = {}
    for version in query.order_by("cliente_id", "fecha", "-version", "-pk"):
        selected.setdefault((version.cliente_id, version.fecha), version)
    rows = sorted(
        selected.values(), key=lambda row: (row.cliente_id, row.fecha, row.version, row.pk)
    )
    return rows[:limit]


def _base_authority(version, classification, **extra):
    return {
        "tipo_registro": "hallazgo",
        "schema_version": SCHEMA_VERSION,
        "plane": "authority_propagation",
        "cliente_id": version.cliente_id,
        "fecha": version.fecha.isoformat(),
        "version_id": version.pk,
        "version": version.version,
        "decision_id": version.decision_id,
        "classification": classification,
        **extra,
    }


def _physical_contract(version):
    snapshot = version.snapshot
    if not isinstance(snapshot, dict) or "physical_snapshot" not in snapshot:
        return None, "invalid_or_missing_physical_snapshot"
    physical = snapshot.get("physical_snapshot")
    if not isinstance(physical, dict) or physical.get("status") == "unavailable":
        return None, "invalid_or_missing_physical_snapshot"
    if not (
        physical.get("schema_version") == 1
        and physical.get("cliente_id") == version.cliente_id
        and physical.get("as_of_date") == version.fecha.isoformat()
        and isinstance(physical.get("signals"), dict)
    ):
        return None, "invalid_or_missing_physical_snapshot"
    return physical, None


def _injury_items(physical):
    signal = physical["signals"].get("active_injuries")
    if not isinstance(signal, dict):
        return None
    if signal.get("status") not in {"available", "missing"}:
        return None
    items = signal.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            return None
        if not isinstance(item.get("zone"), str) or not item.get("zone").strip():
            return None
        if item.get("phase") not in {"AGUDA", "SUB_AGUDA", "RETORNO", "RECUPERADO"}:
            return None
        tags = item.get("restricted_tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            return None
    if signal.get("status") == "missing" and items:
        return None
    return items


def _exercise_rows(snapshot):
    training = snapshot.get("entrenamiento")
    if training in (None, {}):
        return []
    if not isinstance(training, dict) or not isinstance(training.get("ejercicios", []), list):
        return None
    exercises = training.get("ejercicios", [])
    rows = []
    for exercise in exercises:
        if not isinstance(exercise, dict):
            return None
        name = exercise.get("nombre")
        tags = exercise.get("risk_tags")
        if not isinstance(name, str) or not name.strip():
            return None
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            return None
        rows.append((name, set(tags)))
    return rows


def _authority_evidence(injuries, exercises, *, conflicting_tags=None):
    return {
        "injury_ids": sorted(item.get("id") for item in injuries if item.get("id") is not None),
        "phases": sorted(set(item["phase"] for item in injuries)),
        "zones": sorted(set(item["zone"] for item in injuries)),
        "restricted_tags": sorted({
            tag for item in injuries for tag in item["restricted_tags"]
        }),
        "exercise_tags_complete": exercises is not None,
        "conflicting_tags": sorted(set(conflicting_tags or [])),
    }


def _warning_exposed(snapshot, conflicts):
    warning = snapshot.get("lesion_aviso")
    if not isinstance(warning, dict) or warning.get("fase") != RETURN_PHASE:
        return False
    warned = warning.get("ejercicios_en_riesgo")
    return isinstance(warned, list) and bool(set(conflicts) & set(warned))


def _classify_authority(version):
    physical, error = _physical_contract(version)
    if error:
        return _base_authority(version, error)
    injuries = _injury_items(physical)
    if injuries is None:
        return _base_authority(version, "injury_snapshot_contract_invalid")
    if not injuries:
        return _base_authority(version, "no_injury_in_snapshot")
    exercises = _exercise_rows(version.snapshot)
    if exercises is None:
        return _base_authority(
            version, "unverifiable_exercise_tags",
            **_authority_evidence(injuries, exercises),
        )
    tagged = [item for item in injuries if item["restricted_tags"]]
    if not tagged:
        return _base_authority(
            version, "injury_present_empty_tags",
            **_authority_evidence(injuries, exercises),
        )

    blocking_conflicts = []
    return_conflicts = []
    conflicting_tags = set()
    for injury in tagged:
        restricted = set(injury["restricted_tags"])
        conflicts = []
        for name, tags in exercises:
            overlap = tags & restricted
            if overlap:
                conflicts.append(name)
                conflicting_tags.update(overlap)
        if injury["phase"] in BLOCKING_PHASES:
            blocking_conflicts.extend(conflicts)
        elif injury["phase"] == RETURN_PHASE:
            return_conflicts.extend(conflicts)
    blocking_conflicts = sorted(set(blocking_conflicts))
    return_conflicts = sorted(set(return_conflicts))

    if blocking_conflicts and version.postura != "proteger":
        return _base_authority(
            version, "blocking_restriction_not_enforced",
            conflicting_exercises=blocking_conflicts,
            actual={"postura": version.postura},
            expected={"postura": "proteger"},
            **_authority_evidence(injuries, exercises, conflicting_tags=conflicting_tags),
        )
    if return_conflicts and not _warning_exposed(version.snapshot, return_conflicts):
        return _base_authority(
            version, "return_warning_not_exposed",
            conflicting_exercises=return_conflicts,
            actual={"warning_exposed": False},
            expected={"warning_exposed": True},
            **_authority_evidence(injuries, exercises, conflicting_tags=conflicting_tags),
        )
    if blocking_conflicts and version.postura == "proteger":
        return _base_authority(
            version, "restriction_enforced",
            conflicting_exercises=blocking_conflicts,
            **_authority_evidence(injuries, exercises, conflicting_tags=conflicting_tags),
        )
    if return_conflicts:
        return _base_authority(
            version, "return_warning_exposed",
            conflicting_exercises=return_conflicts,
            **_authority_evidence(injuries, exercises, conflicting_tags=conflicting_tags),
        )
    return _base_authority(
        version, "injury_present_no_session_conflict", conflicting_exercises=[],
        **_authority_evidence(injuries, exercises),
    )


def _side_from_text(value):
    found = {SIDE_ALIASES[token] for token in _normalize(value).split() if token in SIDE_ALIASES}
    return next(iter(found)) if len(found) == 1 else None


def _sides_compatible(episode_side, injury_side):
    if injury_side is None:
        return True
    return (
        episode_side == injury_side
        or episode_side == "bilateral"
        or injury_side == "bilateral"
    )


def _zone_matches(zone, injury_zone):
    left = _normalize(zone)
    right = _normalize(injury_zone)
    if not left or not right:
        return False
    return left == right or f" {left} " in f" {right} " or f" {right} " in f" {left} "


def _latest_rehab_session(episode, as_of):
    session = episode.sesiones.filter(fecha__lte=as_of).order_by("-fecha", "-pk").first()
    if session is None:
        return {
            "fecha": None, "estado": None, "dolor_durante": None,
            "dolor_post_24h": None, "response_24h_status": "not_available",
        }
    return {
        "fecha": session.fecha.isoformat(),
        "estado": session.estado,
        "dolor_durante": session.dolor_durante,
        "dolor_post_24h": session.dolor_post_24h,
        "response_24h_status": (
            "present" if session.dolor_post_24h is not None else "missing"
        ),
    }


def _source_alignment(cliente_id, as_of):
    episodes = list(
        EpisodioRehab.objects.filter(
            cliente_id=cliente_id, estado="ACTIVO", fecha_inicio__lte=as_of,
        )
        .select_related("protocolo")
        .order_by("pk")
    )
    injuries = list(
        UserInjury.objects.filter(
            cliente_id=cliente_id,
            activa=True,
            fecha_inicio__lte=as_of,
        ).exclude(fase=UserInjury.Fase.RECUPERADO).filter(
            Q(fecha_resolucion__isnull=True) | Q(fecha_resolucion__gt=as_of)
        ).order_by("pk")
    )
    base = {
        "tipo_registro": "hallazgo",
        "schema_version": SCHEMA_VERSION,
        "plane": "source_alignment",
        "cliente_id": cliente_id,
        "as_of": as_of.isoformat(),
    }
    rows = []
    covered_injuries = set()
    for episode in episodes:
        candidates = []
        for injury in injuries:
            if not _zone_matches(episode.protocolo.zona, injury.zona_afectada):
                continue
            injury_side = _side_from_text(injury.zona_afectada)
            if not _sides_compatible(episode.lateralidad, injury_side):
                continue
            strength = "strong" if injury_side is not None else "probable"
            candidates.append((injury, strength))
        covered_injuries.update(injury.pk for injury, _ in candidates)
        if len(candidates) > 1:
            classification = "ambiguous_alignment"
        elif len(candidates) == 1 and candidates[0][1] == "strong":
            classification = "aligned"
        elif len(candidates) == 1:
            classification = "probable_alignment"
        elif injuries:
            classification = "unmatchable_zone"
        else:
            classification = "rehab_without_injury"
        rows.append({
            **base,
            "entity": "rehab_episode",
            "entity_id": episode.pk,
            "classification": classification,
            "zone": episode.protocolo.zona,
            "laterality": episode.lateralidad,
            "candidate_injury_ids": [injury.pk for injury, _ in candidates],
            "latest_rehab_session": _latest_rehab_session(episode, as_of),
        })
    for injury in injuries:
        if injury.pk not in covered_injuries:
            rows.append({
                **base,
                "entity": "user_injury",
                "entity_id": injury.pk,
                "classification": "injury_without_rehab",
                "zone": injury.zona_afectada,
                "laterality": _side_from_text(injury.zona_afectada),
            })
    return rows


def _inventory(*, cliente_id, as_of):
    query = IntervencionMolestiaGym.objects.filter(iniciada_en__date__lte=as_of)
    if cliente_id is not None:
        query = query.filter(cliente_id=cliente_id)
    counts = Counter(query.values_list("estado", flat=True))
    return {"total": sum(counts.values()), "by_status": dict(sorted(counts.items()))}


def auditar_autoridad_lesion_gym(
    *, cliente_id=None, desde, hasta, limit=MAX_LIMIT, as_of=None,
):
    """Clasifica evidencia persistida y fuentes actuales sin escribir ni reconstruir."""
    if desde > hasta:
        raise ValueError("desde no puede ser posterior a hasta")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")
    as_of = as_of or hasta
    versions = _select_versions(
        cliente_id=cliente_id, desde=desde, hasta=hasta, limit=limit,
    )
    findings = [_classify_authority(version) for version in versions]
    client_ids = {version.cliente_id for version in versions}
    if cliente_id is not None:
        client_ids.add(cliente_id)
    else:
        client_ids.update(EpisodioRehab.objects.filter(estado="ACTIVO").values_list("cliente_id", flat=True))
        client_ids.update(UserInjury.objects.filter(activa=True).values_list("cliente_id", flat=True))
    for pk in sorted(client_ids):
        findings.extend(_source_alignment(pk, as_of))
    findings.sort(key=lambda row: (
        row["cliente_id"], row["plane"], row.get("fecha", ""), row.get("version", 0),
        row["classification"],
    ))
    counts = Counter(
        (row["plane"], row["classification"]) for row in findings
    )
    summary = {
        "tipo_registro": "resumen",
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "as_of": as_of.isoformat(),
        "limit": limit,
        "evaluated_versions": len(versions),
        "counts_by_plane_and_classification": {
            f"{plane}:{classification}": count
            for (plane, classification), count in sorted(counts.items())
        },
        "intervention_inventory": _inventory(cliente_id=cliente_id, as_of=as_of),
        "solo_lectura": True,
    }
    return {"findings": findings, "summary": summary}
