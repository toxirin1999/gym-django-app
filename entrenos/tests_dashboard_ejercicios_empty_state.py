"""Contrato del estado inicial del análisis de ejercicios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class DashboardEjerciciosEmptyStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="analitica-sin-sesiones", password="secreto"
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse("entrenos:dashboard_ejercicios", args=[self.cliente.id])

    def test_sin_sesiones_ofrece_una_salida_hacia_la_rutina(self):
        """El análisis vacío no debe invitar a registrar sin indicar dónde hacerlo."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["sin_datos"])
        self.assertContains(response, "Ver tu rutina")
        self.assertContains(
            response,
            reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id]),
        )
        self.assertContains(response, 'class="btn-primary empty-state-action"')
