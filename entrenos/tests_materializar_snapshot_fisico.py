import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.autoridad_diaria_gym_service import (
    SCHEMA_VERSION,
    _fingerprint,
    _persistir_version_motor,
    resolver_autoridad_diaria_gym,
)


class MaterializarSnapshotFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("materializar-physical")
        self.cliente = Cliente.objects.get(user=self.user)
        self.fecha = date(2031, 4, 20)

    def tearDown(self):
        cache.clear()

    def physical(self, **changes):
        value = {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.fecha.isoformat(),
            "signals": {},
            "fingerprint": "physical-v1",
        }
        value.update(changes)
        return value

    def authority(self, physical=None):
        return {
            "schema_version": 1,
            "decision_id": "gym-legacy-same",
            "fingerprint": "same-fingerprint",
            "fecha": self.fecha.isoformat(),
            "postura": "empujar",
            "estado": "entrenar",
            "causa_principal": "sesion_hoy",
            "contexto_fisico": {"energia_baja": False},
            "physical_snapshot": physical if physical is not None else self.physical(),
            "physical_snapshot_fingerprint": "physical-v1",
        }

    def version(self, *, origen=GymDecisionVersion.ORIGEN_MOTOR, snapshot=None, **changes):
        attrs = {
            "cliente": self.cliente,
            "fecha": self.fecha,
            "version": 1,
            "decision_id": "gym-legacy-same",
            "schema_version": 1,
            "origen": origen,
            "vigente": True,
            "fingerprint": "same-fingerprint",
            "base_fingerprint": "same-fingerprint",
            "postura": "empujar",
            "causa_principal": "sesion_hoy",
            "snapshot": snapshot if snapshot is not None else {"contexto_fisico": {}},
        }
        attrs.update(changes)
        return GymDecisionVersion.objects.create(**attrs)


class PersistenciaUpgradeSnapshotTests(MaterializarSnapshotFixture):
    def test_promueve_legacy_creando_sucesora_sin_reescribir_historia(self):
        legacy = self.version()
        before_snapshot = dict(legacy.snapshot)

        result = _persistir_version_motor(
            self.cliente, self.fecha, self.authority(), "same-fingerprint",
        )

        legacy.refresh_from_db()
        successor = GymDecisionVersion.objects.get(vigente=True)
        self.assertFalse(legacy.vigente)
        self.assertEqual(legacy.snapshot, before_snapshot)
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.reemplaza, legacy)
        self.assertEqual(successor.decision_id, legacy.decision_id)
        self.assertEqual(successor.fingerprint, legacy.fingerprint)
        self.assertEqual(successor.base_fingerprint, legacy.base_fingerprint)
        self.assertEqual(successor.postura, legacy.postura)
        self.assertEqual(successor.causa_principal, legacy.causa_principal)
        self.assertEqual(successor.snapshot["physical_snapshot"], self.physical())
        self.assertEqual(successor.snapshot["contract_upgrade"], "physical_snapshot_v1")
        self.assertEqual(result["version_persistida"], 2)

    def test_upgrade_ocurre_una_sola_vez(self):
        self.version()
        authority = self.authority()
        _persistir_version_motor(self.cliente, self.fecha, authority, "same-fingerprint")

        second = _persistir_version_motor(
            self.cliente, self.fecha, authority, "same-fingerprint",
        )

        self.assertEqual(GymDecisionVersion.objects.count(), 2)
        self.assertEqual(second["version_persistida"], 2)

    def test_snapshot_unavailable_no_promueve_legacy(self):
        legacy = self.version()
        unavailable = self.physical(status="unavailable", signals={})

        result = _persistir_version_motor(
            self.cliente,
            self.fecha,
            self.authority(physical=unavailable),
            "same-fingerprint",
        )

        legacy.refresh_from_db()
        self.assertTrue(legacy.vigente)
        self.assertEqual(GymDecisionVersion.objects.count(), 1)
        self.assertEqual(result["version_persistida"], 1)

    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    @patch("core.services.physical_snapshot.build_physical_snapshot")
    def test_force_refresh_omite_cache_legacy_pero_lectura_normal_la_conserva(
        self, build_snapshot, obtener_base,
    ):
        decision_base = {
            "tipo": "programada_hoy",
            "estado": "entrenar",
            "causa_principal": "sesion_hoy",
            "mensaje": "Sesión prevista.",
            "entrenamiento": None,
        }
        huella = _fingerprint(decision_base, self.fecha)
        legacy = self.version(
            decision_id=f"gym-{self.fecha.isoformat()}-{huella}",
            fingerprint=huella,
            base_fingerprint=huella,
        )
        physical = self.physical()
        build_snapshot.return_value = physical
        obtener_base.return_value = decision_base
        cache_key = (
            f"autoridad_diaria_gym_v{SCHEMA_VERSION}_{self.cliente.pk}_"
            f"{self.fecha.isoformat()}_{huella}"
        )
        cached_legacy = {"decision_id": legacy.decision_id, "version_persistida": 1}
        cache.set(cache_key, cached_legacy, 900)

        normal = resolver_autoridad_diaria_gym(self.cliente, self.fecha)
        refreshed = resolver_autoridad_diaria_gym(
            self.cliente, self.fecha, force_refresh=True,
        )

        self.assertEqual(normal, cached_legacy)
        self.assertEqual(refreshed["version_persistida"], 2)
        self.assertEqual(GymDecisionVersion.objects.count(), 2)
        self.assertEqual(
            GymDecisionVersion.objects.get(vigente=True).snapshot["physical_snapshot"],
            physical,
        )


