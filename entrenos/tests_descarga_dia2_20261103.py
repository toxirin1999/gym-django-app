"""3-nov-2026 · Día 2 de la descarga y gráficas de Cuerpo.

1. Reps de descarga: 3 menos que la última vez (que sobren 3 o 4 a RPE 6).
2. En versión suave, el briefing pone los principales primero y marca los
   accesorios como opcionales; el estado no dice «todo en orden» a secas.
4. Calentamiento de descarga: dos escalones, y ninguno con poco peso.
Cuerpo: puntos con punto decimal (con coma el SVG no los dibujaba), 14
mañanas, línea de tendencia de 7 días y la frase de hoy.
"""

import re
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento
from entrenos.services.panel_cuerpo_service import pulso, variabilidad
from entrenos.services.sesion_descarga_service import reps_descarga
from entrenos.tests_estado_carga_20261025 import HOY, Base


class RepsDescarga(SimpleTestCase):
    def test_tres_menos_dentro_del_rango(self):
        self.assertEqual(reps_descarga(15, 10, 15), 12)
        self.assertEqual(reps_descarga(17, 10, 15), 12)
        self.assertEqual(reps_descarga(14, 10, 15), 11)
        self.assertEqual(reps_descarga(13, 10, 15), 10)

    def test_nunca_por_debajo_del_minimo(self):
        self.assertEqual(reps_descarga(11, 10, 15), 10)
        self.assertEqual(reps_descarga(10, 10, 15), 10)
        self.assertEqual(reps_descarga(6, 6, 8), 6)


class CalentamientoDescarga(SimpleTestCase):
    def test_dos_escalones(self):
        a = get_aproximaciones_calentamiento(65, True, incremento=5, descarga=True)
        self.assertIsNone(a['peso3'])
        self.assertTrue(0 < a['peso1'] < a['peso2'] < 65)

    def test_con_poco_peso_ninguno(self):
        self.assertIsNone(get_aproximaciones_calentamiento(20, True, incremento=5, descarga=True))
        self.assertIsNone(get_aproximaciones_calentamiento(17.5, True, incremento=2.5, descarga=True))

    def test_semana_normal_sin_cambios(self):
        self.assertIsNotNone(get_aproximaciones_calentamiento(65, True, incremento=5)['peso3'])


_FECHA = date.today().strftime('%Y-%m-%d')


class BriefingVersionSuave(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('tester_suave_20261103', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def _get(self, ejercicios, **extra):
        cache.set(f"transporte_ejercicios_dia_{self.cliente.id}_{_FECHA}", ejercicios, 900)
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        return self.client.get(url, dict({'fecha': _FECHA, 'rutina_nombre': 'Dia 2'}, **extra))

    EJERCICIOS = [
        {'nombre': 'Crunch en Polea', 'series': 2, 'repeticiones': '10-15', 'peso_kg': 65,
         'tipo_progresion': 'peso_reps', 'tipo_ejercicio': 'aislamiento'},
        {'nombre': 'Jalón al Pecho', 'series': 2, 'repeticiones': '10-15', 'peso_kg': 45,
         'tipo_progresion': 'peso_reps', 'tipo_ejercicio': 'compuesto_principal'},
    ]

    def test_principales_primero_y_accesorios_opcionales(self):
        r = self._get([dict(e) for e in self.EJERCICIOS], modo_reducido='1')
        html = r.content.decode()
        self.assertLess(html.index('Jalón al Pecho'), html.index('Crunch en Polea'))
        self.assertEqual(html.count('OPCIONAL HOY'), 1)

    def test_sin_version_suave_nada_es_opcional(self):
        r = self._get([dict(e) for e in self.EJERCICIOS])
        self.assertNotContains(r, 'OPCIONAL HOY')


class GraficasCuerpo(Base):
    def test_puntos_con_punto_decimal_y_tendencia(self):
        self.base(dias=10)
        self.reloj(0, hrv=32, fc=58, sueno=7.5)
        self.client.force_login(self.user)
        html = self.client.get(reverse('clientes:cuerpo')).content.decode()
        self.assertFalse(re.search(r'c[xy]="\d+,\d', html), 'coordenadas con coma decimal')
        self.assertIn('Tendencia 7 días', html)
        self.assertIn('Hoy: <strong>32 ms</strong>', html)

    def test_14_mananas_y_lectura(self):
        self.base(dias=10)
        self.reloj(0, hrv=32, fc=58, sueno=7.5)
        v = variabilidad(self.cliente, HOY)
        self.assertEqual(v['marcas'][-1]['texto'], 'hoy')
        self.assertLessEqual(len(v['puntos']), 14)
        self.assertIn('por debajo de lo habitual', v['hoy_lectura'])
        self.assertTrue(v['tendencia'])
        for par in v['tendencia'].split():
            x, y = par.split(',')
            float(x), float(y)
        p = pulso(self.cliente, HOY)
        self.assertIn('hoy_lectura', p)
