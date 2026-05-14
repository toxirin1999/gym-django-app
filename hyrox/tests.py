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
