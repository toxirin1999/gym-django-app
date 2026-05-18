"""
Phase 28.1 — Tests for injury safety layer (lesion_aviso).

Rule: The system does not improvise a new routine; first it protects the decision.
lesion_aviso is ALWAYS secondary — it never changes estado or causa_principal.

Checklist:
1.  No aviso when no active injury.
2.  No aviso when injury has no risk tags.
3.  No aviso when session has no exercises.
4.  Aviso fires for RETORNO injury + matching exercise risk_tags.
5.  Aviso fires for AGUDA injury + matching exercise risk_tags (supplementary).
6.  RECUPERADO injury never triggers aviso.
7.  No aviso when exercise risk_tags don't intersect injury tags.
8.  aviso does NOT change estado or causa_principal.
9.  aviso contains: zona, fase, ejercicios_en_riesgo, mensaje.
10. AGUDA aviso has es_bloqueante=True; RETORNO has es_bloqueante=False.
11. Mensaje uses soft language — no "nunca", "debes", "prohibido".
12. No aviso when entrenamiento has no exercises (descanso).
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.services.sesion_recomendada import (
    _aplicar_aviso_lesion,
    _detectar_riesgo_lesion,
)


class LesionAvisoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_lesion28', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestL28', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 23)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_lesion(self, fase='RETORNO', tags=None):
        from hyrox.models import UserInjury
        tags_val = tags if tags is not None else ['flexion_rodilla_profunda', 'impacto_vertical']
        return UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla izquierda',
            fase=fase,
            activa=True,
            tags_restringidos=tags_val,
        )

    def _entrenamiento_pierna(self, con_tags=True):
        return {
            'ejercicios': [
                {
                    'nombre': 'Sentadilla trasera',
                    'grupo_muscular': 'Cuadriceps',
                    'risk_tags': ['flexion_rodilla_profunda', 'triple_extension_explosiva'] if con_tags else [],
                },
                {
                    'nombre': 'Prensa de pierna',
                    'grupo_muscular': 'Cuadriceps',
                    'risk_tags': ['flexion_rodilla_profunda'] if con_tags else [],
                },
            ]
        }

    def _entrenamiento_tren_superior(self):
        return {
            'ejercicios': [
                {'nombre': 'Press banca', 'grupo_muscular': 'Pecho', 'risk_tags': ['hombro_inestable']},
                {'nombre': 'Remo con barra', 'grupo_muscular': 'Espalda', 'risk_tags': []},
            ]
        }

    def _decision_base(self, entrenamiento=None, causa='sesion_hoy', estado='entrenar'):
        return {
            'tipo': 'programada_hoy', 'estado': estado,
            'sesion_programada': None,
            'entrenamiento': entrenamiento or {},
            'mensaje': 'Sesión de hoy.', 'causa_principal': causa,
            'modo_reducido': False, 'distribucion_aviso': None,
            'contexto_fisico': {},
        }


# ── Cases 1-3: no aviso ───────────────────────────────────────────────────────

class TestCase1_SinLesion(LesionAvisoBase):
    def test_no_aviso_sin_lesion(self):
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNone(aviso)


class TestCase2_SinTags(LesionAvisoBase):
    def test_no_aviso_si_lesion_sin_tags(self):
        self._crear_lesion(tags=[])
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNone(aviso)


class TestCase3_SinEjercicios(LesionAvisoBase):
    def test_no_aviso_sin_ejercicios(self):
        self._crear_lesion()
        aviso = _detectar_riesgo_lesion(self.cliente, {'ejercicios': []})
        self.assertIsNone(aviso)

    def test_no_aviso_entrenamiento_vacio(self):
        self._crear_lesion()
        aviso = _detectar_riesgo_lesion(self.cliente, {})
        self.assertIsNone(aviso)


# ── Cases 4-5: aviso fires ────────────────────────────────────────────────────

class TestCase4_RetornoConRiesgo(LesionAvisoBase):
    def test_aviso_retorno_con_ejercicios_riesgosos(self):
        self._crear_lesion(fase='RETORNO')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNotNone(aviso)
        self.assertIn('Rodilla izquierda', aviso['zona'])
        self.assertGreater(len(aviso['ejercicios_en_riesgo']), 0)

    def test_aviso_retorno_no_es_bloqueante(self):
        self._crear_lesion(fase='RETORNO')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertFalse(aviso['es_bloqueante'])


class TestCase5_AguadaConRiesgo(LesionAvisoBase):
    def test_aviso_aguda_es_bloqueante(self):
        self._crear_lesion(fase='AGUDA')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNotNone(aviso)
        self.assertTrue(aviso['es_bloqueante'])

    def test_aviso_sub_aguda_es_bloqueante(self):
        self._crear_lesion(fase='SUB_AGUDA')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNotNone(aviso)
        self.assertTrue(aviso['es_bloqueante'])


# ── Case 6: RECUPERADO nunca dispara ─────────────────────────────────────────

class TestCase6_Recuperado(LesionAvisoBase):
    def test_lesion_recuperada_no_dispara_aviso(self):
        from hyrox.models import UserInjury
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='RECUPERADO',
            activa=False,  # también inactiva
            tags_restringidos=['flexion_rodilla_profunda'],
        )
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNone(aviso)


# ── Case 7: sin intersección de tags ─────────────────────────────────────────

class TestCase7_SinInterseccion(LesionAvisoBase):
    def test_no_aviso_si_tags_no_coinciden(self):
        self._crear_lesion(tags=['hombro_inestable', 'manguito_rotador'])
        # Session has flexion_rodilla_profunda — no overlap with shoulder tags
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNone(aviso)

    def test_no_aviso_tren_superior_con_lesion_rodilla(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda', 'impacto_vertical'])
        # Tren superior exercises don't have knee tags
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_tren_superior())
        self.assertIsNone(aviso)


# ── Case 8: no cambia estado ni causa ────────────────────────────────────────

class TestCase8_NoAlteraDecision(LesionAvisoBase):
    def test_aviso_no_cambia_estado(self):
        self._crear_lesion(fase='RETORNO')
        decision = self._decision_base(
            entrenamiento=self._entrenamiento_pierna(),
            estado='entrenar', causa='sesion_hoy',
        )
        result = _aplicar_aviso_lesion(self.cliente, decision, self.hoy)
        self.assertEqual(result['estado'], 'entrenar')
        self.assertEqual(result['causa_principal'], 'sesion_hoy')
        self.assertIn('lesion_aviso', result)

    def test_aviso_no_cambia_estado_recuperar(self):
        # Even when estado is already 'recuperar', aviso adds info without changing it
        self._crear_lesion(fase='AGUDA')
        decision = self._decision_base(
            entrenamiento=self._entrenamiento_pierna(),
            estado='recuperar', causa='lesion',
        )
        result = _aplicar_aviso_lesion(self.cliente, decision, self.hoy)
        self.assertEqual(result['estado'], 'recuperar')
        self.assertEqual(result['causa_principal'], 'lesion')


# ── Case 9: campos del aviso ─────────────────────────────────────────────────

class TestCase9_CamposAviso(LesionAvisoBase):
    def test_aviso_tiene_campos_requeridos(self):
        self._crear_lesion(fase='RETORNO')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIsNotNone(aviso)
        for campo in ['zona', 'fase', 'ejercicios_en_riesgo', 'mensaje', 'es_bloqueante']:
            self.assertIn(campo, aviso, msg=f"Falta campo '{campo}' en aviso")

    def test_aviso_identifica_ejercicios_correctos(self):
        self._crear_lesion(fase='RETORNO', tags=['flexion_rodilla_profunda'])
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIn('Sentadilla trasera', aviso['ejercicios_en_riesgo'])
        self.assertIn('Prensa de pierna', aviso['ejercicios_en_riesgo'])


# ── Case 10: es_bloqueante correcto por fase ─────────────────────────────────

class TestCase10_EsBloqueante(LesionAvisoBase):
    def test_retorno_no_es_bloqueante(self):
        self._crear_lesion(fase='RETORNO')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertFalse(aviso['es_bloqueante'])

    def test_aguda_es_bloqueante(self):
        self._crear_lesion(fase='AGUDA')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertTrue(aviso['es_bloqueante'])


# ── Case 11: lenguaje blando en el mensaje ───────────────────────────────────

class TestCase11_LenguajeBlando(LesionAvisoBase):
    def test_mensaje_sin_absolutas(self):
        for fase in ['AGUDA', 'SUB_AGUDA', 'RETORNO']:
            self._crear_lesion(fase=fase)
            aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
            if aviso:
                texto = aviso['mensaje'].lower()
                for palabra in ['nunca', 'prohibido', 'jamás', 'imposible']:
                    self.assertNotIn(palabra, texto,
                                     msg=f"Fase {fase}: mensaje usa '{palabra}'")
            # Clean up for next iteration
            from hyrox.models import UserInjury
            UserInjury.objects.filter(cliente=self.cliente).delete()

    def test_mensaje_menciona_zona(self):
        self._crear_lesion(fase='RETORNO')
        aviso = _detectar_riesgo_lesion(self.cliente, self._entrenamiento_pierna())
        self.assertIn('Rodilla', aviso['mensaje'])


# ── Case 12: descanso no dispara ─────────────────────────────────────────────

class TestCase12_DescansoNodispara(LesionAvisoBase):
    def test_sin_entrenamiento_no_hay_aviso(self):
        self._crear_lesion()
        aviso = _detectar_riesgo_lesion(self.cliente, None)
        self.assertIsNone(aviso)
