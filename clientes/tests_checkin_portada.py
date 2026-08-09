from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import BitacoraDiaria, Cliente


class CheckinPortadaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="atleta-checkin", password="test-pass-123"
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.url = reverse("clientes:checkin_matutino")
        self.portada_url = reverse("clientes:mockup_demo")

    def test_get_endpoint_no_muta_y_responde_method_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(BitacoraDiaria.objects.filter(cliente=self.cliente).exists())

    def test_portada_no_bloquea_y_explica_contrato_accesible(self):
        response = self.client.get(self.portada_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["checkin_pendiente"])
        self.assertContains(response, "CHECK-IN PENDIENTE")
        self.assertNotContains(response, "Completar ahora")
        self.assertContains(response, "Más tarde")
        self.assertContains(response, "Sueño y energía son obligatorios")
        self.assertContains(response, "Datos biométricos opcionales")
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, 'aria-labelledby="rbCheckinTitle"')
        self.assertNotContains(response, "Auto-open check-in modal")

    def test_evidencia_sueno_y_energia_marca_checkin_completado_sin_fc(self):
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=7.5,
            energia_subjetiva=6,
        )

        response = self.client.get(self.portada_url)

        self.assertFalse(response.context["checkin_pendiente"])
        self.assertIsNotNone(response.context["checkin_hoy"])

    def test_post_requiere_sueno_y_energia_y_no_crea_registro_parcial(self):
        response = self.client.post(self.url, {"horas_sueno": "7.5"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("energía", response.json()["error"].lower())
        self.assertFalse(BitacoraDiaria.objects.filter(cliente=self.cliente).exists())

    def test_post_valida_rangos_con_error_util(self):
        response = self.client.post(
            self.url, {"horas_sueno": "18", "energia_subjetiva": "11"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("horas_sueno", response.json()["errors"])
        self.assertIn("energia_subjetiva", response.json()["errors"])
        self.assertFalse(BitacoraDiaria.objects.filter(cliente=self.cliente).exists())

    def test_post_crea_sin_biometria_y_exige_recarga_de_portada(self):
        response = self.client.post(
            self.url, {"horas_sueno": "7.5", "energia_subjetiva": "6"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["reload_required"])
        self.assertEqual(response.json()["reload_url"], self.portada_url)
        bitacora = BitacoraDiaria.objects.get(cliente=self.cliente, fecha=timezone.localdate())
        self.assertEqual(float(bitacora.horas_sueno), 7.5)
        self.assertEqual(bitacora.energia_subjetiva, 6)
        self.assertIsNone(bitacora.fc_reposo)

    def test_posts_repetidos_actualizan_unico_registro_del_dia(self):
        self.client.post(self.url, {"horas_sueno": "7", "energia_subjetiva": "5"})
        response = self.client.post(
            self.url,
            {
                "horas_sueno": "8",
                "energia_subjetiva": "8",
                "fc_reposo": "54",
                "hrv_ms": "68",
            },
        )

        self.assertEqual(response.status_code, 200)
        registros = BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=timezone.localdate())
        self.assertEqual(registros.count(), 1)
        bitacora = registros.get()
        self.assertEqual(float(bitacora.horas_sueno), 8)
        self.assertEqual(bitacora.energia_subjetiva, 8)
        self.assertEqual(bitacora.fc_reposo, 54)
        self.assertEqual(bitacora.hrv_ms, 68)

    def test_actualizacion_sin_biometria_conserva_valores_opcionales_previos(self):
        self.client.post(
            self.url,
            {
                "horas_sueno": "7",
                "energia_subjetiva": "5",
                "fc_reposo": "55",
                "hrv_ms": "70",
            },
        )

        response = self.client.post(
            self.url, {"horas_sueno": "8", "energia_subjetiva": "7"}
        )

        self.assertEqual(response.status_code, 200)
        bitacora = BitacoraDiaria.objects.get(cliente=self.cliente, fecha=timezone.localdate())
        self.assertEqual(bitacora.fc_reposo, 55)
        self.assertEqual(bitacora.hrv_ms, 70)

    def test_endpoint_preserva_auth_y_csrf(self):
        self.client.logout()
        anonymous = self.client.post(
            self.url, {"horas_sueno": "7", "energia_subjetiva": "6"}
        )
        self.assertEqual(anonymous.status_code, 302)

        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        rejected = csrf_client.post(
            self.url, {"horas_sueno": "7", "energia_subjetiva": "6"}
        )
        self.assertEqual(rejected.status_code, 403)
