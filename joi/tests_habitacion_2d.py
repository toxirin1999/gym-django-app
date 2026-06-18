"""
Tests for Phase JOI Habitación 2D — Feedback sobre encaje del estado.

Verifica que el feedback de encaje se registra sin modificar la lógica de estados.
6 tests: crear, validar, evitar duplicados, no modificar estado, autenticación.
"""

import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from joi.models import EstadoFeedback
from joi.services import determinar_estado_habitacion_joi


class JoiHabitacion2DFeedbackTests(TestCase):
    """Tests para feedback_estado_encaje()"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil

    def tearDown(self):
        User.objects.all().delete()
        EstadoFeedback.objects.all().delete()

    # Test 1: Crear feedback "encaja"
    def test_crear_feedback_encaja(self):
        """POST con feedback='encaja' crea EstadoFeedback"""
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'SILENCIO',
                'motivo': 'sin_senales',
                'feedback': 'encaja'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['saved'])

        # Verificar que se guardó
        hoy = timezone.now().date()
        obj = EstadoFeedback.objects.get(
            usuario=self.user,
            fecha=hoy,
            estado='SILENCIO',
            motivo='sin_senales'
        )
        self.assertEqual(obj.feedback, 'encaja')

    # Test 2: Crear feedback "no_encaja"
    def test_crear_feedback_no_encaja(self):
        """POST con feedback='no_encaja' crea EstadoFeedback"""
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'OBSERVANDO',
                'motivo': 'diario_hoy_sin_lectura',
                'feedback': 'no_encaja'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])

        hoy = timezone.now().date()
        obj = EstadoFeedback.objects.get(
            usuario=self.user,
            fecha=hoy,
            estado='OBSERVANDO'
        )
        self.assertEqual(obj.feedback, 'no_encaja')

    # Test 3: Rechazar feedback inválido
    def test_rechazar_feedback_invalido(self):
        """POST con feedback inválido retorna error 400"""
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'PRESENTE',
                'motivo': 'mensaje_joi_hoy',
                'feedback': 'util'  # inválido
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'feedback_invalido')

    # Test 4: Upsert — actualizar feedback existente
    def test_upsert_feedback_existente(self):
        """Si ya existe feedback para usuario/fecha/estado/motivo, actualiza"""
        hoy = timezone.now().date()
        EstadoFeedback.objects.create(
            usuario=self.user,
            fecha=hoy,
            estado='PROTEGIENDO',
            motivo='rpe_extremo',
            feedback='encaja'
        )

        self.client.login(username='testuser', password='pass123')

        # Cambiar feedback de "encaja" a "no_encaja"
        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'PROTEGIENDO',
                'motivo': 'rpe_extremo',
                'feedback': 'no_encaja'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verificar que solo existe UNO, con feedback actualizado
        feedbacks = EstadoFeedback.objects.filter(
            usuario=self.user,
            fecha=hoy,
            estado='PROTEGIENDO'
        )
        self.assertEqual(feedbacks.count(), 1)
        self.assertEqual(feedbacks.first().feedback, 'no_encaja')

    # Test 5: No modifica determinar_estado_habitacion_joi()
    def test_feedback_no_modifica_estado(self):
        """Registrar feedback no cambia el estado actual"""
        self.client.login(username='testuser', password='pass123')

        # Estado actual debe ser SILENCIO (sin señales)
        estado_antes, motivo_antes = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado_antes, 'SILENCIO')

        # Registrar feedback diciendo que no encaja
        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'SILENCIO',
                'motivo': 'sin_senales',
                'feedback': 'no_encaja'
            }),
            content_type='application/json'
        )
        self.assertTrue(response.json()['ok'])

        # Estado sigue siendo el mismo
        estado_despues, motivo_despues = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado_despues, 'SILENCIO')
        self.assertEqual(estado_antes, estado_despues)

    # Test 6: Endpoint requiere autenticación
    def test_feedback_requiere_autenticacion(self):
        """GET anónimo al endpoint retorna 403 (login_required)"""
        # Sin login
        response = self.client.post(
            '/joi/api/feedback-estado/',
            data=json.dumps({
                'estado': 'SILENCIO',
                'motivo': 'sin_senales',
                'feedback': 'encaja'
            }),
            content_type='application/json'
        )

        # Redirecciona a login (302) o deniega acceso (403)
        self.assertIn(response.status_code, [302, 403])
