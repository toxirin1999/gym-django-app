import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.test import TestCase

from entrenos.models import ActividadRealizada
from hyrox.models import HyroxObjective, HyroxSession, HyroxActivity, StravaActivityRaw
from hyrox.training_engine import HyroxLoadManager


def _make_user(username='tester_acwr'):
    user, _ = User.objects.get_or_create(username=username)
    return user


def _make_objetivo(user, fc_max=None, fc_reposo=None):
    cliente = user.cliente_perfil
    return HyroxObjective.objects.create(
        cliente=cliente,
        fecha_evento=datetime.date(2027, 4, 1),
        fc_max_real=fc_max,
        fc_reposo=fc_reposo,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. estimar_rpe_desde_fc
# ─────────────────────────────────────────────────────────────────────────────

class EstimarRpeDesFCTests(TestCase):

    def test_formula_defaults(self):
        # (140 - 60) / (185 - 60) * 10 = 6.4
        rpe = HyroxLoadManager.estimar_rpe_desde_fc(140)
        self.assertAlmostEqual(rpe, 6.4, places=1)

    def test_usa_fc_max_del_objetivo(self):
        user = _make_user()
        objetivo = _make_objetivo(user, fc_max=200, fc_reposo=50)
        # (140 - 50) / (200 - 50) * 10 = 6.0
        rpe = HyroxLoadManager.estimar_rpe_desde_fc(140, objetivo)
        self.assertAlmostEqual(rpe, 6.0, places=1)

    def test_clamp_maximo(self):
        rpe = HyroxLoadManager.estimar_rpe_desde_fc(185)
        self.assertEqual(rpe, 10.0)

    def test_clamp_minimo(self):
        # FC por debajo de fc_reposo → resultado negativo → clamp a 1
        rpe = HyroxLoadManager.estimar_rpe_desde_fc(50)
        self.assertEqual(rpe, 1.0)

    def test_none_si_no_hay_fc(self):
        self.assertIsNone(HyroxLoadManager.estimar_rpe_desde_fc(None))
        self.assertIsNone(HyroxLoadManager.estimar_rpe_desde_fc(0))

    def test_none_si_fc_max_igual_fc_reposo(self):
        user = _make_user()
        objetivo = _make_objetivo(user, fc_max=60, fc_reposo=60)
        self.assertIsNone(HyroxLoadManager.estimar_rpe_desde_fc(140, objetivo))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Signal sincronizar_hyrox_al_hub
# ─────────────────────────────────────────────────────────────────────────────

class SincronizarHyroxAlHubTests(TestCase):

    def setUp(self):
        self.user = _make_user('tester_signal_hyrox')
        self.objetivo = _make_objetivo(self.user, fc_max=185, fc_reposo=60)

    def _completar_session(self, rpe=None, minutos=None, hr_media=None):
        s = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=datetime.date.today(),
            estado='planificado',
            rpe_global=rpe,
            tiempo_total_minutos=minutos,
            hr_media=hr_media,
        )
        s.estado = 'completado'
        s.save()
        return s

    def test_carga_ua_con_rpe_manual(self):
        s = self._completar_session(rpe=7, minutos=18)
        act = ActividadRealizada.objects.get(sesion_hyrox=s)
        self.assertAlmostEqual(act.carga_ua, 7 * 18, places=1)

    def test_carga_ua_estimada_desde_fc(self):
        s = self._completar_session(rpe=None, minutos=60, hr_media=160)
        act = ActividadRealizada.objects.get(sesion_hyrox=s)
        rpe_esperado = HyroxLoadManager.estimar_rpe_desde_fc(160, self.objetivo)
        self.assertAlmostEqual(act.carga_ua, rpe_esperado * 60, places=1)

    def test_carga_ua_fallback_sin_rpe_ni_fc(self):
        s = self._completar_session(rpe=None, minutos=45, hr_media=None)
        act = ActividadRealizada.objects.get(sesion_hyrox=s)
        self.assertAlmostEqual(act.carga_ua, 6.5 * 45, places=1)

    def test_carga_ua_none_sin_minutos(self):
        s = self._completar_session(rpe=7, minutos=None, hr_media=None)
        act = ActividadRealizada.objects.get(sesion_hyrox=s)
        self.assertIsNone(act.carga_ua)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Management command recalcular_carga_ua
