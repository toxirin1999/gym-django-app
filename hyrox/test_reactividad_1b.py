"""
Tests Phase Reactividad 1B.

Verifican que:
- guardar_sesion_hyrox_service() encapsula correctamente el guardado de dominio
- construir_respuesta_sesion_guardada() genera payload JSON-friendly con consecuencias visibles
- El flujo HTML (registrar_entrenamiento) sigue haciendo redirect exactamente igual
- El endpoint AJAX (api_guardar_sesion) devuelve JsonResponse con el payload correcto
- Bio-safety revierte la sesión a 'planificado' y retorna success=False
- Un motor que falla individualmente no cancela el guardado (warning, no exception)
- HTML y AJAX comparten la misma función de dominio (arquitectura unificada)
"""

import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from hyrox.models import HyroxObjective, HyroxSession, HyroxActivity, UserInjury


def _make_user(username='rb1b_tester'):
    user, _ = User.objects.get_or_create(username=username)
    user.set_password('testpass')
    user.save()
    return user


def _make_objetivo(user):
    cliente = user.cliente_perfil
    return HyroxObjective.objects.create(
        cliente=cliente,
        fecha_evento=datetime.date(2027, 4, 1),
    )


def _make_sesion(objetivo, titulo='Sesión test'):
    return HyroxSession.objects.create(
        objective=objetivo,
        fecha=datetime.date.today(),
        estado='planificado',
        titulo=titulo,
    )


class GuardarSesionHyroxServiceTest(TestCase):
    """Tests del servicio de dominio guardar_sesion_hyrox_service()."""

    def setUp(self):
        self.user = _make_user('rb1b_service')
        self.objetivo = _make_objetivo(self.user)
        self.sesion = _make_sesion(self.objetivo)

    def test_guardado_normal_retorna_success(self):
        """Guardado sin notas ni lesión → success=True, estado='completado'."""
        from hyrox.services import guardar_sesion_hyrox_service

        form_data = {'notas_raw': '', 'sustituir_material': False}
        resultado = guardar_sesion_hyrox_service(self.objetivo, self.sesion, form_data)

        self.assertTrue(resultado['success'])
        self.assertIsNone(resultado['error'])
        self.assertEqual(resultado['sesion_id'], self.sesion.id)

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, 'completado')

    def test_bio_safety_bloquea_y_revierte(self):
        """Si hay lesión activa con tags que colisionan, retorna success=False y estado='planificado'."""
        from hyrox.services import guardar_sesion_hyrox_service

        lesion = UserInjury.objects.create(
            cliente=self.objetivo.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=['impacto_vertical'],
        )
        HyroxActivity.objects.create(
            sesion=self.sesion,
            tipo_actividad='carrera',
            nombre_ejercicio='carrera 1km',
            data_metricas={},
        )

        form_data = {'notas_raw': '', 'sustituir_material': False}
        resultado = guardar_sesion_hyrox_service(self.objetivo, self.sesion, form_data)

        self.assertFalse(resultado['success'])
        self.assertIn('AGUDA', resultado['error'])

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, 'planificado',
                         "Bio-safety debe revertir el estado a 'planificado'")

    def test_motor_falla_no_cancela_sesion(self):
        """Si un motor post-guardado lanza excepción, la sesión queda completada con warning."""
        from hyrox.services import guardar_sesion_hyrox_service

        form_data = {'notas_raw': '', 'sustituir_material': False}

        with patch('hyrox.training_engine.HyroxTrainingEngine.scale_volume_by_energy',
                   side_effect=RuntimeError('fallo simulado')):
            resultado = guardar_sesion_hyrox_service(self.objetivo, self.sesion, form_data)

        self.assertTrue(resultado['success'],
                        "El fallo de un motor accesorio no debe cancelar el guardado")
        self.assertTrue(
            any('motor_scale_volume_failed' in w for w in resultado['warnings']),
            f"Debe aparecer warning del motor. Warnings: {resultado['warnings']}"
        )
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, 'completado')


class ConstruirRespuestaSesionTest(TestCase):
    """Tests de construir_respuesta_sesion_guardada() — payload JSON-friendly."""

    def setUp(self):
        self.user = _make_user('rb1b_payload')
        self.objetivo = _make_objetivo(self.user)
        self.sesion = _make_sesion(self.objetivo)
        self.sesion.estado = 'completado'
        self.sesion.save()

    def test_payload_contiene_campos_json_visibles(self):
        """El payload debe contener readiness_score, hyrox_decision, sesiones_proximas y messages."""
        from hyrox.services import construir_respuesta_sesion_guardada

        resultado_dominio = {
            'success': True,
            'error': None,
            'sesion_id': self.sesion.id,
            'readiness_score_antes': 70,
            'eventos': ['rm_updated'],
            'warnings': [],
            'messages': [{'level': 'success', 'text': 'RM actualizado'}],
        }

        payload = construir_respuesta_sesion_guardada(self.objetivo, self.sesion, resultado_dominio)

        self.assertIn('readiness_score', payload)
        self.assertIn('hyrox_decision', payload)
        self.assertIn('sesiones_proximas', payload)
        self.assertIn('messages', payload)
        self.assertIn('success', payload)
        # Los campos de hyrox_decision deben ser serializables (no objetos Django)
        decision = payload['hyrox_decision']
        self.assertIn('estado', decision)
        self.assertIn('puede_ejecutar_plan', decision)


