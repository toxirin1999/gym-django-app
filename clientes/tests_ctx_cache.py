"""
_cache_ctx — las 15 funciones _ctx_* del dashboard (distribución semanal,
candidata a preferencia, evaluación de intervención...) no tenían ningún
caché: cada una repetía su propia query en cada carga del dashboard.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from clientes.views import _cache_ctx


class CacheCtxDecoratorTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ctx_cache_user', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        cache.clear()

    def test_segunda_llamada_con_mismos_argumentos_no_recalcula(self):
        llamadas = []

        @_cache_ctx()
        def _fn(cliente, fecha_ref):
            llamadas.append(1)
            return 'resultado'

        _fn(self.cliente, date(2026, 7, 18))
        _fn(self.cliente, date(2026, 7, 18))
        self.assertEqual(len(llamadas), 1)

    def test_fecha_distinta_no_comparte_cache(self):
        llamadas = []

        @_cache_ctx()
        def _fn(cliente, fecha_ref):
            llamadas.append(1)
            return 'resultado'

        _fn(self.cliente, date(2026, 7, 18))
        _fn(self.cliente, date(2026, 7, 19))
        self.assertEqual(len(llamadas), 2)

    def test_resultado_none_se_sirve_desde_cache_sin_recalcular(self):
        """None es un resultado válido de varias _ctx_* — debe distinguirse de 'no cacheado'."""
        llamadas = []

        @_cache_ctx()
        def _fn(cliente, fecha_ref):
            llamadas.append(1)
            return None

        r1 = _fn(self.cliente, date(2026, 7, 18))
        r2 = _fn(self.cliente, date(2026, 7, 18))
        self.assertIsNone(r1)
        self.assertIsNone(r2)
        self.assertEqual(len(llamadas), 1)

    def test_funcion_de_un_solo_argumento_tambien_cachea(self):
        llamadas = []

        @_cache_ctx()
        def _fn(cliente):
            llamadas.append(1)
            return 'x'

        _fn(self.cliente)
        _fn(self.cliente)
        self.assertEqual(len(llamadas), 1)