# ─────────────────────────────────────────────────────────────────────────────

class RecalcularCargaUaTests(TestCase):

    def setUp(self):
        self.user = _make_user('tester_cmd')
        self.objetivo = _make_objetivo(self.user, fc_max=185, fc_reposo=60)
        self.cliente = self.user.cliente_perfil

    def _run_cmd(self, *args):
        from django.core.management import call_command
        out = StringIO()
        call_command('recalcular_carga_ua', *args, stdout=out)
        return out.getvalue()

    def test_corrige_carga_con_rpe_y_duracion(self):
        act = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            fecha=datetime.date.today(),
            rpe_medio=8.0,
            duracion_minutos=45,
            carga_ua=50.0,  # valor incorrecto — debería ser 360
        )
        self._run_cmd()
        act.refresh_from_db()
        self.assertAlmostEqual(act.carga_ua, 8.0 * 45, places=1)

    def test_dry_run_no_guarda(self):
        act = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            fecha=datetime.date.today(),
            rpe_medio=8.0,
            duracion_minutos=45,
            carga_ua=50.0,
        )
        self._run_cmd('--dry-run')
        act.refresh_from_db()
        self.assertAlmostEqual(act.carga_ua, 50.0, places=1)

    def test_fallback_sin_rpe(self):
        act = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            fecha=datetime.date.today(),
            rpe_medio=None,
            duracion_minutos=60,
            carga_ua=50.0,
        )
        self._run_cmd()
        act.refresh_from_db()
        self.assertAlmostEqual(act.carga_ua, 6.5 * 60, places=1)

    def test_with_hr_estimation_rellena_rpe_y_carga(self):
        act = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='cardio_sustituto',
            fecha=datetime.date.today(),
            rpe_medio=None,
            duracion_minutos=60,
            hr_media=160,
            carga_ua=50.0,
        )
        self._run_cmd('--with-hr-estimation')
        act.refresh_from_db()
        rpe_esperado = HyroxLoadManager.estimar_rpe_desde_fc(160, self.objetivo)
        self.assertAlmostEqual(act.rpe_medio, rpe_esperado, places=1)
        self.assertAlmostEqual(act.carga_ua, rpe_esperado * 60, places=1)

    def test_none_si_sin_rpe_ni_duracion(self):
        act = ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='otro',
            fecha=datetime.date.today(),
            rpe_medio=None,
            duracion_minutos=None,
            carga_ua=99.0,
        )
        self._run_cmd()
        act.refresh_from_db()
        self.assertIsNone(act.carga_ua)


# ─────────────────────────────────────────────────────────────────────────────
# Phase Hyrox-Gym 1.0 — Estado global compartido de descanso
# ─────────────────────────────────────────────────────────────────────────────
from hyrox.views import _crear_hyrox_decision, _leer_senales_secundarias


class TestHyroxDecisionDescansoGlobal(TestCase):
    """_crear_hyrox_decision respeta el estado de descanso global del plan gym."""

    def _decision(self, **kwargs):
        defaults = dict(current_score=89, resumen_semanal={'tsb': 4.5, 'acwr': 0.9})
        defaults.update(kwargs)
        return _crear_hyrox_decision(**defaults)

    def test_es_descanso_plan_true_no_devuelve_empujar(self):
        d = self._decision(es_descanso_plan=True)
        self.assertNotEqual(d['estado'], 'empujar')

    def test_estado_entreno_descanso_no_devuelve_empujar(self):
        d = self._decision(estado_entreno='descanso')
        self.assertNotEqual(d['estado'], 'empujar')

    def test_readiness_alto_tsb_positivo_pero_descanso_global_gana(self):
        d = self._decision(current_score=95, resumen_semanal={'tsb': 10, 'acwr': 0.8}, es_descanso_plan=True)
        self.assertEqual(d['causa'], 'descanso_plan')
        self.assertFalse(d['puede_ejecutar_plan'])

    def test_sin_descanso_global_decide_por_metricas(self):
        d = self._decision(es_descanso_plan=False, estado_entreno='entrenar')
        self.assertEqual(d['estado'], 'empujar')
        self.assertTrue(d['puede_ejecutar_plan'])

    def test_mensaje_explica_descanso_plan_no_metricas(self):
        d = self._decision(es_descanso_plan=True)
        self.assertEqual(d['estado'], 'recuperar')
        self.assertIn('plan', d['mensaje'].lower())

    def test_semaforo_hereda_descanso_global(self):
        d = self._decision(es_descanso_plan=True)
        self.assertFalse(d['puede_ejecutar_plan'])
        self.assertEqual(d['causa'], 'descanso_plan')


