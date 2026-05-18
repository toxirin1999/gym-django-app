"""
Phase 24.1 — Tests for active preference inclining motor decisions.

Rule: A preference does not rewrite the plan; it inclines decisions
when the context allows it. It is always a secondary cause.

Hierarchy (safety > decision > recovery > preference > calendar):
  lesion > fatiga_alta > energia_baja/futbol > preferencia_activa > normal

Checklist (10 cases + 3 edge):
1.  Active preference appears in contexto_fisico['preferencias_activas'].
2.  Revoked preference does NOT appear.
3.  evitar_pierna_tras_futbol fires only when pierna + fútbol reciente.
4.  evitar_pierna_tras_futbol does NOT fire without fútbol reciente.
5.  evitar_pierna_tras_futbol does NOT fire when session has no leg exercises.
6.  Lesión overrides preference — preferencia_aplicada absent when lesión active.
7.  Fatiga alta overrides preference — preferencia_aplicada absent.
8.  Motor returns preferencia_aplicada without changing PlanificadorHelms.
9.  preferencia_aplicada mensaje uses soft language.
10. preferencia_aplicada does not change causa_principal.
11. No preferencia_aplicada when no active preferences.
12. menos_dias fires only for normal-priority sessions.
13. aligerar_dia fires when session has exercises.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, PreferenciaPlanAprendida, SesionProgramada
from entrenos.services.preferencias_service import crear_preferencia
from entrenos.services.sesion_recomendada import (
    _aplicar_preferencia_activa,
    _aplicar_contexto,
    _es_sesion_pierna,
    _obtener_contexto_fisico,
)


class PreferenciaMotorBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_motor24', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestMotor24', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 22)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_pref(self, tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL):
        return PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=tipo,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
            evidencia_count=2,
            descripcion='El plan intentará no colocar pierna tras el fútbol.',
        )

    def _decision_base(self, causa='sesion_hoy', estado='entrenar', entrenamiento=None,
                        sesion_programada=None):
        return {
            'tipo': 'programada_hoy',
            'estado': estado,
            'sesion_programada': sesion_programada,
            'entrenamiento': entrenamiento or {},
            'mensaje': 'Sesión prevista para hoy.',
            'causa_principal': causa,
            'modo_reducido': False,
            'distribucion_aviso': None,
            'contexto_fisico': {},
        }

    def _con_contexto(self, decision, prefs=None, futbol=False, lesion=False,
                      fatiga=False):
        ctx = {
            'lesion_activa': lesion,
            'lesion_fase': 'AGUDA' if lesion else None,
            'futbol_reciente': futbol,
            'energia_baja': False,
            'energia_valor': None,
            'readiness_bajo': fatiga,
            'readiness_valor': 40 if fatiga else None,
            'preferencias_activas': prefs or [],
        }
        decision = dict(decision)
        decision['contexto_fisico'] = ctx
        return decision

    def _entrenamiento_pierna(self):
        return {
            'ejercicios': [
                {'nombre': 'Sentadilla', 'grupo_muscular': 'Cuadriceps', 'tipo_ejercicio': 'compuesto_principal'},
                {'nombre': 'Prensa de pierna', 'grupo_muscular': 'Cuadriceps', 'tipo_ejercicio': 'accesorio'},
            ]
        }

    def _entrenamiento_tren_superior(self):
        return {
            'ejercicios': [
                {'nombre': 'Press banca', 'grupo_muscular': 'Pecho', 'tipo_ejercicio': 'compuesto_principal'},
                {'nombre': 'Remo con barra', 'grupo_muscular': 'Espalda', 'tipo_ejercicio': 'compuesto_principal'},
            ]
        }


# ── Case 1 & 2: contexto_fisico con preferencias ─────────────────────────────

class TestCase1_PreferenciaEnContexto(PreferenciaMotorBase):
    def test_preferencia_activa_en_contexto_fisico(self):
        self._crear_pref()
        ctx = _obtener_contexto_fisico(self.cliente, self.hoy)
        self.assertIn(PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                      ctx['preferencias_activas'])

    def test_preferencia_revocada_no_aparece_en_contexto(self):
        pref = self._crear_pref()
        cache.clear()
        pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
        pref.save()
        cache.clear()
        ctx = _obtener_contexto_fisico(self.cliente, self.hoy)
        self.assertNotIn(PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                         ctx['preferencias_activas'])


# ── Cases 3-5: evitar_pierna_tras_futbol conditions ──────────────────────────

class TestCase3_PreferenciaPiernaFutbol(PreferenciaMotorBase):
    def test_preferencia_se_activa_pierna_y_futbol(self):
        self._crear_pref()
        decision = self._decision_base(entrenamiento=self._entrenamiento_pierna())
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertIn('preferencia_aplicada', result)
        self.assertEqual(result['preferencia_aplicada']['tipo'],
                         PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL)


class TestCase4_PreferenciaSinFutbol(PreferenciaMotorBase):
    def test_preferencia_no_aplica_sin_futbol_reciente(self):
        self._crear_pref()
        decision = self._decision_base(entrenamiento=self._entrenamiento_pierna())
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=False,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


class TestCase5_PreferenciaSinPierna(PreferenciaMotorBase):
    def test_preferencia_no_aplica_sin_sesion_pierna(self):
        self._crear_pref()
        decision = self._decision_base(entrenamiento=self._entrenamiento_tren_superior())
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True,  # football recent but no leg session
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


# ── Cases 6-7: safety hierarchy wins ─────────────────────────────────────────

class TestCase6_LesionGanaSobrePreferencia(PreferenciaMotorBase):
    def test_lesion_activa_bloquea_preferencia_aplicada(self):
        self._crear_pref()
        decision = self._decision_base(
            causa='lesion', estado='recuperar',
            entrenamiento=self._entrenamiento_pierna(),
        )
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True, lesion=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)
        self.assertEqual(result['causa_principal'], 'lesion')


class TestCase7_FatigaGanaSobrePreferencia(PreferenciaMotorBase):
    def test_fatiga_alta_bloquea_preferencia_aplicada(self):
        self._crear_pref()
        decision = self._decision_base(
            causa='fatiga_alta', estado='recuperar',
            entrenamiento=self._entrenamiento_pierna(),
        )
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True, fatiga=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


# ── Case 8: sin tocar PlanificadorHelms ──────────────────────────────────────

class TestCase8_SinPlanificador(PreferenciaMotorBase):
    def test_preferencia_aplicada_no_llama_planificador(self):
        self._crear_pref()
        with patch('analytics.planificador_helms.core.PlanificadorHelms') as mock_plan:
            decision = self._decision_base(entrenamiento=self._entrenamiento_pierna())
            decision = self._con_contexto(
                decision,
                prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
                futbol=True,
            )
            _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        mock_plan.assert_not_called()


# ── Case 9: lenguaje blando ───────────────────────────────────────────────────

class TestCase9_LenguajeBlando(PreferenciaMotorBase):
    def test_mensaje_preferencia_usa_tono_blando(self):
        self._crear_pref()
        decision = self._decision_base(entrenamiento=self._entrenamiento_pierna())
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        msg = result.get('preferencia_aplicada', {}).get('mensaje', '').lower()

        # Should NOT use absolute commands
        forbidden = ['no puedes', 'tienes que', 'debes', 'nunca', 'siempre']
        for palabra in forbidden:
            self.assertNotIn(palabra, msg, msg=f"Mensaje usa '{palabra}'")

        # Should use soft language
        soft = ['referencia', 'recuerda', 'margen', 'suele', 'opcional']
        usa_soft = any(k in msg for k in soft)
        self.assertTrue(usa_soft, msg=f"Mensaje no usa tono blando: {msg}")

    def test_mensajes_todos_los_tipos_son_blandos(self):
        from entrenos.services.sesion_recomendada import _PREF_MENSAJES
        forbidden = ['no puedes', 'tienes que', 'debes hacer', 'nunca', 'siempre debes']
        for tipo, msg in _PREF_MENSAJES.items():
            texto = msg.lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, texto, msg=f"Tipo '{tipo}' usa '{palabra}'")


# ── Case 10: causa_principal no cambia ───────────────────────────────────────

class TestCase10_CausaPrincipalIntacta(PreferenciaMotorBase):
    def test_preferencia_no_cambia_causa_principal(self):
        self._crear_pref()
        decision = self._decision_base(
            causa='futbol_reciente', estado='posponer',
            entrenamiento=self._entrenamiento_pierna(),
        )
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertEqual(result['causa_principal'], 'futbol_reciente')
        self.assertEqual(result['estado'], 'posponer')

    def test_preferencia_no_cambia_estado(self):
        self._crear_pref()
        decision = self._decision_base(
            causa='sesion_hoy', estado='entrenar',
            entrenamiento=self._entrenamiento_pierna(),
        )
        decision = self._con_contexto(
            decision,
            prefs=[PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL],
            futbol=True,
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        # Preference fires but estado stays 'entrenar'
        self.assertIn('preferencia_aplicada', result)
        self.assertEqual(result['estado'], 'entrenar')


# ── Case 11: sin preferencias, sin ruido ─────────────────────────────────────

class TestCase11_SinPreferencias(PreferenciaMotorBase):
    def test_sin_preferencias_activas_no_hay_preferencia_aplicada(self):
        decision = self._decision_base(entrenamiento=self._entrenamiento_pierna())
        decision = self._con_contexto(decision, prefs=[], futbol=True)
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


# ── Cases 12-13: otras preferencias ──────────────────────────────────────────

class TestCase12_MenosDias(PreferenciaMotorBase):
    def test_menos_dias_se_activa_con_sesion_normal(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            prioridad=SesionProgramada.PRIORIDAD_NORMAL,
        )
        decision = self._decision_base(
            entrenamiento=self._entrenamiento_tren_superior(),
            sesion_programada=sp,
        )
        decision = self._con_contexto(
            decision, prefs=[PreferenciaPlanAprendida.TIPO_MENOS_DIAS],
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertIn('preferencia_aplicada', result)
        self.assertEqual(result['preferencia_aplicada']['tipo'],
                         PreferenciaPlanAprendida.TIPO_MENOS_DIAS)

    def test_menos_dias_no_aplica_a_sesion_alta_prioridad(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            prioridad=SesionProgramada.PRIORIDAD_ALTA,
        )
        decision = self._decision_base(
            entrenamiento=self._entrenamiento_tren_superior(),
            sesion_programada=sp,
        )
        decision = self._con_contexto(
            decision, prefs=[PreferenciaPlanAprendida.TIPO_MENOS_DIAS],
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


class TestCase13_AligerarDia(PreferenciaMotorBase):
    def test_aligerar_dia_se_activa_si_hay_ejercicios(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        decision = self._decision_base(entrenamiento=self._entrenamiento_tren_superior())
        decision = self._con_contexto(
            decision, prefs=[PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA],
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertIn('preferencia_aplicada', result)
        self.assertEqual(result['preferencia_aplicada']['tipo'],
                         PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA)

    def test_aligerar_dia_no_aplica_sin_ejercicios(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        decision = self._decision_base(entrenamiento={'ejercicios': []})
        decision = self._con_contexto(
            decision, prefs=[PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA],
        )
        result = _aplicar_preferencia_activa(self.cliente, decision, self.hoy)
        self.assertNotIn('preferencia_aplicada', result)


# ── _es_sesion_pierna helper ──────────────────────────────────────────────────

class TestEsSesionPierna(PreferenciaMotorBase):
    def test_detecta_sentadilla(self):
        entreno = {'ejercicios': [{'nombre': 'Sentadilla trasera', 'grupo_muscular': 'Cuadriceps'}]}
        self.assertTrue(_es_sesion_pierna(entreno))

    def test_detecta_prensa(self):
        entreno = {'ejercicios': [{'nombre': 'Prensa de pierna', 'grupo_muscular': 'Cuadriceps'}]}
        self.assertTrue(_es_sesion_pierna(entreno))

    def test_no_detecta_press_banca(self):
        entreno = {'ejercicios': [{'nombre': 'Press banca', 'grupo_muscular': 'Pecho'}]}
        self.assertFalse(_es_sesion_pierna(entreno))

    def test_vacio_es_false(self):
        self.assertFalse(_es_sesion_pierna(None))
        self.assertFalse(_es_sesion_pierna({}))
        self.assertFalse(_es_sesion_pierna({'ejercicios': []}))
