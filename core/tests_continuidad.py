"""
Phase Continuidad 1.0 — Servicio único de lectura de continuidad.

Contrato testeado:
  - Detección de nivel por días desde el último entreno de GYM.
  - Disciplina-consciente: fútbol/hyrox no resetean dias_sin_gym.
  - Descanso planificado no activa narrativa de pausa, pero sí prudencia física.
  - Recalibración (+21d) se detecta pero NO se ejecuta en 1.0.
  - Consolidación: el semáforo consume este servicio (fuente única), sin
    cambiar su salida visible ("No tienes que compensar").
  - Auditoría de lenguaje SEMÁNTICA (deuda prohibida, uso protector permitido).
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from core.continuidad import (
    evaluar_continuidad_entrenamiento,
    auditar_lenguaje_continuidad,
    NIVEL_NORMAL, NIVEL_LEVE, NIVEL_CLARA, NIVEL_LARGA, NIVEL_RECALIBRACION,
)
from core.daily_decision import DailyDecisionEngine as DDE

REF = date(2026, 6, 6)  # sábado, fecha de referencia fija para los tests


class ContinuidadBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_cont10', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _act(self, dias_atras, tipo='gym'):
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo=tipo, fecha=REF - timedelta(days=dias_atras),
        )

    def _lectura(self, **kw):
        return evaluar_continuidad_entrenamiento(self.cliente, fecha_ref=REF, **kw)


class TestNivelPorDias(ContinuidadBase):
    def test_sin_entrenos_es_normal_seguro(self):
        r = self._lectura()
        self.assertEqual(r['nivel'], NIVEL_NORMAL)
        self.assertIsNone(r['dias_sin_gym'])
        self.assertFalse(r['hay_pausa_significativa'])

    def test_2_dias_normal(self):
        self._act(2)
        self.assertEqual(self._lectura()['nivel'], NIVEL_NORMAL)

    def test_5_dias_leve(self):
        self._act(5)
        r = self._lectura()
        self.assertEqual(r['nivel'], NIVEL_LEVE)
        self.assertFalse(r['hay_pausa_significativa'])  # leve NO es pausa significativa

    def test_7_dias_clara(self):
        self._act(7)
        r = self._lectura()
        self.assertEqual(r['nivel'], NIVEL_CLARA)
        self.assertTrue(r['hay_pausa_significativa'])
        self.assertTrue(r['congelar_progresion'])

    def test_14_dias_larga(self):
        self._act(14)
        self.assertEqual(self._lectura()['nivel'], NIVEL_LARGA)

    def test_22_dias_recalibracion(self):
        self._act(22)
        r = self._lectura()
        self.assertEqual(r['nivel'], NIVEL_RECALIBRACION)
        # 1.0 detecta pero NO ejecuta recalibración: solo describe.
        self.assertEqual(r['fuente'], 'continuidad_service')


class TestDisciplinaConsciente(ContinuidadBase):
    def test_futbol_reciente_no_resetea_dias_sin_gym(self):
        self._act(7, tipo='gym')
        self._act(1, tipo='futbol')
        r = self._lectura()
        self.assertEqual(r['dias_sin_gym'], 7)
        self.assertEqual(r['dias_sin_actividad'], 1)
        self.assertEqual(r['nivel'], NIVEL_CLARA)

    def test_hyrox_no_resetea_dias_sin_gym(self):
        self._act(8, tipo='gym')
        self._act(1, tipo='hyrox')
        r = self._lectura()
        self.assertEqual(r['dias_sin_gym'], 8)
        self.assertEqual(r['nivel'], NIVEL_CLARA)


class TestDescansoPlanificado(ContinuidadBase):
    def test_descanso_planificado_no_activa_narrativa(self):
        self._act(7)
        r = self._lectura(es_descanso_plan=True)
        self.assertEqual(r['tipo'], 'descanso_planificado')
        self.assertFalse(r['activar_narrativa_pausa'])

    def test_descanso_planificado_mantiene_prudencia_fisica(self):
        self._act(14)
        r = self._lectura(es_descanso_plan=True)
        self.assertFalse(r['activar_narrativa_pausa'])   # narrativa: no ruptura
        self.assertTrue(r['aplicar_prudencia_retorno'])  # física: sí prudencia
        self.assertTrue(r['congelar_progresion'])

    def test_pausa_no_declarada_si_no_planificada(self):
        self._act(7)
        r = self._lectura()
        self.assertEqual(r['tipo'], 'pausa_no_declarada')
        self.assertTrue(r['activar_narrativa_pausa'])


class TestConsolidacionSemaforo(ContinuidadBase):
    def test_semaforo_delega_en_continuidad_service(self):
        self._act(8)
        with patch('core.continuidad.evaluar_continuidad_entrenamiento',
                   wraps=evaluar_continuidad_entrenamiento) as spy:
            DDE._calcular_ausencia_dias(self.cliente)
        self.assertTrue(spy.called, "el semáforo debe consumir continuidad_service")

    def test_paridad_ausencia_dias(self):
        # Misma salida que el cálculo histórico: días desde la última actividad.
        self._act(8, tipo='gym')
        self._act(3, tipo='futbol')
        self.assertEqual(DDE._calcular_ausencia_dias(self.cliente), 3)

    def test_semaforo_conserva_mensaje_no_compensar(self):
        # Ausencia >= 5 → estado 'volver' con mensaje protector intacto.
        self._act(8)
        bio = {'has_data': False, 'hrv_ms': None, 'energia': None}
        with patch('core.bio_context.BioContextProvider.get_bio_signals', return_value=bio), \
             patch('core.bio_context.BioContextProvider.get_readiness_score', return_value={'score': 0.8}), \
             patch('entrenos.services.services.EstadisticasService.analizar_acwr_unificado',
                   return_value={'acwr_actual': 1.0}):
            e = DDE.get_estado_hoy(self.cliente)
        self.assertEqual(e['estado'], 'volver')
        self.assertIn('No tienes que compensar', e['mensaje'])


class TestAuditoriaLenguaje(TestCase):
    def test_uso_protector_permitido(self):
        self.assertEqual(auditar_lenguaje_continuidad("No tienes que compensar la pausa."), [])
        self.assertEqual(auditar_lenguaje_continuidad("Vuelve con margen, sin compensar de golpe."), [])

    def test_expresiones_de_deuda_prohibidas(self):
        self.assertIn('recuperar lo perdido',
                      auditar_lenguaje_continuidad("Hoy toca recuperar lo perdido."))
        self.assertIn('tienes que compensar',
                      auditar_lenguaje_continuidad("Ahora tienes que compensar los días."))
        self.assertIn('ponerte al día',
                      auditar_lenguaje_continuidad("Hay que ponerte al día."))
