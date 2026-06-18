"""
Test: Gym App Viva Step 2 — Dashboard detects session completion
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionEntrenamiento
from rutinas.models import Rutina


class TestGymDashboardSessionDetection(TestCase):
    """Dashboard shows session completed today, hides start button"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

    def test_dashboard_shows_session_completed_today(self):
        """Dashboard shows ✓ Sesión Completada when session saved today"""
        self.client.login(username='testuser', password='pass123')

        # Create session today
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=8000,
        )
        
        # Update or create sesion_detalle with rpe_medio = 7.0
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 7.0}
        )
        sesion.rpe_medio = 7.0
        sesion.save()

        # Dashboard now shows session completed
        response = self.client.get('/mi-panel/blade-runner/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SESIÓN COMPLETADA')
        self.assertContains(response, '✓')

    def test_dashboard_shows_high_rpe_badge(self):
        """Dashboard shows RPE badge when RPE >= 8"""
        self.client.login(username='testuser', password='pass123')

        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=10000,
        )
        
        # High RPE session (8.5)
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 8.5}
        )
        sesion.rpe_medio = 8.5
        sesion.save()

        response = self.client.get('/mi-panel/blade-runner/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SESIÓN COMPLETADA')
        self.assertContains(response, 'RPE')
        self.assertContains(response, 'ALTO')

    def test_dashboard_no_high_rpe_badge_when_rpe_below_8(self):
        """Dashboard doesn't show RPE badge when RPE < 8"""
        self.client.login(username='testuser', password='pass123')

        rutina, _ = Rutina.objects.get_or_create(nombre='Test Routine')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=self.hoy,
            duracion_minutos=60,
            volumen_total_kg=6000,
        )
        
        # Normal RPE session (7.0)
        sesion, _ = SesionEntrenamiento.objects.get_or_create(
            entreno=entreno,
            defaults={'duracion_minutos': 60, 'rpe_medio': 7.0}
        )
        sesion.rpe_medio = 7.0
        sesion.save()

        response = self.client.get('/mi-panel/blade-runner/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SESIÓN COMPLETADA')
        # Should NOT contain "ALTO" badge (RPE < 8)
        content = response.content.decode()
        # Check that "RPE" + "ALTO" combination is NOT present for this low RPE
        import re
        # Count occurrences of ALTO badge pattern
        alto_badge_count = len(re.findall(r'RPE.*ALTO', content, re.IGNORECASE))
        self.assertEqual(alto_badge_count, 0, f"Should not show ALTO badge when RPE < 8. Found: {alto_badge_count}")
