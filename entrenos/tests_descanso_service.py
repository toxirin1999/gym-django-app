"""
Phase 64B — Descanso: hacer visible y reutilizable la lógica existente.

`entrenos/services/descanso_service.py` extrae el cálculo que ya existía
(enterrado) en `PlanificadorHelms._calcular_descanso_pormenorizado`, sin
cambiar sus valores, y añade label/motivo/fuente para mostrar en sesión.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from analytics.planificador_helms.core import PlanificadorHelms
from entrenos.services.descanso_service import get_descanso_sugerido


class TestGetDescansoSugeridoReproduceValores(TestCase):
    """Reproduce los 4 valores de la fórmula original de
    _calcular_descanso_pormenorizado (1/2/3/4 min)."""

    def test_compuesto_principal_rpe_alto(self):
        self.assertEqual(
            get_descanso_sugerido('compuesto_principal', rpe_objetivo=8)['minutos'], 4
        )

    def test_compuesto_principal_rpe_bajo(self):
        self.assertEqual(
            get_descanso_sugerido('compuesto_principal', rpe_objetivo=7)['minutos'], 3
        )

    def test_aislamiento_rpe_alto(self):
        self.assertEqual(
            get_descanso_sugerido('aislamiento', rpe_objetivo=8)['minutos'], 2
        )

    def test_aislamiento_rpe_bajo(self):
        self.assertEqual(
            get_descanso_sugerido('aislamiento', rpe_objetivo=7)['minutos'], 1
        )


class TestPlanificadorHelmsDelega(TestCase):
    """_calcular_descanso_pormenorizado delega en descanso_service y
    produce los mismos valores que antes."""

    def setUp(self):
        self.planificador = PlanificadorHelms.__new__(PlanificadorHelms)

    def test_compuesto_principal_rpe_alto(self):
        self.assertEqual(
            self.planificador._calcular_descanso_pormenorizado('Cualquiera', 8, 'compuesto_principal'),
            4,
        )

    def test_aislamiento_rpe_bajo(self):
        self.assertEqual(
            self.planificador._calcular_descanso_pormenorizado('Cualquiera', 5, 'aislamiento'),
            1,
        )


class TestCompuestoPrincipalRpeAltoDevuelve3a4Min(TestCase):
    def test_label_y_motivo(self):
        info = get_descanso_sugerido('compuesto_principal', rpe_objetivo=9)
        self.assertEqual(info, {
            'minutos': 4,
            'label': '3-4 min',
            'motivo': 'principal con RPE alto',
            'fuente': 'helms',
        })


class TestAccesoriosRestoDevuelven1a2Min(TestCase):
    def test_compuesto_secundario(self):
        info = get_descanso_sugerido('compuesto_secundario', rpe_objetivo=6)
        self.assertEqual(info['label'], '1-2 min')

    def test_aislamiento(self):
        info = get_descanso_sugerido('aislamiento', rpe_objetivo=9)
        self.assertEqual(info['label'], '1-2 min')


_OBTENER_PROXIMO_PATH = 'clientes.views.obtener_proximo_entrenamiento'


class PortalSesionBase(TestCase):
    """portal_sesion.html (clientes:portal_sesion) solo construye
    rutina_ajustada si hay un check-in (BitacoraDiaria) de hoy."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_descanso64b', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDescanso64B', 'dias_disponibles': 4},
        )
        self.hoy = date.today()
        # Readiness "excelente" (modificacion_rpe=0, modificacion_volumen=1.0)
        # para que rpe_objetivo/series no cambien respecto al plan.
        BitacoraDiaria.objects.create(
            cliente=self.cliente, energia_subjetiva=10, dolor_articular=0, horas_sueno=10,
        )

    def _get(self, ejercicio):
        plan = {'fecha': self.hoy, 'ejercicios': [ejercicio]}
        c = Client()
        c.login(username='tester_descanso64b', password='x')
        url = reverse('clientes:portal_sesion', args=[self.cliente.id])
        with patch(_OBTENER_PROXIMO_PATH, return_value=plan):
            return c.get(url)


class TestPortalSesionMuestranLabelMotivo(PortalSesionBase):
    def test_compuesto_principal_rpe_alto_muestra_label_y_motivo(self):
        ejercicio = {
            'nombre': 'Sentadilla con Barra',
            'grupo_muscular': 'pierna',
            'tipo_ejercicio': 'compuesto_principal',
            'peso_kg': 80.0,
            'series': 4,
            'repeticiones': '8',
            'rpe_objetivo': 9,
        }

        response = self._get(ejercicio)
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['descanso_label'], '3-4 min')
        self.assertEqual(ej['descanso_motivo'], 'principal con RPE alto')

        html = response.content.decode()
        self.assertIn('3-4 min', html)
        self.assertIn('Principal con RPE alto', html)


class TestPortalSesionFallbackSinDescansoEnJson(PortalSesionBase):
    def test_sin_tipo_ejercicio_ni_descanso_usa_fallback_y_calcula_label(self):
        ejercicio = {
            'nombre': 'Curl Bíceps',
            'grupo_muscular': 'brazo',
            'peso_kg': 20.0,
            'series': 3,
            'repeticiones': '10',
            'rpe_objetivo': 6,
        }

        response = self._get(ejercicio)
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['descanso_minutos'], 2)
        self.assertEqual(ej['descanso_label'], '1-2 min')
        self.assertEqual(ej['descanso_motivo'], 'accesorio')