class ArquitecturaUnificadaTest(TestCase):
    """
    Test de arquitectura: HTML y AJAX deben usar la misma función de dominio.
    Verifica que guardar_sesion_hyrox_service es el punto único de lógica.
    """

    def setUp(self):
        self.user = _make_user('rb1b_arq')
        self.objetivo = _make_objetivo(self.user)

    def test_html_y_ajax_llaman_mismo_servicio(self):
        """
        Ambos flujos deben importar guardar_sesion_hyrox_service desde hyrox.services.
        Si el import falla, la arquitectura está rota.
        """
        from hyrox.services import guardar_sesion_hyrox_service, construir_respuesta_sesion_guardada
        import inspect

        # El servicio debe existir y ser callable
        self.assertTrue(callable(guardar_sesion_hyrox_service))
        self.assertTrue(callable(construir_respuesta_sesion_guardada))

        # Verificar que registrar_entrenamiento llama al servicio (lo importa desde services)
        import hyrox.views as views_module
        source = inspect.getsource(views_module.registrar_entrenamiento)
        self.assertIn('guardar_sesion_hyrox_service', source,
                      "registrar_entrenamiento debe delegar en guardar_sesion_hyrox_service")

        # Verificar que api_guardar_sesion también lo llama
        source_api = inspect.getsource(views_module.api_guardar_sesion)
        self.assertIn('guardar_sesion_hyrox_service', source_api,
                      "api_guardar_sesion debe delegar en guardar_sesion_hyrox_service")


class FlujoHTMLFallbackTest(TransactionTestCase):
    """
    El flujo HTML tradicional debe seguir haciendo redirect al dashboard.
    Usa TransactionTestCase para que el TestClient pueda ver los datos
    creados en setUp (los TestCase normales usan savepoints invisibles para
    otras conexiones).
    """

    def setUp(self):
        self.user = _make_user('rb1b_html')
        self.client = Client()
        self.client.login(username='rb1b_html', password='testpass')
        self.objetivo = _make_objetivo(self.user)
        self.sesion = _make_sesion(self.objetivo)

    def test_post_html_redirige_al_dashboard(self):
        """POST a registrar_entrenamiento debe redirigir a hyrox:dashboard."""
        url = reverse('hyrox:registrar_entrenamiento_session',
                      kwargs={'objective_id': self.objetivo.id, 'session_id': self.sesion.id})

        response = self.client.post(url, {
            'notas_raw': '',
            'sustituir_material': False,
            'energia_pre': 7,
        })

        self.assertRedirects(response, reverse('hyrox:dashboard'),
                             msg_prefix="El flujo HTML debe redirigir al dashboard tras guardar")


class EndpointAJAXJsonResponseTest(TransactionTestCase):
    """
    El endpoint AJAX debe retornar JsonResponse con el payload correcto.
    Usa TransactionTestCase para que el TestClient pueda ver los objetos del setUp.
    """

    def setUp(self):
        self.user = _make_user('rb1b_ajax')
        self.client = Client()
        self.client.login(username='rb1b_ajax', password='testpass')
        self.objetivo = _make_objetivo(self.user)
        self.sesion = _make_sesion(self.objetivo)

    def test_ajax_retorna_json_con_readiness_score(self):
        """POST al endpoint AJAX debe retornar JSON con success=True y readiness_score."""
        url = reverse('hyrox:api_guardar_sesion',
                      kwargs={'objective_id': self.objetivo.id, 'session_id': self.sesion.id})

        response = self.client.post(url, {
            'notas_raw': '',
            'sustituir_material': False,
            'energia_pre': 7,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = response.json()
        self.assertTrue(data.get('success'), f"Respuesta AJAX inesperada: {data}")
        self.assertIn('readiness_score', data)
        self.assertIn('hyrox_decision', data)
        self.assertIn('sesiones_proximas', data)
        self.assertIn('messages', data)

    def test_ajax_endpoint_devuelve_json_no_redirect(self):
        """
        El endpoint AJAX debe devolver JSON (application/json), nunca un redirect HTML.
        Esto verifica que el endpoint está correctamente separado del flujo HTML.
        """
        url = reverse('hyrox:api_guardar_sesion',
                      kwargs={'objective_id': self.objetivo.id, 'session_id': self.sesion.id})

        response = self.client.post(url, {
            'notas_raw': '',
            'sustituir_material': False,
        })

        # No debe redirigir — debe retornar JSON
        self.assertNotEqual(response.status_code, 302,
                            "El endpoint AJAX no debe redirigir; debe retornar JSON")
        self.assertIn('application/json', response.get('Content-Type', ''),
                      "El endpoint AJAX debe retornar Content-Type: application/json")
