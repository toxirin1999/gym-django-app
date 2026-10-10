"""Contrato del estado inicial del análisis de ejercicios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


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

    def test_sesion_sin_ejercicios_no_se_presenta_como_analitica_a_cero(self):
        """Una sesión incompleta no es evidencia suficiente para calcular progreso."""
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=Rutina.objects.create(nombre="Rutina sin detalle"),
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["sin_datos"])
        self.assertTrue(response.context["sin_registros_ejercicio"])
        self.assertContains(response, "todavía no contienen ejercicios analizables")
