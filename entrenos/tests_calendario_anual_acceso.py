"""Calendario anual: acceso del dueño, ruta antigua redirigida y texto de la próxima fase."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

PLANTILLA = 'entrenos/templates/entrenos/vista_plan_calendario.html'


class CalendarioAnualAccesoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dueno = User.objects.create_user('cal_dueno', password='x')
        self.ajeno = User.objects.create_user('cal_ajeno', password='x')
        self.cliente = self.dueno.cliente_perfil
        self.url = reverse('entrenos:vista_plan_anual', args=[self.cliente.id])

    def test_anonimo_va_al_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_otro_usuario_recibe_404(self):
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_ruta_antigua_lleva_al_calendario_vigente(self):
        self.client.force_login(self.dueno)
        response = self.client.get(reverse('entrenos:vista_plan_calendario', args=[self.cliente.id]))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    def test_la_proxima_fase_no_tiene_texto_fijo(self):
        from pathlib import Path
        plantilla = Path(PLANTILLA).read_text(encoding='utf-8')
        self.assertNotIn('<div class="np-next-desc">Desarrollo de fuerza máxima', plantilla)
        self.assertIn('{{ proxima_fase_descripcion }}', plantilla)
