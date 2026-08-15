"""Auditoría pasiva del contrato físico persistido en la autoridad Gym."""

from collections import Counter
from datetime import timedelta

from entrenos.models import GymDecisionVersion


AUDIT_SCHEMA_VERSION = 1
MAX_LIMIT = 500
_CONTEXT_FIELDS = (
    "calidad_sueno",
    "dolor",
    "energia_baja",
    "energia_valor",
    "evidencia_fecha",
    "evidencia_presente",
    "frecuencia_cardiaca_reposo",
    "futbol_reciente",
    "horas_sueno",
    "hrv_ms",
    "hyrox_reciente",
    "lesion_activa",
    "lesion_fase",
    "readiness_bajo",
    "readiness_valor",
)


def _base_motor(version):
    """Una corrección no aporta nueva evidencia: sigue hasta su motor base."""
    current = version
    visited = set()
    while current and current.pk not in visited:
        visited.add(current.pk)
        if current.origen == GymDecisionVersion.ORIGEN_MOTOR:
            return current
        current = current.reemplaza
    return (
        GymDecisionVersion.objects.filter(
            cliente_id=version.cliente_id,
            fecha=version.fecha,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            base_fingerprint=version.base_fingerprint,
        )
        .order_by("-version", "-pk")
        .first()
    )


def _select_versions(*, cliente_id, desde, hasta, limit):
    query = GymDecisionVersion.objects.filter(
        vigente=True,
        fecha__range=(desde, hasta),
    ).select_related("reemplaza")
    if cliente_id is not None:
        query = query.filter(cliente_id=cliente_id)

    # Una sola autoridad por cliente/día. En datos legacy con varios `vigente`,
    # gana la versión más alta igual que en la lectura ejecutiva.
    selected = {}
    for version in query.order_by("cliente_id", "fecha", "-version", "-pk"):
        selected.setdefault((version.cliente_id, version.fecha), version)

    result = []
    for version in selected.values():
        motor = _base_motor(version)
        if motor is not None:
            result.append((motor, motor.pk != version.pk))
    result.sort(key=lambda pair: (pair[0].cliente_id, pair[0].fecha, pair[0].version, pair[0].pk))
    return result[:limit]


def _derive_context(physical, fecha):
    signals = physical["signals"]
    expected = {
        "lesion_activa": False,
        "lesion_fase": None,
        "futbol_reciente": False,
        "hyrox_reciente": False,
        "energia_baja": False,
        "energia_valor": None,
        "horas_sueno": None,
        "frecuencia_cardiaca_reposo": None,
        "hrv_ms": None,
        "calidad_sueno": None,
        "dolor": None,
        "evidencia_fecha": None,
        "evidencia_presente": False,
        "readiness_bajo": False,
        "readiness_valor": None,
    }

    injuries = (signals.get("active_injuries") or {}).get("items") or []
    injury = next(
        (
            item for item in injuries
            if isinstance(item, dict) and item.get("phase") in {"AGUDA", "SUB_AGUDA"}
        ),
        None,
    )
    if injury:
        expected["lesion_activa"] = True
        expected["lesion_fase"] = injury.get("phase")

    start = (fecha - timedelta(days=2)).isoformat()
    end = (fecha - timedelta(days=1)).isoformat()
    items = (signals.get("recent_activity") or {}).get("items") or []
    in_window = [
        item for item in items
        if isinstance(item, dict)
        and isinstance(item.get("effective_date"), str)
        and start <= item["effective_date"] <= end
    ]
    expected["futbol_reciente"] = any(item.get("type") == "futbol" for item in in_window)
    expected["hyrox_reciente"] = any(
        item.get("type") == "hyrox"
        and item.get("rpe") is not None
        and _float_or_none(item.get("rpe")) is not None
        and _float_or_none(item.get("rpe")) >= 7
        for item in in_window
    )

    checkin = signals.get("checkin") or {}
    if checkin.get("observed_on") == fecha.isoformat():
        values = checkin.get("values") or {}
        expected.update({
            "evidencia_fecha": fecha.isoformat(),
            "evidencia_presente": True,
            "horas_sueno": values.get("sleep_hours"),
            "frecuencia_cardiaca_reposo": values.get("resting_hr"),
            "hrv_ms": values.get("hrv_ms"),
            "calidad_sueno": values.get("sleep_quality"),
            "dolor": values.get("joint_pain"),
        })
        energy = values.get("energy")
        if energy is not None:
            expected["energia_valor"] = int(energy)
            expected["energia_baja"] = expected["energia_valor"] <= 3

    readiness = signals.get("hyrox_readiness") or {}
    if readiness.get("observed_on") == fecha.isoformat():
        score = (readiness.get("values") or {}).get("score")
        if score is not None:
            expected["readiness_valor"] = score
            expected["readiness_bajo"] = score < 45
    return expected


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _finding(version, code, *, field=None, expected=None, actual=None):
    return {
        "tipo_registro": "hallazgo",
        "schema_version": AUDIT_SCHEMA_VERSION,
        "cliente_id": version.cliente_id,
        "fecha": version.fecha.isoformat(),
        "version_id": version.pk,
        "version": version.version,
        "code": code,
        "field": field,
        "expected": expected,
        "actual": actual,
    }


