"""Memoria: serie crítica por tasa y ejercicios emblema con el cálculo del mapa."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services.modelo_usuario_service import (
    _get_ejercicios_emblema, _get_serie_critica_global,
)
from rutinas.models import EjercicioBase, Rutina


class SerieCriticaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='serie-crit', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()
        self.base = EjercicioBase.objects.create(nombre='Press banca test')

    def _sesion(self, calidades, aproximacion_s1=False):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='r'),
            fecha=self.hoy - timedelta(days=3),
        )
        for n, calidad in enumerate(calidades, start=1):
            SerieRealizada.objects.create(
                entreno=entreno, ejercicio=self.base, serie_numero=n, repeticiones=8,
                peso_kg=60, completado=True, tecnica_calidad=calidad,
                es_aproximacion=aproximacion_s1 and n == 1,
            )

    def test_la_posicion_con_mayor_tasa_gana_aunque_tenga_menos_casos(self):
        # S1 aparece siempre (10 veces, 3 malas = 30 %); S4 solo 5 veces, 4 malas = 80 %.
        for i in range(10):
            calidades = ['comprometida' if i < 3 else 'buena', 'buena', 'buena']
            if i < 5:
                calidades.append('comprometida' if i < 4 else 'buena')
            self._sesion(calidades)
        resultado = _get_serie_critica_global(self.cliente, self.hoy)
        self.assertEqual(resultado['serie'], 4)
        self.assertEqual(resultado['pct'], 80)
        self.assertIn('80 %', resultado['descripcion'])

    def test_las_aproximaciones_no_cuentan(self):
        for _ in range(8):
            self._sesion(['comprometida', 'buena', 'buena'], aproximacion_s1=True)
        self.assertIsNone(_get_serie_critica_global(self.cliente, self.hoy))

    def test_sin_patron_claro_no_inventa_serie(self):
        for _ in range(8):
            self._sesion(['comprometida', 'comprometida', 'comprometida'])
        self.assertIsNone(_get_serie_critica_global(self.cliente, self.hoy))


class EmblemaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='emblema', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()

    def _sesion(self, dias, nombre, peso, grupo='Pecho'):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'{nombre}{dias}'),
            fecha=self.hoy - timedelta(days=dias),
        )
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio=nombre, grupo_muscular=grupo,
            peso_kg=peso, repeticiones=8, series=3,
        )])

    def test_usa_la_comparacion_del_mapa_y_descarta_dudosos_y_ligeros(self):
        self._sesion(120, 'Press banca', 80)
        self._sesion(10, 'Press banca', 90)
        self._sesion(120, 'Hiperextensiones', 5, 'Isquios')   # ligero
        self._sesion(10, 'Hiperextensiones', 15, 'Isquios')
        self._sesion(120, 'Curl femoral', 40, 'Isquios')      # dudoso (+150 %)
        self._sesion(10, 'Curl femoral', 100, 'Isquios')
        emblemas = _get_ejercicios_emblema(self.cliente, self.hoy)
        self.assertEqual([e['ejercicio'] for e in emblemas], ['Press banca'])
        self.assertEqual(emblemas[0]['peso_antes'], 80)
        self.assertEqual(emblemas[0]['reps_ahora'], 8)
        self.assertAlmostEqual(emblemas[0]['pct'], 12.5, places=1)
