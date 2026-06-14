"""
Phase Hábitos 2.0D.1 — Neutralizar entrada legacy de hábitos en Prosoche.

Cubre: la tarjeta "Hábitos" de prosoche_dashboard ya no expone UI legacy
(crear/registrar/borrar ProsocheHabito) y apunta a /diario/habitos/ (Gestos).
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from diario.models import Gesto, RegistroGesto


class ProsocheDashboardSinUiLegacyTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)

    def test_no_contiene_copiar_habitos_mes_anterior(self):
        response = self.client.get(reverse('diario:prosoche_dashboard'))
        url_copiar = reverse('diario:copiar_habitos_mes_anterior')
        self.assertNotContains(response, url_copiar)
        self.assertNotContains(response, 'Copiar del mes anterior')

    def test_no_contiene_form_crear_habito_legacy(self):
        response = self.client.get(reverse('diario:prosoche_dashboard'))
        url_crear = reverse('diario:prosoche_crear_habito')
        self.assertNotContains(response, url_crear)

    def test_no_contiene_eliminar_habito_legacy(self):
        response = self.client.get(reverse('diario:prosoche_dashboard'))
        url_eliminar = reverse('diario:eliminar_habito', args=[1])
        self.assertNotContains(response, url_eliminar)

    def test_contiene_enlace_a_habitos_dashboard(self):
        response = self.client.get(reverse('diario:prosoche_dashboard'))
        url_gestos = reverse('diario:habitos_dashboard')
        self.assertContains(response, url_gestos)

    def test_prosoche_dashboard_devuelve_200(self):
        response = self.client.get(reverse('diario:prosoche_dashboard'))
        self.assertEqual(response.status_code, 200)


class FlujoGestosSigueOperandoTestCase(TestCase):
    """5. habito_crear + habito_toggle_dia siguen operando sobre Gesto/RegistroGesto."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)

    def test_crear_gesto_y_toggle_dia(self):
        response = self.client.post(reverse('diario:habito_crear'), {
            'nombre': 'Leer 10 min',
            'descripcion': '',
            'periodo_observacion_dias': 30,
            'color': '#F49459',
            'tipo_habito': 'positivo',
        })
        self.assertEqual(response.status_code, 302)

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Leer 10 min')
        self.assertEqual(gesto.tipo, 'cultivo')

        hoy = date.today()
        response = self.client.post(
            reverse('diario:habito_toggle_dia'),
            data='{"habito_id": %d, "dia": %d}' % (gesto.id, hoy.day),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            RegistroGesto.objects.filter(gesto=gesto, fecha=hoy, estado='cumplido').exists()
        )
