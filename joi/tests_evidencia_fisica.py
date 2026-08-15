from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from joi.models import MensajeJOI


class EvidenciaFisicaFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joi-evidencia")
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = date(2026, 8, 15)

    def physical(self, **changes):
        snapshot = {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.hoy.isoformat(),
            "status": "available",
            "fingerprint": "physical-fingerprint",
            "signals": {
                "checkin": {
                    "status": "available",
                    "observed_on": self.hoy.isoformat(),
                    "age_days": 0,
                    "values": {
                        "energy": 0,
                        "sleep_hours": 0.0,
                        "sleep_quality": 0,
                        "resting_hr": 0,
                        "hrv_ms": 0,
                        "joint_pain": 0,
                        "private_note": "no debe salir",
                    },
                    "provenance": {
                        "source": "clientes.BitacoraDiaria",
                        "record_id": 11,
                        "private": "no debe salir",
                    },
                },
                "hyrox_readiness": {
                    "status": "stale",
                    "observed_on": "2026-08-11",
                    "age_days": 4,
                    "values": {"score": 0, "hrv_ms": None},
                    "provenance": {
                        "source": "hyrox.HyroxReadinessLog",
                        "record_id": 22,
                    },
                },
                "unknown_signal": {
                    "status": "available",
                    "values": {"secret": 99},
                    "provenance": {"source": "otro.Modelo"},
                },
            },
        }
        snapshot.update(changes)
        return snapshot

    def version(self, physical=None, **changes):
        attrs = {
            "cliente": self.cliente,
            "fecha": self.hoy,
            "version": 1,
            "decision_id": "gym-test",
            "schema_version": 1,
            "origen": GymDecisionVersion.ORIGEN_MOTOR,
            "vigente": True,
            "fingerprint": "decision-fingerprint",
            "base_fingerprint": "base-fingerprint",
            "postura": "empujar",
            "causa_principal": "sesion_hoy",
            "snapshot": {"physical_snapshot": physical or self.physical()},
        }
        attrs.update(changes)
        return GymDecisionVersion.objects.create(**attrs)


class PhysicalEvidenceContextTests(EvidenciaFisicaFixture):
    def build(self, cliente=None, fecha=None):
        from joi.context_builders.physical_evidence_context import (
            build_physical_evidence_context,
        )
        return build_physical_evidence_context(
            cliente or self.cliente,
            fecha or self.hoy,
        )

    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_lee_version_vigente_sin_recalcular_ni_escribir(self, resolver, build_snapshot):
        self.version()
        antes = GymDecisionVersion.objects.count()

        result = self.build()

        self.assertEqual(GymDecisionVersion.objects.count(), antes)
        resolver.assert_not_called()
        build_snapshot.assert_not_called()
        self.assertEqual(result["physical_evidence"]["fingerprint"], "physical-fingerprint")

    def test_aplica_whitelist_y_conserva_ceros_y_procedencia(self):
        self.version()

        evidence = self.build()["physical_evidence"]

        self.assertEqual(set(evidence["signals"]), {"checkin", "hyrox_readiness"})
        checkin = evidence["signals"]["checkin"]
        self.assertEqual(checkin["status"], "available")
        self.assertEqual(checkin["observed_on"], self.hoy.isoformat())
        self.assertEqual(checkin["age_days"], 0)
        self.assertEqual(checkin["values"]["energy"], 0)
        self.assertEqual(checkin["values"]["sleep_hours"], 0.0)
        self.assertNotIn("private_note", checkin["values"])
        self.assertEqual(
            checkin["provenance"],
            {"source": "clientes.BitacoraDiaria", "record_id": 11},
        )

    def test_stale_se_conserva_como_hecho_pero_no_se_afirma_en_bloque(self):
        self.version()
        evidence = self.build()["physical_evidence"]
        self.assertEqual(evidence["signals"]["hyrox_readiness"]["status"], "stale")

        from joi.context_builders.physical_evidence_context import _bloque_hechos_fisicos
        block = _bloque_hechos_fisicos(evidence)

        self.assertIn("EVIDENCIA FÍSICA", block)
        self.assertIn("Energía registrada: 0/10", block)
        self.assertNotIn("readiness", block.lower())
        self.assertNotIn("obsoleto", block.lower())

    def test_bloque_hace_trazable_corte_huella_fecha_y_solo_fuentes_afirmadas(self):
        self.version()
        evidence = self.build()["physical_evidence"]

        from joi.context_builders.physical_evidence_context import _bloque_hechos_fisicos
        block = _bloque_hechos_fisicos(evidence)

        self.assertIn("Corte: 2026-08-15", block)
        self.assertIn("Huella física: physical-fin", block)
        self.assertIn(
            "Fuente: clientes.BitacoraDiaria; observada: 2026-08-15",
            block,
        )
        self.assertNotIn("hyrox.HyroxReadinessLog", block)
        self.assertNotIn("record_id", block)
        self.assertNotIn("11", block)

    def test_lesion_y_actividad_declaran_su_fuente_y_fecha_disponible(self):
        physical = self.physical()
        physical["signals"].update({
            "active_injuries": {
                "status": "available",
                "items": [{
                    "id": 44,
                    "zone": "rodilla",
                    "phase": "SUB_AGUDA",
                    "started_on": "2026-08-12",
                }],
                "provenance": {
                    "source": "hyrox.UserInjury",
                    "record_ids": [44],
                },
            },
            "recent_activity": {
                "status": "available",
                "items": [{
                    "id": 55,
                    "type": "futbol",
                    "effective_date": "2026-08-14",
                }],
                "provenance": {
                    "source": "entrenos.ActividadRealizada",
                    "record_ids": [55],
                    "effective_date_rule": "fecha_realizado_or_fecha",
                },
            },
        })
        self.version(physical=physical)
        evidence = self.build()["physical_evidence"]

        from joi.context_builders.physical_evidence_context import _bloque_hechos_fisicos
        block = _bloque_hechos_fisicos(evidence)

        self.assertIn("Fuente: hyrox.UserInjury; inicio: 2026-08-12", block)
        self.assertIn(
            "Fuente: entrenos.ActividadRealizada; fecha efectiva: 2026-08-14",
            block,
        )
        self.assertNotIn("44", block)
        self.assertNotIn("55", block)

    def test_omite_version_ausente_malformada_no_disponible_fecha_o_tenant_incorrectos(self):
        self.assertEqual(self.build(), {})

        invalidos = [
            None,
            {"status": "unavailable", "schema_version": 1},
            self.physical(schema_version=2),
            self.physical(cliente_id=self.cliente.pk + 999),
            self.physical(as_of_date="2026-08-14"),
            self.physical(signals=[]),
        ]
        for index, physical in enumerate(invalidos, start=1):
            GymDecisionVersion.objects.all().delete()
            self.version(
                physical=physical or {},
                version=index,
                snapshot={"physical_snapshot": physical} if physical is not None else {},
            )
            self.assertEqual(self.build(), {}, msg=f"invalid case {index}")

    def test_no_lee_version_de_otro_cliente_ni_version_no_vigente(self):
        otro_user = User.objects.create_user("otro-joi-evidencia")
        otro = Cliente.objects.get(user=otro_user)
        self.version(vigente=False)
        GymDecisionVersion.objects.create(
            cliente=otro, fecha=self.hoy, version=1, decision_id="otra",
            schema_version=1, origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True, fingerprint="x", base_fingerprint="y",
            postura="empujar", snapshot={"physical_snapshot": self.physical()},
        )
        self.assertEqual(self.build(), {})


