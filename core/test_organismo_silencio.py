"""SILENCIO no es una orden de descanso.

SILENCIO solo significa que el Organismo no tiene una acción que pedir. Puede
ser un descanso del plan, una sesión ya hecha o simplemente que algo falló o no
hay datos. Solo el primero se muestra como DESCANSAR.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from core.organismo import estado_operativo_visible, resolver_estado_sistema_hoy


class EstadoVisibleTests(TestCase):
    def test_solo_el_descanso_del_plan_es_descansar(self):
        self.assertEqual(estado_operativo_visible('SILENCIO', 'descanso_planificado'), 'DESCANSAR')

    def test_sesion_hecha_no_es_descansar(self):
        self.assertEqual(estado_operativo_visible('SILENCIO', 'sesion_completada'), 'HECHO')

    def test_sin_motivo_o_con_fallo_es_ajustar(self):
        self.assertEqual(estado_operativo_visible('SILENCIO'), 'AJUSTAR')
        self.assertEqual(estado_operativo_visible('SILENCIO', 'sin_lectura'), 'AJUSTAR')

    def test_resto_de_estados_sin_cambios(self):
        self.assertEqual(estado_operativo_visible('EN_MARGEN'), 'ENTRENAR')
        self.assertEqual(estado_operativo_visible('PROTEGIENDO'), 'RECUPERAR')
        self.assertEqual(estado_operativo_visible('OBSERVANDO'), 'AJUSTAR')
        self.assertEqual(estado_operativo_visible('HECHO'), 'HECHO')


@patch('core.organismo._check_observando', return_value=None)
@patch('core.organismo._check_protegiendo', return_value=None)
class ResolverSilencioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='silencio', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_dia_de_descanso(self, *_):
        estado = resolver_estado_sistema_hoy(self.user, decision_gym={'estado': 'descanso'})
        self.assertEqual(estado['estado'], 'SILENCIO')
        self.assertEqual(estado['motivo'], 'descanso_planificado')

    def test_sesion_de_hoy_ya_hecha(self, *_):
        from entrenos.models import EntrenoRealizado
        from rutinas.models import Rutina
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='Día 1'),
            fecha=date(2026, 10, 8), fecha_ejecucion=timezone.localdate(),
        )
        decision = {'estado': 'entrenar', 'entrenamiento': {'ejercicios': [{'nombre': 'Press'}]}}
        estado = resolver_estado_sistema_hoy(self.user, decision_gym=decision)
        self.assertEqual(estado['estado'], 'SILENCIO')
        self.assertEqual(estado['motivo'], 'sesion_completada')
        self.assertIn('hecha', estado['texto'])

    def test_sin_sesion_clara_no_dice_descansar(self, *_):
        estado = resolver_estado_sistema_hoy(self.user, decision_gym={'estado': 'entrenar', 'entrenamiento': {}})
        self.assertEqual(estado['motivo'], 'sin_lectura')
        self.assertEqual(estado_operativo_visible(estado['estado'], estado['motivo']), 'AJUSTAR')

    def test_un_fallo_no_se_convierte_en_descanso(self, protegiendo, _):
        protegiendo.side_effect = RuntimeError('boom')
        estado = resolver_estado_sistema_hoy(self.user, decision_gym={'estado': 'descanso'})
        self.assertEqual(estado['motivo'], 'sin_lectura')
        self.assertEqual(estado_operativo_visible(estado['estado'], estado['motivo']), 'AJUSTAR')


class PortadaSilencioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='portada-silencio', password='x')
        self.url = reverse('clientes:dashboard_silencioso_preview')
        self.ctx = {
            '_decision_gym_raw': {}, 'proximo_entrenamiento': {},
            'explicacion_decision': {}, 'acwr_actual': None,
        }
        self.client.force_login(self.user)

    def test_sesion_hecha_muestra_hecho_y_lleva_a_movilidad(self):
        with patch('clientes.views._get_dashboard_context_data', return_value=self.ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', return_value={
                    'estado': 'SILENCIO', 'motivo': 'sesion_completada',
                    'texto': 'La sesión de hoy ya está hecha.', 'accion_label': None, 'accion_url': None,
                }):
            response = self.client.get(self.url)
        decision = response.context['quiet_decision']
        self.assertEqual(decision['estado'], 'HECHO')
        self.assertEqual(decision['cta_url'], reverse('estiramientos:panel'))

    def test_fallo_del_organismo_no_muestra_descansar(self):
        with patch('clientes.views._get_dashboard_context_data', return_value=self.ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', side_effect=RuntimeError('boom')):
            response = self.client.get(self.url)
        self.assertEqual(response.context['quiet_decision']['estado'], 'AJUSTAR')
        self.assertNotContains(response, 'DESCANSAR')

    def test_memoria_usa_el_mismo_criterio(self):
        cliente = Cliente.objects.get(user=self.user)
        with patch('core.organismo.resolver_estado_sistema_hoy', return_value={
            'estado': 'SILENCIO', 'motivo': 'sin_lectura', 'texto': 'x',
        }):
            response = self.client.get(reverse('clientes:memoria_entrenador', args=[cliente.id]))
        self.assertEqual(response.context['decision_hoy']['estado'], 'AJUSTAR')
