import hashlib
import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Model
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ExperimentoVarianteGym
from logros.models import HistorialPuntos, PerfilGamificacion

from core.services.archive_audit_service import audit_archive_surfaces


class ArchiveAuditServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(
            user=User.objects.create_user("archive-audit-owner")
        )
        self.other = Cliente.objects.get(
            user=User.objects.create_user("archive-audit-other")
        )

    def audit(self):
        return audit_archive_surfaces(
            cliente_id=self.cliente.pk,
            hasta=date(2026, 8, 23),
            ventana_dias=90,
        )

    def test_deterministic_payload_and_fingerprint_excludes_generated_time(self):
        first = self.audit()
        second = self.audit()
        self.assertEqual(first, second)
        unsigned = {key: value for key, value in first.items() if key != "fingerprint"}
        expected = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(first["fingerprint"], expected)
        self.assertNotIn("generated_at", first)
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first["ventana"], {"desde": "2026-05-26", "hasta": "2026-08-23", "inclusiva": True})

    def test_client_scope_and_safe_allowlist(self):
        own_profile = PerfilGamificacion.objects.create(cliente=self.cliente)
        other_profile = PerfilGamificacion.objects.create(cliente=self.other)
        HistorialPuntos.objects.create(perfil=own_profile, puntos=3, descripcion="private own text")
        HistorialPuntos.objects.create(perfil=other_profile, puntos=99, descripcion="private other text")

        result = self.audit()
        gamification = next(row for row in result["evidence"] if row["domain"] == "gamificacion")
        self.assertEqual(gamification["row_count"], 1)
        serialized = json.dumps(result, sort_keys=True).lower()
        for forbidden in (
            "archive-audit-owner", "archive-audit-other", "private own text",
            "private other text", "access_token", "refresh_token", "raw_json",
            "lesion", "biometr", "athlete_id", "strava_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_read_only_even_when_orm_mutators_are_guarded(self):
        before = {
            "clientes": Cliente.objects.count(),
            "perfiles": PerfilGamificacion.objects.count(),
            "historial": HistorialPuntos.objects.count(),
            "experimentos": ExperimentoVarianteGym.objects.count(),
        }
        with (
            patch.object(Model, "save", side_effect=AssertionError("save called")),
            patch("django.db.models.query.QuerySet.update", side_effect=AssertionError("update called")),
            patch("django.db.models.query.QuerySet.delete", side_effect=AssertionError("delete called")),
            patch("django.db.models.query.QuerySet.get_or_create", side_effect=AssertionError("get_or_create called")),
            patch("urllib.request.urlopen", side_effect=AssertionError("external call")),
        ):
            self.audit()
        self.assertEqual(before, {
            "clientes": Cliente.objects.count(),
            "perfiles": PerfilGamificacion.objects.count(),
            "historial": HistorialPuntos.objects.count(),
            "experimentos": ExperimentoVarianteGym.objects.count(),
        })

    def test_zero_counts_are_only_reported_with_success(self):
        result = self.audit()
        count_keys = {
            "row_count", "recent_write_count", "reachable_route_count",
            "active_producer_count", "active_consumer_count",
        }
        for evidence in result["evidence"]:
            for key in count_keys.intersection(evidence):
                if evidence[key] == 0:
                    self.assertEqual(evidence["query_status"], "success")

    def test_missing_route_or_query_is_unknown_limitation_not_crash(self):
        with patch("core.services.archive_audit_service.reverse", side_effect=Exception("missing config")):
            result = self.audit()
        self.assertTrue(result["limitations"])
        self.assertTrue(any(row["classification"] == "unknown" for row in result["evidence"]))
        self.assertFalse(any(row["query_status"] == "success" and row.get("reachable_route_count") == 0 for row in result["evidence"] if row["classification"] == "unknown"))

    def test_classifications_are_conservative_and_never_archive_candidate(self):
        result = self.audit()
        allowed = {
            "core_active", "active_support", "historical_required",
            "security_exposed", "protected_integration", "unknown",
        }
        self.assertTrue(all(row["classification"] in allowed for row in result["evidence"]))
        self.assertNotIn("archive_candidate", json.dumps(result))
        strava = next(row for row in result["evidence"] if row["domain"] == "strava")
        self.assertEqual(strava["classification"], "protected_integration")

    def test_liftin_keeps_historical_classification_and_reports_archived_ux(self):
        liftin = next(row for row in self.audit()["evidence"] if row["domain"] == "liftin")
        self.assertEqual(liftin["classification"], "historical_required")
        self.assertEqual(liftin["ux_status"], "archived")
        self.assertEqual(liftin["ui_enabled"], False)
        self.assertEqual(liftin["route_status"], "archived")
        self.assertEqual(liftin["reachable_route_count"], 0)
        self.assertEqual(liftin["active_producer_count"], 0)
        self.assertEqual(liftin["active_consumer_count"], 4)
        self.assertEqual(len(liftin["registered_routes"]), 13)


class ArchiveAuditCommandTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(user=User.objects.create_user("archive-command"))

    def test_cli_requires_single_client_and_validates_date_and_positive_window(self):
        with self.assertRaises(CommandError):
            call_command("auditar_superficies_archivo", hasta="2026-08-23")
        with self.assertRaises(CommandError):
            call_command("auditar_superficies_archivo", cliente="all", hasta="2026-08-23")
        with self.assertRaises(CommandError):
            call_command("auditar_superficies_archivo", cliente=self.cliente.pk, hasta="bad")
        with self.assertRaises(CommandError):
            call_command("auditar_superficies_archivo", cliente=self.cliente.pk, hasta="2026-08-23", ventana_dias=0)
        with self.assertRaises(CommandError):
            call_command("auditar_superficies_archivo", cliente=999999, hasta="2026-08-23")

    def test_cli_emits_deterministic_json_with_default_window(self):
        stdout = StringIO()
        call_command(
            "auditar_superficies_archivo", cliente=self.cliente.pk,
            hasta="2026-08-23", stdout=stdout,
        )
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["cliente_id"], self.cliente.pk)
        self.assertEqual(document["ventana"]["desde"], "2026-05-26")
