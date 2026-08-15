"""Snapshot físico canónico V1.

El servicio conserva hechos observados y su procedencia. No interpreta umbrales,
no propone decisiones y no persiste nada.
"""

import hashlib
import json
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from clientes.models import BitacoraDiaria
from entrenos.models import ActividadRealizada
from hyrox.models import HyroxObjective, HyroxReadinessLog, UserInjury


SCHEMA_VERSION = 1
CHECKIN_FRESH_DAYS = 3


def _number(value):
    """Convierte Decimal a float sin convertir cero o ausencia en defaults."""
    return None if value is None else float(value)


def _missing_signal(source):
    return {
        "status": "missing",
        "observed_on": None,
        "age_days": None,
        "values": None,
        "provenance": {"source": source, "record_id": None},
    }


def _checkin_signal(cliente, as_of_date):
    record = (
        BitacoraDiaria.objects.filter(cliente=cliente, fecha__lte=as_of_date)
        .order_by("-fecha", "-pk")
        .first()
    )
    if record is None:
        return _missing_signal("clientes.BitacoraDiaria")

    age_days = (as_of_date - record.fecha).days
    return {
        "status": "available" if age_days <= CHECKIN_FRESH_DAYS else "stale",
        "observed_on": record.fecha.isoformat(),
        "age_days": age_days,
        "values": {
            "sleep_hours": _number(record.horas_sueno),
            "energy": record.energia_subjetiva,
            "sleep_quality": record.calidad_sueno,
            "resting_hr": record.fc_reposo,
            "hrv_ms": record.hrv_ms,
            "joint_pain": record.dolor_articular,
        },
        "provenance": {
            "source": "clientes.BitacoraDiaria",
            "record_id": record.pk,
        },
    }


def _readiness_signal(cliente, as_of_date):
    # Un objetivo cancelado/completado o un evento ya pasado no es aplicable a
    # la lectura física del día. El orden hace determinista el caso legado de
    # varios objetivos activos.
    objective = (
        HyroxObjective.objects.filter(
            cliente=cliente,
            estado="activo",
            fecha_evento__gte=as_of_date,
        )
        .order_by("fecha_evento", "pk")
        .first()
    )
    if objective is None:
        result = _missing_signal("hyrox.HyroxReadinessLog")
        result["objective_id"] = None
        return result

    log = (
        HyroxReadinessLog.objects.filter(objective=objective, fecha=as_of_date)
        .order_by("-pk")
        .first()
    )
    if log is None:
        result = _missing_signal("hyrox.HyroxReadinessLog")
        result["objective_id"] = objective.pk
        return result

    return {
        "status": "available",
        "observed_on": log.fecha.isoformat(),
        "age_days": 0,
        "objective_id": objective.pk,
        "values": {
            "score": log.score,
            "resting_hr": log.fc_reposo,
            "sleep_hours": _number(log.horas_sueno),
            "sleep_quality": log.calidad_sueno,
            "hrv_ms": log.hrv_ms,
        },
        "provenance": {
            "source": "hyrox.HyroxReadinessLog",
            "record_id": log.pk,
        },
    }


def _active_injuries_signal(cliente, as_of_date):
    injuries = (
        UserInjury.objects.filter(
            cliente=cliente,
            activa=True,
            fecha_inicio__lte=as_of_date,
        )
        .exclude(fase=UserInjury.Fase.RECUPERADO)
        .filter(Q(fecha_resolucion__isnull=True) | Q(fecha_resolucion__gt=as_of_date))
        # Equivale al `.first()` legacy de UserInjury (Meta: fecha más reciente).
        .order_by("-fecha_inicio", "-pk")
    )
    items = [
        {
            "id": injury.pk,
            "zone": injury.zona_afectada,
            "phase": injury.fase,
            "severity": injury.gravedad,
            "restricted_tags": list(injury.tags_restringidos or []),
            "started_on": injury.fecha_inicio.isoformat(),
            "resolved_on": (
                injury.fecha_resolucion.isoformat() if injury.fecha_resolucion else None
            ),
        }
        for injury in injuries
    ]
    return {
        "status": "available" if items else "missing",
        "items": items,
        "provenance": {
            "source": "hyrox.UserInjury",
            "record_ids": [item["id"] for item in items],
        },
    }


def _recent_activity_signal(cliente, as_of_date):
    # El modelo solo guarda fechas (no una hora final fiable). La regla legacy
    # "48 h antes" equivale a los dos días naturales previos: nunca incluye hoy.
    window_start = as_of_date - timedelta(days=2)
    window_end = as_of_date - timedelta(days=1)
    activities = ActividadRealizada.objects.filter(cliente=cliente).filter(
        Q(fecha_realizado__range=(window_start, window_end))
        | Q(fecha_realizado__isnull=True, fecha__range=(window_start, window_end))
    )
    items = []
    for activity in activities:
        effective_date = activity.fecha_realizado or activity.fecha
        items.append(
            {
                "id": activity.pk,
                "type": activity.tipo,
                "title": activity.titulo,
                "effective_date": effective_date.isoformat(),
                "planned_date": activity.fecha.isoformat(),
                "duration_minutes": activity.duracion_minutos,
                "load_au": _number(activity.carga_ua),
                "rpe": _number(activity.rpe_medio),
                "source": activity.fuente,
            }
        )
    items.sort(key=lambda item: (item["effective_date"], item["id"]))
    return {
        "status": "available" if items else "missing",
        "window": {"from": window_start.isoformat(), "to": window_end.isoformat()},
        "items": items,
        "provenance": {
            "source": "entrenos.ActividadRealizada",
            "record_ids": [item["id"] for item in items],
            "effective_date_rule": "fecha_realizado_or_fecha",
        },
    }


def _fingerprint(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_physical_snapshot(cliente, as_of_date):
    """Construye un snapshot V1 determinista de hechos físicos conocidos."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente.pk,
        "as_of_date": as_of_date.isoformat(),
        "signals": {
            "checkin": _checkin_signal(cliente, as_of_date),
            "hyrox_readiness": _readiness_signal(cliente, as_of_date),
            "active_injuries": _active_injuries_signal(cliente, as_of_date),
            "recent_activity": _recent_activity_signal(cliente, as_of_date),
        },
    }
    return {
        **payload,
        "captured_at": timezone.now().isoformat(),
        "fingerprint": _fingerprint(payload),
    }
