"""
Tests para _decidir_accion / generar_decisiones_para_entreno con ejercicios
tipo_progresion='progresion_reps' (peso corporal / core, sin carga externa
real que subir — el avance es por repeticiones, no por peso).

Bug original: la función siempre devolvía 'subir_peso' al detectar éxito en
2 sesiones, sin mirar tipo_progresion. Para un ejercicio con peso=0 eso era
un no-op silencioso: nunca progresaba.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymAdaptationProfile
from entrenos.services.decision_log_service import generar_decisiones_para_entreno, _decidir_accion
from rutinas.models import EjercicioBase, Rutina


class DecisionLogProgresionRepsBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_dlsr', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDLSR', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina Test DLSR')
        self.hoy = date(2026, 6, 11)

    def _entreno(self, fecha, **kwargs):
        return EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha, **kwargs)

    def _ejercicio_realizado(self, entreno, nombre='Elevaciones de Piernas Colgado', **kwargs):
        defaults = dict(nombre_ejercicio=nombre, peso_kg=0, series=4, repeticiones=10,
                         rpe=7.0, completado=True, fallo_muscular=False)
        defaults.update(kwargs)
        return EjercicioRealizado.objects.create(entreno=entreno, **defaults)


class TestDecidirAccionProgresionReps(TestCase):
    """Unit tests directos de _decidir_accion — sin BD, perfil/historial a mano."""

    def _perfil(self):
        return GymAdaptationProfile(incremento_peso_pct=5.0, reduccion_peso_pct=10.0)

    def _ejercicio_realizado_obj(self, rpe=7.0, fallo=False, rir=None):
        class _Ej:
            pass
        ej = _Ej()
        ej.rpe = rpe
        ej.rir = rir
        ej.fallo_muscular = fallo
        return ej

    def test_exito_con_progresion_reps_devuelve_subir_reps(self):
        ej = self._ejercicio_realizado_obj(rpe=7.0)
        prev = self._ejercicio_realizado_obj(rpe=7.5)
        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial=[prev], perfil=self._perfil(), rpe=7.0, fallo=False, es_tope=False,
            tipo_progresion='progresion_reps',
        )
        self.assertEqual(accion, 'subir_reps')
        self.assertEqual(valor_cambio, 1)

    def test_exito_con_peso_reps_sigue_devolviendo_subir_peso(self):
        """Regresión: el comportamiento para ejercicios con carga no cambia."""
        ej = self._ejercicio_realizado_obj(rpe=7.0)
        prev = self._ejercicio_realizado_obj(rpe=7.5)
        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial=[prev], perfil=self._perfil(), rpe=7.0, fallo=False, es_tope=False,
            tipo_progresion='peso_reps',
        )
        self.assertEqual(accion, 'subir_peso')
        self.assertEqual(valor_cambio, 5.0)

    def test_tope_maquina_sigue_devolviendo_subir_reps_sin_importar_tipo(self):
        ej = self._ejercicio_realizado_obj(rpe=7.0)
        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial=[], perfil=self._perfil(), rpe=7.0, fallo=False, es_tope=True,
            tipo_progresion='peso_reps',
        )
        self.assertEqual(accion, 'subir_reps')


class TestGenerarDecisionesUsaTipoProgresion(DecisionLogProgresionRepsBase):
    def test_ejercicio_progresion_reps_genera_subir_reps_tras_dos_sesiones_exitosas(self):
        EjercicioBase.objects.get_or_create(
            nombre='Elevaciones de Piernas Colgado',
            defaults={'grupo_muscular': 'core', 'tipo_progresion': 'progresion_reps'},
        )

        anterior = self._entreno(self.hoy - timedelta(days=3))
        self._ejercicio_realizado(anterior, rpe=7.0, repeticiones=10)

        hoy_entreno = self._entreno(self.hoy)
        self._ejercicio_realizado(hoy_entreno, rpe=7.0, repeticiones=10)

        generar_decisiones_para_entreno(hoy_entreno)

        from entrenos.models import GymDecisionLog
        log = GymDecisionLog.objects.get(
            cliente=self.cliente, ejercicio='elevaciones de piernas colgado',
        )
        self.assertEqual(log.accion, 'subir_reps')
        self.assertEqual(log.reps_anteriores, 10)
        self.assertEqual(log.reps_sugeridas, 11)
