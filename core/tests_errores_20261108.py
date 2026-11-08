"""8-nov-2026 · Los errores 500 quedan registrados y se ven en la app."""

import logging
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from core.errores import errores_recientes, resumen_errores


LOG = """2026-11-01 10:00:00|Internal Server Error: /viejo/
Traceback (most recent call last):
  File "x.py", line 1
2026-11-07 09:00:00|Internal Server Error: /panel/
Traceback (most recent call last):
ValueError: algo
2026-11-08 08:30:00|Internal Server Error: /panel/
2026-11-08 08:31:00|Internal Server Error: /clientes/panel/
"""


class Lectura(SimpleTestCase):
    def setUp(self):
        fd, self.ruta = tempfile.mkstemp()
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(LOG)
        self.addCleanup(os.remove, self.ruta)

    def test_ultimos_dias_sin_la_traza(self):
        e = errores_recientes(7, ahora=datetime(2026, 11, 8, 12), ruta=self.ruta)
        self.assertEqual([x['ruta'] for x in e], ['/clientes/panel/', '/panel/', '/panel/'])
        r = resumen_errores(7, ahora=datetime(2026, 11, 8, 12), ruta=self.ruta)
        self.assertEqual(r['total'], 3)
        self.assertEqual(r['por_ruta'][0], ('/panel/', 2))

    def test_sin_fichero_o_sin_errores(self):
        self.assertEqual(errores_recientes(ruta='/no/existe.log'), [])
        self.assertIsNone(resumen_errores(1, ahora=datetime(2026, 12, 30), ruta=self.ruta))


class Configuracion(SimpleTestCase):
    def test_django_request_escribe_en_el_fichero(self):
        nombres = [h.__class__.__name__ for h in logging.getLogger('django.request').handlers]
        self.assertIn('FileHandler', nombres)
        fichero = [h for h in logging.getLogger('django.request').handlers if hasattr(h, 'baseFilename')][0]
        self.assertTrue(fichero.baseFilename.endswith('errores_500.log'))


class Pantallas(TestCase):
    def test_pagina_y_aviso_en_el_centro(self):
        user = User.objects.create_user('errores_20261108', password='x')
        self.client.force_login(user)
        resumen = {'total': 2, 'dias': 7, 'por_ruta': [('/panel/', 2)],
                   'ultimo': {'fecha': datetime(2026, 11, 8, 8, 30), 'ruta': '/panel/', 'mensaje': 'x'}}
        with patch('core.errores.resumen_errores', return_value=resumen):
            html = self.client.get('/clientes/plan/decisiones/').content.decode()
        self.assertIn('Errores del servidor: 2 en los últimos 7 días', html)
        r = self.client.get('/clientes/errores/')
        self.assertEqual(r.status_code, 200)
