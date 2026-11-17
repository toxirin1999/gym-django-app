"""17-nov-2026 · Lentitud: perfil por tramos (core.perfil_tramos)."""
import time
from unittest.mock import patch

from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from core import perfil_tramos
from core.lentitud_middleware import PeticionesLentasMiddleware
from core.perfil_tramos import tramo, tramo_de


class TramosSueltos(SimpleTestCase):
    def tearDown(self):
        perfil_tramos.terminar()

    def test_fuera_de_una_peticion_no_hace_nada(self):
        @tramo_de('x')
        def f():
            return 7
        self.assertEqual(f(), 7)
        with tramo('y'):
            pass
        self.assertEqual(perfil_tramos.terminar(), {})

    def test_el_tiempo_propio_no_cuenta_lo_anidado(self):
        perfil_tramos.iniciar()
        with tramo('externo'):
            time.sleep(0.03)
            with tramo('interno'):
                time.sleep(0.06)
        acum = perfil_tramos.terminar()
        self.assertAlmostEqual(acum['interno'][1], 0.06, delta=0.03)
        # el externo solo cuenta lo suyo (~0,03 s), no los 0,09 s
        self.assertLess(acum['externo'][1], 0.055)
        total = sum(v[1] for v in acum.values())
        self.assertAlmostEqual(total, 0.09, delta=0.04)

    def test_las_consultas_van_al_tramo_abierto(self):
        perfil_tramos.iniciar()
        perfil_tramos.consulta(0.01)
        with tramo('a'):
            perfil_tramos.consulta(0.02)
            perfil_tramos.consulta(0.02)
            with tramo('b'):
                perfil_tramos.consulta(0.05)
        acum = perfil_tramos.terminar()
        self.assertEqual(acum['a'][3], 2)
        self.assertAlmostEqual(acum['a'][2], 0.04)
        self.assertEqual(acum['b'][3], 1)
        self.assertEqual(acum[perfil_tramos.RESTO][3], 1)

    def test_varias_llamadas_se_acumulan_y_la_excepcion_cierra_el_tramo(self):
        perfil_tramos.iniciar()

        @tramo_de('rota')
        def rota():
            raise ValueError('x')

        for _ in range(2):
            with self.assertRaises(ValueError):
                rota()
        acum = perfil_tramos.terminar()
        self.assertEqual(acum['rota'][0], 2)

    def test_resumen_ordena_por_tiempo_propio(self):
        txt = perfil_tramos.resumen({'a': (1, 0.1, 0.05, 3), 'b': (2, 0.9, 0.1, 9)})
        self.assertTrue(txt.startswith('b x2 propio=0.90s bd=0.10s q=9 fuera_sql=0.80s'))


class MiddlewareRegistraTramos(TestCase):
    def test_peticion_lenta_deja_linea_tramos_con_su_bd(self):
        @tramo_de('lectura')
        def leer():
            with connection.cursor() as c:
                c.execute('SELECT 1')

        def vista(request):
            leer()
            return HttpResponse('ok')

        with self.settings(LENTITUD_UMBRAL_S=0):
            with self.assertLogs('lentitud', level='WARNING') as cap:
                PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/?token=secreto'))
        tramos = [l for l in cap.output if 'TRAMOS' in l]
        self.assertEqual(len(tramos), 1)
        self.assertIn('lectura x1', tramos[0])
        self.assertIn('q=1', tramos[0])
        self.assertIn('resto x1', tramos[0])
        self.assertNotIn('secreto', tramos[0])

    def test_peticion_rapida_no_deja_linea(self):
        with self.settings(LENTITUD_UMBRAL_S=60):
            with self.assertNoLogs('lentitud', level='WARNING'):
                PeticionesLentasMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_el_perfil_no_queda_abierto_tras_la_peticion(self):
        PeticionesLentasMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/x/'))
        self.assertFalse(perfil_tramos.activo())