# ─────────────────────────────────────────────────────────────────────────────
# Phase Hyrox-Gym 1.1 — Señales secundarias del diario
# ─────────────────────────────────────────────────────────────────────────────

def _senal(intensidad):
    return {'senal_corporal': {'hay_senal': True, 'intensidad': intensidad, 'texto': 'Señal test.'}}

def _senal_vacia():
    return {'senal_corporal': {'hay_senal': False}, 'vigilar_senal_activa': False, 'futbol_reciente': False}


class TestHyroxDecisionSenalesSecundarias(TestCase):
    """Señales del diario modulan solo el resultado 'empujar'; respetan tiers 1 y 2."""

    _BUENAS = dict(current_score=88, resumen_semanal={'tsb': 5, 'acwr': 0.85})

    def _empujar_con(self, **sec_kwargs):
        ss = {**_senal_vacia(), **sec_kwargs}
        return _crear_hyrox_decision(**self._BUENAS, senales_secundarias=ss)

    def test_senal_alta_nudge_a_sostener(self):
        d = self._empujar_con(**_senal('alta'))
        self.assertEqual(d['estado'], 'sostener')
        self.assertEqual(d['causa'], 'senal_corporal')

    def test_senal_moderada_nudge_a_sostener(self):
        d = self._empujar_con(**_senal('moderada'))
        self.assertEqual(d['estado'], 'sostener')

    def test_senal_suave_no_cambia_estado(self):
        d = self._empujar_con(**_senal('suave'))
        self.assertEqual(d['estado'], 'empujar')

    def test_futbol_reciente_nudge_a_sostener(self):
        d = self._empujar_con(futbol_reciente=True)
        self.assertEqual(d['estado'], 'sostener')
        self.assertEqual(d['causa'], 'actividad_reciente')

    def test_vigilar_senal_solo_no_cambia_estado(self):
        d = self._empujar_con(vigilar_senal_activa=True)
        self.assertEqual(d['estado'], 'empujar')

    def test_secundaria_no_supera_descanso_global_tier1(self):
        ss = {**_senal('alta'), 'futbol_reciente': True, 'vigilar_senal_activa': True}
        d = _crear_hyrox_decision(**self._BUENAS, es_descanso_plan=True, senales_secundarias=ss)
        self.assertEqual(d['causa'], 'descanso_plan')

    def test_secundaria_no_supera_tsb_alto_tier2(self):
        ss = {**_senal('alta')}
        d = _crear_hyrox_decision(
            current_score=80,
            resumen_semanal={'tsb': -22, 'acwr': 0.9},
            senales_secundarias=ss,
        )
        self.assertEqual(d['causa'], 'fatiga')


# ─────────────────────────────────────────────────────────────────────────────
# Phase Hyrox-Gym 1.2 — Explicación visible de señales compartidas
# ─────────────────────────────────────────────────────────────────────────────

class TestHyroxDecisionExplicacionModulacion(TestCase):
    """explicacion_modulacion aparece solo cuando hay modulación real."""

    _BUENAS = dict(current_score=88, resumen_semanal={'tsb': 5, 'acwr': 0.85})

    def test_explicacion_presente_en_senal_alta(self):
        ss = {**_senal_vacia(), **_senal('alta')}
        d = _crear_hyrox_decision(**self._BUENAS, senales_secundarias=ss)
        self.assertIn('explicacion_modulacion', d)
        exp = d['explicacion_modulacion']
        self.assertIn('bullets', exp)
        self.assertTrue(len(exp['bullets']) >= 1)
        self.assertIn('cierre', exp)

    def test_explicacion_contiene_futbol_si_aplica(self):
        ss = {**_senal_vacia(), 'futbol_reciente': True}
        d = _crear_hyrox_decision(**self._BUENAS, senales_secundarias=ss)
        bullets = d['explicacion_modulacion']['bullets']
        self.assertTrue(any('fútbol' in b.lower() or 'futbol' in b.lower() for b in bullets))

    def test_sin_modulacion_no_hay_explicacion(self):
        d = _crear_hyrox_decision(**self._BUENAS, senales_secundarias=_senal_vacia())
        self.assertNotIn('explicacion_modulacion', d)

    def test_descanso_plan_no_genera_explicacion_modulacion(self):
        ss = {**_senal('alta')}
        d = _crear_hyrox_decision(**self._BUENAS, es_descanso_plan=True, senales_secundarias=ss)
        self.assertNotIn('explicacion_modulacion', d)


