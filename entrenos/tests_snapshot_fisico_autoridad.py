from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.autoridad_diaria_gym_service import (
    _fingerprint,
    corregir_autoridad_diaria_gym,
    resolver_autoridad_diaria_gym,
    revertir_correccion_autoridad_diaria_gym,
)


class SnapshotFisicoAutoridadTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user("autoridad-snapshot")
        self.cliente = Cliente.objects.get(user=user)
        self.fecha = date(2026, 8, 15)
        self.base = {
            "tipo": "programada_hoy",
            "estado": "entrenar",
            "causa_principal": "sesion_hoy",
            "mensaje": "Sesión prevista.",
            "entrenamiento": {
                "rutina_nombre": "Push",
                "ejercicios": [{"nombre": "Press banca", "series": 3, "repeticiones": 8}],
            },
        }
        self.physical = {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.fecha.isoformat(),
            "captured_at": "2026-08-15T08:00:00+00:00",
            "capabilities": ["active_rehab_v1"],
            "signals": {
                "checkin": {"status": "missing"},
                "active_rehab": {"schema_version": 1, "status": "missing", "items": []},
            },
            "fingerprint": "physical-a",
        }

    def tearDown(self):
        cache.clear()

    def _resolver(self):
        return resolver_autoridad_diaria_gym(self.cliente, self.fecha)

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_adjunta_y_persiste_snapshot_sin_cambiar_identidad_ni_postura(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        obtener_base.return_value = self.base
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])
        build_snapshot.return_value = self.physical

        autoridad = self._resolver()

        expected_base_fingerprint = _fingerprint(self.base, self.fecha)
        self.assertEqual(autoridad["decision_id"], f"gym-{self.fecha.isoformat()}-{expected_base_fingerprint}")
        self.assertEqual(autoridad["postura"], "empujar")
        self.assertEqual(autoridad["estado"], "entrenar")
        self.assertEqual(autoridad["physical_snapshot"], self.physical)
        self.assertEqual(autoridad["physical_snapshot_fingerprint"], "physical-a")
        version = GymDecisionVersion.objects.get(cliente=self.cliente, fecha=self.fecha)
        self.assertEqual(version.base_fingerprint, expected_base_fingerprint)
        self.assertEqual(version.snapshot["physical_snapshot"], self.physical)
        self.assertEqual(version.snapshot["physical_snapshot_fingerprint"], "physical-a")
        self.assertIn(
            "active_rehab_v1",
            version.snapshot["physical_snapshot"]["capabilities"],
        )
        build_snapshot.assert_called_once_with(self.cliente, self.fecha)
        obtener_base.assert_called_once_with(
            self.cliente,
            self.fecha,
            physical_snapshot=self.physical,
        )

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_relectura_sin_cache_recaptura_una_vez_y_no_versiona_si_decision_equivale(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        obtener_base.return_value = self.base
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])
        build_snapshot.return_value = self.physical
        primera = self._resolver()
        cache.clear()

        segunda = self._resolver()

        self.assertEqual(segunda["decision_id"], primera["decision_id"])
        self.assertEqual(segunda["physical_snapshot"], self.physical)
        self.assertEqual(GymDecisionVersion.objects.filter(cliente=self.cliente, fecha=self.fecha).count(), 1)
        self.assertEqual(build_snapshot.call_count, 2)
        build_snapshot.assert_called_with(self.cliente, self.fecha)

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_resolver_normal_no_promueve_capability_rehab_en_version_motor_existente(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        huella = _fingerprint(self.base, self.fecha)
        legacy_physical = {
            **self.physical,
            "capabilities": [],
        }
        GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=self.fecha,
            version=1,
            decision_id=f"gym-{self.fecha.isoformat()}-{huella}",
            schema_version=1,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True,
            fingerprint=huella,
            base_fingerprint=huella,
            postura="empujar",
            causa_principal="sesion_hoy",
            snapshot={
                **self.base,
                "physical_snapshot": legacy_physical,
                "physical_snapshot_fingerprint": "legacy-physical",
            },
        )
        obtener_base.return_value = self.base
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])
        build_snapshot.return_value = self.physical

        result = resolver_autoridad_diaria_gym(
            self.cliente, self.fecha, force_refresh=True,
        )

        self.assertEqual(GymDecisionVersion.objects.count(), 1)
        self.assertEqual(result["version_persistida"], 1)
        self.assertEqual(result["physical_snapshot"], legacy_physical)

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_nueva_evidencia_sin_limpiar_cache_se_recaptura_y_llega_al_motor(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        normal = {**self.physical, "signals": {"checkin": {"values": {"energy": 7}}}, "fingerprint": "physical-normal"}
        baja = {**self.physical, "signals": {"checkin": {"values": {"energy": 2}}}, "fingerprint": "physical-low"}
        build_snapshot.side_effect = [normal, baja]

        def decidir(_cliente, _fecha, *, physical_snapshot):
            decision = dict(self.base)
            energy = physical_snapshot["signals"]["checkin"]["values"]["energy"]
            if energy <= 3:
                decision.update(estado="version_reducida", causa_principal="energia_baja")
            return decision

        obtener_base.side_effect = decidir
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])

        primera = self._resolver()
        segunda = self._resolver()

        self.assertEqual(build_snapshot.call_count, 2)
        self.assertEqual(obtener_base.call_args_list[0].kwargs["physical_snapshot"], normal)
        self.assertEqual(obtener_base.call_args_list[1].kwargs["physical_snapshot"], baja)
        self.assertEqual(primera["postura"], "empujar")
        self.assertEqual(segunda["postura"], "sostener")
        self.assertNotEqual(primera["decision_id"], segunda["decision_id"])

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_correccion_y_reversion_conservan_snapshot_base_sin_recapturar(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        obtener_base.return_value = self.base
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])
        build_snapshot.return_value = self.physical
        original = self._resolver()
        cache.clear()

        corregida = corregir_autoridad_diaria_gym(
            self.cliente,
            self.fecha,
            decision_id_esperada=original["decision_id"],
            ajustes={"postura": "sostener"},
            motivo="Conservar margen.",
        )
        cache.clear()
        revertida = revertir_correccion_autoridad_diaria_gym(
            self.cliente,
            self.fecha,
            decision_id_esperada=corregida["decision_id"],
            motivo="Volver a la propuesta.",
        )

        self.assertEqual(corregida["physical_snapshot"], self.physical)
        self.assertEqual(revertida["physical_snapshot"], self.physical)
        for version in GymDecisionVersion.objects.filter(cliente=self.cliente, fecha=self.fecha):
            self.assertEqual(version.snapshot["physical_snapshot"], self.physical)
            self.assertEqual(version.snapshot["physical_snapshot_fingerprint"], "physical-a")
        build_snapshot.assert_called_once_with(self.cliente, self.fecha)

    @patch("core.services.physical_snapshot.build_physical_snapshot", side_effect=RuntimeError("secret details"))
    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_fallo_del_builder_no_rompe_autoridad_y_expone_error_estable_sin_detalles(
        self, obtener_base, aplicar_plan, build_snapshot,
    ):
        obtener_base.return_value = self.base
        aplicar_plan.return_value = (self.base["entrenamiento"]["ejercicios"], [])

        autoridad = self._resolver()

        self.assertEqual(autoridad["estado"], "entrenar")
        self.assertEqual(autoridad["postura"], "empujar")
        self.assertEqual(
            autoridad["physical_snapshot"],
            {
                "schema_version": 1,
                "cliente_id": self.cliente.pk,
                "as_of_date": self.fecha.isoformat(),
                "status": "unavailable",
                "error_code": "physical_snapshot_unavailable",
            },
        )
        self.assertNotIn("secret", str(autoridad["physical_snapshot"]))
        self.assertEqual(len(autoridad["physical_snapshot_fingerprint"]), 64)
        build_snapshot.assert_called_once_with(self.cliente, self.fecha)
