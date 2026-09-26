"""Contrato de la preview compacta de Rutina.

La preview no reemplaza al calendario histórico: ofrece una entrada móvil y
debe conservar siempre los destinos profundos de planificación y movilidad.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class RutinaSilenciosaPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rutina-silenciosa", password="secreto"
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id])

    def test_anonimo_es_redirigido_a_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_dueno_puede_renderizar_contexto_real_del_plan(self):
        """El modo móvil usa el contrato real del plan, no solo el mock del test."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fase actual")
        self.assertContains(response, "Elegir día")

    @patch("entrenos.views._obtener_contexto_rutina_silenciosa")
    def test_dueno_ve_fase_hoy_y_destinos_reales(self, contexto):
        contexto.return_value = {
            "fase": {"nombre": "DESCARGA ACTIVA", "objetivo": "Recuperación activa"},
            "semana": [{"numero": 26, "fecha": date(2026, 9, 26), "es_hoy": True}],
            "hoy": {"tipo": "descanso", "titulo": "Día de descanso", "detalle": "El plan no programa entreno hoy."},
            "rms": [{"nombre": "Press banca", "valor": 100}],
            "insight": "La descarga protege tu adaptación.",
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "entrenos/rutina_silenciosa_preview.html")
        self.assertContains(response, "DESCARGA ACTIVA")
        self.assertContains(response, "Día de descanso")
        self.assertContains(response, "La descarga protege tu adaptación.")
        self.assertContains(response, reverse("entrenos:vista_plan_anual", args=[self.cliente.id]))
        self.assertContains(response, reverse("estiramientos:panel"))

    def test_otro_usuario_no_puede_ver_la_preview(self):
        otro = get_user_model().objects.create_user(
            username="intruso-rutina", password="secreto"
        )
        self.client.force_login(otro)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
