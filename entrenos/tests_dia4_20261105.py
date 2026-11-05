"""5-nov-2026 · Briefing del Día 4 de la descarga (día después del fútbol).

1. Versión suave por el fútbol: solo la pierna es opcional (R10).
2. El estado dice el porqué real de la versión suave (el partido, no cómo amaneces).
3. «(1 ejercicio)», en singular.
4. Si bajar un salto en descarga quita más de un 20 % (laterales 10 → 5 kg),
   se mantiene el peso y se quitan reps.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from entrenos.tests_descarga_semana_20261102 import LUNES
from entrenos.tests_ultima_sesion import Base
from entrenos.views import _es_principal_hoy

_HOY = date.today()
_FECHA = _HOY.strftime('%Y-%m-%d')


class PrincipalSoloPierna(SimpleTestCase):
    def test_con_futbol_solo_la_pierna_es_opcional(self):
        laterales = {'grupo_muscular': 'hombros', 'tipo_ejercicio': 'aislamiento'}
        curl = {'grupo_muscular': 'isquios', 'tipo_ejercicio': 'aislamiento', 'pierna_suave': True}
        self.assertTrue(_es_principal_hoy(laterales, solo_pierna=True))
        self.assertFalse(_es_principal_hoy(curl, solo_pierna=True))
        self.assertFalse(_es_principal_hoy(laterales))  # por recuperación, sigue siendo accesorio


class BriefingTrasElFutbol(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('tester_futbol_20261105', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol',
                                          fecha=_HOY - timedelta(days=1), duracion_minutos=60, carga_ua=500)
        self.client = Client()
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def test_notas_1_2_y_3(self):
        ejercicios = [
            {'nombre': 'Elevaciones Laterales en Polea', 'grupo_muscular': 'hombros', 'series': 3,
             'repeticiones': '10-15', 'peso_kg': 10, 'tipo_progresion': 'peso_reps', 'tipo_ejercicio': 'aislamiento'},
            {'nombre': 'Curl Femoral Sentado', 'grupo_muscular': 'isquios', 'series': 3,
             'repeticiones': '10-15', 'peso_kg': 30, 'tipo_progresion': 'peso_reps', 'tipo_ejercicio': 'aislamiento'},
        ]
        cache.set(f"transporte_ejercicios_dia_{self.cliente.id}_{_FECHA}", ejercicios, 900)
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        html = self.client.get(url, {'fecha': _FECHA, 'rutina_nombre': 'Dia 4', 'modo_reducido': '1'}).content.decode()
        self.assertEqual(html.count('OPCIONAL HOY'), 1)
        self.assertLess(html.index('Elevaciones Laterales en Polea'), html.index('OPCIONAL HOY'))
        self.assertIn('(1 ejercicio).', html)
        self.assertNotIn('va por cómo amaneces', html)


class DescargaMismoPeso(Base):
    def test_nota4_laterales_mantienen_el_peso(self):
        from rutinas.models import EjercicioBase
        from entrenos.services.sesion_descarga_service import ajustar_a_descarga
        lat = EjercicioBase.objects.create(nombre='Elevaciones Laterales en Polea', grupo_muscular='hombros',
                                           tipo_progresion='peso_reps', equipo='Polea')
        e = self.entreno(LUNES - timedelta(days=5), {lat.nombre: '10-15'})
        self.hacer(e, lat, [(10, 16, 8), (10, 16, 8), (10, 16, 8)])
        ej = {'nombre': lat.nombre, 'repeticiones': '10-15', 'tipo_progresion': 'peso_reps',
              'rpe_objetivo': 6, 'peso_kg': 999}
        frase = ajustar_a_descarga(self.cliente, ej, LUNES)
        self.assertEqual(ej['peso_kg'], 10.0)
        self.assertEqual(ej['reps_objetivo_hoy'], 11)
        self.assertIn('mismo peso y menos reps', frase)
        self.assertNotIn('_descarga_mismo_peso', ej)
