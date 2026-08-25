"""
Tests de regresión — tope de máquina, usa_peso (distancia+carga) y progresión
de distancia en la rama canónica de vista_entrenamiento_activo.

Contexto: la rama canónica (es_sesion_canonica=True, cuando el snapshot ya
viene de la autoridad diaria materializada) reimplementaba el enriquecimiento
de UI con .setdefault(...) pero omitía tres piezas que sí existen en la rama
legacy: tope de máquina (calcular_sugerencia_tope), el caso especial de
usa_peso para ejercicios de distancia con carga externa, y la progresión de
distancia desde el historial real. Bugs verificados en producción esta
semana con datos reales (ver CLAUDE.md / memoria de sesión).
"""
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client as DjangoClient
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina


class BaseTopeCanonica(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test_tope_canonica', password='x',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestTopeCanonica', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_tope_canonica_rutina')
        self.http = DjangoClient()
        self.http.force_login(self.user)
        self.fecha_str = date.today().strftime('%Y-%m-%d')

    def _crear_entreno(self, delta_dias):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina,
            fecha=date.today() - timedelta(days=delta_dias),
        )

    def _crear_ej(self, entreno, peso, reps, rpe=8, es_tope=False):
        return EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=self.NOMBRE_EJ,
            peso_kg=peso, repeticiones=reps, rpe=rpe, es_tope_maquina=es_tope,
        )

    def _get_vista(self, ejercicio_hoy):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        return self.http.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Sesión canónica de test',
            'ejercicios': json.dumps([ejercicio_hoy]),
        })

    def _ej_contexto(self, response):
        self.assertEqual(
            response.status_code, 200,
            f"La vista no devolvió 200 (status={response.status_code})",
        )
        return response.context['ejercicios_planificados'][0]


class TestTopeMaquinaEnCanonica(BaseTopeCanonica):
    """
    Ejercicio con es_tope_maquina=True en la última sesión real (peso=100 kg).
    En sesión canónica de hoy, peso_inicial_kg debe congelarse en 100 (no
    tomar el peso recalculado de fase que trae el snapshot), y
    sugerencia_tope debe ser True.
    """
    NOMBRE_EJ = 'Prensa Tope Canonica Test'

    def setUp(self):
        super().setUp()
        entreno = self._crear_entreno(delta_dias=3)
        self._crear_ej(entreno, peso=100.0, reps=8, es_tope=True)

    def test_peso_inicial_congelado_en_el_tope(self):
        ejercicio_hoy = {
            'nombre': self.NOMBRE_EJ,
            'series': 3,
            'repeticiones': '8-10',
            'peso_kg': 102.5,
            'rpe_objetivo': 8,
            'tipo_ejercicio': 'compuesto_principal',
            '_autoridad_gym_materializada': True,
        }
        resp = self._get_vista(ejercicio_hoy)
        ej = self._ej_contexto(resp)
        self.assertTrue(ej.get('sugerencia_tope'), "sugerencia_tope debe ser True con tope de máquina")
        self.assertAlmostEqual(
            float(ej.get('peso_inicial_kg') or 0), 100.0, delta=0.01,
            msg=f"peso_inicial_kg debe quedar en 100.0 (tope), se obtuvo {ej.get('peso_inicial_kg')}",
        )
        self.assertEqual(ej.get('reps_sugeridas_tope'), 9)


class TestDistanciaConCargaEnCanonica(BaseTopeCanonica):
    """
    Farmer Walk (progresion_distancia) con última sesión real a 38 m / 75 kg.
    En sesión canónica de hoy: usa_peso debe ser True (peso_recomendado_kg>0)
    y reps_objetivo (que en distancia representa metros) debe continuar desde
    38 (39, dado que el mínimo del rango de hoy es 30 <= 38), no caer al
    mínimo del rango.
    """
    NOMBRE_EJ = 'Farmer Walk Canonica Test'

    def setUp(self):
        super().setUp()
        entreno = self._crear_entreno(delta_dias=3)
        self._crear_ej(entreno, peso=75.0, reps=38)

    def test_usa_peso_y_progresion_de_distancia_desde_historial(self):
        ejercicio_hoy = {
            'nombre': self.NOMBRE_EJ,
            'series': 3,
            'repeticiones': '30-40',
            'peso_recomendado_kg': 75.0,
            'rpe_objetivo': 7,
            'tipo_progresion': 'progresion_distancia',
            'tipo_ejercicio': 'accesorio',
            '_autoridad_gym_materializada': True,
        }
        resp = self._get_vista(ejercicio_hoy)
        ej = self._ej_contexto(resp)
        self.assertTrue(ej.get('usa_distancia'))
        self.assertTrue(
            ej.get('usa_peso'),
            "usa_peso debe ser True cuando usa_distancia y peso_recomendado_kg > 0",
        )
        self.assertEqual(
            ej.get('reps_objetivo'), 39,
            "reps_objetivo (metros) debe continuar desde 38 -> 39, no caer al mínimo del rango (30)",
        )


class TestSinDatosAnteriorEnCanonica(BaseTopeCanonica):
    """
    Primera vez que se hace un ejercicio (sin datos_anterior). No debe romper
    y sugerencia_tope debe quedar en False sin cambiar el comportamiento
    actual.
    """
    NOMBRE_EJ = 'Ejercicio Nuevo Sin Historial Canonica Test'

    def test_no_rompe_y_sugerencia_tope_false(self):
        ejercicio_hoy = {
            'nombre': self.NOMBRE_EJ,
            'series': 3,
            'repeticiones': '8-10',
            'peso_recomendado_kg': 50.0,
            'rpe_objetivo': 8,
            'tipo_ejercicio': 'compuesto_principal',
            '_autoridad_gym_materializada': True,
        }
        resp = self._get_vista(ejercicio_hoy)
        ej = self._ej_contexto(resp)
        self.assertFalse(ej.get('sugerencia_tope'))
        self.assertAlmostEqual(float(ej.get('peso_anterior_kg') or 0), 0.0, delta=0.01)
