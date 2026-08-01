from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from diario.models import PersonaInterina


class SimbiosisEnPortadaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('simbiosis-portada')
        self.client.force_login(self.user)

    def test_una_primera_mencion_no_se_presenta_como_repeticion(self):
        PersonaInterina.objects.create(
            usuario=self.user, nombre='Ana', estado='sombra', veces_mencionada=1,
        )

        respuesta = self.client.get(reverse('diario:dashboard_diario'))

        self.assertEqual(respuesta.context['n_radar'], 0)
        self.assertNotContains(respuesta, '1 nombre repitiéndose')

    def test_solo_el_radar_confirmado_se_presenta_como_decision_pendiente(self):
        PersonaInterina.objects.create(
            usuario=self.user, nombre='Ana', estado='sombra', veces_mencionada=1,
        )
        PersonaInterina.objects.create(
            usuario=self.user, nombre='Bea', estado='radar', veces_mencionada=2,
        )

        respuesta = self.client.get(reverse('diario:dashboard_diario'))

        self.assertEqual(respuesta.context['n_radar'], 1)
        self.assertContains(respuesta, '1 vínculo requiere que lo revises')
