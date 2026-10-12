"""Sin ejercicios, el entrenamiento activo explica que no hay sesión."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class EntrenamientoActivoVacioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='vacio', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        self.client.force_login(self.user)

    def test_sin_ejercicios_muestra_estado_vacio_con_salidas(self):
        with patch('entrenos.views._calcular_ejercicios_dia', return_value=[]):
            response = self.client.get(self.url, {'fecha': '2026-10-11'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entrenos/entrenamiento_activo_vacio.html')
        self.assertContains(response, 'Hoy no hay sesión')
        self.assertContains(response, reverse('entrenos:rutina_silenciosa_preview', args=[self.cliente.id]))
        self.assertContains(response, reverse('estiramientos:panel'))
        self.assertNotContains(response, 'tiempo-transcurrido')

    def test_ejercicios_sin_series_cuentan_como_vacio(self):
        with patch('entrenos.views._calcular_ejercicios_dia', return_value=[{'nombre': 'Press', 'series': 0}]):
            response = self.client.get(self.url, {'fecha': '2026-10-11'})
        self.assertTemplateUsed(response, 'entrenos/entrenamiento_activo_vacio.html')
