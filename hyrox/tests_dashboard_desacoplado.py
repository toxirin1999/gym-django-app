import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import GymDecisionVersion, SesionProgramada
from hyrox.models import (
    ContratoCampanaHyrox, HyroxActivity, HyroxObjective, HyroxSession,
)


class DashboardHyroxDesacopladoTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user('hyrox-desacoplado', password='secret')
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=70),
            estado='activo',
        )
        self.objetivo_historico_mas_nuevo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=140),
            estado='completado',
        )
        self.plan = HyroxSession.objects.create(
            objective=self.objetivo, fecha=self.hoy,
            estado='planificado', titulo='Plan Hyrox existente',
        )
        HyroxActivity.objects.create(
            sesion=self.plan, tipo_actividad='carrera',
            nombre_ejercicio='Carrera existente',
        )
        self.futura = HyroxSession.objects.create(
            objective=self.objetivo, fecha=self.hoy + datetime.timedelta(days=2),
            estado='planificado', titulo='Futuro preservado',
        )
        self.completada = HyroxSession.objects.create(
            objective=self.objetivo, fecha=self.hoy - datetime.timedelta(days=2),
            estado='completado', titulo='Historial Hyrox existente', rpe_global=6,
        )
        self.campana = ContratoCampanaHyrox.objects.create(
            cliente=self.cliente, version=1, estado='inactiva',
            objetivo=self.objetivo, objetivo_snapshot={}, bloque_gym_snapshot={},
            limites_snapshot={}, fingerprint='9' * 64,
        )
        GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=self.hoy, version=1,
            decision_id='gym-desacoplado', schema_version=2,
            origen=GymDecisionVersion.ORIGEN_MOTOR, vigente=True,
            fingerprint='8' * 64, base_fingerprint='8' * 64,
            postura='empujar', causa_principal='gym_prioritario',
            snapshot={'estado': 'entrenar', 'postura': 'empujar'},
        )
        self.gym = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.hoy,
            nombre_sesion='Gym prioritario',
        )
        self.client.login(username='hyrox-desacoplado', password='secret')

    @patch('hyrox.services.HyroxSessionOverrideEngine.apply_today_override')
    @patch('hyrox.training_engine.HyroxTrainingEngine.generate_training_plan')
    @patch('entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym')
    def test_inactivo_recupera_dashboard_competitivo_sin_escribir_autoridad(
        self, resolver_gym, generar_plan, auto_adjust,
    ):
        response = self.client.get(reverse('hyrox:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['hyrox_desacoplado'])
        self.assertFalse(response.context['campana_hyrox_activa'])
        self.assertEqual(response.context['objetivo_activo'], self.objetivo)
        self.assertContains(response, 'Race Command')
        self.assertContains(response, 'Macrociclo')
        self.assertContains(response, 'Plan de entrenamiento')
        self.assertContains(response, 'Carrera existente')
        self.assertContains(
            response,
            reverse(
                'hyrox:registrar_entrenamiento_session',
                kwargs={
                    'objective_id': self.objetivo.pk,
                    'session_id': self.plan.pk,
                },
            ),
        )
        self.assertContains(response, 'Historial Hyrox existente')
        self.assertContains(response, 'GYM PRIORITARIO')
        self.assertContains(response, 'Gym dirige el panel principal y Hyrox solo opera aquí')
        self.assertNotContains(response, 'HYROX EN PAUSA')
        resolver_gym.assert_not_called()
        generar_plan.assert_not_called()
        auto_adjust.assert_not_called()

    def test_consumidores_externos_y_joi_siguen_sin_objetivo_autorizado(self):
        from clientes.views import _ctx_hyrox
        from joi.context_builders.hyrox_context import build_hyrox_context

        self.assertEqual(_ctx_hyrox(self.cliente, self.hoy), (None, None))
        self.assertEqual(
            build_hyrox_context(
                self.cliente, self.hoy,
                self.hoy - datetime.timedelta(days=7),
            ),
            {},
        )

    @patch('hyrox.services.HyroxSessionOverrideEngine.apply_today_override')
    @patch('hyrox.training_engine.HyroxTrainingEngine.generate_training_plan')
    def test_registro_manual_existente_es_factual_sin_mutar_futuro_gym_o_campana(
        self, generar_plan, auto_adjust,
    ):
        gym_antes = (self.gym.estado, self.gym.fecha_prevista, self.gym.pospuesta_hasta)
        futuras_antes = list(HyroxSession.objects.filter(
            objective=self.objetivo, fecha__gt=self.hoy
        ).values_list('pk', 'fecha', 'estado', 'titulo'))

        response = self.client.post(
            reverse('hyrox:registrar_entrenamiento_session', args=[self.objetivo.pk, self.plan.pk]),
            {
                'titulo': 'Plan Hyrox existente', 'nivel_energia_pre': 7,
                'tiempo_total_minutos': 30, 'rpe_global': 6, 'notas_raw': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.gym.refresh_from_db()
        self.campana.refresh_from_db()
        self.assertEqual(self.plan.estado, 'completado')
        self.assertEqual(
            (self.gym.estado, self.gym.fecha_prevista, self.gym.pospuesta_hasta),
            gym_antes,
        )
        self.assertEqual(self.campana.estado, 'inactiva')
        self.assertEqual(list(HyroxSession.objects.filter(
            objective=self.objetivo, fecha__gt=self.hoy
        ).values_list('pk', 'fecha', 'estado', 'titulo')), futuras_antes)
        generar_plan.assert_not_called()
        auto_adjust.assert_not_called()
