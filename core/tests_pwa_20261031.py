"""31-oct-2026 · Icono de la app en el iPhone y aviso de carga."""

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from core.pwa_middleware import PwaMiddleware


def _mw(respuesta):
    return PwaMiddleware(lambda request: respuesta)(RequestFactory().get('/'))


class Middleware(SimpleTestCase):
    def test_anade_icono_y_aviso_de_carga(self):
        r = _mw(HttpResponse('<html><head><title>Ahora</title></head><body>hola</body></html>'))
        html = r.content.decode()
        self.assertIn('apple-touch-icon', html)
        self.assertIn('icons/apple-touch-icon.png', html)
        self.assertIn('apple-mobile-web-app-title" content="Gym"', html)
        self.assertIn('id="pwa-carga"', html)

    def test_respeta_el_icono_que_ya_trae(self):
        r = _mw(HttpResponse('<html><head><link rel="apple-touch-icon" href="/x.png"></head><body></body></html>'))
        html = r.content.decode()
        self.assertEqual(html.count('apple-touch-icon'), 1)
        self.assertIn('id="pwa-carga"', html)

    def test_no_toca_json_ni_errores(self):
        j = _mw(JsonResponse({'a': 1}))
        self.assertEqual(j.content, b'{"a": 1}')
        e = HttpResponse('<html><head></head><body></body></html>', status=500)
        self.assertNotIn(b'pwa-carga', _mw(e).content)

    def test_no_duplica(self):
        r = _mw(HttpResponse('<html><head></head><body></body></html>'))
        r2 = PwaMiddleware(lambda request: r)(RequestFactory().get('/'))
        self.assertEqual(r2.content.count(b'id="pwa-carga"'), 1)


class Rutas(TestCase):
    def test_icono_en_la_raiz(self):
        r = self.client.get('/apple-touch-icon.png')
        self.assertEqual(r.status_code, 302)
        self.assertIn('icons/apple-touch-icon', r['Location'])

    def test_login_lleva_el_icono(self):
        r = self.client.get('/login/')
        self.assertContains(r, 'apple-touch-icon')
        self.assertContains(r, 'id="pwa-carga"')
