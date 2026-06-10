"""
Phase 28.1 — Tests for per-exercise injury progression brake.

Rule: Ante lesión, el sistema no pasa por encima de una señal de cuidado.
La progresión automática propone; la lesión activa frena ejercicios afectados.

Checklist:
1.  Sin lesión: entrenamiento no modificado.
2.  Con lesión pero sin tags_restringidos: no bloquea ningún ejercicio.
3.  Ejercicio con risk_tags coincidentes → progresion_bloqueada=True.
4.  Ejercicio sin risk_tags → no bloqueado.
5.  Ejercicio ya bloqueado por freno contextual → motivo no sobreescrito.
6.  AGUDA/SUB_AGUDA → motivo_bloqueo='lesion_activa'.
7.  RETORNO → motivo_bloqueo='lesion_retorno'.
8.  motivo_bloqueo_lesion=True en ejercicios frenados por lesión.
9.  Ejercicio no afectado en misma sesión → libre (no bloqueado).
10. peso_kg_propuesto guardado al bloquear (para auditoría).
11. RECUPERADO → no bloquea nada.
12. Sin ejercicios → devuelve entrenamiento sin modificar.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.services.progresion_contextual_service import (
    aplicar_freno_lesion,
    _obtener_info_lesion,
)


class FrenoLesionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_freno28', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestFreno28', 'dias_disponibles': 4},
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_lesion(self, fase='RETORNO', tags=None, activa=True):
        from hyrox.models import UserInjury
        tags_val = tags if tags is not None else ['flexion_rodilla_profunda', 'impacto_vertical']
        return UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase=fase,
            activa=activa,
            tags_restringidos=tags_val,
        )

    def _entrenam(self, ejercicios):
        return {'ejercicios': ejercicios}

    def _ej(self, nombre='Sentadilla', risk_tags=None, peso_kg=90.0, bloqueado=False, motivo=None):
        return {
            'nombre': nombre,
            'peso_kg': peso_kg,
            'risk_tags': risk_tags if risk_tags is not None else ['flexion_rodilla_profunda'],
            'progresion_bloqueada': bloqueado,
            'motivo_bloqueo': motivo,
            'tipo_ejercicio': 'compuesto_principal',
            'grupo_muscular': 'Cuadriceps',
        }


# ── Cases 1-2: sin efecto ─────────────────────────────────────────────────────

class TestCase1_SinLesion(FrenoLesionBase):
    def test_sin_lesion_entrenamiento_no_cambia(self):
        entreno = self._entrenam([self._ej()])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertFalse(result['ejercicios'][0]['progresion_bloqueada'])

    def test_sin_lesion_no_cambia_peso(self):
        entreno = self._entrenam([self._ej(peso_kg=90.0)])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'][0]['peso_kg'], 90.0)


class TestCase2_SinTags(FrenoLesionBase):
    def test_lesion_sin_tags_no_bloquea(self):
        self._crear_lesion(tags=[])
        entreno = self._entrenam([self._ej()])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertFalse(result['ejercicios'][0]['progresion_bloqueada'])


# ── Cases 3-4: bloqueo selectivo ─────────────────────────────────────────────

class TestCase3_EjercicioAfectado(FrenoLesionBase):
    def test_ejercicio_con_tags_coincidentes_bloqueado(self):
        self._crear_lesion(fase='RETORNO', tags=['flexion_rodilla_profunda'])
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertTrue(result['ejercicios'][0]['progresion_bloqueada'])

    def test_peso_propuesto_guardado(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(peso_kg=90.0, risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        # peso_kg_propuesto should be the original proposed weight
        self.assertEqual(result['ejercicios'][0]['peso_kg_propuesto'], 90.0)


class TestCase4_EjercicioNoAfectado(FrenoLesionBase):
    def test_ejercicio_sin_tags_coincidentes_libre(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        # Exercise has 'hombro_inestable' — no overlap
        entreno = self._entrenam([self._ej(risk_tags=['hombro_inestable'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertFalse(result['ejercicios'][0]['progresion_bloqueada'])

    def test_solo_ejercicios_afectados_se_frenan(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = self._entrenam([
            self._ej('Sentadilla', risk_tags=['flexion_rodilla_profunda'], peso_kg=90.0),
            self._ej('Press banca', risk_tags=['hombro_inestable'], peso_kg=80.0),
        ])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertTrue(result['ejercicios'][0]['progresion_bloqueada'])
        self.assertFalse(result['ejercicios'][1]['progresion_bloqueada'])


# ── Case 5: respeta freno contextual ─────────────────────────────────────────

class TestCase5_RespetaFrenoContextual(FrenoLesionBase):
    def test_ejercicio_ya_bloqueado_no_cambia_motivo(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([
            self._ej(risk_tags=['flexion_rodilla_profunda'],
                     bloqueado=True, motivo='carga_alta_semanal')
        ])
        result = aplicar_freno_lesion(self.cliente, entreno)
        # Motivo should remain the original (contextual brake wins)
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'carga_alta_semanal')


# ── Cases 6-7: motivo por fase ────────────────────────────────────────────────

class TestCase6_MotivoAguda(FrenoLesionBase):
    def test_aguda_motivo_lesion_activa(self):
        self._crear_lesion(fase='AGUDA')
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'lesion_activa')

    def test_sub_aguda_motivo_lesion_activa(self):
        self._crear_lesion(fase='SUB_AGUDA')
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'lesion_activa')


class TestCase7_MotivoRetorno(FrenoLesionBase):
    def test_retorno_motivo_lesion_retorno(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'lesion_retorno')


# ── Case 8: flag motivo_bloqueo_lesion ───────────────────────────────────────

class TestCase8_Flag(FrenoLesionBase):
    def test_motivo_bloqueo_lesion_true(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertTrue(result['ejercicios'][0].get('motivo_bloqueo_lesion'))

    def test_ejercicio_no_afectado_flag_false(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = self._entrenam([self._ej(risk_tags=['hombro_inestable'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertFalse(result['ejercicios'][0].get('motivo_bloqueo_lesion'))


# ── Cases 9-10: ejercicio libre + peso_propuesto ──────────────────────────────

class TestCase9_EjercicioLibre(FrenoLesionBase):
    def test_ejercicio_sin_riesgo_en_misma_sesion_libre(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = self._entrenam([
            self._ej('Sentadilla', risk_tags=['flexion_rodilla_profunda']),
            self._ej('Curl bíceps', risk_tags=[]),
            self._ej('Press banca', risk_tags=['hombro_inestable']),
        ])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertTrue(result['ejercicios'][0]['progresion_bloqueada'])
        self.assertFalse(result['ejercicios'][1]['progresion_bloqueada'])
        self.assertFalse(result['ejercicios'][2]['progresion_bloqueada'])


class TestCase10_PesoPropuesto(FrenoLesionBase):
    def test_peso_propuesto_original_guardado(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(peso_kg=100.0, risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        ej = result['ejercicios'][0]
        # Original weight is preserved as propuesto
        self.assertEqual(ej.get('peso_kg_propuesto'), 100.0)


# ── Case 11: RECUPERADO excluido ─────────────────────────────────────────────

class TestCase11_Recuperado(FrenoLesionBase):
    def test_lesion_recuperada_no_bloquea(self):
        from hyrox.models import UserInjury
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='RECUPERADO',
            activa=False,
            tags_restringidos=['flexion_rodilla_profunda'],
        )
        entreno = self._entrenam([self._ej(risk_tags=['flexion_rodilla_profunda'])])
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertFalse(result['ejercicios'][0]['progresion_bloqueada'])


# ── Case 12: sin ejercicios ───────────────────────────────────────────────────

class TestCase12_SinEjercicios(FrenoLesionBase):
    def test_entrenamiento_sin_ejercicios_no_cambia(self):
        self._crear_lesion()
        entreno = {'ejercicios': []}
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'], [])

    def test_entrenamiento_none_devuelve_none(self):
        self._crear_lesion()
        result = aplicar_freno_lesion(self.cliente, None)
        self.assertIsNone(result)


# ── Case 13: el freno es un techo, no una sustitución ────────────────────────

class TestCase13_FrenoEsTechoNoSustitucion(FrenoLesionBase):
    """
    'conserva X' debe cumplir siempre X <= peso_kg_propuesto. Si el plan ya
    propuso un peso menor que el último registrado (p.ej. RPE alto), el
    freno por lesión no debe revertir esa bajada.
    """
    def test_no_sube_si_propuesto_ya_es_menor_que_ultimo_registrado(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(peso_kg=52.5, risk_tags=['flexion_rodilla_profunda'])])
        with patch('entrenos.services.progresion_contextual_service._obtener_peso_actual',
                   return_value=53.8):
            result = aplicar_freno_lesion(self.cliente, entreno)
        ej = result['ejercicios'][0]
        self.assertEqual(ej['peso_kg_propuesto'], 52.5)
        self.assertEqual(ej['peso_kg'], 52.5)

    def test_capa_a_ultimo_registrado_si_propuesto_es_mayor(self):
        self._crear_lesion(fase='RETORNO')
        entreno = self._entrenam([self._ej(peso_kg=55.0, risk_tags=['flexion_rodilla_profunda'])])
        with patch('entrenos.services.progresion_contextual_service._obtener_peso_actual',
                   return_value=52.5):
            result = aplicar_freno_lesion(self.cliente, entreno)
        ej = result['ejercicios'][0]
        self.assertEqual(ej['peso_kg_propuesto'], 55.0)
        self.assertEqual(ej['peso_kg'], 52.5)
