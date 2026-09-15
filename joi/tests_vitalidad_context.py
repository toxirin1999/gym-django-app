"""
Tests de joi.context_builders.vitalidad_context — eje de Vitalidad JOI.

Cubre: periodo de gracia, decaimiento gradual, suelo mínimo (nunca cero),
gracia extendida por racha, recuperación inmediata al entrenar hoy,
y robustez cuando no hay ninguna actividad registrada.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.utils import get_cliente_actual
from entrenos.models import ActividadRealizada
from joi.context_builders.vitalidad_context import (
    calcular_vitalidad_joi,
    VITALIDAD_MAXIMA,
    VITALIDAD_MINIMA,
)

HOY = date(2026, 9, 13)


class VitalidadJoiBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_vitalidad', password='x')
        self.cliente = get_cliente_actual(self.user)

    def _registrar_actividad(self, hace_dias):
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            fecha=HOY - timedelta(days=hace_dias),
        )


class TestSinActividadNunca(VitalidadJoiBase):
    def test_sin_actividad_devuelve_estado_neutro_no_hibernando(self):
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertIsNone(resultado['dias_inactivo'])
        self.assertEqual(resultado['nivel_visual'], 'estable')
        self.assertGreater(resultado['valor'], VITALIDAD_MINIMA)


class TestPeriodoDeGracia(VitalidadJoiBase):
    def test_actividad_hoy_es_vitalidad_maxima(self):
        self._registrar_actividad(hace_dias=0)
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertEqual(resultado['valor'], VITALIDAD_MAXIMA)
        self.assertEqual(resultado['nivel_visual'], 'plena')
        self.assertTrue(resultado['en_gracia'])

    def test_un_dia_sin_entrenar_no_penaliza(self):
        self._registrar_actividad(hace_dias=1)
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertEqual(resultado['valor'], VITALIDAD_MAXIMA)
        self.assertTrue(resultado['en_gracia'])


class TestDecaimientoGradual(VitalidadJoiBase):
    def test_decae_progresivamente_tras_la_gracia(self):
        self._registrar_actividad(hace_dias=10)
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertFalse(resultado['en_gracia'])
        self.assertLess(resultado['valor'], VITALIDAD_MAXIMA)
        self.assertGreater(resultado['valor'], VITALIDAD_MINIMA)
        self.assertEqual(resultado['nivel_visual'], 'bajando')

    def test_mas_dias_inactivo_nunca_sube_la_vitalidad(self):
        self._registrar_actividad(hace_dias=4)
        v4 = calcular_vitalidad_joi(self.cliente, HOY)['valor']
        self._registrar_actividad.__self__  # no-op, mantiene el mismo cliente
        # Simulamos más días inactivo evaluando en una fecha posterior
        resultado_8 = calcular_vitalidad_joi(self.cliente, HOY + timedelta(days=4))
        self.assertLessEqual(resultado_8['valor'], v4)


class TestSueloMinimoNuncaCero(VitalidadJoiBase):
    def test_muy_inactivo_toca_suelo_pero_no_cero(self):
        self._registrar_actividad(hace_dias=60)
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertEqual(resultado['valor'], VITALIDAD_MINIMA)
        self.assertEqual(resultado['nivel_visual'], 'hibernando')
        self.assertGreater(resultado['valor'], 0)


class TestRecuperacionInmediata(VitalidadJoiBase):
    def test_volver_a_entrenar_recupera_de_golpe(self):
        self._registrar_actividad(hace_dias=20)  # hibernando
        antes = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertEqual(antes['nivel_visual'], 'hibernando')

        self._registrar_actividad(hace_dias=0)  # entrena hoy
        despues = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertEqual(despues['valor'], VITALIDAD_MAXIMA)
        self.assertEqual(despues['nivel_visual'], 'plena')


class TestGraciaExtendidaPorRacha(VitalidadJoiBase):
    def test_racha_larga_alarga_la_gracia(self):
        # Racha de 14 días consecutivos terminando hace 3 días (gracia base = 2).
        # Sin racha, día 3 ya estaría fuera de gracia; con racha de 14 días
        # (2 semanas completas) la gracia se extiende y día 3 sigue protegido.
        for hace in range(3, 17):  # 14 días consecutivos, el más reciente hace 3 días
            self._registrar_actividad(hace_dias=hace)

        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        # racha_dias (la ACTUAL) es 0 porque hoy no hay actividad — la racha
        # se rompió hace 3 días. Lo que alarga la gracia es racha_referencia,
        # que mira la constancia que había justo antes de parar.
        self.assertEqual(resultado['racha_dias'], 0)
        self.assertEqual(resultado['racha_referencia'], 14)
        self.assertTrue(resultado['en_gracia'])
        self.assertEqual(resultado['valor'], VITALIDAD_MAXIMA)


class TestNoInterfiereConEstadoAtencion(VitalidadJoiBase):
    def test_no_importa_ni_toca_determinar_estado_habitacion_joi(self):
        """Smoke test: calcular_vitalidad_joi es autónomo, no debe importar
        ni depender de la máquina de estados SILENCIO/OBSERVANDO/PRESENTE/
        PROTEGIENDO."""
        self._registrar_actividad(hace_dias=2)
        resultado = calcular_vitalidad_joi(self.cliente, HOY)
        self.assertNotIn('joi_estado', resultado)
        self.assertNotIn('joi_motivo', resultado)