class PhysicalEvidenceJoiIntegrationTests(EvidenciaFisicaFixture):
    def _generate_capture(self, trigger, ctx):
        captured = {}

        def fake_haiku(prompt, **kwargs):
            captured["prompt"] = prompt
            return "Mensaje único."

        with patch("joi.services.construir_contexto", return_value=ctx), \
             patch("joi.services.build_continuidad_context", return_value={}), \
             patch("joi.services._bloque_continuidad", return_value="CONTINUIDAD"), \
             patch("joi.services._bloque_marco_narrativo", return_value="NARRATIVA"), \
             patch("joi.services._bloque_narrativa", return_value="NARRATIVA"), \
             patch("joi.services._bloque_manual", return_value="MANUAL"), \
             patch("joi.services._bloque_memoria", return_value="MEMORIA"), \
             patch("joi.services._bloque_temporal", return_value="TEMPORAL"), \
             patch("joi.services._llamar_haiku", side_effect=fake_haiku), \
             patch("joi.services.validar_semantica_joi"):
            from joi.services import generar_mensaje_joi
            msg = generar_mensaje_joi(
                self.cliente,
                trigger,
                {"accion": "mantener", "ejercicio": "press", "motivo": "técnica"},
            )
        return msg, captured.get("prompt", "")

    def _evidence(self):
        self.version()
        from joi.context_builders.physical_evidence_context import build_physical_evidence_context
        return build_physical_evidence_context(self.cliente, self.hoy)["physical_evidence"]

    def test_apertura_y_decision_reciben_evidencia_despues_de_continuidad_antes_del_trigger(self):
        evidence = self._evidence()
        for trigger in ("apertura_manana", "decision_plan"):
            MensajeJOI.objects.all().delete()
            antes_decisiones = GymDecisionVersion.objects.count()
            msg, prompt = self._generate_capture(trigger, {"physical_evidence": evidence})

            self.assertIsNotNone(msg)
            self.assertEqual(MensajeJOI.objects.count(), 1)
            self.assertEqual(GymDecisionVersion.objects.count(), antes_decisiones)
            self.assertLess(prompt.index("NARRATIVA"), prompt.index("MANUAL"))
            self.assertLess(prompt.index("MANUAL"), prompt.index("CONTINUIDAD"))
            self.assertLess(prompt.index("CONTINUIDAD"), prompt.index("EVIDENCIA FÍSICA"))
            self.assertLess(prompt.index("EVIDENCIA FÍSICA"), prompt.index("press") if trigger == "decision_plan" else len(prompt))

    def test_bloque_ausente_no_deja_seccion_y_resumen_semanal_lo_excluye(self):
        _, no_evidence = self._generate_capture("apertura_manana", {})
        _, summary = self._generate_capture("resumen_semanal", {"physical_evidence": self._evidence()})
        self.assertNotIn("EVIDENCIA FÍSICA", no_evidence)
        self.assertNotIn("EVIDENCIA FÍSICA", summary)

    @patch(
        "joi.context_builders.physical_evidence_context.build_physical_evidence_context",
        side_effect=RuntimeError("fallo aislado"),
    )
    def test_construir_contexto_tolera_fallo_del_builder(self, _builder):
        with patch("joi.context_builders.activity_context.build_activity_context", return_value={}), \
             patch("joi.context_builders.gym_context.build_gym_context", return_value={}), \
             patch("joi.context_builders.hyrox_context.build_hyrox_context", return_value={}), \
             patch("joi.context_builders.joi_state_context.build_joi_state_context", return_value={}), \
             patch("joi.context_builders.life_context.build_life_context", return_value={}), \
             patch("core.continuidad.evaluar_continuidad_entrenamiento", return_value={}):
            from joi.services import construir_contexto
            self.assertNotIn("physical_evidence", construir_contexto(self.cliente))
