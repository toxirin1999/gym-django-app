"""
Phase Continuidad 1.4 (Centro) — el Centro de decisiones muestra la pausa.

plan_decisiones_view expone 'continuidad' solo cuando hay pausa significativa,
para que el motivo (fuente única) sea visible también ahí.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ActividadRealizada


class TestCentroContinuidad(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_centro14', password='testpass')
        self.cliente = Cliente.objects.get(user=self.user)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _get(self):
        c = Client()
        c.login(username='tester_centro14', password='testpass')
        return c.get(reverse('clientes:plan_decisiones'))

    def test_sin_pausa_no_hay_continuidad(self):
        hoy = timezone.now().date()
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym',
                                          fecha=hoy - timedelta(days=2))
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['continuidad'])

    def test_con_pausa_significativa_hay_continuidad(self):
        hoy = timezone.now().date()
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym',
                                          fecha=hoy - timedelta(days=8))
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        cont = resp.context['continuidad']
        self.assertIsNotNone(cont)
        self.assertEqual(cont['nivel'], 'clara')
        self.assertTrue(cont['hay_pausa_significativa'])
