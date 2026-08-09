import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado, GymDecisionLog
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym


class ApiMarcarCompletadoCierreAprendizajeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='analytics_causal', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Analytics causal'},
        )
        self.client.force_login(self.user)

    def test_post_cierra_aprendizaje_una_vez_tras_guardar_los_hijos(self):
        previa = GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='Press banca',
            ejercicio_normalizado='press banca',
            accion='mantener',
            peso_anterior=60,
            reps_anteriores=8,
            motivo='Decisión pendiente anterior',
        )
        payload = {
            'fecha': '2026-08-09',
            'rutina_nombre': 'Push Analytics',
            'ejercicios': [{
                'nombre': 'Press banca',
                'series': 3,
                'repeticiones': '8, 8, 8',
                'peso_recomendado_kg': 60,
            }],
        }
        url = reverse('analytics:api_marcar_completado', kwargs={'cliente_id': self.cliente.pk})

        with patch(
            'entrenos.services.decision_log_service.cerrar_aprendizaje_gym',
            wraps=cerrar_aprendizaje_gym,
        ) as cierre:
            response = self.client.post(
                url, data=json.dumps(payload), content_type='application/json',
            )

        self.assertEqual(response.status_code, 200, response.content.decode())
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente, fecha=date(2026, 8, 9))
        self.assertEqual(ActividadRealizada.objects.filter(entreno_gym=entreno).count(), 1)
        previa.refresh_from_db()
        self.assertIsNotNone(previa.resultado)
        nuevas = GymDecisionLog.objects.filter(entreno_origen=entreno)
        self.assertEqual(nuevas.count(), 1)
        self.assertIsNone(nuevas.get().resultado)
        self.assertEqual(cierre.call_count, 1)

        cerrar_aprendizaje_gym(entreno)
        self.assertEqual(GymDecisionLog.objects.filter(entreno_origen=entreno).count(), 1)
