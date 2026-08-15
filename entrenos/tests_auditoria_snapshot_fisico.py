import json
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion


class AuditoriaSnapshotFisicoFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("audit-physical")
        self.cliente = Cliente.objects.get(user=self.user)
        self.fecha = date(2026, 8, 15)

    def physical(self, **changes):
        physical = {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.fecha.isoformat(),
            "signals": {
                "checkin": {
                    "status": "available",
                    "observed_on": self.fecha.isoformat(),
                    "age_days": 0,
                    "values": {
                        "energy": 0,
                        "sleep_hours": 0.0,
                        "resting_hr": 0,
                        "hrv_ms": 0,
                        "sleep_quality": 0,
                        "joint_pain": 0,
                    },
                },
                "hyrox_readiness": {
                    "status": "available",
                    "observed_on": self.fecha.isoformat(),
                    "values": {"score": 0},
                },
                "active_injuries": {
                    "status": "available",
                    "items": [{"phase": "AGUDA"}],
                },
                "recent_activity": {
                    "status": "available",
                    "items": [
                        {"type": "futbol", "effective_date": "2026-08-14", "rpe": 1},
                        {"type": "hyrox", "effective_date": "2026-08-13", "rpe": 7},
                    ],
                },
            },
        }
        physical.update(changes)
        return physical

    def expected_context(self):
        return {
            "lesion_activa": True,
            "lesion_fase": "AGUDA",
            "futbol_reciente": True,
            "hyrox_reciente": True,
            "energia_baja": True,
            "energia_valor": 0,
            "horas_sueno": 0.0,
            "frecuencia_cardiaca_reposo": 0,
            "hrv_ms": 0,
            "calidad_sueno": 0,
            "dolor": 0,
            "evidencia_fecha": self.fecha.isoformat(),
            "evidencia_presente": True,
            "readiness_bajo": True,
            "readiness_valor": 0,
        }

    def version(self, *, physical="default", context="default", **changes):
        if physical == "default":
            physical = self.physical()
        if context == "default":
            context = self.expected_context()
        snapshot = {}
        if physical is not None:
            snapshot["physical_snapshot"] = physical
        if context is not None:
            snapshot["contexto_fisico"] = context
        attrs = {
            "cliente": self.cliente,
            "fecha": self.fecha,
            "version": 1,
            "decision_id": "gym-audit",
            "schema_version": 1,
            "origen": GymDecisionVersion.ORIGEN_MOTOR,
            "vigente": True,
            "fingerprint": "decision",
            "base_fingerprint": "base",
            "postura": "proteger",
            "snapshot": snapshot,
        }
        attrs.update(changes)
        return GymDecisionVersion.objects.create(**attrs)


