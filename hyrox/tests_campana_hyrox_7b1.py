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
    UserInjury,
)
from hyrox.training_engine import HyroxTrainingEngine
from hyrox.views import _crear_hyrox_decision
from core.bio_context import BioContextProvider


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