def _contract_error(physical, version):
    if not isinstance(physical, dict):
        return True
    if not (
        physical.get("schema_version") == 1
        and physical.get("cliente_id") == version.cliente_id
        and physical.get("as_of_date") == version.fecha.isoformat()
        and isinstance(physical.get("signals"), dict)
    ):
        return True
    signals = physical["signals"]
    for name in ("checkin", "hyrox_readiness", "active_injuries", "recent_activity"):
        if name in signals and not isinstance(signals[name], dict):
            return True
    for name in ("checkin", "hyrox_readiness"):
        signal = signals.get(name)
        if signal is not None and signal.get("values") is not None and not isinstance(signal["values"], dict):
            return True
    for name in ("active_injuries", "recent_activity"):
        signal = signals.get(name)
        if signal is not None and signal.get("items") is not None and not isinstance(signal["items"], list):
            return True
    return False


def auditar_snapshots_fisicos(*, cliente_id=None, desde, hasta, limit=MAX_LIMIT):
    """Compara evidencia y contexto materializados sin consultar fuentes vivas."""
    if desde > hasta:
        raise ValueError("desde no puede ser posterior a hasta")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")

    pairs = _select_versions(
        cliente_id=cliente_id,
        desde=desde,
        hasta=hasta,
        limit=limit,
    )
    findings = []
    comparable = 0
    manual_base_reused = 0
    for version, reused in pairs:
        manual_base_reused += int(reused)
        snapshot = version.snapshot if isinstance(version.snapshot, dict) else {}
        if "physical_snapshot" not in snapshot:
            findings.append(_finding(version, "missing_physical_snapshot"))
            continue
        physical = snapshot.get("physical_snapshot")
        if isinstance(physical, dict) and physical.get("status") == "unavailable":
            findings.append(_finding(version, "unavailable_physical_snapshot"))
            continue
        if _contract_error(physical, version):
            findings.append(_finding(version, "invalid_physical_snapshot_contract"))
            continue

        actual = snapshot.get("contexto_fisico")
        if not isinstance(actual, dict):
            actual = {}
        expected = _derive_context(physical, version.fecha)
        comparable += 1
        for field in _CONTEXT_FIELDS:
            # Solo auditamos campos que esta decisión llegó a materializar. Así
            # snapshots antiguos con contratos menores no generan falsos positivos.
            if field not in actual:
                continue
            if actual[field] != expected[field]:
                findings.append(_finding(
                    version,
                    "physical_context_mismatch",
                    field=field,
                    expected=expected[field],
                    actual=actual[field],
                ))

    findings.sort(key=lambda item: (
        item["cliente_id"], item["fecha"], item["version"], item["code"], item["field"] or "",
    ))
    counts = dict(sorted(Counter(item["code"] for item in findings).items()))
    mismatch_count = counts.get("physical_context_mismatch", 0)
    summary = {
        "tipo_registro": "resumen",
        "schema_version": AUDIT_SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "limit": limit,
        "evaluated": len(pairs),
        "mismatches": mismatch_count,
        "counts_by_code": counts,
        "coverage": {
            "comparable": comparable,
            "manual_base_reused": manual_base_reused,
            "classified_without_comparison": len(pairs) - comparable,
        },
        "solo_lectura": True,
    }
    return {"findings": findings, "summary": summary}
