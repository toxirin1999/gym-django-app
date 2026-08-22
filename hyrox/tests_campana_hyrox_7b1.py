import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.campaign_authority import CampanaHyroxNoAutoriza, exigir_prescripcion
from hyrox.models import (
    ContratoCampanaHyrox,
    HyroxActivity,
    HyroxObjective,
    HyroxSession,
    HyroxReadinessLog,
    UserInjury,
)
from hyrox.training_engine import HyroxTrainingEngine
from hyrox.views import _crear_hyrox_decision
from core.bio_context import BioContextProvider
from hyrox.services import guardar_sesion_hyrox_service
from hyrox.training_engine import (
    DeloadAutoTrigger,
    HyroxLoadManager,
    PaceAutoUpdater,
    PostMilestoneEngine,
    RMAutoUpdater,
    RPECalibrator,
)


class CampanaHyrox7B1Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('campana7b1', password='test')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.localdate()
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=60),
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=5,
            minimo_valido=3,
            vigente_desde=self.hoy,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activo',
            semana_inicio=self.hoy,
            semanas_previstas=4,
            semana_fin_prevista=self.hoy + datetime.timedelta(days=27),
            estrategia=estrategia,
            objetivo_sesiones=5,
            minimo_valido=3,
            objetivo_principal='hipertrofia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='7' * 64,
        )

    def _contrato(self, estado):
        return ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado=estado,
            objetivo=self.objetivo if estado == 'activa' else None,
            bloque_gym=self.bloque if estado == 'activa' else None,
            objetivo_snapshot=(
                {'id': self.objetivo.pk, 'fecha_evento': str(self.objetivo.fecha_evento)}
                if estado == 'activa' else {}
            ),
            bloque_gym_snapshot=(
                {'id': self.bloque.pk, 'estado': 'activo'} if estado == 'activa' else {}
            ),
            limites_snapshot={},
            fingerprint=estado[0] * 64,
        )

    def _sesion_futura(self, titulo='Carrera crítica'):
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo=titulo,
        )
        HyroxActivity.objects.create(
            sesion=sesion,
            tipo_actividad='carrera',
            nombre_ejercicio='Carrera',
        )
        return sesion

    def test_gate_rechaza_todos_los_estados_salvo_campana_activa_valida(self):
        for estado in ('inactiva', 'exploracion', 'finalizada'):
            ContratoCampanaHyrox.objects.all().delete()
            self._contrato(estado)
            with self.assertRaises(CampanaHyroxNoAutoriza):
                exigir_prescripcion(self.cliente, accion='generar_plan')

        ContratoCampanaHyrox.objects.all().delete()
        self._contrato('activa')
        autoridad = exigir_prescripcion(
            self.cliente,
            accion='generar_plan',
            objective=self.objetivo,
        )
        self.assertEqual(autoridad['estado'], 'activa')

    def test_registro_manual_strava_carga_y_seguridad_siguen_permitidos(self):
        self._contrato('inactiva')
        for accion in ('registro_manual', 'sincronizar_strava', 'aportar_carga', 'seguridad'):
            with self.subTest(accion=accion):
                autoridad = exigir_prescripcion(self.cliente, accion=accion)
                self.assertEqual(autoridad['estado'], 'inactiva')

    def test_generate_training_plan_defensa_profunda_no_muta_sin_campana(self):
        for estado in ('inactiva', 'exploracion', 'finalizada'):
            ContratoCampanaHyrox.objects.all().delete()
            self._contrato(estado)
            with self.assertRaises(CampanaHyroxNoAutoriza):
                HyroxTrainingEngine.generate_training_plan(self.objetivo)
            self.assertEqual(HyroxSession.objects.count(), 0)

    def test_generate_training_plan_con_campana_activa_conserva_comportamiento(self):
        self._contrato('activa')
        with patch.object(HyroxTrainingEngine, '_create_session') as crear:
            HyroxTrainingEngine.generate_training_plan(self.objetivo)
        self.assertTrue(crear.called)

    def test_campana_activa_de_objetivo_a_no_autoriza_generar_objetivo_b(self):
        self._contrato('activa')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        with self.assertRaises(CampanaHyroxNoAutoriza) as error:
            HyroxTrainingEngine.generate_training_plan(objetivo_b)
        self.assertIn('objetivo_fuera_campana', error.exception.autoridad['hallazgos'])
        self.assertEqual(HyroxSession.objects.filter(objective=objetivo_b).count(), 0)

    def test_auto_adjust_no_muta_sin_campana_y_activa_si(self):
        atrasada = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy - datetime.timedelta(days=1),
            titulo='Carrera crítica',
        )
        HyroxActivity.objects.create(
            sesion=atrasada,
            tipo_actividad='carrera',
            nombre_ejercicio='Carrera',
        )
        self._contrato('inactiva')
        HyroxTrainingEngine.auto_adjust(self.objetivo)
        atrasada.refresh_from_db()
        self.assertEqual(atrasada.fecha, self.hoy - datetime.timedelta(days=1))

        ContratoCampanaHyrox.objects.all().delete()
        self._contrato('activa')
        HyroxTrainingEngine.auto_adjust(self.objetivo)
        atrasada.refresh_from_db()
        self.assertEqual(atrasada.fecha, self.hoy)

    def test_lesion_se_registra_pero_no_borra_plan_si_campana_inactiva(self):
        self._contrato('inactiva')
        sesion = self._sesion_futura()
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='rodilla',
            activa=True,
            tags_restringidos=['impacto_vertical'],
        )
        self.assertTrue(HyroxSession.objects.filter(pk=sesion.pk).exists())

    def test_regenerar_plan_html_inactivo_avisa_y_no_borra(self):
        self.client.force_login(self.user)
        self._contrato('inactiva')
        sesion = self._sesion_futura()
        respuesta = self.client.get(reverse('hyrox:regenerar_plan', args=[self.objetivo.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion.pk).exists())
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertTrue(any('campaña' in m.lower() for m in mensajes))

    def test_regenerar_plan_con_campana_activa_conserva_el_flujo(self):
        self.client.force_login(self.user)
        self._contrato('activa')
        sesion = self._sesion_futura()
        with patch.object(HyroxTrainingEngine, 'generate_training_plan') as generar:
            respuesta = self.client.get(
                reverse('hyrox:regenerar_plan', args=[self.objetivo.pk])
            )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(HyroxSession.objects.filter(pk=sesion.pk).exists())
        generar.assert_called_once_with(self.objetivo)

    def test_regenerar_objetivo_b_no_usa_campana_activa_de_objetivo_a(self):
        self.client.force_login(self.user)
        self._contrato('activa')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        sesion_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B legacy',
        )
        respuesta = self.client.get(reverse('hyrox:regenerar_plan', args=[objetivo_b.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_b.pk).exists())

    def test_editar_objetivo_b_no_regenera_con_campana_de_objetivo_a(self):
        self.client.force_login(self.user)
        self._contrato('activa')
        self.objetivo.estado = 'cancelado'
        self.objetivo.save(update_fields=['estado'])
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        sesion_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B legacy',
        )
        respuesta = self.client.post(reverse('hyrox:crear_objetivo'), {
            'categoria': 'open_men',
            'fecha_evento': str(self.hoy + datetime.timedelta(days=100)),
            'primer_hyrox': 'on',
            'nivel_experiencia': 'intermedio',
            'genero': 'M',
            'fc_reposo': 54,
            'lesiones_previas': '',
            'material_disponible': '',
            'dias_preferidos': '0,2,4,6',
        })
        self.assertEqual(respuesta.status_code, 302)
        objetivo_b.refresh_from_db()
        self.assertEqual(objetivo_b.fc_reposo, 54)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_b.pk).exists())

    def test_lesion_con_multiples_objetivos_solo_regenera_objetivo_contratado(self):
        self._contrato('activa')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        sesion_a = self._sesion_futura('A futura')
        sesion_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B futura',
        )
        with patch.object(HyroxTrainingEngine, 'generate_training_plan') as generar:
            UserInjury.objects.create(
                cliente=self.cliente,
                zona_afectada='rodilla',
                activa=True,
                tags_restringidos=['impacto_vertical'],
            )
        self.assertFalse(HyroxSession.objects.filter(pk=sesion_a.pk).exists())
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_b.pk).exists())
        generar.assert_called_once_with(self.objetivo)

    def test_bio_purge_inactivo_devuelve_cero_y_no_toca_ningun_objetivo(self):
        self._contrato('inactiva')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        sesion_a = self._sesion_futura('A legacy')
        sesion_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B legacy',
        )
        with patch.object(HyroxTrainingEngine, 'generate_training_plan') as generar:
            eliminadas = BioContextProvider.force_clean_future_workouts(self.cliente)
        self.assertEqual(eliminadas, 0)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_a.pk).exists())
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_b.pk).exists())
        generar.assert_not_called()

    def test_bio_purge_activo_solo_muta_objetivo_contractual(self):
        self._contrato('activa')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        sesion_a = self._sesion_futura('A futura')
        sesion_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B futura',
        )
        with patch.object(HyroxTrainingEngine, 'generate_training_plan') as generar:
            eliminadas = BioContextProvider.force_clean_future_workouts(self.cliente)
        self.assertEqual(eliminadas, 1)
        self.assertFalse(HyroxSession.objects.filter(pk=sesion_a.pk).exists())
        self.assertTrue(HyroxSession.objects.filter(pk=sesion_b.pk).exists())
        generar.assert_called_once_with(self.objetivo)

    def test_bio_purge_snapshot_incoherente_no_muta(self):
        contrato = self._contrato('activa')
        ContratoCampanaHyrox.objects.filter(pk=contrato.pk).update(
            objetivo_snapshot={'id': self.objetivo.pk, 'fecha_evento': '2099-01-01'}
        )
        sesion = self._sesion_futura('A protegida')
        with patch.object(HyroxTrainingEngine, 'generate_training_plan') as generar:
            eliminadas = BioContextProvider.force_clean_future_workouts(self.cliente)
        self.assertEqual(eliminadas, 0)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion.pk).exists())
        generar.assert_not_called()

    def test_guardar_sesion_inactiva_conserva_hechos_y_hub_sin_efectos(self):
        from entrenos.models import ActividadRealizada

        self._contrato('inactiva')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='Sesión factual',
        )
        with (
            patch.object(HyroxTrainingEngine, 'scale_volume_by_energy') as escala,
            patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation') as adapta,
            patch.object(RMAutoUpdater, 'update_from_session') as rm,
            patch.object(PaceAutoUpdater, 'update_from_session') as pace,
            patch.object(RPECalibrator, 'check_and_notify') as rpe,
            patch.object(DeloadAutoTrigger, 'check_and_apply') as deload,
            patch.object(PostMilestoneEngine, 'adapt_after_milestone') as hito,
        ):
            resultado = guardar_sesion_hyrox_service(self.objetivo, sesion, {
                'rpe_global': 8,
                'tiempo_total_minutos': 40,
            })
        self.assertTrue(resultado['success'])
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'completado')
        self.assertTrue(ActividadRealizada.objects.filter(sesion_hyrox=sesion).exists())
        for motor in (escala, adapta, rm, pace, rpe, deload, hito):
            motor.assert_not_called()

    def test_campana_activa_adapta_una_sola_vez_desde_orquestador(self):
        self._contrato('activa')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='Sesión activa',
        )
        with (
            patch.object(HyroxTrainingEngine, 'scale_volume_by_energy', return_value=None),
            patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation', return_value=[]) as adapta,
            patch.object(RMAutoUpdater, 'update_from_session', return_value=[]),
            patch.object(PaceAutoUpdater, 'update_from_session', return_value=[]),
            patch.object(RPECalibrator, 'check_and_notify', return_value=[]),
            patch.object(DeloadAutoTrigger, 'check_and_apply', return_value=[]),
        ):
            resultado = guardar_sesion_hyrox_service(self.objetivo, sesion, {
                'rpe_global': 8,
                'tiempo_total_minutos': 40,
            })
        self.assertTrue(resultado['success'])
        adapta.assert_called_once_with(sesion)

    def test_signal_activo_propaga_fatiga_tsb_sin_adaptacion_continua(self):
        from hyrox.signals import autorregular_plan_futuro

        self._contrato('activa')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='TSB factual',
            estado='planificado',
            rpe_global=8,
        )
        futura = self._sesion_futura('Futura por TSB')
        sesion.estado = 'completado'

        with (
            patch('hyrox.signals._calcular_y_guardar_carga', return_value={'tsb': -30}),
            patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation') as adapta,
            patch('joi.services.generar_mensaje_joi'),
        ):
            autorregular_plan_futuro(HyroxSession, sesion, False)

        futura.refresh_from_db()
        self.assertEqual(futura.muscle_fatigue_index, 'Alta')
        adapta.assert_not_called()

    def test_signal_inactivo_con_tsb_no_muta_sesion_futura(self):
        from hyrox.signals import autorregular_plan_futuro

        self._contrato('inactiva')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='TSB sin autoridad',
            estado='planificado',
            rpe_global=9,
        )
        futura = self._sesion_futura('Futura intacta por campaña')
        sesion.estado = 'completado'

        with (
            patch('hyrox.signals._calcular_y_guardar_carga', return_value={'tsb': -30}),
            patch('joi.services.generar_mensaje_joi'),
        ):
            autorregular_plan_futuro(HyroxSession, sesion, False)

        futura.refresh_from_db()
        self.assertIsNone(futura.muscle_fatigue_index)

    def test_signal_activo_propaga_fc_reposo_elevada(self):
        from hyrox.signals import autorregular_plan_futuro

        self._contrato('activa')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='FC factual',
            estado='planificado',
            rpe_global=7,
        )
        futura = self._sesion_futura('Futura por FC')
        HyroxReadinessLog.objects.create(
            objective=self.objetivo,
            score=70,
            fc_reposo=70,
        )
        sesion.estado = 'completado'

        with (
            patch('hyrox.signals._calcular_y_guardar_carga', return_value={'tsb': 0}),
            patch.object(HyroxLoadManager, 'get_fc_reposo_basal', return_value=55),
            patch('joi.services.generar_mensaje_joi'),
        ):
            autorregular_plan_futuro(HyroxSession, sesion, False)

        futura.refresh_from_db()
        self.assertEqual(futura.muscle_fatigue_index, 'Media')

    def test_bitacora_inactiva_no_inyecta_fatiga_en_futuro(self):
        from clientes.models import BitacoraDiaria

        self._contrato('inactiva')
        futura = self._sesion_futura('Futura intacta')
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=4,
            energia_subjetiva=2,
        )
        futura.refresh_from_db()
        self.assertIsNone(futura.muscle_fatigue_index)

    def test_bitacora_activa_inyecta_fatiga_solo_en_objetivo_contractual(self):
        from clientes.models import BitacoraDiaria

        self._contrato('activa')
        objetivo_b = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        futura_a = self._sesion_futura('A futura')
        futura_b = HyroxSession.objects.create(
            objective=objetivo_b,
            fecha=self.hoy + datetime.timedelta(days=2),
            titulo='B futura',
        )
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=4,
            energia_subjetiva=2,
        )
        futura_a.refresh_from_db()
        futura_b.refresh_from_db()
        self.assertEqual(futura_a.muscle_fatigue_index, 'Alta')
        self.assertIsNone(futura_b.muscle_fatigue_index)

    def test_5k_inactivo_es_hecho_permitido_sin_recalibrar_objetivo(self):
        self._contrato('inactiva')
        self.objetivo.tiempo_5k_base = '25:00'
        self.objetivo.save(update_fields=['tiempo_5k_base'])

        actualizado = HyroxLoadManager.actualizar_5k_si_pr(self.objetivo, 23 * 60)

        self.objetivo.refresh_from_db()
        self.assertFalse(actualizado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '25:00')

    def test_5k_activo_recalibra_solo_objetivo_contractual(self):
        self._contrato('activa')
        self.objetivo.tiempo_5k_base = '25:00'
        self.objetivo.save(update_fields=['tiempo_5k_base'])

        objetivo_ajeno = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
            tiempo_5k_base='26:00',
        )

        actualizado = HyroxLoadManager.actualizar_5k_si_pr(self.objetivo, 23 * 60)
        ajeno_actualizado = HyroxLoadManager.actualizar_5k_si_pr(
            objetivo_ajeno, 22 * 60
        )

        self.objetivo.refresh_from_db()
        objetivo_ajeno.refresh_from_db()
        self.assertTrue(actualizado)
        self.assertFalse(ajeno_actualizado)
        self.assertEqual(self.objetivo.tiempo_5k_base, '23:00')
        self.assertEqual(objetivo_ajeno.tiempo_5k_base, '26:00')

    def test_rm_y_deload_inactivos_no_mutan_objetivo_ni_ciclo(self):
        from entrenos.models import CicloDeload

        self._contrato('inactiva')
        self.objetivo.rm_sentadilla = 100
        self.objetivo.save(update_fields=['rm_sentadilla'])
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='Fuerza factual',
            estado='completado',
        )
        HyroxActivity.objects.create(
            sesion=sesion,
            tipo_actividad='fuerza',
            nombre_ejercicio='Sentadilla',
            data_metricas={'series': [{'peso_kg': 120, 'reps': 5}]},
        )

        with patch.object(HyroxLoadManager, 'calcular_ctl_atl_tsb', return_value={'tsb': -30}):
            self.assertEqual(RMAutoUpdater.update_from_session(sesion), [])
            self.assertEqual(DeloadAutoTrigger.check_and_apply(sesion), [])

        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.rm_sentadilla, 100)
        self.assertFalse(CicloDeload.objects.filter(cliente=self.cliente).exists())

    def test_correctivos_inactivos_no_ejecutan_adaptador_de_hito(self):
        self._contrato('inactiva')
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='Hito factual',
            estado='completado',
        )
        with patch.object(PostMilestoneEngine, '_adapt_after_simulation') as adaptar:
            mensajes = PostMilestoneEngine.adapt_after_milestone(sesion, 'sim_completa')
        self.assertEqual(mensajes, [])
        adaptar.assert_not_called()

    def test_crear_objetivo_guarda_datos_pero_no_borra_plan_inactivo(self):
        self.client.force_login(self.user)
        self._contrato('inactiva')
        sesion = self._sesion_futura()
        respuesta = self.client.post(reverse('hyrox:crear_objetivo'), {
            'categoria': 'open_men',
            'fecha_evento': str(self.hoy + datetime.timedelta(days=90)),
            'primer_hyrox': 'on',
            'nivel_experiencia': 'intermedio',
            'genero': 'M',
            'fc_reposo': 55,
            'lesiones_previas': '',
            'material_disponible': '',
            'dias_preferidos': '0,2,4,6',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.fc_reposo, 55)
        self.assertTrue(HyroxSession.objects.filter(pk=sesion.pk).exists())
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertTrue(any('guardado' in m.lower() and 'plan' in m.lower() for m in mensajes))

    def test_decision_hyrox_es_neutra_sin_campana_activa(self):
        self._contrato('inactiva')
        decision = _crear_hyrox_decision(current_score=100, cliente=self.cliente)
        self.assertEqual(decision['estado'], 'inactivo')
        self.assertEqual(decision['causa'], 'campana_inactiva')
        self.assertFalse(decision['puede_ejecutar_plan'])
