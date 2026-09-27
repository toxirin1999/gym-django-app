"""Contrato de presentación para la memoria del entrenador."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class MemoriaEntrenadorUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='memoria-ui', password='secreto',
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('clientes:memoria_entrenador', args=[self.cliente.id])

    def test_memoria_prioriza_lectura_de_hoy_y_profundidad_plegable(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'clientes/memoria_entrenador.html')
        self.assertContains(response, 'Lectura de hoy')
        self.assertContains(response, 'Señales esenciales')
        self.assertContains(response, 'Expediente completo')
        self.assertContains(response, 'Memoria')

    def test_plantilla_fija_nav_global_y_secciones_de_profundidad(self):
        plantilla = Path('clientes/templates/clientes/memoria_entrenador.html').read_text()

        self.assertIn("{% url 'clientes:dashboard_silencioso_preview' %}", plantilla)
        self.assertIn("{% url 'clientes:trayectoria_plan' %}", plantilla)
        self.assertIn("{% url 'entrenos:rutina_silenciosa_preview' cliente.id %}", plantilla)
        self.assertIn('mem-depth', plantilla)
        self.assertIn('<details', plantilla)
