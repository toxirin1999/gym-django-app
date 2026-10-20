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


class TestDescansosSegunEvidencia(TestCase):
    """20-oct-2026: 2:30 básicos, 1:30 aislamiento/core, 3:00 fuerza (antes 4 min en un crunch)."""

    def test_basico(self):
        self.assertEqual(get_descanso_sugerido('compuesto_principal', 8, nombre='Jalón al Pecho', reps='12-15')['minutos'], 2.5)

    def test_core_aunque_cuente_como_principal(self):
        self.assertEqual(get_descanso_sugerido('compuesto_principal', 9, nombre='Crunch en Polea (Cable Crunch)', reps='15-20')['minutos'], 1.5)

    def test_aislamiento(self):
        self.assertEqual(get_descanso_sugerido('aislamiento', 9)['label'], '1:30')

    def test_fuerza(self):
        self.assertEqual(get_descanso_sugerido('compuesto_principal', 8, nombre='Sentadilla Hack', reps='4-6')['minutos'], 3)


class TestPlanificadorHelmsDelega(TestCase):
    def setUp(self):
        self.planificador = PlanificadorHelms.__new__(PlanificadorHelms)

    def test_delega_con_nombre_y_reps(self):
        self.assertEqual(self.planificador._calcular_descanso_pormenorizado('Prensa de Piernas', 8, 'compuesto_principal', '12-15'), 2.5)
        self.assertEqual(self.planificador._calcular_descanso_pormenorizado('Curl Araña', 9, 'aislamiento', '15-20'), 1.5)


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
        # 20-oct-2026: básico → 2:30.
        self.assertEqual(ej['descanso_label'], '2:30')
        self.assertEqual(ej['descanso_motivo'], 'ejercicio básico')

        html = response.content.decode()
        self.assertIn('2:30', html)
        self.assertIn('Ejercicio básico', html)


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
        self.assertEqual(ej['descanso_label'], '1:30')
        self.assertEqual(ej['descanso_motivo'], 'aislamiento o core')
