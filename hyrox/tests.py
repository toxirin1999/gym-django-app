import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.test import TestCase

from entrenos.models import ActividadRealizada
from hyrox.models import HyroxObjective, HyroxSession
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
