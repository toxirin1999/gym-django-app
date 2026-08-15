"""Hechos físicos ya materializados para el contexto de JOI.

Este builder es deliberadamente de solo lectura: proyecta una versión vigente
de la autoridad Gym, no vuelve a calcular el organismo ni toma decisiones.
"""

from copy import deepcopy


_SIGNAL_SOURCES = {
    "checkin": "clientes.BitacoraDiaria",
    "hyrox_readiness": "hyrox.HyroxReadinessLog",
    "active_injuries": "hyrox.UserInjury",
    "recent_activity": "entrenos.ActividadRealizada",
}

_VALUE_FIELDS = {
    "checkin": {
        "sleep_hours", "energy", "sleep_quality", "resting_hr", "hrv_ms",
        "joint_pain",
    },
    "hyrox_readiness": {
        "score", "resting_hr", "sleep_hours", "sleep_quality", "hrv_ms",
    },
}

_INJURY_FIELDS = {
    "id", "zone", "phase", "severity", "restricted_tags", "started_on",
    "resolved_on",
}
_ACTIVITY_FIELDS = {
    "id", "type", "title", "effective_date", "planned_date",
    "duration_minutes", "load_au", "rpe", "source",
}


def _project_provenance(signal_name, signal):
    provenance = signal.get("provenance")
    if not isinstance(provenance, dict):
        return None
    expected_source = _SIGNAL_SOURCES[signal_name]
    if provenance.get("source") != expected_source:
        return None
    result = {"source": expected_source}
    for field in ("record_id", "record_ids", "effective_date_rule"):
        if field in provenance:
            result[field] = deepcopy(provenance[field])
    return result


def _project_signal(signal_name, signal):
    if not isinstance(signal, dict):
        return None
    provenance = _project_provenance(signal_name, signal)
    if provenance is None:
        return None

    projected = {}
    for field in ("status", "observed_on", "age_days"):
        if field in signal:
            projected[field] = signal[field]

    if signal_name in _VALUE_FIELDS:
        values = signal.get("values")
        if values is not None and not isinstance(values, dict):
            return None
        projected["values"] = (
            {
                field: deepcopy(values[field])
                for field in _VALUE_FIELDS[signal_name]
                if field in values
            }
            if values is not None else None
        )
        if "objective_id" in signal:
            projected["objective_id"] = signal["objective_id"]
    elif signal_name == "active_injuries":
        items = signal.get("items")
        if not isinstance(items, list):
            return None
        projected["items"] = [
            {field: deepcopy(item[field]) for field in _INJURY_FIELDS if field in item}
            for item in items if isinstance(item, dict)
        ]
    elif signal_name == "recent_activity":
        items = signal.get("items")
        if not isinstance(items, list):
            return None
        projected["items"] = [
            {field: deepcopy(item[field]) for field in _ACTIVITY_FIELDS if field in item}
            for item in items if isinstance(item, dict)
        ]
        window = signal.get("window")
        if isinstance(window, dict):
            projected["window"] = {
                field: window[field] for field in ("from", "to") if field in window
            }

    projected["provenance"] = provenance
    return projected


def build_physical_evidence_context(cliente, as_of_date):
    """Devuelve evidencia física validada de la versión Gym vigente del día."""
    from entrenos.models import GymDecisionVersion

    version = (
        GymDecisionVersion.objects.filter(
            cliente=cliente,
            fecha=as_of_date,
            vigente=True,
        )
        .order_by("-version", "-pk")
        .first()
    )
    if version is None or not isinstance(version.snapshot, dict):
        return {}

    physical = version.snapshot.get("physical_snapshot")
    if not isinstance(physical, dict):
        return {}
    if (
        physical.get("status") == "unavailable"
        or physical.get("schema_version") != 1
        or physical.get("cliente_id") != cliente.pk
        or physical.get("as_of_date") != as_of_date.isoformat()
        or not isinstance(physical.get("signals"), dict)
    ):
        return {}

    signals = {}
    for signal_name in _SIGNAL_SOURCES:
        if signal_name not in physical["signals"]:
            continue
        projected = _project_signal(signal_name, physical["signals"][signal_name])
        if projected is not None:
            signals[signal_name] = projected

    return {
        "physical_evidence": {
            "schema_version": 1,
            "as_of_date": physical["as_of_date"],
            "fingerprint": physical.get("fingerprint"),
            "signals": signals,
        }
    }


