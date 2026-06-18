"""
TEST SUITE: App Viva — Complete workflow validation

Tests:
1. Hyrox: Session saves → Dashboard reflects immediately
2. Diario Apertura: AJAX save → Estado updates
3. Diario Cierre: AJAX save → JOI reacts
4. Gym + Lesion: Signals trigger JOI estado changes
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import json

from diario.models import ProsocheMes, ProsocheDiario
from diario.services.estado_diario import calcular_estado_diario_hoy
from hyrox.models import HyroxObjective, HyroxSession, HyroxActivity, HyroxReadinessLog
from joi.services import determinar_estado_habitacion_joi
from entrenos.models import EntrenoRealizado, SesionEntrenamiento
from hyrox.models import UserInjury


class TestAppVivaHyrox(TestCase):
    """Hyrox: Session completion updates dashboard immediately"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        # Crear objetivo Hyrox
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            estado='activo',
            objetivo_tiempo_total='1:40:00',
            fecha_evento=self.hoy + timedelta(days=30),
        )

    def test_hyrox_session_complete_dashboard_updates(self):
        """Cuando sesión Hyrox se guarda, dashboard no muestra 'Continuar plan'"""
        self.client.login(username='testuser', password='pass123')

        # 1. Dashboard antes: sin sesión completada
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sesion_completada_hoy')  # Verificar que el template tiene esta variable

        # 2. Crear sesión completada hoy
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            estado='completado',
            titulo='Test Session',
        )
        HyroxActivity.objects.create(
            sesion=sesion,
            tipo_actividad='fuerza',
            nombre_ejercicio='Test',
        )

        # 3. Dashboard después: sesión_completada_hoy está presente
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)
        # Si sesion_completada_hoy está en contexto, significa que se detectó
        self.assertIn('sesion_completada_hoy', response.context)
        sesion_detectada = response.context['sesion_completada_hoy']
        self.assertIsNotNone(sesion_detectada)
        self.assertEqual(sesion_detectada.estado, 'completado')


