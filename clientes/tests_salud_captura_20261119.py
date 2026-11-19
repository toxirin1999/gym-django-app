"""Captura temporal del Atajo de Salud (19-nov-2026): apagada por defecto, solo lista blanca, nunca rompe."""
import json
import os
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes import salud_captura_temporal as cap
from clientes.models import Cliente


class CapturaTemporal(TestCase):
    def setUp(self):
        cache.clear()
        self.dir = tempfile.mkdtemp()
        self.addCleanup(cache.clear)
        self.ruta = os.path.join(self.dir, cap.NOMBRE)
        self.hoy = timezone.localdate()

    def entorno(self, hasta):
        return mock.patch.dict(os.environ, {'SALUD_CAPTURA_HASTA': hasta} if hasta is not None else {}, clear=False)

    def lineas(self):
        with open(self.ruta, encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_apagada_por_defecto_y_con_fecha_pasada(self):
        with override_settings(LOGS_DIR=self.dir):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('SALUD_CAPTURA_HASTA', None)
                self.assertFalse(cap.capturar(1, {'sueno': '1:00:00'}))
            with self.entorno((self.hoy - timedelta(days=1)).isoformat()):
                self.assertFalse(cap.capturar(1, {'sueno': '1:00:00'}))
            with self.entorno('no es fecha'):
                self.assertFalse(cap.capturar(1, {'sueno': '1:00:00'}))
        self.assertFalse(os.path.exists(self.ruta))

    def test_activa_hasta_la_fecha_inclusive_y_solo_lista_blanca(self):
        envio = {'token': 'SECRETO', 'sueno': '3:00:00\n1:00:00', 'fases': 'Core\nDeep',
                 'inicios': '2026-11-18 23:10\n2026-11-19 02:10', 'otro': 'no', 'peso': 80}
        with override_settings(LOGS_DIR=self.dir), self.entorno(self.hoy.isoformat()):
            self.assertTrue(cap.capturar(2, envio, {'x': {'horas_sueno': 4.0}}))
        texto = open(self.ruta, encoding='utf-8').read()
        self.assertNotIn('SECRETO', texto)
        self.assertNotIn('"otro"', texto)
        self.assertNotIn('"peso"', texto)
        fila = self.lineas()[0]
        self.assertEqual(fila['campos'], ['fases', 'inicios', 'sueno'])
        self.assertEqual(fila['cliente'], 2)
        self.assertEqual(fila['recibido']['fases'], 'Core\nDeep')
        self.assertEqual(oct(os.stat(self.ruta).st_mode & 0o777), '0o600')

    def test_sin_campos_utiles_no_escribe(self):
        with override_settings(LOGS_DIR=self.dir), self.entorno(self.hoy.isoformat()):
            self.assertFalse(cap.capturar(1, {'token': 'x', 'otro': 1}))
            self.assertFalse(cap.capturar(1, ['no', 'dict']))
        self.assertFalse(os.path.exists(self.ruta))

    def test_conserva_solo_los_ultimos_y_recorta(self):
        with override_settings(LOGS_DIR=self.dir), self.entorno(self.hoy.isoformat()):
            for i in range(cap.MAX_CAPTURAS + 5):
                cap.capturar(1, {'hrv': str(i)})
            cap.capturar(1, {'sueno': 'x' * (cap.MAX_CARACTERES + 500)})
        filas = self.lineas()
        self.assertEqual(len(filas), cap.MAX_CAPTURAS)
        self.assertEqual(len(filas[-1]['recibido']['sueno']), cap.MAX_CARACTERES)

    def test_un_fallo_no_rompe(self):
        with override_settings(LOGS_DIR=os.path.join(self.dir, 'no', 'existe')), self.entorno(self.hoy.isoformat()):
            self.assertFalse(cap.capturar(1, {'sueno': '1:00:00'}))


class CapturaEnElEndpoint(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = User.objects.create_user(username='cap', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        self.token = self.cliente.get_or_create_api_token()
        self.dir = tempfile.mkdtemp()

    def post(self, cuerpo):
        return self.client.post(reverse('clientes:api_salud_iphone'), data=json.dumps(cuerpo),
                                content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_endpoint_captura_cuando_esta_activa_y_no_cuando_no(self):
        hoy = timezone.localdate().isoformat()
        with override_settings(LOGS_DIR=self.dir):
            with mock.patch.dict(os.environ, {'SALUD_CAPTURA_HASTA': hoy}):
                r = self.post({'hrv': '50 ms', 'token': self.token})
            self.assertEqual(r.status_code, 200)
            ruta = os.path.join(self.dir, cap.NOMBRE)
            self.assertTrue(os.path.exists(ruta))
            self.assertNotIn(self.token, open(ruta, encoding='utf-8').read())
            os.remove(ruta)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('SALUD_CAPTURA_HASTA', None)
                self.assertEqual(self.post({'hrv': '50 ms'}).status_code, 200)
            self.assertFalse(os.path.exists(ruta))

    def test_si_la_captura_falla_la_importacion_sigue(self):
        with override_settings(LOGS_DIR=os.path.join(self.dir, 'no', 'existe')), \
                mock.patch.dict(os.environ, {'SALUD_CAPTURA_HASTA': timezone.localdate().isoformat()}):
            r = self.post({'hrv': '50 ms'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
