"""
Phase 64C — Calentamiento: hacer visible y reutilizable la lógica existente.

`entrenos/services/calentamiento_service.py` extrae el cálculo que ya existía
(enterrado) en `vista_entrenamiento_activo` para las series de aproximación
(50% / 70% / 85% del peso de trabajo, redondeadas a 2.5 kg), sin cambiar sus
valores, y lo lleva a `portal_sesion_unificado` — solo para el bloque principal.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento


class TestGetAproximacionesCalentamientoReproduceValores(TestCase):
    def test_peso_redondo(self):
        self.assertEqual(
            get_aproximaciones_calentamiento(100),
            {'peso1': 50.0, 'peso2': 70.0, 'peso3': 85.0},
        )

    def test_peso_con_redondeo_a_2_5(self):
        self.assertEqual(
            get_aproximaciones_calentamiento(83),
            {'peso1': 42.5, 'peso2': 57.5, 'peso3': 70.0},
        )


class TestGetAproximacionesCalentamientoNoAplica(TestCase):
    def test_usa_peso_false_devuelve_none(self):
        self.assertIsNone(get_aproximaciones_calentamiento(100, usa_peso=False))

    def test_peso_cero_devuelve_none(self):
        self.assertIsNone(get_aproximaciones_calentamiento(0))

    def test_peso_negativo_devuelve_none(self):
        self.assertIsNone(get_aproximaciones_calentamiento(-10))


_OBTENER_PROXIMO_PATH = 'clientes.views.obtener_proximo_entrenamiento'


class PortalSesionCalentamientoBase(TestCase):
    """portal_sesion.html (clientes:portal_sesion) solo construye
    rutina_ajustada si hay un check-in (BitacoraDiaria) de hoy."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_calent64c', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCalent64C', 'dias_disponibles': 4},
        )
        self.hoy = date.today()
        BitacoraDiaria.objects.create(
            cliente=self.cliente, energia_subjetiva=10, dolor_articular=0, horas_sueno=10,
        )

    def _get(self, ejercicios):
        plan = {'fecha': self.hoy, 'ejercicios': ejercicios}
        c = Client()
        c.login(username='tester_calent64c', password='x')
        url = reverse('clientes:portal_sesion', args=[self.cliente.id])
        with patch(_OBTENER_PROXIMO_PATH, return_value=plan):
            return c.get(url)


class TestPortalSesionMuestraCalentamientoEnPrincipal(PortalSesionCalentamientoBase):
    def test_compuesto_principal_con_peso_calcula_aproximaciones(self):
        ejercicio = {
            'nombre': 'Sentadilla con Barra', 'grupo_muscular': 'pierna',
            'tipo_ejercicio': 'compuesto_principal', 'tipo_progresion': 'peso_reps',
            'peso_kg': 100.0, 'series': 4, 'repeticiones': '8', 'rpe_objetivo': 7,
        }

        response = self._get([ejercicio])
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['aproximaciones'], {'peso1': 50.0, 'peso2': 70.0, 'peso3': 85.0})

        html = response.content.decode()
        self.assertIn('Calentamiento sugerido', html)
        self.assertIn('50.0 kg', html)


class TestPortalSesionSinCalentamientoEnAccesorios(PortalSesionCalentamientoBase):
    def test_accesorio_con_peso_no_muestra_calentamiento(self):
        ejercicio = {
            'nombre': 'Curl Bíceps', 'grupo_muscular': 'brazo',
            'tipo_ejercicio': 'aislamiento', 'tipo_progresion': 'peso_reps',
            'peso_kg': 20.0, 'series': 3, 'repeticiones': '10', 'rpe_objetivo': 8,
        }

        response = self._get([ejercicio])
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertIsNone(ej['aproximaciones'])

        html = response.content.decode()
        self.assertNotIn('Calentamiento sugerido', html)

    def test_progresion_reps_sin_tipo_ejercicio_no_muestra_calentamiento(self):
        ejercicio = {
            'nombre': 'Dominadas', 'grupo_muscular': 'espalda',
            'tipo_progresion': 'progresion_reps',
            'peso_kg': 0.0, 'series': 3, 'repeticiones': '8', 'rpe_objetivo': 8,
        }

        response = self._get([ejercicio])
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertIsNone(ej['aproximaciones'])

        html = response.content.decode()
        self.assertNotIn('Calentamiento sugerido', html)
