"""
Test: Gym App Viva Step 3 — JOI Reacts to High RPE
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
import json

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionEntrenamiento
from rutinas.models import Rutina
from joi.services import determinar_estado_habitacion_joi


class TestGymJOIReactivity(TestCase):
    """JOI reacts to high RPE Gym sessions"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

    def test_joi_detects_high_rpe_gym_session(self):
        """JOI state becomes PROTEGIENDO when Gym RPE >= 8"""
        # Create Gym session with high RPE (8.5)
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=10000,
        )
        
        # Create sesion_detalle with high RPE
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 8.5}
        )
        sesion.rpe_medio = 8.5
        sesion.save()

        # Determine JOI state
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        
        # Verify JOI reacts
        self.assertEqual(estado, 'PROTEGIENDO')
        self.assertEqual(motivo, 'rpe_extremo')

    def test_joi_normal_rpe_gym_session_stays_silent(self):
        """JOI stays SILENCIO when Gym RPE < 8"""
        # Create Gym session with normal RPE (7.0)
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=6000,
        )
        
        # Create sesion_detalle with normal RPE
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 7.0}
        )
        sesion.rpe_medio = 7.0
        sesion.save()

        # Determine JOI state
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        
        # JOI should be SILENCIO (no signal)
        self.assertEqual(estado, 'SILENCIO')
        self.assertEqual(motivo, 'sin_senales')

    def test_joi_api_endpoint_returns_protegiendo_on_high_rpe(self):
        """GET /joi/api/pulso-actual/ returns PROTEGIENDO when RPE >= 8"""
        self.client.login(username='testuser', password='pass123')

        # Create high RPE session
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=12000,
        )
        
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 8.8}
        )
        sesion.rpe_medio = 8.8
        sesion.save()

        # Call JOI API
        response = self.client.get('/joi/api/pulso-actual/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['estado'], 'PROTEGIENDO')
        self.assertEqual(data['motivo'], 'rpe_extremo')
        self.assertIn('texto_motivo', data)

    def test_joi_signal_invalidates_cache_on_high_rpe(self):
        """Signal automatically invalidates JOI cache on high RPE Gym save"""
        # Create high RPE session (triggers signal)
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=11000,
        )
        
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 8.2}
        )
        sesion.rpe_medio = 8.2
        sesion.save()

        # Verify state changed
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')
        self.assertEqual(motivo, 'rpe_extremo')
