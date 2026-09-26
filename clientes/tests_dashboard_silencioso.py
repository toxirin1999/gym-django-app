"""Contrato de la vista previa del dashboard silencioso."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class DashboardSilenciosoPreviewTests(TestCase):
    def setUp(self):
        self.url = reverse("clientes:dashboard_silencioso_preview")
        self.user = get_user_model().objects.create_user(
            username="dashboard-silencioso", password="secreto"
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={"nombre": "David", "dias_disponibles": 4}
        )

    def test_anonimo_es_redirigido_a_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_usuario_autenticado_ve_decision_y_destinos_profundos(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clientes/dashboard_silencioso_preview.html")
        self.assertContains(response, "Ahora")
        self.assertContains(response, "Esta semana")
        self.assertContains(response, "Lo que el plan aprendió")
        self.assertContains(response, "Entreno")
        self.assertContains(response, "Plan")
        self.assertContains(response, "Memoria")
        self.assertContains(response, "Vida")
        self.assertContains(response, reverse("entrenos:vista_plan_anual", args=[self.cliente.id]))
        self.assertContains(response, reverse("clientes:memoria_entrenador", args=[self.cliente.id]))
