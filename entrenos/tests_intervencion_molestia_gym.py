from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionTrace, IntervencionMolestiaGym
from rutinas.models import EjercicioBase, Rutina


class IntervencionMolestiaGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('molestia_gym')
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre='Push')
        self.original = EjercicioBase.objects.create(
            nombre='Press Banca', grupo_muscular='Pecho',
            risk_tags=['empuje_horizontal'],
        )
        self.alternativa = EjercicioBase.objects.create(
            nombre='Aperturas suaves', grupo_muscular='Pecho', risk_tags=[],
        )
        self.hoy = timezone.localdate()

    def _evidencia(self, offset, severidad=1):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina,
            fecha=self.hoy - timedelta(days=offset),
            fecha_ejecucion=self.hoy - timedelta(days=offset),
        )
        ejercicio = EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press Banca', grupo_muscular='Pecho',
            peso_kg=60, repeticiones=8, rpe=8, completado=True,
            molestia_reportada=True, molestia_zona=' HOMBRO ',
            molestia_severidad=severidad,
        )
        return entreno, ejercicio

    def test_tres_entrenos_leves_crean_una_intervencion_idempotente(self):
        from entrenos.services.intervencion_molestia_gym_service import procesar_molestias_recurrentes
        for offset in (14, 7, 0):
            entreno, _ = self._evidencia(offset)
        primera = procesar_molestias_recurrentes(entreno)
        segunda = procesar_molestias_recurrentes(entreno)
        self.assertEqual(len(primera), 1)
        self.assertEqual(primera[0].pk, segunda[0].pk)
        self.assertEqual(primera[0].zona_canonica, 'hombro')
        self.assertEqual(primera[0].alternativa['nombre'], 'Aperturas suaves')
        self.assertEqual(IntervencionMolestiaGym.objects.count(), 1)

    def test_evidencia_severidad_dos_bloquea_intervencion_gym(self):
        from entrenos.services.intervencion_molestia_gym_service import procesar_molestias_recurrentes
        for offset in (14, 7):
            self._evidencia(offset)
        entreno, _ = self._evidencia(0, severidad=2)
        self.assertEqual(procesar_molestias_recurrentes(entreno), [])
        self.assertFalse(IntervencionMolestiaGym.objects.exists())

    @patch('entrenos.services.briefing_service.necesita_deload_gym', return_value=False)
    def test_plan_aplica_alternativa_fija_por_tags_y_prioriza_sobre_estancamiento(self, _):
        from entrenos.services.intervencion_molestia_gym_service import procesar_molestias_recurrentes
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        from entrenos.models import ExperimentoVarianteGym, GymDecisionLog
        for offset in (14, 7, 0):
            entreno, _ej = self._evidencia(offset)
        intervencion = procesar_molestias_recurrentes(entreno)[0]
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press Banca', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones.',
        )
        ahora = timezone.now()
        experimento = ExperimentoVarianteGym.objects.create(
            cliente=self.cliente, decision_origen=decision,
            original={'nombre': 'Press Banca'}, original_normalizado='press banca',
            variante={'nombre': 'Cruce de Poleas'}, variante_normalizada='cruce de poleas',
            baseline={'version': 1}, iniciada_en=ahora, vence_en=ahora + timedelta(days=21),
        )
        salida, cambios = aplicar_plan_dinamico(self.cliente, [{
            'nombre': 'Press Banca', 'grupo_muscular': 'Pecho',
            'risk_tags': ['empuje_horizontal'],
        }], self.hoy)
        experimento.refresh_from_db()
        self.assertEqual(salida[0]['nombre'], 'Aperturas suaves')
        self.assertEqual(salida[0]['intervencion_molestia_id'], intervencion.pk)
        self.assertEqual(experimento.estado, ExperimentoVarianteGym.ESTADO_INSUFICIENTE)
        self.assertTrue(any(c['tipo'] == 'sustitucion_molestia' for c in cambios))
        intervencion.decision_origen.refresh_from_db()
        self.assertEqual(intervencion.decision_origen.estado_aplicacion, 'aplicada')

    def test_fallo_o_misma_molestia_cierra_fallida_y_terminal_revierte(self):
        from entrenos.services.intervencion_molestia_gym_service import (
            enlazar_y_evaluar_ejecucion_molestia, procesar_molestias_recurrentes,
        )
        for offset in (14, 7, 0):
            entreno, _ = self._evidencia(offset)
        intervencion = procesar_molestias_recurrentes(entreno)[0]
        nuevo = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy,
        )
        ejecucion = EjercicioRealizado.objects.create(
            entreno=nuevo, nombre_ejercicio='Aperturas suaves', grupo_muscular='Pecho',
            repeticiones=8, rpe=8, completado=True, fallo_muscular=True,
        )
        enlazar_y_evaluar_ejecucion_molestia(ejecucion)
        intervencion.refresh_from_db(); ejecucion.refresh_from_db()
        self.assertEqual(intervencion.estado, IntervencionMolestiaGym.ESTADO_FALLIDA)
        self.assertEqual(ejecucion.intervencion_molestia_id, intervencion.pk)
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        with patch('entrenos.services.briefing_service.necesita_deload_gym', return_value=False):
            salida, _ = aplicar_plan_dinamico(self.cliente, [{
                'nombre': 'Press Banca', 'grupo_muscular': 'Pecho',
                'risk_tags': ['empuje_horizontal'],
            }], self.hoy)
        self.assertEqual(salida[0]['nombre'], 'Press Banca')

    def test_dos_ejecuciones_limpias_cierran_favorable(self):
        from entrenos.services.intervencion_molestia_gym_service import procesar_molestias_recurrentes
        for offset in (14, 7, 0):
            entreno, _ = self._evidencia(offset)
        intervencion = procesar_molestias_recurrentes(entreno)[0]
        for offset in (1, 8):
            sesion = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina, fecha=self.hoy + timedelta(days=offset),
            )
            EjercicioRealizado.objects.create(
                entreno=sesion, nombre_ejercicio='Aperturas suaves', grupo_muscular='Pecho',
                repeticiones=10, rpe=8, completado=True,
            )
        intervencion.refresh_from_db()
        self.assertEqual(intervencion.estado, IntervencionMolestiaGym.ESTADO_FAVORABLE)

    @patch('entrenos.services.briefing_service.necesita_deload_gym', return_value=False)
    def test_sin_alternativa_segura_pospone_explicita(self, _):
        from entrenos.services.intervencion_molestia_gym_service import procesar_molestias_recurrentes
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        self.alternativa.delete()
        for offset in (14, 7, 0):
            entreno, _ej = self._evidencia(offset)
        intervencion = procesar_molestias_recurrentes(entreno)[0]
        self.assertEqual(intervencion.alternativa, {})
        salida, cambios = aplicar_plan_dinamico(self.cliente, [{
            'nombre': 'Press Banca', 'grupo_muscular': 'Pecho',
            'risk_tags': ['empuje_horizontal'],
        }], self.hoy)
        self.assertEqual(salida[0]['nombre'], 'Press Banca')
        self.assertTrue(salida[0]['intervencion_pospuesta'])
        self.assertEqual(cambios[0]['tipo'], 'intervencion_molestia_pospuesta')
        intervencion.decision_origen.refresh_from_db()
        self.assertEqual(intervencion.decision_origen.estado_aplicacion, 'pospuesta')

    def test_signal_entreno_crea_intervencion_tras_tercera_evidencia(self):
        for offset in (14, 7, 0):
            entreno, _ = self._evidencia(offset)
        self.assertFalse(IntervencionMolestiaGym.objects.exists())
        entreno.save()
        self.assertEqual(IntervencionMolestiaGym.objects.count(), 1)

    @patch('entrenos.services.intervencion_molestia_gym_service.procesar_molestias_recurrentes')
    def test_signal_trace_no_invoca_servicio_molestia_y_conserva_backlog(self, procesar):
        with self.captureOnCommitCallbacks(execute=True):
            GymDecisionTrace.objects.create(
                cliente=self.cliente, fecha=self.hoy, decision_estado='entrenar',
                causa_principal='sesion_hoy',
            )
        procesar.assert_not_called()
