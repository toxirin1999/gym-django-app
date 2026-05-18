"""
Phase 28.3 — Convivencia de frenos: auditoría de jerarquía.

Confirma que cuando coinciden varias causas, no se pisan visual ni semánticamente.

Jerarquía de frenos (prioridad de motivo_bloqueo):
  1. aplicar_freno_contextual  → intervención / modo_esencial / carga/patrón
  2. aplicar_freno_lesion      → lesión (solo si ejercicio NO ya bloqueado)
  Paralelo: _aplicar_preferencia_activa / _aplicar_aviso_lesion (no modifican motivo)

Casos auditados:
1.  Freno contextual + lesión retorno en mismo ejercicio
    → motivo_bloqueo = contextual (no sobreescrito)
    → lesion_aviso en workout card existe igualmente
2.  Lesión aguda (causa_principal='lesion') + preferencia activa
    → preferencia NO aparece (causa bloqueante gana)
3.  Modo esencial (mantener_carga) + lesión retorno
    → ejercicios bloqueados por esencial, no por lesión
    → lesion_aviso sigue visible en workout card
4.  Freno contextual global + ejercicio sin risk_tags de lesión
    → bloqueado por contexto, motivo NO es lesión
5.  Lesión rodilla afecta sentadilla, NO afecta press banca
    → selectividad correcta
6.  Lesión aguda → es_bloqueante=True en aviso
7.  Lesión retorno + freno contextual: lesion_aviso aparece aunque esté bloqueado
8.  Preferencia activa aparece con lesión RETORNO (no aguda)
9.  Dos lesiones: solo primera con intersección dispara aviso
10. Sin nada activo: entrenamiento pasa limpio
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import PreferenciaPlanAprendida
from entrenos.services.progresion_contextual_service import aplicar_freno_lesion
from entrenos.services.sesion_recomendada import (
    _aplicar_aviso_lesion,
    _aplicar_preferencia_activa,
    _detectar_riesgo_lesion,
)


class ConvivenciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_conv283', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestConv283', 'dias_disponibles': 4},
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_lesion(self, fase='RETORNO', tags=None, zona='Rodilla'):
        from hyrox.models import UserInjury
        tags_val = tags if tags is not None else ['flexion_rodilla_profunda']
        return UserInjury.objects.create(
            cliente=self.cliente, zona_afectada=zona,
            fase=fase, activa=True, tags_restringidos=tags_val,
        )

    def _ej(self, nombre='Sentadilla', risk_tags=None, bloqueado=False,
             motivo='', peso=90.0):
        return {
            'nombre': nombre,
            'risk_tags': risk_tags if risk_tags is not None else ['flexion_rodilla_profunda'],
            'progresion_bloqueada': bloqueado,
            'motivo_bloqueo': motivo,
            'peso_kg': peso,
            'tipo_ejercicio': 'compuesto_principal',
            'grupo_muscular': 'Cuadriceps',
        }

    def _decision(self, entrenamiento=None, causa='sesion_hoy', estado='entrenar'):
        return {
            'tipo': 'programada_hoy', 'estado': estado,
            'sesion_programada': None,
            'entrenamiento': entrenamiento or {'ejercicios': []},
            'mensaje': '', 'causa_principal': causa,
            'modo_reducido': False, 'distribucion_aviso': None,
            'contexto_fisico': {'preferencias_activas': []},
        }


# ── Case 1: contextual gana sobre lesión ──────────────────────────────────────

class TestCase1_ContextualGana(ConvivenciaBase):
    def test_ejercicio_bloqueado_por_contextual_no_cambia_motivo(self):
        self._crear_lesion(fase='RETORNO')
        # Exercise already blocked by contextual brake (e.g., intervención)
        entreno = {'ejercicios': [
            self._ej(bloqueado=True, motivo='carga_alta_semanal')
        ]}
        result = aplicar_freno_lesion(self.cliente, entreno)
        # Motivo must remain the contextual one
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'carga_alta_semanal')

    def test_ejercicio_bloqueado_por_intervencion_no_cambia_motivo(self):
        self._crear_lesion(fase='RETORNO')
        entreno = {'ejercicios': [
            self._ej(bloqueado=True, motivo='intervencion_no_subir_cargas')
        ]}
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertEqual(result['ejercicios'][0]['motivo_bloqueo'], 'intervencion_no_subir_cargas')

    def test_lesion_aviso_existe_aunque_freno_contextual_activo(self):
        """lesion_aviso in workout card survives even when contextual brake blocks the session."""
        self._crear_lesion(fase='RETORNO')
        entreno = {'ejercicios': [
            self._ej(risk_tags=['flexion_rodilla_profunda'])
        ]}
        decision = self._decision(entrenamiento=entreno, causa='carga_alta_semanal')
        decision['contexto_fisico'] = {'preferencias_activas': [], 'lesion_activa': False}
        result = _aplicar_aviso_lesion(self.cliente, decision, date(2026, 5, 24))
        # lesion_aviso should still appear in the workout card
        self.assertIn('lesion_aviso', result)
        self.assertIsNotNone(result['lesion_aviso'])


# ── Case 2: lesión aguda bloquea preferencia ─────────────────────────────────

class TestCase2_AgudaBloqueoPreferencia(ConvivenciaBase):
    def test_preferencia_no_aplica_con_causa_lesion(self):
        with patch('joi.services.generar_mensaje_joi'):
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=date(2026, 5, 24),
                ultima_confirmacion=date(2026, 5, 24),
            )
        decision = self._decision(
            causa='lesion', estado='recuperar',
            entrenamiento={'ejercicios': [self._ej()]},
        )
        decision['contexto_fisico'] = {
            'preferencias_activas': [PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            'futbol_reciente': True, 'lesion_activa': True, 'lesion_fase': 'AGUDA',
            'energia_baja': False, 'energia_valor': None,
            'readiness_bajo': False, 'readiness_valor': None,
        }
        result = _aplicar_preferencia_activa(self.cliente, decision, date(2026, 5, 24))
        # Preference must not fire when injury is the dominant cause
        self.assertNotIn('preferencia_aplicada', result)

    def test_preferencia_si_aplica_con_lesion_retorno(self):
        """RETORNO injury does NOT block the session — preference can still fire."""
        with patch('joi.services.generar_mensaje_joi'):
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=date(2026, 5, 24),
                ultima_confirmacion=date(2026, 5, 24),
            )
        decision = self._decision(
            causa='futbol_reciente', estado='posponer',
            entrenamiento={'ejercicios': [
                self._ej(risk_tags=['flexion_rodilla_profunda']),
            ]},
        )
        decision['contexto_fisico'] = {
            'preferencias_activas': [PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            'futbol_reciente': True, 'lesion_activa': False, 'lesion_fase': 'RETORNO',
            'energia_baja': False, 'energia_valor': None,
            'readiness_bajo': False, 'readiness_valor': None,
        }
        result = _aplicar_preferencia_activa(self.cliente, decision, date(2026, 5, 24))
        # RETORNO doesn't block the session → preference can coexist
        self.assertIn('preferencia_aplicada', result)


# ── Case 3: modo esencial + lesión retorno ────────────────────────────────────

class TestCase3_EsencialPlusLesion(ConvivenciaBase):
    def test_modo_esencial_bloquea_todos_lesion_no_sobreescribe(self):
        self._crear_lesion(fase='RETORNO')
        # Simulate aplicar_freno_contextual with modo_reducido → mantener_carga
        ejercicios = [
            self._ej('Sentadilla', risk_tags=['flexion_rodilla_profunda'],
                     bloqueado=True, motivo='modo_reducido'),
            self._ej('Press banca', risk_tags=[],
                     bloqueado=True, motivo='modo_reducido'),
        ]
        entreno = {'ejercicios': ejercicios}
        result = aplicar_freno_lesion(self.cliente, entreno)
        # Both blocked by esencial mode — lesion freno skips them
        for ej in result['ejercicios']:
            self.assertEqual(ej['motivo_bloqueo'], 'modo_reducido')

    def test_lesion_aviso_visible_con_modo_esencial(self):
        """lesion_aviso in workout card is shown even when session is in esencial mode."""
        self._crear_lesion(fase='RETORNO')
        entreno = {'ejercicios': [self._ej(risk_tags=['flexion_rodilla_profunda'])]}
        decision = self._decision(entrenamiento=entreno, causa='energia_baja', estado='version_reducida')
        decision['contexto_fisico'] = {'preferencias_activas': [], 'lesion_activa': False}
        result = _aplicar_aviso_lesion(self.cliente, decision, date(2026, 5, 24))
        self.assertIn('lesion_aviso', result)


# ── Case 4: freno contextual + ejercicio sin risk_tags de lesión ──────────────

class TestCase4_ContextualGlobalEjSinRiesgo(ConvivenciaBase):
    def test_ejercicio_bloqueado_por_contexto_no_tiene_motivo_lesion(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        # Exercise blocked by contextual (e.g., carga_alta_semanal) but NO knee tags
        entreno = {'ejercicios': [
            self._ej('Press banca', risk_tags=['hombro_inestable'],
                     bloqueado=True, motivo='carga_alta_semanal'),
        ]}
        result = aplicar_freno_lesion(self.cliente, entreno)
        ej = result['ejercicios'][0]
        self.assertEqual(ej['motivo_bloqueo'], 'carga_alta_semanal')
        self.assertFalse(ej.get('motivo_bloqueo_lesion', False))


# ── Case 5: selectividad — rodilla no afecta press banca ─────────────────────

class TestCase5_Selectividad(ConvivenciaBase):
    def test_lesion_rodilla_no_bloquea_press_banca(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda', 'impacto_vertical'])
        entreno = {'ejercicios': [
            self._ej('Sentadilla', risk_tags=['flexion_rodilla_profunda']),
            self._ej('Press banca', risk_tags=['hombro_inestable']),
        ]}
        result = aplicar_freno_lesion(self.cliente, entreno)
        self.assertTrue(result['ejercicios'][0]['progresion_bloqueada'])
        self.assertFalse(result['ejercicios'][1]['progresion_bloqueada'])

    def test_lesion_aviso_no_incluye_ejercicios_sin_interseccion(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = {'ejercicios': [
            self._ej('Press banca', risk_tags=['hombro_inestable']),
        ]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNone(aviso)


# ── Case 6: lesión aguda es_bloqueante ────────────────────────────────────────

class TestCase6_AguadaEsBloqueante(ConvivenciaBase):
    def test_aguda_es_bloqueante_true(self):
        self._crear_lesion(fase='AGUDA')
        entreno = {'ejercicios': [self._ej(risk_tags=['flexion_rodilla_profunda'])]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNotNone(aviso)
        self.assertTrue(aviso['es_bloqueante'])

    def test_retorno_es_bloqueante_false(self):
        self._crear_lesion(fase='RETORNO')
        entreno = {'ejercicios': [self._ej(risk_tags=['flexion_rodilla_profunda'])]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNotNone(aviso)
        self.assertFalse(aviso['es_bloqueante'])


# ── Case 9: dos lesiones — primera con intersección dispara ──────────────────

class TestCase9_DosLesiones(ConvivenciaBase):
    def test_dos_lesiones_primera_coincidente_gana(self):
        from hyrox.models import UserInjury
        # First injury: knee
        UserInjury.objects.create(
            cliente=self.cliente, zona_afectada='Rodilla', fase='RETORNO',
            activa=True, tags_restringidos=['flexion_rodilla_profunda'],
        )
        # Second injury: shoulder (no intersection with sentadilla)
        UserInjury.objects.create(
            cliente=self.cliente, zona_afectada='Hombro', fase='RETORNO',
            activa=True, tags_restringidos=['hombro_inestable'],
        )
        entreno = {'ejercicios': [self._ej(risk_tags=['flexion_rodilla_profunda'])]}
        result = aplicar_freno_lesion(self.cliente, entreno)
        ej = result['ejercicios'][0]
        self.assertTrue(ej['progresion_bloqueada'])
        # Motivo should be lesion_retorno (knee matched)
        self.assertEqual(ej['motivo_bloqueo'], 'lesion_retorno')


# ── Case 10: sin nada activo — pasa limpio ───────────────────────────────────

class TestCase10_SinNadaActivo(ConvivenciaBase):
    def test_sin_lesion_sin_frenos_entrenamiento_libre(self):
        ejercicios = [
            self._ej('Sentadilla', risk_tags=['flexion_rodilla_profunda'], bloqueado=False),
            self._ej('Press banca', risk_tags=[], bloqueado=False),
        ]
        entreno = {'ejercicios': ejercicios}
        result = aplicar_freno_lesion(self.cliente, entreno)
        for ej in result['ejercicios']:
            self.assertFalse(ej['progresion_bloqueada'])

    def test_sin_lesion_sin_preferencia_sin_aviso(self):
        entreno = {'ejercicios': [self._ej()]}
        decision = self._decision(entrenamiento=entreno)
        decision['contexto_fisico'] = {'preferencias_activas': [], 'lesion_activa': False}
        result = _aplicar_aviso_lesion(self.cliente, decision, date(2026, 5, 24))
        self.assertNotIn('lesion_aviso', result)
        result2 = _aplicar_preferencia_activa(self.cliente, decision, date(2026, 5, 24))
        self.assertNotIn('preferencia_aplicada', result2)
