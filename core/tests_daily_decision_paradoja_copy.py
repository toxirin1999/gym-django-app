"""
Phase 62D — Copy humano del semáforo: Paradoja A/B accionables.

Pendiente desde Phase 62 (dashboard): "Esa energía que sientes hoy puede
ser real. Pero los datos piden calma. Escucha a ambos." es filosófico
pero no dice qué hacer. Objetivo: que el mensaje de Paradoja A/B indique
una acción concreta, coherente con recomendacion_gym del mismo estado.

No cambia estado/causa/tipo_recuperar/datos_raw — solo el texto de
_PARADOJA_A (ahora dividido por estado) y _PARADOJA_B.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from core.daily_decision import DailyDecisionEngine as DDE


_ACT_CTX_NEUTRO = {
    'sesiones_gym_semana': 0,
    'sesiones_hyrox_semana': 0,
    'sesiones_semana_total': 0,
    'actividad_semana': {},
    'ultima_actividad': None,
    'racha_dias': 0,
    'fase_plan': None,
}


class TestParadojaCopyAccionable(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('tester_62d', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _estado(self, *, readiness, acwr=None, energia=None):
        bio = {
            'has_data': energia is not None, 'hrv_ms': None,
            'energia': energia, 'horas_sueno': None,
        }
        with patch('core.daily_decision.BioContextProvider.get_bio_signals', return_value=bio), \
             patch('core.daily_decision.BioContextProvider.get_readiness_score',
                   return_value={'score': readiness}), \
             patch('core.daily_decision.get_actividad_context', return_value=_ACT_CTX_NEUTRO), \
             patch('entrenos.services.services.EstadisticasService.analizar_acwr_unificado',
                   return_value={'acwr_actual': acwr}):
            return DDE.get_estado_hoy(self.cliente)

    # ── Paradoja A + RECUPERAR (fatiga real + energía alta) ──────────────
    def test_paradoja_a_recuperar_es_accionable(self):
        e = self._estado(readiness=0.30, energia=8)
        self.assertEqual(e['causa'], 'fatiga')
        self.assertEqual(e['paradoja'], 'A')
        self.assertEqual(e['mensaje'], DDE._PARADOJA_A_RECUPERAR)
        msg = e['mensaje'].lower()
        self.assertTrue('movilidad' in msg or 'descanso' in msg,
                        "el mensaje debe indicar la acción, no solo 'escucha a ambos'")

    # ── Paradoja A + SOSTENER (carga alta + energía alta) ────────────────
    def test_paradoja_a_sostener_es_accionable(self):
        e = self._estado(readiness=0.65, acwr=1.8, energia=8)
        self.assertEqual(e['causa'], 'carga')
        self.assertEqual(e['estado'], DDE.SOSTENER)
        self.assertEqual(e['paradoja'], 'A')
        self.assertEqual(e['mensaje'], DDE._PARADOJA_A_SOSTENER)
        self.assertNotEqual(DDE._PARADOJA_A_RECUPERAR, DDE._PARADOJA_A_SOSTENER,
                             "RECUPERAR y SOSTENER deben tener copy distinto")

    # ── Paradoja B (empujar permitido + energía baja) ────────────────────
    def test_paradoja_b_es_accionable(self):
        e = self._estado(readiness=0.75, energia=3)
        self.assertEqual(e['estado'], DDE.EMPUJAR)
        self.assertEqual(e['paradoja'], 'B')
        self.assertEqual(e['mensaje'], DDE._PARADOJA_B)
        self.assertIn('muév', e['mensaje'].lower())

    # ── Regresión: sin paradoja, mensaje normal sin cambios ──────────────
    def test_sin_paradoja_mensaje_normal(self):
        e = self._estado(readiness=0.75, energia=None)
        self.assertIsNone(e['paradoja'])
        self.assertEqual(e['mensaje'], DDE._MENSAJES['empujar'])


class TestLimpiezaClavesMuertas(TestCase):
    """recuperar_movimiento nunca se alcanza: causa='descanso_plan' siempre
    se intercepta antes en _mensajes_causa/_gym_causa/_hyrox_causa."""

    def test_recuperar_movimiento_eliminado_de_mensajes(self):
        self.assertNotIn('recuperar_movimiento', DDE._MENSAJES)

    def test_recuperar_movimiento_eliminado_de_recomendaciones(self):
        self.assertNotIn('recuperar_movimiento', DDE._RECOMENDACIONES_GYM)
        self.assertNotIn('recuperar_movimiento', DDE._RECOMENDACIONES_HYROX)
