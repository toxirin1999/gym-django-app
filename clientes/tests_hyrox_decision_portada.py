from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from hyrox.models import HyroxObjective


class HyroxDecisionPortadaAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('portada_hyrox', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=date.today() + timedelta(days=90),
            estado='activo',
        )
        self.client.force_login(self.user)

    def _get(self, decision=None, error=None):
        kwargs = {'side_effect': error} if error else {'return_value': decision}
        with patch('hyrox.decision_service.calcular_hyrox_decision', **kwargs) as autoridad:
            response = self.client.get(reverse('clientes:mockup_demo'))
        return response, autoridad

    def test_portada_inyecta_la_decision_soberana_existente(self):
        decision = {
            'estado': 'empujar', 'causa': 'normal', 'titulo': 'Empujar',
            'subtitulo': 'Señales favorables', 'mensaje': 'Ejecuta con intención.',
            'accion_label': 'Ejecutar plan', 'puede_ejecutar_plan': True,
            'permitido': ['Sesión planificada'], 'evitar': [],
        }

        response, autoridad = self._get(decision=decision)

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['hyrox_decision'], decision)
        autoridad.assert_called_once()
        self.assertContains(response, 'Ejecutar Hyrox')

    def test_bloqueo_soberano_muestra_proteccion_y_no_cta_de_ejecucion(self):
        decision = {
            'estado': 'recuperar', 'causa': 'fatiga', 'titulo': 'Recuperar',
            'subtitulo': 'Fatiga acumulada alta',
            'mensaje': 'La carga reciente pesa demasiado.',
            'accion_label': 'Recuperación activa', 'puede_ejecutar_plan': False,
            'permitido': ['Zona 2 suave', 'Movilidad'],
            'evitar': ['Series duras', 'Trabajo al fallo'],
        }

        response, _ = self._get(decision=decision)
        html = response.content.decode()
        inicio = html.index('id="rbHyroxContent"')
        fin = html.index('<!-- ── DIARIO', inicio)
        card_hyrox = html[inicio:fin]

        self.assertIn('Fatiga acumulada alta', card_hyrox)
        self.assertIn('Series duras', card_hyrox)
        self.assertIn('recuperación', card_hyrox.lower())
        self.assertNotIn('Ejecutar Hyrox', card_hyrox)
        self.assertNotIn('fas fa-bolt', card_hyrox)

    def test_fallo_de_autoridad_degrada_a_protegido_sin_optimo_ni_ejecucion(self):
        response, _ = self._get(error=RuntimeError('motor no disponible'))

        self.assertEqual(response.status_code, 200)
        decision = response.context['hyrox_decision']
        self.assertFalse(decision['puede_ejecutar_plan'])
        self.assertEqual(decision['causa'], 'autoridad_no_disponible')
        html = response.content.decode()
        inicio = html.index('id="rbHyroxContent"')
        fin = html.index('<!-- ── DIARIO', inicio)
        card_hyrox = html[inicio:fin]
        self.assertIn('Decisión no disponible', card_hyrox)
        self.assertNotIn('Óptimo', card_hyrox)
        self.assertNotIn('Ejecutar Hyrox', card_hyrox)
