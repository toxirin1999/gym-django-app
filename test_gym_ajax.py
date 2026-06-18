"""
Test: Gym App Viva Step 1 — AJAX save session
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import json

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina


class TestGymAJAXSave(TestCase):
    """Gym AJAX: Session saves return JSON without reload"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

    def test_guardar_entrenamiento_activo_ajax_returns_json(self):
        """POST con X-Requested-With header retorna JSON"""
        self.client.login(username='testuser', password='pass123')

        # Prepare minimal session data
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')

        response = self.client.post(
            f'/entrenos/cliente/{self.cliente.id}/guardar-entrenamiento-activo/',
            data={
                'fecha': str(self.hoy),
                'rutina_nombre': 'Test Routine',
                'duracion_minutos_real': '60',
                'calorias_quemadas': '500',
                'rpe_global_sesion': '7',
                'ejercicio_1_nombre': 'Bench Press',
                'ejercicio_1_peso_1': '100',
                'ejercicio_1_reps_1': '8',
                'ejercicio_1_rpe_1': '7',
                'ejercicio_1_tecnica_1': 'buena',
                'ejercicio_1_tipo_progresion': 'peso_reps',
                'ejercicio_1_es_principal': '1',
                'series_completadas': '1',
                'series_totales': '1',
                'ejercicios_completados': '1',
                'ejercicios_totales': '1',
                'volumen_total_sesion': '800',
                'rpe_medio_sesion': '7',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        # 1. Response is JSON
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # 2. Response contains required fields
        self.assertIn('entreno_id', data)
        self.assertIn('rpe_final', data)
        self.assertIn('volumen', data)
        self.assertIn('refresh_joi', data)
        self.assertTrue(data['refresh_joi'])

        # 3. Session was created in DB
        entreno = EntrenoRealizado.objects.get(id=data['entreno_id'])
        self.assertEqual(entreno.cliente, self.cliente)
        self.assertEqual(entreno.fecha, self.hoy)

    def test_guardar_entrenamiento_sin_ajax_redirige(self):
        """POST sin AJAX header redirige como siempre"""
        self.client.login(username='testuser', password='pass123')

        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')

        response = self.client.post(
            f'/entrenos/cliente/{self.cliente.id}/guardar-entrenamiento-activo/',
            data={
                'fecha': str(self.hoy),
                'rutina_nombre': 'Test Routine',
                'duracion_minutos_real': '60',
                'calorias_quemadas': '500',
                'rpe_global_sesion': '7',
                'ejercicio_1_nombre': 'Bench Press',
                'ejercicio_1_peso_1': '100',
                'ejercicio_1_reps_1': '8',
                'ejercicio_1_rpe_1': '7',
                'ejercicio_1_tecnica_1': 'buena',
                'ejercicio_1_tipo_progresion': 'peso_reps',
                'ejercicio_1_es_principal': '1',
                'series_completadas': '1',
                'series_totales': '1',
                'ejercicios_completados': '1',
                'ejercicios_totales': '1',
                'volumen_total_sesion': '800',
                'rpe_medio_sesion': '7',
            },
            follow=False,
        )

        # Debería redirigir (código 302)
        self.assertEqual(response.status_code, 302)
        self.assertIn('cierre', response.url)  # Post-session summary URL
