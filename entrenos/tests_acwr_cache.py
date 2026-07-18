"""
ACWR self-caching — analizar_acwr_unificado es la única fuente de verdad del
caché (antes había 5 call sites, 2 con cache keys/TTL distintos y 3 sin
ningún caché, recomputando en cada request del dashboard).
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.services.services import EstadisticasService


class AcwrSelfCachingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('acwr_cache_user', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        cache.clear()

    def test_segunda_llamada_con_periodo_por_defecto_no_recalcula(self):
        with patch.object(
            EstadisticasService, '_analizar_acwr_unificado_calc',
            return_value={'acwr_actual': 1.0, 'dataframe': []},
        ) as mock_calc:
            EstadisticasService.analizar_acwr_unificado(self.cliente)
            EstadisticasService.analizar_acwr_unificado(self.cliente)
            self.assertEqual(mock_calc.call_count, 1, msg='La segunda llamada debe servirse desde caché.')

    def test_periodo_distinto_de_90_nunca_usa_cache(self):
        with patch.object(
            EstadisticasService, '_analizar_acwr_unificado_calc',
            return_value={'acwr_actual': 1.0, 'dataframe': []},
        ) as mock_calc:
            EstadisticasService.analizar_acwr_unificado(self.cliente, periodo_dias=30)
            EstadisticasService.analizar_acwr_unificado(self.cliente, periodo_dias=30)
            self.assertEqual(mock_calc.call_count, 2, msg='periodo_dias custom no debe compartir caché con el default.')

    def test_usa_la_misma_clave_que_las_señales_de_invalidacion(self):
        """Las señales en entrenos/signals.py, hyrox_bridge.py y views.py invalidan
        'dashboard_acwr_unificado_{id}' directamente — si esta clave cambia sin
        actualizar esos 4 sitios, el caché queda huérfano y nunca se invalida."""
        with patch.object(
            EstadisticasService, '_analizar_acwr_unificado_calc',
            return_value={'acwr_actual': 1.0, 'dataframe': []},
        ):
            EstadisticasService.analizar_acwr_unificado(self.cliente)
        self.assertIsNotNone(cache.get(f'dashboard_acwr_unificado_{self.cliente.id}'))

    def test_invalidar_la_clave_fuerza_recalculo(self):
        with patch.object(
            EstadisticasService, '_analizar_acwr_unificado_calc',
            return_value={'acwr_actual': 1.0, 'dataframe': []},
        ) as mock_calc:
            EstadisticasService.analizar_acwr_unificado(self.cliente)
            cache.delete(f'dashboard_acwr_unificado_{self.cliente.id}')
            EstadisticasService.analizar_acwr_unificado(self.cliente)
            self.assertEqual(mock_calc.call_count, 2)
