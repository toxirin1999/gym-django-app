"""
Tests para _decidir_accion / generar_decisiones_para_entreno con ejercicios
tipo_progresion='progresion_distancia' (Farmer Walk, Sled, etc. — carga
externa fija por diseño del ejercicio, el avance real es la distancia
recorrida, no el peso).

Bug original: al tocar tope de máquina, _decidir_accion siempre devolvía
valor_cambio=None (incremento +1 rep) sin mirar tipo_progresion. Para un
ejercicio de distancia (donde el campo `repeticiones` almacena metros), un
incremento de +1 m es insuficiente — la decisión de producto es +5 m.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymAdaptationProfile, GymDecisionLog
from entrenos.services.decision_log_service import (
    generar_decisiones_para_entreno,
    evaluar_decisiones_para_entreno,
    _decidir_accion,
    _evaluar_log,
)
from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
from rutinas.models import EjercicioBase, Rutina


class TestDecidirAccionTopeProgresionDistancia(TestCase):
    """Unit tests directos de _decidir_accion — sin BD, perfil a mano."""

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

    def test_tope_con_progresion_distancia_devuelve_valor_cambio_5(self):
        ej = self._ejercicio_realizado_obj(rpe=7.0)
        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial=[], perfil=self._perfil(), rpe=7.0, fallo=False, es_tope=True,
            tipo_progresion='progresion_distancia',
        )
        self.assertEqual(accion, 'subir_reps')
        self.assertEqual(valor_cambio, 5)
        self.assertIn('distancia', motivo.lower())

    def test_tope_con_peso_reps_mantiene_valor_cambio_none(self):
        """Regresión: comportamiento actual (peso_reps, ej. abducción de cadera) no cambia."""
        ej = self._ejercicio_realizado_obj(rpe=7.0)
        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial=[], perfil=self._perfil(), rpe=7.0, fallo=False, es_tope=True,
            tipo_progresion='peso_reps',
        )
        self.assertEqual(accion, 'subir_reps')
        self.assertIsNone(valor_cambio)
        self.assertIn('repeticiones', motivo.lower())


class TestRepsSugeridasConValorCambio(TestCase):
    def test_reps_sugeridas_usa_valor_cambio_5(self):
        log = GymDecisionLog(accion='subir_reps', reps_anteriores=20, valor_cambio=5)
        self.assertEqual(log.reps_sugeridas, 25)

    def test_reps_sugeridas_sin_valor_cambio_incrementa_1(self):
        log = GymDecisionLog(accion='subir_reps', reps_anteriores=10, valor_cambio=None)
        self.assertEqual(log.reps_sugeridas, 11)


class DecisionLogProgresionDistanciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_dlsd', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDLSD', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina Test DLSD')
        self.hoy = date(2026, 6, 11)
        EjercicioBase.objects.get_or_create(
            nombre='Farmer Walk',
            defaults={'grupo_muscular': 'full_body', 'tipo_progresion': 'progresion_distancia'},
        )

    def _entreno(self, fecha, **kwargs):
        return EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha, **kwargs)

    def _ejercicio_realizado(self, entreno, nombre='Farmer Walk', **kwargs):
        defaults = dict(nombre_ejercicio=nombre, peso_kg=32, series=4, repeticiones=20,
                         rpe=7.0, completado=True, fallo_muscular=False, es_tope_maquina=False)
        defaults.update(kwargs)
        return EjercicioRealizado.objects.create(entreno=entreno, **defaults)


class TestGenerarDecisionesTopeProgresionDistancia(DecisionLogProgresionDistanciaBase):
    def test_tope_maquina_en_farmer_walk_genera_subir_reps_valor_cambio_5(self):
        entreno = self._entreno(self.hoy)
        self._ejercicio_realizado(entreno, es_tope_maquina=True, repeticiones=20)

        generar_decisiones_para_entreno(entreno)

        log = GymDecisionLog.objects.get(cliente=self.cliente, ejercicio='farmer walk')
        self.assertEqual(log.accion, 'subir_reps')
        self.assertEqual(log.valor_cambio, 5)
        self.assertEqual(log.reps_anteriores, 20)
        self.assertEqual(log.reps_sugeridas, 25)


class TestProgresionEjecutivaAplicaDistanciaConTope(DecisionLogProgresionDistanciaBase):
    def test_plan_dinamico_fija_reps_objetivo_en_reps_anteriores_mas_5(self):
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='farmer walk', accion='subir_reps',
            peso_anterior=32, valor_cambio=5, reps_anteriores=20,
            motivo='Tope de peso alcanzado — progresión por distancia (+5 m)',
            resultado=None,
        )
        ejercicios = [{
            'nombre': 'Farmer Walk',
            'grupo_muscular': 'full_body',
            'tipo_ejercicio': 'accesorio',
            'peso_kg': 32,
            'series': 4,
            'repeticiones': '20',
            'rpe_objetivo': 8,
        }]

        permiso_permitido = {
            'accion': 'progresion_permitida',
            'motivo': 'ok',
            'mensaje': 'Semana con margen. La progresión está autorizada.',
            'aplica_a_principales': False,
            'aplica_a_accesorios': False,
            'hay_datos_semana': True,
        }

        from unittest.mock import patch
        with patch('entrenos.services.progresion_contextual_service.evaluar_permiso_progresion',
                   return_value=permiso_permitido), \
                patch('entrenos.services.briefing_service.necesita_deload_gym', return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'subir_reps')
        self.assertEqual(ej['reps_objetivo'], 25)

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')


class TestEvaluarLogWordingDistancia(DecisionLogProgresionDistanciaBase):
    def test_evaluar_log_subir_reps_progresion_distancia_usa_wording_distancia(self):
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='farmer walk', accion='subir_reps',
            peso_anterior=32, valor_cambio=5, reps_anteriores=20,
            motivo='Tope de peso alcanzado — progresión por distancia (+5 m)',
            resultado=None,
        )
        entreno = self._entreno(self.hoy)
        ej = self._ejercicio_realizado(entreno, repeticiones=25, rpe=7.0)

        evaluar_decisiones_para_entreno(entreno)

        log.refresh_from_db()
        self.assertEqual(log.resultado, 'validada')
        self.assertIn('distancia', log.notas_resultado.lower())

    def test_evaluar_log_subir_reps_peso_reps_mantiene_wording_reps(self):
        EjercicioBase.objects.get_or_create(
            nombre='Elevaciones de Piernas Colgado',
            defaults={'grupo_muscular': 'core', 'tipo_progresion': 'progresion_reps'},
        )
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='elevaciones de piernas colgado', accion='subir_reps',
            peso_anterior=0, valor_cambio=1, reps_anteriores=10,
            motivo='Completado con éxito en 2 sesiones consecutivas con RPE controlado',
            resultado=None,
        )
        entreno = self._entreno(self.hoy)
        ej = self._ejercicio_realizado(
            entreno, nombre='Elevaciones de Piernas Colgado', repeticiones=11, rpe=7.0,
        )

        evaluar_decisiones_para_entreno(entreno)

        log.refresh_from_db()
        self.assertEqual(log.resultado, 'validada')
        self.assertIn('repeticiones', log.notas_resultado.lower())
        self.assertNotIn('distancia', log.notas_resultado.lower())