# ─────────────────────────────────────────────────────────────────────────────
# calcular_delta_readiness_checkin — función pura
# ─────────────────────────────────────────────────────────────────────────────
from hyrox.services import calcular_delta_readiness_checkin


def _baseline(valor=60.0):
    return valor


def _ultimos5(valor=60):
    return [valor] * 5


class TestCalcularDeltaReadinessCheckin(TestCase):
    """calcular_delta_readiness_checkin es pura: sin ORM, sin efectos."""

    # ── Sueño ──

    def test_sueno_sin_datos_delta_cero(self):
        delta, _ = calcular_delta_readiness_checkin(None, None, None, None, None, [])
        self.assertEqual(delta, 0)

    def test_sueno_menos_5h_penaliza_10(self):
        delta, _ = calcular_delta_readiness_checkin(None, 4.5, None, None, None, [])
        self.assertEqual(delta, -10)

    def test_sueno_5h_a_6h_penaliza_5(self):
        delta, _ = calcular_delta_readiness_checkin(None, 5.5, None, None, None, [])
        self.assertEqual(delta, -5)

    def test_sueno_6h_a_7h_penaliza_2(self):
        delta, _ = calcular_delta_readiness_checkin(None, 6.5, None, None, None, [])
        self.assertEqual(delta, -2)

    def test_sueno_7h_o_mas_no_penaliza(self):
        delta, _ = calcular_delta_readiness_checkin(None, 8.0, None, None, None, [])
        self.assertEqual(delta, 0)

    # ── Calidad sueño ──

    def test_calidad_menos_40_penaliza_10(self):
        delta, _ = calcular_delta_readiness_checkin(30, None, None, None, None, [])
        self.assertEqual(delta, -10)

    def test_calidad_40_a_60_penaliza_5(self):
        delta, _ = calcular_delta_readiness_checkin(55, None, None, None, None, [])
        self.assertEqual(delta, -5)

    def test_calidad_60_o_mas_no_penaliza(self):
        delta, _ = calcular_delta_readiness_checkin(75, None, None, None, None, [])
        self.assertEqual(delta, 0)

    # ── Energía ──

    def test_energia_menos_4_penaliza_8(self):
        delta, _ = calcular_delta_readiness_checkin(None, None, 3, None, None, [])
        self.assertEqual(delta, -8)

    def test_energia_4_a_6_penaliza_3(self):
        delta, _ = calcular_delta_readiness_checkin(None, None, 5, None, None, [])
        self.assertEqual(delta, -3)

    def test_energia_6_o_mas_no_penaliza(self):
        delta, _ = calcular_delta_readiness_checkin(None, None, 7, None, None, [])
        self.assertEqual(delta, 0)

    # ── HRV: sin dato suficiente ──

    def test_hrv_sin_baseline_no_penaliza(self):
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 45, None, [])
        self.assertEqual(delta, 0)
        self.assertEqual(estado, 'sin_dato')

    def test_hrv_menos_de_5_dias_no_penaliza(self):
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 45, 60.0, [50, 55, 48])
        self.assertEqual(delta, 0)
        self.assertEqual(estado, 'sin_dato')

    # ── HRV: sin freno (> 110%) ──

    def test_hrv_alta_no_bonifica(self):
        # HRV hoy = 72 (120% de baseline 60) → sin penalización, sin bonus
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 72, 60.0, _ultimos5(60))
        self.assertEqual(delta, 0)
        self.assertEqual(estado, 'sin_freno')

    # ── HRV: normal (90–110%) ──

    def test_hrv_normal_no_penaliza(self):
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 57, 60.0, _ultimos5(60))
        self.assertEqual(delta, 0)
        self.assertEqual(estado, 'normal')

    # ── HRV: leve (80–90%, 1 día) ──

    def test_hrv_leve_un_dia_penaliza_2(self):
        # Hoy = 51 (85%), últimos 5 todos normales (100%)
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 51, 60.0, _ultimos5(60))
        self.assertEqual(delta, -2)
        self.assertEqual(estado, 'leve')

    # ── HRV: leve con tendencia (80–90%, ≥2 días) ──

    def test_hrv_moderada_por_tendencia_penaliza_5(self):
        # Hoy = 51 (85%), 3 de los 5 días anteriores también por debajo de 90%
        ultimos5 = [51, 52, 53, 62, 63]  # 3 < 90% de baseline 60
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 51, 60.0, ultimos5)
        self.assertEqual(delta, -5)
        self.assertEqual(estado, 'moderada')

    # ── HRV: caída fuerte (70–80%, 1 día) ──

    def test_hrv_fuerte_un_dia_penaliza_5(self):
        # Hoy = 45 (75%), últimos 5 normales
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 45, 60.0, _ultimos5(60))
        self.assertEqual(delta, -5)
        self.assertEqual(estado, 'moderada')

    # ── HRV: caída fuerte con tendencia (70–80%, ≥2 días) ──

    def test_hrv_marcada_por_tendencia_penaliza_10(self):
        # Hoy = 45 (75%), 2 de los 5 días también < 80%
        ultimos5 = [44, 45, 62, 63, 64]  # 2 < 80% de baseline 60
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 45, 60.0, ultimos5)
        self.assertEqual(delta, -10)
        self.assertEqual(estado, 'marcada')

    # ── HRV: caída muy marcada (< 70%) ──

    def test_hrv_menos_70_penaliza_10_aunque_sea_1_dia(self):
        # Hoy = 38 (63%), últimos 5 normales — caída fuerte: no necesita tendencia
        delta, estado = calcular_delta_readiness_checkin(None, None, None, 38, 60.0, _ultimos5(60))
        self.assertEqual(delta, -10)
        self.assertEqual(estado, 'marcada')

    # ── Stacking con cap implícito ──

    def test_stacking_severo_acumula_correctamente(self):
        # 4h30 sueño (-10) + energía 3 (-8) + HRV 62% un día (-10)
        delta, _ = calcular_delta_readiness_checkin(None, 4.5, 3, 37, 60.0, _ultimos5(60))
        self.assertEqual(delta, -28)

    def test_hrv_alta_no_compensa_sueno_malo(self):
        # HRV alta no debe subir el delta; el sueño malo sigue penalizando
        delta, estado = calcular_delta_readiness_checkin(None, 4.5, None, 72, 60.0, _ultimos5(60))
        self.assertEqual(delta, -10)
        self.assertEqual(estado, 'sin_freno')


