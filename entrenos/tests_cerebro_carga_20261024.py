"""24-oct-2026 · Paso 1 a la sombra: la regla única de carga y su comparación."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from entrenos.models import GymDecisionVersion
from entrenos.services.cerebro_carga_service import decidir_carga
from entrenos.tests_ultima_sesion import Base

HOY = timezone.localdate()


class ReglaUnica(Base):
    def _ej(self, nombre, rango, rpe=8):
        return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': rpe, 'tipo_progresion': 'peso_reps'}

    def test_sin_historial_manda_el_plan(self):
        self.assertIsNone(decidir_carga(self.cliente, self._ej('Sentadilla Hack', '12-15'), HOY))

    def test_regla_c_una_rep_mas(self):
        e = self.entreno(HOY - timedelta(days=3), {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 12, 8), (60, 12, 8)])
        d = decidir_carga(self.cliente, self._ej('Sentadilla Hack', '12-15'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (60, 13, 'mantener'))

    def test_tope_del_rango_sube_y_vuelve_al_minimo(self):
        e = self.entreno(HOY - timedelta(days=3), {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 15, 7), (60, 15, 8)])
        d = decidir_carga(self.cliente, self._ej('Sentadilla Hack', '12-15'), HOY)
        self.assertEqual((d['reps'], d['regla']), (12, 'subir'))
        self.assertGreater(d['peso'], 60)

    def test_hundimiento_baja(self):
        e = self.entreno(HOY - timedelta(days=3), {'Sentadilla Hack': '15-20'})
        self.hacer(e, self.hack, [(60, 15, 7), (60, 13, 9), (60, 8, 9)])
        d = decidir_carga(self.cliente, self._ej('Sentadilla Hack', '15-20'), HOY)
        self.assertEqual((d['regla'], d['reps']), ('bajar', 15))
        self.assertLess(d['peso'], 60)


class AjustesDel24(Base):
    def _ej(self, nombre, rango, tipo='peso_reps'):
        return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': 7, 'tipo_progresion': tipo}

    def test_historial_antiguo_se_estima(self):
        e = self.entreno(HOY - timedelta(days=60), {'Sentadilla Hack': '6-8'})
        self.hacer(e, self.hack, [(60, 8, 8)])
        d = decidir_carga(self.cliente, self._ej('Sentadilla Hack', '15-20'), HOY)
        self.assertEqual(d['regla'], 'antigua')
        self.assertLess(d['peso'], 60)

    def test_convergent_va_de_discos(self):
        from entrenos.services.maquina_service import salto_fisico
        self.assertEqual(salto_fisico('Convergent Machine Press'), 2.5)


class ComandoSoloLectura(Base):
    def test_no_guarda_nada_y_compara(self):
        e = self.entreno(HOY - timedelta(days=3), {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 12, 8)])
        antes = GymDecisionVersion.objects.count()
        out = StringIO()
        call_command('comparar_cerebro_carga', str(self.cliente.id), '--dias-adelante', '2', stdout=out)
        texto = out.getvalue()
        self.assertIn('ÚLTIMAS SESIONES', texto)
        self.assertIn('Sentadilla Hack: propuesto', texto)
        self.assertIn('hecho 60×12@8', texto)
        self.assertIn('No se ha guardado nada', texto)
        self.assertEqual(GymDecisionVersion.objects.count(), antes)


class ReglaConectadaAlPlan(Base):
    def test_el_plan_usa_la_regla_unica(self):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        e = self.entreno(HOY - timedelta(days=70), {'Sentadilla Hack': '6-8'})
        self.hacer(e, self.hack, [(60, 8, 8)])
        plan = [{'nombre': 'Sentadilla Hack', 'series': 3, 'repeticiones': '15-20', 'peso_kg': 60,
                 'rpe_objetivo': 7, 'tipo_progresion': 'peso_reps', 'grupo_muscular': 'cuadriceps'}]
        ejercicios, _ = aplicar_plan_dinamico(self.cliente, plan, HOY)
        decision = decidir_carga(self.cliente, plan[0], HOY)
        self.assertEqual(ejercicios[0]['peso_kg'], decision['peso'])
        self.assertEqual(ejercicios[0]['reps_objetivo_hoy'], 15)
        self.assertLess(ejercicios[0]['peso_kg'], 60)

    def test_solo_cambia_lo_que_difiere(self):
        from entrenos.services.cerebro_carga_service import aplicar_decision_carga
        ej = {'peso_kg': 40, 'reps_objetivo_hoy': 12}
        self.assertFalse(aplicar_decision_carga(ej, {'peso': 40, 'reps': 12, 'regla': 'mantener', 'frase': 'x'}))
        self.assertTrue(aplicar_decision_carga(ej, {'peso': 45, 'reps': 10, 'regla': 'subir', 'frase': 'sube'}))
        self.assertEqual((ej['peso_kg'], ej['reps_objetivo_hoy'], ej['progresion_motivo']), (45, 10, 'sube'))
