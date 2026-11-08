"""8-nov-2026 · /panel/ y /clientes/panel/ daban 500: ahora llevan a la portada."""

from django.contrib.auth.models import User
from django.test import TestCase


class PanelAntiguo(TestCase):
    def test_redirige_a_ahora(self):
        user = User.objects.create_user('panel_antiguo_20261108', password='x')
        self.client.force_login(user)
        for url in ('/panel/', '/clientes/panel/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertNotEqual(r['Location'], url)

    def test_sin_sesion_pide_login(self):
        r = self.client.get('/panel/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])