# ─────────────────────────────────────────────────────────────────────────────
# _crear_hyrox_decision — estado ejecutar_con_margen
# ─────────────────────────────────────────────────────────────────────────────

class TestHyroxDecisionEjecutarConMargen(TestCase):
    """readiness 45-69 produce estado ejecutar_con_margen."""

    _BASE = dict(resumen_semanal={'tsb': 2, 'acwr': 0.9})

    def test_score_45_produce_ejecutar_con_margen(self):
        d = _crear_hyrox_decision(current_score=45, **self._BASE)
        self.assertEqual(d['estado'], 'ejecutar_con_margen')

    def test_score_69_produce_ejecutar_con_margen(self):
        d = _crear_hyrox_decision(current_score=69, **self._BASE)
        self.assertEqual(d['estado'], 'ejecutar_con_margen')

    def test_score_70_produce_empujar(self):
        d = _crear_hyrox_decision(current_score=70, **self._BASE)
        self.assertEqual(d['estado'], 'empujar')

    def test_score_44_produce_sostener(self):
        d = _crear_hyrox_decision(current_score=44, **self._BASE)
        self.assertEqual(d['estado'], 'sostener')

    def test_ejecutar_con_margen_puede_ejecutar_plan(self):
        d = _crear_hyrox_decision(current_score=60, **self._BASE)
        self.assertTrue(d['puede_ejecutar_plan'])

    def test_tsb_bajo_gana_a_ejecutar_con_margen(self):
        # TSB ≤ -20 siempre produce recuperar, aunque score sea 60
        d = _crear_hyrox_decision(current_score=60, resumen_semanal={'tsb': -22, 'acwr': 0.9})
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa'], 'fatiga')