class AuditoriaSnapshotFisicoServiceTests(AuditoriaSnapshotFisicoFixture):
    def audit(self, **kwargs):
        from entrenos.services.auditoria_snapshot_fisico_service import (
            auditar_snapshots_fisicos,
        )
        return auditar_snapshots_fisicos(
            cliente_id=self.cliente.pk,
            desde=self.fecha - timedelta(days=1),
            hasta=self.fecha + timedelta(days=1),
            limit=500,
            **kwargs,
        )

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_match_exacto_es_solo_lectura_y_no_recalcula(self, resolver, build):
        self.version()
        before = list(GymDecisionVersion.objects.values_list("pk", "snapshot"))

        result = self.audit()

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"]["evaluated"], 1)
        self.assertEqual(result["summary"]["mismatches"], 0)
        self.assertEqual(result["summary"]["coverage"]["comparable"], 1)
        self.assertTrue(result["summary"]["solo_lectura"])
        self.assertEqual(before, list(GymDecisionVersion.objects.values_list("pk", "snapshot")))
        resolver.assert_not_called()
        build.assert_not_called()

    def test_clasifica_legacy_unavailable_y_contrato_invalido(self):
        self.version(physical=None)
        self.version(
            version=2, vigente=True,
            physical={"schema_version": 1, "status": "unavailable"},
        )
        GymDecisionVersion.objects.filter(version=1).update(vigente=False)
        unavailable = self.audit()
        self.assertEqual(unavailable["findings"][0]["code"], "unavailable_physical_snapshot")

        GymDecisionVersion.objects.all().delete()
        self.version(physical=None)
        legacy = self.audit()
        self.assertEqual(legacy["findings"][0]["code"], "missing_physical_snapshot")

        GymDecisionVersion.objects.all().delete()
        self.version(physical={"schema_version": 2, "signals": {}})
        invalid = self.audit()
        self.assertEqual(invalid["findings"][0]["code"], "invalid_physical_snapshot_contract")

        GymDecisionVersion.objects.all().delete()
        nested_invalid = self.physical()
        nested_invalid["signals"]["checkin"] = []
        self.version(physical=nested_invalid)
        invalid_nested = self.audit()
        self.assertEqual(
            invalid_nested["findings"][0]["code"],
            "invalid_physical_snapshot_contract",
        )

    def test_reporta_cada_mismatch_incluidos_ceros_con_json_estable(self):
        actual = self.expected_context()
        actual.update({
            "energia_valor": 5,
            "energia_baja": False,
            "readiness_valor": 50,
            "readiness_bajo": False,
            "lesion_activa": False,
            "futbol_reciente": False,
            "hyrox_reciente": False,
            "horas_sueno": None,
        })
        self.version(context=actual)

        result = self.audit()
        fields = [finding["field"] for finding in result["findings"]]

        self.assertEqual(fields, sorted(fields))
        for field in (
            "energia_valor", "energia_baja", "readiness_valor", "readiness_bajo",
            "lesion_activa", "futbol_reciente", "hyrox_reciente", "horas_sueno",
        ):
            self.assertIn(field, fields)
        energy = next(f for f in result["findings"] if f["field"] == "energia_valor")
        self.assertEqual(energy["expected"], 0)
        self.assertEqual(energy["actual"], 5)
        self.assertNotIn("nombre", json.dumps(result))
        self.assertEqual(
            result["summary"]["counts_by_code"]["physical_context_mismatch"],
            len(result["findings"]),
        )

    def test_fecha_exacta_y_actividad_efectiva_gobiernan_derivacion(self):
        physical = self.physical()
        physical["signals"]["checkin"]["observed_on"] = "2026-08-14"
        physical["signals"]["hyrox_readiness"]["observed_on"] = "2026-08-14"
        physical["signals"]["recent_activity"]["items"] = [
            {"type": "futbol", "effective_date": "2026-08-15", "rpe": 10},
            {"type": "hyrox", "effective_date": "2026-08-14", "rpe": 6.9},
        ]
        context = {
            "energia_valor": None, "energia_baja": False,
            "evidencia_presente": False, "readiness_valor": None,
            "readiness_bajo": False, "futbol_reciente": False,
            "hyrox_reciente": False,
        }
        self.version(physical=physical, context=context)
        self.assertEqual(self.audit()["findings"], [])

    def test_correccion_manual_audita_motor_base_y_no_snapshot_manual(self):
        motor = self.version(vigente=False)
        bad_context = {**self.expected_context(), "energia_valor": 9}
        self.version(
            version=2,
            origen=GymDecisionVersion.ORIGEN_CORRECCION,
            reemplaza=motor,
            context=bad_context,
            physical={"status": "unavailable"},
        )

        result = self.audit()

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"]["evaluated"], 1)
        self.assertEqual(result["summary"]["coverage"]["manual_base_reused"], 1)

    def test_filtra_tenant_rango_y_limit(self):
        self.version()
        otro_user = User.objects.create_user("audit-physical-other")
        otro = Cliente.objects.get(user=otro_user)
        self.version(
            cliente=otro, version=1, decision_id="otro",
            physical={**self.physical(), "cliente_id": otro.pk},
        )
        from entrenos.services.auditoria_snapshot_fisico_service import auditar_snapshots_fisicos
        only_other = auditar_snapshots_fisicos(
            cliente_id=otro.pk, desde=self.fecha, hasta=self.fecha, limit=1,
        )
        self.assertEqual(only_other["summary"]["evaluated"], 1)
        self.assertTrue(all(f["cliente_id"] == otro.pk for f in only_other["findings"]))


class AuditoriaSnapshotFisicoCommandTests(AuditoriaSnapshotFisicoFixture):
    @patch("django.utils.timezone.localdate", return_value=date(2031, 4, 20))
    def test_rango_default_usa_fecha_local_django_y_cubre_30_dias(self, _localdate):
        out = StringIO()
        call_command("auditar_snapshot_fisico_gym", todos=True, stdout=out)

        summary = json.loads(out.getvalue().splitlines()[-1])

        self.assertEqual(summary["desde"], "2031-03-22")
        self.assertEqual(summary["hasta"], "2031-04-20")

    def test_comando_jsonl_determinista_y_sin_apply(self):
        self.version()
        out = StringIO()
        call_command(
            "auditar_snapshot_fisico_gym",
            cliente=self.cliente.pk,
            desde=self.fecha.isoformat(),
            hasta=self.fecha.isoformat(),
            limit=10,
            stdout=out,
        )
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(rows[-1]["tipo_registro"], "resumen")
        self.assertTrue(rows[-1]["solo_lectura"])
        self.assertEqual(rows[-1]["evaluated"], 1)

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_comando_no_recalcula_y_valida_selector_fechas_limit(self, resolver, build):
        self.version()
        with self.assertRaises(CommandError):
            call_command("auditar_snapshot_fisico_gym", desde="bad", todos=True)
        with self.assertRaises(CommandError):
            call_command(
                "auditar_snapshot_fisico_gym", cliente=self.cliente.pk,
                desde="2026-08-16", hasta="2026-08-15",
            )
        with self.assertRaises(CommandError):
            call_command(
                "auditar_snapshot_fisico_gym", cliente=self.cliente.pk,
                desde="2026-08-15", hasta="2026-08-15", limit=501,
            )
        resolver.assert_not_called()
        build.assert_not_called()