class MaterializarSnapshotCommandTests(MaterializarSnapshotFixture):
    def run_command(self, **kwargs):
        out = StringIO()
        call_command(
            "materializar_snapshot_fisico_gym",
            cliente=self.cliente.pk,
            stdout=out,
            **kwargs,
        )
        return json.loads(out.getvalue().splitlines()[-1])

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_dry_run_candidato_no_recalcula_ni_escribe(self, resolver, build):
        self.version()
        before = list(GymDecisionVersion.objects.values_list("pk", "vigente", "snapshot"))

        row = self.run_command(fecha=self.fecha.isoformat())

        self.assertEqual(row["estado"], "candidate")
        self.assertTrue(row["solo_lectura"])
        self.assertEqual(before, list(GymDecisionVersion.objects.values_list("pk", "vigente", "snapshot")))
        resolver.assert_not_called()
        build.assert_not_called()

    def test_dry_run_reporta_manual_y_materializado_como_no_elegibles(self):
        self.version(origen=GymDecisionVersion.ORIGEN_CORRECCION)
        manual = self.run_command(fecha=self.fecha.isoformat())
        self.assertEqual(manual["estado"], "skip_manual_supervision")

        GymDecisionVersion.objects.all().delete()
        self.version(snapshot={"physical_snapshot": self.physical()})
        ready = self.run_command(fecha=self.fecha.isoformat())
        self.assertEqual(ready["estado"], "skip_already_materialized")

    @patch("django.utils.timezone.localdate", return_value=date(2031, 4, 20))
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_apply_actual_promueve_y_verifica_snapshot(self, resolver, _localdate):
        self.version()

        def resolve(cliente, fecha, *, force_refresh=False):
            self.assertTrue(force_refresh)
            return _persistir_version_motor(
                cliente, fecha, self.authority(), "same-fingerprint",
            )

        resolver.side_effect = resolve
        row = self.run_command(apply=True)

        self.assertEqual(row["estado"], "materialized")
        self.assertFalse(row["solo_lectura"])
        self.assertEqual(GymDecisionVersion.objects.count(), 2)
        resolver.assert_called_once_with(self.cliente, self.fecha, force_refresh=True)

    @patch("django.utils.timezone.localdate", return_value=date(2031, 4, 20))
    def test_apply_historico_rechazado_y_cliente_fecha_validados(self, _localdate):
        self.version()
        with self.assertRaises(CommandError):
            self.run_command(apply=True, fecha="2031-04-19")
        with self.assertRaises(CommandError):
            call_command("materializar_snapshot_fisico_gym", cliente=999999)
        with self.assertRaises(CommandError):
            self.run_command(fecha="no-fecha")

    @patch("django.utils.timezone.localdate", return_value=date(2031, 4, 20))
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_apply_unavailable_no_marca_exito_ni_promueve(self, resolver, _localdate):
        self.version()
        unavailable = self.physical(status="unavailable", signals={})
        resolver.side_effect = lambda cliente, fecha, **kwargs: _persistir_version_motor(
            cliente, fecha, self.authority(physical=unavailable), "same-fingerprint",
        )

        row = self.run_command(apply=True)

        self.assertEqual(row["estado"], "failed_snapshot_unavailable")
        self.assertEqual(GymDecisionVersion.objects.count(), 1)
        self.assertTrue(GymDecisionVersion.objects.get().vigente)