# ─────────────────────────────────────────────────────────────────────────────
# _crear_hyrox_decision — sesion_protegida (ACWR 1.5–1.7)
# ─────────────────────────────────────────────────────────────────────────────

class TestHyroxDecisionSesionProtegida(TestCase):
    """ACWR 1.5–1.7 produce sesion_protegida. ACWR > 1.7 produce recuperar."""

    def _d(self, acwr, tsb=-5, score=80):
        return _crear_hyrox_decision(current_score=score, resumen_semanal={'tsb': tsb, 'acwr': acwr})

    def test_acwr_1_5_produce_sesion_protegida(self):
        self.assertEqual(self._d(acwr=1.5)['estado'], 'sesion_protegida')

    def test_acwr_1_7_produce_sesion_protegida(self):
        self.assertEqual(self._d(acwr=1.7)['estado'], 'sesion_protegida')

    def test_acwr_encima_1_7_produce_recuperar(self):
        d = self._d(acwr=1.71)
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa'], 'carga')

    def test_sesion_protegida_puede_ejecutar_plan(self):
        self.assertTrue(self._d(acwr=1.6)['puede_ejecutar_plan'])

    def test_recuperar_por_carga_no_puede_ejecutar_plan(self):
        self.assertFalse(self._d(acwr=1.8)['puede_ejecutar_plan'])

    def test_tsb_critico_gana_a_sesion_protegida(self):
        d = self._d(acwr=1.6, tsb=-22)
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa'], 'fatiga')

    def test_acwr_bajo_1_5_no_activa_sesion_protegida(self):
        self.assertNotEqual(self._d(acwr=1.49)['estado'], 'sesion_protegida')

    def test_lesion_gana_a_sesion_protegida(self):
        from unittest.mock import MagicMock
        lesion = MagicMock()
        lesion.zona_afectada = 'rodilla'
        lesion.tags_restringidos = []
        d = _crear_hyrox_decision(
            current_score=80,
            resumen_semanal={'tsb': -5, 'acwr': 1.6},
            lesion_activa=lesion,
        )
        self.assertEqual(d['causa'], 'lesion')


# ─────────────────────────────────────────────────────────────────────────────
# 9. HyroxLoadManager.recalibrar_5k_desde_metricas — unidad
# ─────────────────────────────────────────────────────────────────────────────

