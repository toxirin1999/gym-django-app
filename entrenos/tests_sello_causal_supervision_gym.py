"""Fase 6.4A: la ejecución conserva la autoridad supervisada que la inició."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import signing
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, GymDecisionVersion
from entrenos.services.sello_ejecucion_gym_service import (
    SelloEjecucionGymInvalido,
    emitir_sello_ejecucion_gym,
    validar_sello_ejecucion_gym,
)
from rutinas.models import Rutina


class SelloCausalSupervisionGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sello-causal", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro_user = User.objects.create_user("sello-ajeno", password="x")
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.client.force_login(self.user)
        self.fecha = date(2026, 8, 22)
        self.rutina = Rutina.objects.create(nombre="Sesión sellada")

    def _version(self, *, cliente=None, version=1, decision_id="gym-sellada"):
        return GymDecisionVersion.objects.create(
            cliente=cliente or self.cliente,
            fecha=self.fecha,
            version=version,
            decision_id=decision_id,
            origen=GymDecisionVersion.ORIGEN_CORRECCION,
            vigente=True,
            fingerprint=f"fingerprint-{version}",
            base_fingerprint="base-estable",
            postura="sostener",
            snapshot={"estado": "version_reducida", "postura": "sostener"},
        )

    def _payload(self, *, sello=""):
        return {
            "fecha": self.fecha.isoformat(),
            "rutina_nombre": self.rutina.nombre,
            "sello_autoridad_gym": sello,
            "sesion_programada_id": "",
            "modo_reducido": "1",
            "duracion_minutos_real": "0",
            "series_completadas": "",
            "series_totales": "",
            "ejercicios_completados": "",
            "ejercicios_totales": "",
            "volumen_total_sesion": "",
            "rpe_medio_sesion": "",
            "rpe_global_sesion": "",
            "energia_pre_sesion": "",
        }

    def test_sello_firmado_resuelve_version_exacta_y_su_emision(self):
        version = self._version()
        sello = emitir_sello_ejecucion_gym(version=version, user=self.user)

        validado = validar_sello_ejecucion_gym(
            sello=sello,
            user=self.user,
            cliente=self.cliente,
            fecha_autoridad=self.fecha,
        )

        self.assertEqual(validado.version, version)
        self.assertEqual(validado.estado_causal, "exacta")
        self.assertIsNotNone(validado.emitida_en)

    def test_sello_caduca_a_las_24_horas(self):
        version = self._version()
        with patch("django.core.signing.time.time", return_value=1_000_000):
            sello = emitir_sello_ejecucion_gym(version=version, user=self.user)

        with patch("django.core.signing.time.time", return_value=1_086_401):
            with self.assertRaises(SelloEjecucionGymInvalido):
                validar_sello_ejecucion_gym(
                    sello=sello,
                    user=self.user,
                    cliente=self.cliente,
                    fecha_autoridad=self.fecha,
                )

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_get_validado_emite_sello_y_lo_transporta_en_formulario(self, resolver):
        version = self._version()
        resolver.return_value = {
            "decision_id": version.decision_id,
            "estado": "version_reducida",
            "postura": "sostener",
            "entrenamiento": {"ejercicios": []},
        }
        response = self.client.get(
            reverse("entrenos:entrenamiento_activo", args=[self.cliente.pk]),
            {
                "fecha": self.fecha.isoformat(),
                "rutina_nombre": self.rutina.nombre,
                "decision_id": version.decision_id,
                "ejercicios": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        sello = response.context["sello_autoridad_gym"]
        self.assertTrue(sello)
        self.assertContains(response, 'name="sello_autoridad_gym"')
        self.assertContains(response, sello)

    def test_post_persiste_la_version_exacta(self):
        version = self._version()
        sello = emitir_sello_ejecucion_gym(version=version, user=self.user)

        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            self._payload(sello=sello),
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.gym_decision_version, version)
        self.assertEqual(entreno.gym_decision_estado_causal, "exacta")
        self.assertIsNotNone(entreno.gym_decision_emitida_en)

    def test_sesion_reubicada_conserva_la_fecha_y_version_de_autoridad(self):
        self.fecha = date(2026, 8, 20)
        version = self._version()
        sello = emitir_sello_ejecucion_gym(version=version, user=self.user)

        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            self._payload(sello=sello),
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.fecha, self.fecha)
        self.assertEqual(entreno.gym_decision_version, version)
        self.assertEqual(entreno.gym_decision_version.fecha, self.fecha)

    def test_correccion_durante_entreno_no_pierde_sesion_ni_reasigna_autoria(self):
        vista = self._version()
        sello = emitir_sello_ejecucion_gym(version=vista, user=self.user)
        vista.vigente = False
        vista.save(update_fields=["vigente"])
        nueva = self._version(version=2, decision_id="gym-nueva")

        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            self._payload(sello=sello),
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.gym_decision_version, vista)
        self.assertNotEqual(entreno.gym_decision_version, nueva)
        self.assertEqual(
            entreno.gym_decision_estado_causal, "superada_durante_ejecucion"
        )

    def test_sello_alterado_rechaza_con_cero_escrituras(self):
        version = self._version()
        sello = emitir_sello_ejecucion_gym(version=version, user=self.user) + "alterado"

        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            self._payload(sello=sello),
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(EntrenoRealizado.objects.exists())

    def test_sello_ajeno_o_version_inexistente_se_rechazan(self):
        ajena = self._version(cliente=self.otro, decision_id="gym-ajena")
        sello_ajeno = emitir_sello_ejecucion_gym(version=ajena, user=self.otro_user)
        with self.assertRaises(SelloEjecucionGymInvalido):
            validar_sello_ejecucion_gym(
                sello=sello_ajeno,
                user=self.user,
                cliente=self.cliente,
                fecha_autoridad=self.fecha,
            )

        propia = self._version(version=2, decision_id="gym-borrada")
        sello_inexistente = emitir_sello_ejecucion_gym(version=propia, user=self.user)
        propia.delete()
        with self.assertRaises(SelloEjecucionGymInvalido):
            validar_sello_ejecucion_gym(
                sello=sello_inexistente,
                user=self.user,
                cliente=self.cliente,
                fecha_autoridad=self.fecha,
            )

    def test_sello_de_otra_fecha_se_rechaza(self):
        version = self._version()
        sello = emitir_sello_ejecucion_gym(version=version, user=self.user)
        with self.assertRaises(SelloEjecucionGymInvalido):
            validar_sello_ejecucion_gym(
                sello=sello,
                user=self.user,
                cliente=self.cliente,
                fecha_autoridad=date(2026, 8, 23),
            )

    def test_post_legacy_sin_sello_conserva_campos_causales_nulos(self):
        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            self._payload(),
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertIsNone(entreno.gym_decision_version)
        self.assertIsNone(entreno.gym_decision_emitida_en)
        self.assertIsNone(entreno.gym_decision_estado_causal)

    def test_fallo_tardio_revierte_entreno_ya_creado(self):
        with patch(
            "entrenos.services.decision_log_service.cerrar_aprendizaje_gym",
            side_effect=RuntimeError("fallo tardío deliberado"),
        ):
            response = self.client.post(
                reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
                self._payload(),
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EntrenoRealizado.objects.exists())

    def test_version_usada_por_entreno_esta_protegida_frente_a_borrado(self):
        version = self._version()
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.fecha,
            gym_decision_version=version,
            gym_decision_emitida_en=version.creado_en,
            gym_decision_estado_causal="exacta",
        )

        with self.assertRaises(ProtectedError):
            version.delete()

    def test_sello_no_es_un_json_falsificable_sin_firma(self):
        version = self._version()
        payload = {
            "schema": 1,
            "user_id": self.user.pk,
            "cliente_id": self.cliente.pk,
            "fecha": self.fecha.isoformat(),
            "decision_pk": version.pk,
            "decision_id": version.decision_id,
            "base_fingerprint": version.base_fingerprint,
        }
        falso = signing.b64_encode(str(payload).encode()).decode()
        with self.assertRaises(SelloEjecucionGymInvalido):
            validar_sello_ejecucion_gym(
                sello=falso,
                user=self.user,
                cliente=self.cliente,
                fecha_autoridad=self.fecha,
            )