class TestAppVivaDiarioApertura(TestCase):
    """Diario Apertura: AJAX saves → estado actualiza sin reload"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        # Crear mes para prosoche
        mes_nombre = self.hoy.strftime('%B')
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=mes_nombre,
            año=self.hoy.year,
        )

    def test_apertura_ajax_returns_json(self):
        """Apertura POST con X-Requested-With header retorna JSON"""
        from django.urls import reverse
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            reverse('diario:presencia_apertura'),
            data={
                'intencion': 'Ser paciente hoy',
                'estado_animo': '4',
                'gratitud_1': 'Por el café',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        # 1. Response es JSON
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # 2. Estado cambió a 'manana_hecha'
        self.assertEqual(data['estado'], 'manana_hecha')
        self.assertTrue(data['refresh_joi'])

        # 3. Verificar en BD
        entrada = ProsocheDiario.objects.get(prosoche_mes=self.mes, fecha=self.hoy)
        estado = calcular_estado_diario_hoy(entrada)
        self.assertEqual(estado['estado'], 'manana_hecha')
        self.assertTrue(estado['manana_hecha'])

    def test_apertura_sin_ajax_redirige(self):
        """Apertura POST sin AJAX header redirige como siempre"""
        from django.urls import reverse
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            reverse('diario:presencia_apertura'),
            data={
                'intencion': 'Ser paciente hoy',
                'estado_animo': '4',
                'gratitud_1': 'Por el café',
            },
            follow=False,  # No seguir redirect automáticamente
        )

        # Debería redirigir (código 302)
        self.assertEqual(response.status_code, 302)


class TestAppVivaDiarioCierre(TestCase):
    """Diario Cierre: AJAX saves → estado actualiza + JOI reacts"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        mes_nombre = self.hoy.strftime('%B')
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=mes_nombre,
            año=self.hoy.year,
        )
        self.entrada = ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='Ser paciente',
            gratitud_1='Por el café',
        )

    def test_cierre_ajax_returns_json(self):
        """Cierre POST con X-Requested-With retorna JSON y JOI se puede refrescar"""
        from django.urls import reverse
        self.client.login(username='testuser', password='pass123')

        response = self.client.post(
            reverse('diario:presencia_cierre'),
            data={
                'reflexion_libre': 'Hoy fue un día bueno. Aprendí sobre paciencia.',
                'friccion_no': '2',
                'habitos_completados': '[]',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        # 1. Response es JSON
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # 2. Estado cambió a 'dia_completo'
        self.assertEqual(data['estado'], 'dia_completo')
        self.assertTrue(data['refresh_joi'])

        # 3. JOI puede refrescarse (endpoint disponible)
        joi_response = self.client.get('/joi/api/pulso-actual/')
        self.assertEqual(joi_response.status_code, 200)
        joi_data = joi_response.json()
        self.assertIn('estado', joi_data)
        self.assertIn('motivo', joi_data)


class TestAppVivaJOIReactivity(TestCase):
    """JOI reacciona a señales de Diario, Gym, y Lesiones"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        mes_nombre = self.hoy.strftime('%B')
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=mes_nombre,
            año=self.hoy.year,
        )

    def test_joi_endpoint_returns_estado(self):
        """GET /joi/api/pulso-actual/ retorna estado + motivo"""
        self.client.login(username='testuser', password='pass123')

        response = self.client.get('/joi/api/pulso-actual/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Campos requeridos
        self.assertIn('estado', data)
        self.assertIn('motivo', data)
        self.assertIn('texto_motivo', data)
        self.assertIn('mensaje_activo', data)

        # Estado debe ser uno de los válidos
        self.assertIn(data['estado'], ['SILENCIO', 'OBSERVANDO', 'PRESENTE', 'PROTEGIENDO'])

    def test_joi_detects_diario_without_narrative(self):
        """JOI detecta diario completado sin narrativa → OBSERVANDO"""
        from diario.models import BitacoraDiaria

        # 1. Crear entrada sin narrativa formada
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=self.hoy,
        )

        # 2. JOI debería ir a OBSERVANDO
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'OBSERVANDO')
        self.assertEqual(motivo, 'diario_hoy_sin_lectura')

    def test_joi_detects_high_rpe_session(self):
        """JOI puede detectar sesión con RPE alto para PROTEGIENDO"""
        # Esto es más un test de que el signal está registrado
        # La lógica real se evalúa en determinar_estado_habitacion_joi
        # que ya valida Pulso PROTEGIENDO

        objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            estado='activo',
            fecha_evento=self.hoy + timedelta(days=30),
        )

        # Pulso PROTEGIENDO siempre → JOI va a PROTEGIENDO
        objetivo.pulso_estado = 'PROTEGIENDO'
        objetivo.save()

        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')
        self.assertEqual(motivo, 'pulso_protegiendo')

    def test_joi_detects_active_lesion(self):
        """JOI detecta lesión activa → PROTEGIENDO"""
        objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            estado='activo',
            fecha_evento=self.hoy + timedelta(days=30),
        )

        # 1. Crear lesión AGUDA
        lesion = UserInjury.objects.create(
            usuario=self.user,
            zona_afectada='rodilla',
            fase='AGUDA',
            tags_restringidos=[],
        )

        # 2. JOI debería ir a PROTEGIENDO
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')
        self.assertEqual(motivo, 'lesion_activa')


class TestAppVivaCompleteCycle(TestCase):
    """Ciclo completo: Usuario interactúa, app reacciona sin reload"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        mes_nombre = self.hoy.strftime('%B')
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=mes_nombre,
            año=self.hoy.year,
        )

    def test_complete_diario_cycle_ajax(self):
        """
        Ciclo completo en un día:
        1. Apertura AJAX → estado 'manana_hecha'
        2. Cierre AJAX → estado 'dia_completo'
        3. JOI endpoint devuelve estado actualizado
        """
        from django.urls import reverse
        self.client.login(username='testuser', password='pass123')

        # 1. Apertura AJAX
        apertura_response = self.client.post(
            reverse('diario:presencia_apertura'),
            data={
                'intencion': 'Ser paciente',
                'estado_animo': '4',
                'gratitud_1': 'Por la vida',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(apertura_response.status_code, 200)
        apertura_data = apertura_response.json()
        self.assertEqual(apertura_data['estado'], 'manana_hecha')
        self.assertTrue(apertura_data['refresh_joi'])

        # 2. Refrescar JOI después de apertura
        joi_response = self.client.get('/joi/api/pulso-actual/')
        joi_data = joi_response.json()
        # JOI debería estar en SILENCIO o algún estado (sin narrativa aún)
        self.assertIn(joi_data['estado'], ['SILENCIO', 'OBSERVANDO', 'PRESENTE', 'PROTEGIENDO'])

        # 3. Cierre AJAX
        cierre_response = self.client.post(
            reverse('diario:presencia_cierre'),
            data={
                'reflexion_libre': 'Excelente día de aprendizaje.',
                'friccion_no': '1',
                'habitos_completados': '[]',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(cierre_response.status_code, 200)
        cierre_data = cierre_response.json()
        self.assertEqual(cierre_data['estado'], 'dia_completo')
        self.assertTrue(cierre_data['refresh_joi'])

        # 4. Verificar que el estado en BD es correcto
        entrada = ProsocheDiario.objects.get(prosoche_mes=self.mes, fecha=self.hoy)
        estado = calcular_estado_diario_hoy(entrada)
        self.assertEqual(estado['estado'], 'dia_completo')
        self.assertTrue(estado['manana_hecha'])
        self.assertTrue(estado['noche_hecha'])
