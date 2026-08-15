import hashlib
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import ActividadRealizada
from hyrox.models import HyroxObjective, HyroxReadinessLog, UserInjury

from core.services.physical_snapshot import build_physical_snapshot


AS_OF = date(2026, 8, 15)


class PhysicalSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("physical-snapshot")
        self.cliente = Cliente.objects.get(user=self.user)

    def test_missing_sources_remain_explicit_and_snapshot_is_read_only(self):
        before = {
            "bitacoras": BitacoraDiaria.objects.count(),
            "readiness": HyroxReadinessLog.objects.count(),
            "injuries": UserInjury.objects.count(),
            "activities": ActividadRealizada.objects.count(),
        }

        snapshot = build_physical_snapshot(self.cliente, AS_OF)

        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["cliente_id"], self.cliente.pk)
        self.assertEqual(snapshot["as_of_date"], "2026-08-15")
        self.assertIn("captured_at", snapshot)
        self.assertEqual(snapshot["signals"]["checkin"]["status"], "missing")
        self.assertIsNone(snapshot["signals"]["checkin"]["values"])
        self.assertEqual(snapshot["signals"]["hyrox_readiness"]["status"], "missing")
        self.assertIsNone(snapshot["signals"]["hyrox_readiness"]["values"])
        self.assertEqual(snapshot["signals"]["active_injuries"]["items"], [])
        self.assertEqual(snapshot["signals"]["recent_activity"]["items"], [])
        self.assertEqual(
            before,
            {
                "bitacoras": BitacoraDiaria.objects.count(),
                "readiness": HyroxReadinessLog.objects.count(),
                "injuries": UserInjury.objects.count(),
                "activities": ActividadRealizada.objects.count(),
            },
        )

    def test_checkin_uses_latest_past_record_and_preserves_zero_values(self):
        old = BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=7,
            energia_subjetiva=8,
        )
        BitacoraDiaria.objects.filter(pk=old.pk).update(fecha=AS_OF - timedelta(days=2))
        latest = BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=0,
            energia_subjetiva=0,
            calidad_sueno=0,
            fc_reposo=0,
            hrv_ms=0,
            dolor_articular=0,
        )
        BitacoraDiaria.objects.filter(pk=latest.pk).update(fecha=AS_OF - timedelta(days=1))
        future = BitacoraDiaria.objects.create(cliente=self.cliente, energia_subjetiva=10)
        BitacoraDiaria.objects.filter(pk=future.pk).update(fecha=AS_OF + timedelta(days=1))

        checkin = build_physical_snapshot(self.cliente, AS_OF)["signals"]["checkin"]

        self.assertEqual(checkin["status"], "available")
        self.assertEqual(checkin["observed_on"], "2026-08-14")
        self.assertEqual(checkin["age_days"], 1)
        self.assertEqual(
            checkin["values"],
            {
                "sleep_hours": 0.0,
                "energy": 0,
                "sleep_quality": 0,
                "resting_hr": 0,
                "hrv_ms": 0,
                "joint_pain": 0,
            },
        )
        self.assertEqual(checkin["provenance"]["source"], "clientes.BitacoraDiaria")
        self.assertEqual(checkin["provenance"]["record_id"], latest.pk)

    def test_checkin_older_than_three_days_is_stale_not_missing(self):
        record = BitacoraDiaria.objects.create(cliente=self.cliente, energia_subjetiva=4)
        BitacoraDiaria.objects.filter(pk=record.pk).update(fecha=AS_OF - timedelta(days=4))

        checkin = build_physical_snapshot(self.cliente, AS_OF)["signals"]["checkin"]

        self.assertEqual(checkin["status"], "stale")
        self.assertEqual(checkin["age_days"], 4)
        self.assertEqual(checkin["values"]["energy"], 4)

    def test_readiness_requires_exact_date_and_an_applicable_active_objective(self):
        inactive = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=AS_OF + timedelta(days=30),
            estado="cancelado",
        )
        active = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=AS_OF + timedelta(days=60),
            estado="activo",
        )
        HyroxReadinessLog.objects.create(objective=inactive, score=99)
        log = HyroxReadinessLog.objects.create(
            objective=active,
            score=0,
            fc_reposo=0,
            horas_sueno=0,
            calidad_sueno=0,
            hrv_ms=0,
        )
        HyroxReadinessLog.objects.filter(pk=log.pk).update(fecha=AS_OF)

        readiness = build_physical_snapshot(self.cliente, AS_OF)["signals"]["hyrox_readiness"]

        self.assertEqual(readiness["status"], "available")
        self.assertEqual(readiness["observed_on"], "2026-08-15")
        self.assertEqual(readiness["objective_id"], active.pk)
        self.assertEqual(
            readiness["values"],
            {"score": 0, "resting_hr": 0, "sleep_hours": 0.0, "sleep_quality": 0, "hrv_ms": 0},
        )

    def test_active_injuries_are_historical_as_of_and_have_provenance(self):
        current = UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada="rodilla",
            fase=UserInjury.Fase.SUB_AGUDA,
            fecha_inicio=AS_OF - timedelta(days=3),
            gravedad=0,
            tags_restringidos=["impacto_vertical"],
        )
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada="futura",
            fecha_inicio=AS_OF + timedelta(days=1),
        )
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada="recuperada",
            fase=UserInjury.Fase.RECUPERADO,
            fecha_inicio=AS_OF - timedelta(days=20),
        )

        injuries = build_physical_snapshot(self.cliente, AS_OF)["signals"]["active_injuries"]

        self.assertEqual(injuries["status"], "available")
        self.assertEqual(len(injuries["items"]), 1)
        self.assertEqual(
            injuries["items"][0],
            {
                "id": current.pk,
                "zone": "rodilla",
                "phase": UserInjury.Fase.SUB_AGUDA,
                "severity": 0,
                "restricted_tags": ["impacto_vertical"],
                "started_on": "2026-08-12",
                "resolved_on": None,
            },
        )
        self.assertEqual(injuries["provenance"]["source"], "hyrox.UserInjury")

    def test_recent_activity_uses_effective_date_and_excludes_future(self):
        moved = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="gym",
            titulo="moved",
            fecha=AS_OF - timedelta(days=6),
            fecha_realizado=AS_OF - timedelta(days=1),
            duracion_minutos=0,
            carga_ua=0,
            rpe_medio=0,
            fuente="manual",
        )
        planned_yesterday = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="futbol",
            titulo="planned",
            fecha=AS_OF - timedelta(days=1),
            fuente="strava",
        )
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="otro",
            titulo="future-effective",
            fecha=AS_OF - timedelta(days=1),
            fecha_realizado=AS_OF + timedelta(days=1),
        )
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="carrera",
            titulo="too-old",
            fecha=AS_OF - timedelta(days=2),
        )

        activity = build_physical_snapshot(self.cliente, AS_OF)["signals"]["recent_activity"]

        self.assertEqual(activity["window"], {"from": "2026-08-14", "to": "2026-08-15"})
        self.assertEqual([item["id"] for item in activity["items"]], [moved.pk, planned_yesterday.pk])
        self.assertEqual(activity["items"][0]["effective_date"], "2026-08-14")
        self.assertEqual(activity["items"][0]["planned_date"], "2026-08-09")
        self.assertEqual(activity["items"][0]["duration_minutes"], 0)
        self.assertEqual(activity["items"][0]["load_au"], 0.0)
        self.assertEqual(activity["items"][0]["rpe"], 0.0)

    def test_fingerprint_is_canonical_and_excludes_capture_time(self):
        first = build_physical_snapshot(self.cliente, AS_OF)
        second = build_physical_snapshot(self.cliente, AS_OF)

        self.assertNotEqual(first["captured_at"], "")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        payload = {key: value for key, value in first.items() if key not in {"captured_at", "fingerprint"}}
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self.assertEqual(first["fingerprint"], expected)

        ActividadRealizada.objects.create(cliente=self.cliente, tipo="futbol", fecha=AS_OF)
        changed = build_physical_snapshot(self.cliente, AS_OF)
        self.assertNotEqual(first["fingerprint"], changed["fingerprint"])
