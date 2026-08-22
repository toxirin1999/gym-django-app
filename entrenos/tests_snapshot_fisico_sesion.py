from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import ActividadRealizada
from entrenos.services.sesion_recomendada import (
    _aplicar_contexto,
    _obtener_contexto_fisico,
)
from hyrox.models import HyroxObjective, HyroxReadinessLog, UserInjury


class SnapshotFisicoSesionEquivalenciaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("snapshot-sesion")
        self.cliente = Cliente.objects.get(user=user)
        self.hoy = date(2026, 8, 15)

    def _snapshot(self, *, observed_on="2026-08-15", energy=6, readiness=80, injuries=None):
        return {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.hoy.isoformat(),
            "captured_at": "2026-08-15T07:00:00+00:00",
            "signals": {
                "checkin": {
                    "status": "available",
                    "observed_on": observed_on,
                    "age_days": 0,
                    "values": {
                        "sleep_hours": 0.0,
                        "energy": energy,
                        "sleep_quality": 0,
                        "resting_hr": 0,
                        "hrv_ms": 0,
                        "joint_pain": 0,
                    },
                },
                "hyrox_readiness": {
                    "status": "available",
                    "observed_on": self.hoy.isoformat(),
                    "values": {"score": readiness},
                },
                "active_injuries": {
                    "status": "available" if injuries else "missing",
                    "items": injuries or [],
                },
                "recent_activity": {"status": "missing", "items": []},
            },
            "fingerprint": "snapshot-fixture",
        }

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.preferencias_service.get_preferencias_activas")
    def test_snapshot_inyectado_deriva_campos_legacy_preserva_ceros_y_preferencias(
        self, preferencias, build_snapshot,
    ):
        preferencias.return_value = [SimpleNamespace(tipo="evitar_pierna_tras_futbol")]

        contexto = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=self._snapshot(energy=0, readiness=0),
        )

        self.assertEqual(contexto["energia_valor"], 0)
        self.assertTrue(contexto["energia_baja"])
        self.assertEqual(contexto["horas_sueno"], 0.0)
        self.assertEqual(contexto["frecuencia_cardiaca_reposo"], 0)
        self.assertEqual(contexto["hrv_ms"], 0)
        self.assertEqual(contexto["calidad_sueno"], 0)
        self.assertEqual(contexto["dolor"], 0)
        self.assertEqual(contexto["readiness_valor"], 0)
        self.assertTrue(contexto["readiness_bajo"])
        self.assertEqual(contexto["preferencias_activas"], ["evitar_pierna_tras_futbol"])
        self.assertEqual(contexto["_cliente"], self.cliente)
        build_snapshot.assert_not_called()

    def test_checkin_stale_se_conserva_en_snapshot_pero_no_influye_en_contexto(self):
        snapshot = self._snapshot(observed_on="2026-08-14", energy=0)
        snapshot["signals"]["checkin"]["status"] = "available"

        contexto = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=snapshot,
        )

        self.assertFalse(contexto["evidencia_presente"])
        self.assertIsNone(contexto["evidencia_fecha"])
        self.assertIsNone(contexto["energia_valor"])
        self.assertFalse(contexto["energia_baja"])

    def test_snapshot_solo_activa_lesiones_aguda_o_subaguda(self):
        injuries = [
            {"id": 1, "phase": "RETORNO", "zone": "hombro"},
            {"id": 2, "phase": "SUB_AGUDA", "zone": "rodilla"},
        ]

        contexto = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=self._snapshot(injuries=injuries),
        )

        self.assertTrue(contexto["lesion_activa"])
        self.assertEqual(contexto["lesion_fase"], "SUB_AGUDA")
        self.assertEqual(contexto["_cliente"], self.cliente)

    def test_rehab_observacional_no_cambia_contexto_ejecutivo_ni_decision(self):
        without_rehab = self._snapshot()
        with_rehab = self._snapshot()
        with_rehab["capabilities"] = ["active_rehab_v1"]
        with_rehab["signals"]["active_rehab"] = {
            "schema_version": 1,
            "status": "available",
            "temporal_basis": "current_state_at_capture",
            "items": [{
                "episode_id": 7,
                "protocol_zone": "rodilla",
                "observation_status": "active_observed",
                "executive_capacity": {
                    "can_derive_restrictions": False,
                    "reason": "rehab_has_no_gym_risk_contract",
                },
            }],
        }

        context_without = _obtener_contexto_fisico(
            self.cliente, self.hoy, physical_snapshot=without_rehab,
        )
        context_with = _obtener_contexto_fisico(
            self.cliente, self.hoy, physical_snapshot=with_rehab,
        )
        base = {
            "tipo": "programada_hoy",
            "estado": "entrenar",
            "entrenamiento": None,
            "mensaje": "base",
        }

        self.assertEqual(context_with, context_without)
        self.assertEqual(
            _aplicar_contexto(base, context_with, self.hoy),
            _aplicar_contexto(base, context_without, self.hoy),
        )

    @patch("entrenos.services.sesion_recomendada._detectar_riesgo_lesion")
    def test_lesion_snapshot_conserva_decision_segura_y_conflictiva(self, detectar_riesgo):
        contexto = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=self._snapshot(
                injuries=[{"id": 1, "phase": "AGUDA", "zone": "rodilla"}],
            ),
        )
        base = {
            "tipo": "programada_hoy",
            "estado": "entrenar",
            "entrenamiento": {"ejercicios": [{"nombre": "Press banca"}]},
            "mensaje": "base",
        }
        detectar_riesgo.return_value = None
        segura = _aplicar_contexto(base, contexto, self.hoy)
        detectar_riesgo.return_value = {"zona": "rodilla"}
        conflictiva = _aplicar_contexto(base, contexto, self.hoy)

        self.assertEqual((segura["estado"], segura["causa_principal"]), ("entrenar", "sesion_hoy"))
        self.assertEqual((conflictiva["estado"], conflictiva["causa_principal"]), ("recuperar", "lesion"))

    def test_snapshot_ignora_planificada_ayer_si_fecha_realizada_es_futura(self):
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="futbol",
            fecha=self.hoy - timedelta(days=1),
            fecha_realizado=self.hoy + timedelta(days=1),
        )
        snapshot = self._snapshot()
        snapshot["signals"]["recent_activity"] = {"status": "missing", "items": []}

        contexto = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=snapshot,
        )

        self.assertFalse(contexto["futbol_reciente"])

    def test_snapshot_cuenta_futbol_por_fecha_efectiva_con_cualquier_rpe(self):
        snapshot = self._snapshot()
        snapshot["signals"]["recent_activity"] = {
            "status": "available",
            "items": [
                {"id": 1, "type": "futbol", "effective_date": "2026-08-14", "rpe": None},
            ],
        }

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy, physical_snapshot=snapshot)

        self.assertTrue(contexto["futbol_reciente"])

    def test_snapshot_hyrox_solo_cuenta_desde_rpe_siete_y_otras_actividades_no(self):
        for rpe, esperado in ((None, False), (6.9, False), (7, True)):
            with self.subTest(rpe=rpe):
                snapshot = self._snapshot()
                snapshot["signals"]["recent_activity"] = {
                    "status": "available",
                    "items": [
                        {"id": 1, "type": "otro", "effective_date": "2026-08-14", "rpe": 10},
                        {"id": 2, "type": "hyrox", "effective_date": "2026-08-14", "rpe": rpe},
                    ],
                }
                contexto = _obtener_contexto_fisico(
                    self.cliente,
                    self.hoy,
                    physical_snapshot=snapshot,
                )
                self.assertFalse(contexto["futbol_reciente"])
                self.assertEqual(contexto["hyrox_reciente"], esperado)

    def test_snapshot_filtra_defensivamente_hoy_y_fuera_de_ventana(self):
        snapshot = self._snapshot()
        snapshot["signals"]["recent_activity"] = {
            "status": "available",
            "items": [
                {"id": 1, "type": "futbol", "effective_date": "2026-08-15", "rpe": 9},
                {"id": 2, "type": "hyrox", "effective_date": "2026-08-12", "rpe": 9},
            ],
        }

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy, physical_snapshot=snapshot)

        self.assertFalse(contexto["futbol_reciente"])
        self.assertFalse(contexto["hyrox_reciente"])

    @patch("core.services.physical_snapshot.build_physical_snapshot", side_effect=RuntimeError("source down"))
    def test_fallo_builder_degrada_a_consultas_legacy_sin_cambiar_decision(self, build_snapshot):
        bitacora = BitacoraDiaria.objects.create(cliente=self.cliente, energia_subjetiva=3)
        BitacoraDiaria.objects.filter(pk=bitacora.pk).update(fecha=self.hoy)
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="futbol",
            fecha=self.hoy - timedelta(days=1),
        )
        objective = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + timedelta(days=30),
            estado="activo",
        )
        log = HyroxReadinessLog.objects.create(objective=objective, score=80)
        HyroxReadinessLog.objects.filter(pk=log.pk).update(fecha=self.hoy)

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertEqual(contexto["energia_valor"], 3)
        self.assertTrue(contexto["energia_baja"])
        self.assertEqual(contexto["readiness_valor"], 80)
        self.assertFalse(contexto["readiness_bajo"])
        self.assertTrue(contexto["futbol_reciente"])
        build_snapshot.assert_called_once_with(self.cliente, self.hoy)

    def test_contexto_snapshot_real_equivale_al_legacy_en_campos_decisionales(self):
        BitacoraDiaria.objects.create(cliente=self.cliente, energia_subjetiva=2)
        injury = UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada="rodilla",
            fase=UserInjury.Fase.SUB_AGUDA,
            fecha_inicio=self.hoy,
        )
        UserInjury.objects.filter(pk=injury.pk).update(activa=True)
        from core.services.physical_snapshot import build_physical_snapshot

        snapshot = build_physical_snapshot(self.cliente, self.hoy)
        desde_snapshot = _obtener_contexto_fisico(
            self.cliente,
            self.hoy,
            physical_snapshot=snapshot,
        )
        with patch(
            "core.services.physical_snapshot.build_physical_snapshot",
            side_effect=RuntimeError("force legacy"),
        ):
            legacy = _obtener_contexto_fisico(self.cliente, self.hoy)

        campos = (
            "lesion_activa", "lesion_fase", "energia_baja", "energia_valor",
            "readiness_bajo", "readiness_valor", "futbol_reciente", "hyrox_reciente",
        )
        self.assertEqual(
            {campo: desde_snapshot[campo] for campo in campos},
            {campo: legacy[campo] for campo in campos},
        )
