"""Contrato de la API legacy: nunca inventa estado del plan ni carga."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import SesionProgramada


class ApiEstadisticasCanonicasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('api-estadisticas', password='secreto')
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('entrenos:api_estadisticas')
        self.client.force_login(self.user)

    @patch('entrenos.services.estadisticas_service.EstadisticasService.analizar_acwr')
    def test_expone_acwr_y_siguiente_sesion_reales(self, analizar_acwr):
        analizar_acwr.return_value = {'acwr_actual': 1.37, 'zona_riesgo': 'cuidado'}
        hoy = timezone.localdate()
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=hoy + timedelta(days=2),
            nombre_sesion='Fuerza tronco',
        )

        response = self.client.get(self.url, {'cliente_id': self.cliente.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['acwr'], 1.37)
        self.assertEqual(payload['acwr_zona_riesgo'], 'cuidado')
        self.assertEqual(payload['proximo_entrenamiento'], {
            'nombre': 'Fuerza tronco',
            'fecha': (hoy + timedelta(days=2)).isoformat(),
            'es_hoy': False,
        })

    @patch('entrenos.services.estadisticas_service.EstadisticasService.analizar_acwr')
    def test_no_inventa_proximo_entrenamiento_sin_plan(self, analizar_acwr):
        analizar_acwr.return_value = {'acwr_actual': 0, 'zona_riesgo': 'baja_carga'}

        response = self.client.get(self.url, {'cliente_id': self.cliente.id})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['proximo_entrenamiento'])