class Recalibrar5KDesdeMetricasTests(TestCase):

    def setUp(self):
        self.user = _make_user('tester_recal_5k')
        self.objetivo = _make_objetivo(self.user)
        self.objetivo.tiempo_5k_base = '25:00'
        self.objetivo.save(update_fields=['tiempo_5k_base'])

    def test_recalibra_si_mejora_el_tiempo(self):
        # 23:00 < 25:00 → debe recalibrar
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'distancia_km': 5.0, 'tiempo_minutos': 23}
        )
        self.objetivo.refresh_from_db()
        self.assertTrue(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')

    def test_no_recalibra_si_es_mas_lento(self):
        # 27:00 > 25:00 → no debe tocar el baseline
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'distancia_km': 5.0, 'tiempo_minutos': 27}
        )
        self.objetivo.refresh_from_db()
        self.assertFalse(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_carrera_fuera_de_rango_corto_no_recalibra(self):
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'distancia_km': 3.0, 'tiempo_minutos': 12}
        )
        self.objetivo.refresh_from_db()
        self.assertFalse(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_carrera_fuera_de_rango_largo_no_recalibra(self):
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'distancia_km': 7.0, 'tiempo_minutos': 30}
        )
        self.objetivo.refresh_from_db()
        self.assertFalse(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_sin_distancia_no_rompe_y_no_recalibra(self):
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'tiempo_minutos': 23}
        )
        self.objetivo.refresh_from_db()
        self.assertFalse(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_sin_duracion_no_rompe_y_no_recalibra(self):
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(
            self.objetivo, {'distancia_km': 5.0}
        )
        self.objetivo.refresh_from_db()
        self.assertFalse(recalibrado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_metricas_vacias_no_rompe(self):
        recalibrado = HyroxLoadManager.recalibrar_5k_desde_metricas(self.objetivo, {})
        self.assertFalse(recalibrado)

    def test_reprocesar_misma_evidencia_no_recalibra_dos_veces(self):
        data = {'distancia_km': 5.0, 'tiempo_minutos': 23}
        primero = HyroxLoadManager.recalibrar_5k_desde_metricas(self.objetivo, data)
        self.objetivo.refresh_from_db()
        segundo = HyroxLoadManager.recalibrar_5k_desde_metricas(self.objetivo, data)
        self.objetivo.refresh_from_db()
        self.assertTrue(primero)
        self.assertFalse(segundo)
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')


# ─────────────────────────────────────────────────────────────────────────────
# 10. Phase Strava 1 — Recalibración 5K consistente entre flujos de reconciliación
# ─────────────────────────────────────────────────────────────────────────────

class StravaProcesarRecalibracion5KTests(TestCase):
    """
    Una carrera Strava de ~5km debe recalibrar tiempo_5k_base sin importar
    el flujo de reconciliación elegido (merge_hyrox, create_hyrox, create_gym).
    """

    def setUp(self):
        self.user = User.objects.create_user(username='tester_strava_5k', password='x')
        self.client.force_login(self.user)
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=datetime.date(2027, 4, 1),
            tiempo_5k_base='25:00',
        )

    def _crear_strava_run(self, distancia_metros=5000, duracion_segundos=23 * 60, strava_id=1):
        return StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=strava_id,
            fecha_actividad=datetime.date.today(),
            tipo_strava='Run',
            nombre_strava='Carrera matutina',
            duracion_segundos=duracion_segundos,
            distancia_metros=distancia_metros,
            raw_json={},
            estado='pending',
        )

    def test_create_gym_carrera_5k_recalibra(self):
        act = self._crear_strava_run(strava_id=101)
        resp = self.client.post(
            f'/hyrox/strava/procesar/{act.id}/', {'accion': 'create_gym'}
        )
        self.assertEqual(resp.status_code, 200)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')

    def test_merge_hyrox_carrera_5k_recalibra(self):
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=datetime.date.today(),
            estado='planificado',
            titulo='Carrera planificada',
        )
        HyroxActivity.objects.create(
            sesion=sesion, tipo_actividad='carrera',
            nombre_ejercicio='Carrera Z2', data_metricas={},
        )
        act = self._crear_strava_run(strava_id=102)
        resp = self.client.post(
            f'/hyrox/strava/procesar/{act.id}/',
            {'accion': 'merge_hyrox', 'session_id': sesion.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')

    def test_merge_hyrox_estado_completado_no_duplica_recalibracion(self):
        """
        Cuando la sesión ya está 'completado' al fusionar, sesion.save() dispara
        también detectar_5k_desde_hyrox_session. La recalibración explícita +
        la del signal deben converger al mismo resultado sin duplicar el efecto
        (idempotencia: la segunda llamada ve tiempo_5k_base ya actualizado).
        """
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=datetime.date.today(),
            estado='completado',
            titulo='Carrera completada',
        )
        HyroxActivity.objects.create(
            sesion=sesion, tipo_actividad='carrera',
            nombre_ejercicio='Carrera Z2', data_metricas={},
        )
        act = self._crear_strava_run(strava_id=105)
        resp = self.client.post(
            f'/hyrox/strava/procesar/{act.id}/',
            {'accion': 'merge_hyrox', 'session_id': sesion.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('5K recalibrado a 23:00', resp.json()['msg'])
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')

    def test_create_hyrox_carrera_5k_recalibra(self):
        act = self._crear_strava_run(strava_id=103)
        resp = self.client.post(
            f'/hyrox/strava/procesar/{act.id}/', {'accion': 'create_hyrox'}
        )
        self.assertEqual(resp.status_code, 200)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')

    def test_carrera_fuera_de_rango_no_recalibra(self):
        # 3 km no es representativo de un 5K
        act = self._crear_strava_run(distancia_metros=3000, duracion_segundos=12 * 60, strava_id=104)
        resp = self.client.post(
            f'/hyrox/strava/procesar/{act.id}/', {'accion': 'create_gym'}
        )
        self.assertEqual(resp.status_code, 200)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')
