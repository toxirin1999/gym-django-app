"""Historial con el estilo de la app y lo último arriba (15-oct-2026)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ActividadRealizada


class TimelineEstiloTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="historial-estilo", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def test_lo_mas_reciente_arriba_y_barra_de_la_app(self):
        hoy = timezone.localdate()
        for dias, titulo in ((10, 'Sesión antigua'), (1, 'Sesión de ayer')):
            ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym', titulo=titulo,
                                              fecha=hoy - timedelta(days=dias), duracion_minutos=60)
        r = self.client.get(reverse('entrenos:timeline_atleta', args=[self.cliente.id]))
        html = r.content.decode()
        self.assertEqual(r.context['dias'][0]['fecha'], hoy)
        self.assertLess(html.index('Sesión de ayer'), html.index('Sesión antigua'))
        self.assertNotIn('TIMELINE.EXE', html)
        self.assertIn('bottom-nav-std', html)
        self.assertIn(reverse('clientes:memoria_entrenador', args=[self.cliente.id]), html)
