"""Contrato del estado inicial del dashboard global de analítica."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class DashboardGlobalEmptyStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="analytics-empty-state", password="secreto"
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={
                "nombre": "Analítica Inicial",
                "email": "analytics-empty@example.com",
                "telefono": "000000000",
            },
        )
        self.url = reverse("analytics:dashboard_global", args=[self.cliente.id])
        self.rutina_url = reverse(
            "entrenos:rutina_silenciosa_preview", args=[self.cliente.id]
        )

    def test_sin_entrenos_muestra_un_inicio_honesto_y_lleva_a_la_rutina(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["tiene_historial_entrenos"])
        self.assertContains(response, "Aún no hay datos de entrenamiento")
        self.assertContains(response, self.rutina_url)
        self.assertNotContains(response, "Training Load &amp; Recovery (ACWR)")
        self.assertNotContains(response, 'id="acwrChart"')
        self.assertNotContains(response, 'id="chartVolumenSemanal"')

    def test_con_entrenos_mantiene_el_tablero_de_analitica(self):
        rutina = Rutina.objects.create(nombre="Rutina de prueba")
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina)
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["tiene_historial_entrenos"])
        self.assertContains(response, "Training Load & Recovery (ACWR)")
        self.assertContains(response, 'id="acwrChart"')
        self.assertContains(response, 'id="chartVolumenSemanal"')
