"""El resumen de una sesión solo lo ve su dueño (o staff)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class ResumenAccesoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dueno = User.objects.create_user('resumen_dueno', password='x')
        self.ajeno = User.objects.create_user('resumen_ajeno', password='x')
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.dueno.cliente_perfil, rutina=Rutina.objects.create(nombre='Día 1'),
        )
        self.cierre = reverse('entrenos:post_entreno_resumen', args=[self.entreno.cliente_id, self.entreno.id])
        self.legacy = reverse('entrenos:resumen_entreno', kwargs={'pk': self.entreno.id})

    def test_cierre_ajeno_da_404(self):
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(self.cierre).status_code, 404)

    def test_cierre_propio_200(self):
        self.client.force_login(self.dueno)
        self.assertEqual(self.client.get(self.cierre).status_code, 200)

    def test_resumen_legacy_exige_login_y_dueno_y_lleva_al_cierre(self):
        self.assertEqual(self.client.get(self.legacy).status_code, 302)
        self.assertIn('login', self.client.get(self.legacy)['Location'])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(self.legacy).status_code, 404)
        self.client.force_login(self.dueno)
        self.assertRedirects(self.client.get(self.legacy), self.cierre, fetch_redirect_response=False)