def _bloque_hechos_fisicos(evidence):
    """Formatea hechos actuales; nunca convierte ausencia/caducidad en afirmación."""
    if not isinstance(evidence, dict):
        return ""
    signals = evidence.get("signals")
    if not isinstance(signals, dict):
        return ""

    facts = []
    trace = []
    checkin = signals.get("checkin") or {}
    if checkin.get("status") == "available" and isinstance(checkin.get("values"), dict):
        values = checkin["values"]
        checkin_facts_before = len(facts)
        labels = (
            ("energy", "Energía registrada", "/10"),
            ("sleep_hours", "Sueño registrado", " h"),
            ("sleep_quality", "Calidad del sueño registrada", "/5"),
            ("resting_hr", "Frecuencia cardiaca en reposo registrada", " lpm"),
            ("hrv_ms", "HRV registrada", " ms"),
            ("joint_pain", "Dolor articular registrado", "/10"),
        )
        for key, label, suffix in labels:
            value = values.get(key)
            if value is not None:
                facts.append(f"{label}: {value}{suffix}.")
        if len(facts) > checkin_facts_before:
            source = (checkin.get("provenance") or {}).get("source")
            observed_on = checkin.get("observed_on")
            if source and observed_on:
                trace.append(f"Fuente: {source}; observada: {observed_on}.")

    readiness = signals.get("hyrox_readiness") or {}
    if readiness.get("status") == "available" and isinstance(readiness.get("values"), dict):
        score = readiness["values"].get("score")
        if score is not None:
            facts.append(f"Disponibilidad registrada: {score}/100.")
            source = (readiness.get("provenance") or {}).get("source")
            observed_on = readiness.get("observed_on")
            if source and observed_on:
                trace.append(f"Fuente: {source}; observada: {observed_on}.")

    injuries = signals.get("active_injuries") or {}
    if injuries.get("status") == "available":
        for item in injuries.get("items") or []:
            zone = item.get("zone")
            phase = item.get("phase")
            if zone:
                facts.append(
                    f"Lesión activa registrada: {zone}"
                    + (f" (fase {phase})" if phase else "") + "."
                )
                source = (injuries.get("provenance") or {}).get("source")
                started_on = item.get("started_on")
                if source and started_on:
                    trace.append(f"Fuente: {source}; inicio: {started_on}.")

    activity = signals.get("recent_activity") or {}
    if activity.get("status") == "available":
        for item in activity.get("items") or []:
            kind = item.get("type")
            observed = item.get("effective_date")
            if kind and observed:
                facts.append(f"Actividad registrada: {kind}, fecha efectiva {observed}.")
                source = (activity.get("provenance") or {}).get("source")
                if source:
                    trace.append(
                        f"Fuente: {source}; fecha efectiva: {observed}."
                    )

    if not facts:
        return ""
    fingerprint = evidence.get("fingerprint")
    fingerprint_ref = str(fingerprint)[:12] if fingerprint else "no disponible"
    as_of_date = evidence.get("as_of_date") or "no disponible"
    return (
        "EVIDENCIA FÍSICA VERIFICABLE — hechos, no interpretación ni prescripción:\n"
        f"Corte: {as_of_date}. Huella física: {fingerprint_ref}.\n"
        + "\n".join(f"- {fact}" for fact in facts)
        + ("\nTrazabilidad:\n" + "\n".join(f"- {item}" for item in trace) if trace else "")
        + "\nNo atribuyas causalidad y no conviertas estos hechos en una orden."
    )
