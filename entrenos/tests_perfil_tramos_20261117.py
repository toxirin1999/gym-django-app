"""17-nov-2026 · Lentitud: perfil por tramos (core.perfil_tramos)."""
import time
from unittest.mock import patch

from django.contrib.auth.models import User
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
    def _pasar(self, vista, url='/x/?token=secreto'):
        with self.settings(LENTITUD_UMBRAL_S=0):
            with self.assertLogs('lentitud', level='WARNING') as cap:
                PeticionesLentasMiddleware(vista)(RequestFactory().get(url))
        return cap.output

    def test_peticion_lenta_deja_una_sola_linea_con_tramos_y_tablas(self):
        @tramo_de('lectura')
        def leer():
            with connection.cursor() as c:
                c.execute('SELECT 1')
            list(User.objects.all()[:1])

        def vista(request):
            leer()
            return HttpResponse('ok')

        salida = self._pasar(vista)
        self.assertEqual(len(salida), 1)
        linea = salida[0]
        self.assertIn('tramos: lectura x1', linea)
        self.assertIn('resto x1', linea)
        self.assertIn('tablas:', linea)
        self.assertIn('auth_user x1', linea)
        self.assertNotIn('secreto', linea)

    def test_si_falla_el_perfil_la_linea_lo_dice(self):
        with patch('core.lentitud_middleware.perfil_tramos.terminar', side_effect=RuntimeError('boom')):
            salida = self._pasar(lambda r: HttpResponse('ok'))
        self.assertEqual(len(salida), 1)
        self.assertIn('tramos: n/d (error RuntimeError: boom)', salida[0])

    def test_si_el_perfil_sale_vacio_la_linea_lo_dice(self):
        with patch('core.lentitud_middleware.perfil_tramos.terminar', return_value={}):
            salida = self._pasar(lambda r: HttpResponse('ok'))
        self.assertIn('tramos: n/d (vacio)', salida[0])

    def test_peticion_rapida_no_deja_linea(self):
        with self.settings(LENTITUD_UMBRAL_S=60):
            with self.assertNoLogs('lentitud', level='WARNING'):
                PeticionesLentasMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_el_perfil_no_queda_abierto_tras_la_peticion(self):
        PeticionesLentasMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/x/'))
        self.assertFalse(perfil_tramos.activo())


class ResumenDeTablas(SimpleTestCase):
    def test_agrupa_por_tabla_y_ordena_por_tiempo_sin_valores(self):
        from core.lentitud_middleware import _resumen_tablas
        txt = _resumen_tablas([
            (0.5, "SELECT `joi_mensajejoi`.`id` FROM `joi_mensajejoi` WHERE `mensaje` = 'secreto'"),
            (0.1, "SELECT x FROM `entrenos_entrenorealizado` WHERE id = 1"),
            (0.2, "SELECT x FROM `entrenos_entrenorealizado` WHERE id = 2"),
            (0.05, "INSERT INTO `joi_mensajejoi` (a) VALUES ('secreto')"),
            (0.01, "SAVEPOINT s1"),
        ])
        self.assertTrue(txt.startswith('joi_mensajejoi x2 0.55s, entrenos_entrenorealizado x2 0.30s'))
        self.assertIn('otra x1', txt)
        self.assertNotIn('secreto', txt)


class TablasVigiladas(TestCase):
    """La prueba de que el cierre ya no lee JOI es ``joi_mensajejoi=0``, no que falte entre las 8 más caras."""

    def test_cuenta_todas_las_consultas_aunque_no_esten_entre_las_mas_caras(self):
        from core.lentitud_middleware import _vigiladas
        consultas = [(1.0, f"SELECT x FROM `tabla_{i}`") for i in range(10)]
        consultas += [
            (0.001, "SELECT `joi_mensajejoi`.`id` FROM `joi_mensajejoi` WHERE `mensaje` = 'secreto'"),
            (0.001, 'SELECT a.id FROM "entrenos_entrenorealizado" a INNER JOIN "joi_mensajejoi" j ON j.id = a.id'),
            (0.001, "SELECT x FROM `joi_mensajejoi_extra`"),   # otra tabla con el mismo prefijo: no cuenta
        ]
        self.assertEqual(_vigiladas(consultas, ('joi_mensajejoi',)), 'joi_mensajejoi=2')

    def test_la_linea_dice_cero_cuando_no_se_consulta(self):
        def vista(request):
            list(User.objects.all()[:1])
            return HttpResponse('ok')

        with self.settings(LENTITUD_UMBRAL_S=0):
            with self.assertLogs('lentitud', level='WARNING') as cap:
                PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))
        self.assertIn('vigiladas: joi_mensajejoi=0', cap.output[0])

    def test_la_linea_cuenta_las_consultas_a_joi(self):
        from joi.models import MensajeJOI

        def vista(request):
            list(MensajeJOI.objects.all()[:1])
            list(MensajeJOI.objects.filter(pk=1))
            return HttpResponse('ok')

        with self.settings(LENTITUD_UMBRAL_S=0):
            with self.assertLogs('lentitud', level='WARNING') as cap:
                PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))
        self.assertIn('vigiladas: joi_mensajejoi=2', cap.output[0])
