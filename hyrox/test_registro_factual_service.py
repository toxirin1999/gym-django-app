import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from entrenos.models import ActividadRealizada, ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.models import ContratoCampanaHyrox, HyroxActivity, HyroxObjective, HyroxSession
from hyrox.training_engine import HyroxTrainingEngine


class RegistroFactualHyroxServiceTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('registro_factual_hyrox')
        self.cliente = user.cliente_perfil
        self.hoy = timezone.localdate()
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=60),
        )

    def _sesion(self):
        sesion = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=self.hoy,
            titulo='Registro manual factual',
        )
        HyroxActivity.objects.create(
            sesion=sesion,
            tipo_actividad='hyrox_station',
            nombre_ejercicio='Wall Balls',
            data_metricas={},
        )
        return sesion

    def _activar_campana(self):
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=4,
            minimo_valido=2,
            vigente_desde=self.hoy,
        )
        bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activo',
            semana_inicio=self.hoy,
            semanas_previstas=4,
            semana_fin_prevista=self.hoy + datetime.timedelta(days=27),
            estrategia=estrategia,
            objetivo_sesiones=4,
            minimo_valido=2,
            objetivo_principal='hipertrofia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='f' * 64,
        )
        ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activa',
            objetivo=self.objetivo,
            bloque_gym=bloque,
            objetivo_snapshot={
                'id': self.objetivo.pk,
                'fecha_evento': str(self.objetivo.fecha_evento),
            },
            bloque_gym_snapshot={'id': bloque.pk, 'estado': 'activo'},
            fingerprint='a' * 64,
        )

    @patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation')
    @patch.object(HyroxTrainingEngine, 'scale_volume_by_energy')
    def test_nucleo_factual_inactivo_persiste_sesion_actividad_y_hub_sin_prescribir(
        self, escala, adapta,
    ):
        from hyrox.services import guardar_registro_factual_hyrox_service

        sesion = self._sesion()
        resultado = guardar_registro_factual_hyrox_service(
            self.objetivo,
            sesion,
            {'rpe_global': 8, 'act_reps_st_1': '75', 'act_done_1': '1'},
        )

        self.assertTrue(resultado['success'])
        sesion.refresh_from_db()
        actividad = sesion.activities.get()
        self.assertEqual(sesion.estado, 'completado')
        self.assertEqual(sesion.rpe_global, 8)
        self.assertEqual(actividad.data_metricas['reps_total'], 75)
        self.assertTrue(ActividadRealizada.objects.filter(sesion_hyrox=sesion).exists())
        escala.assert_not_called()
        adapta.assert_not_called()
        self.assertEqual(resultado['eventos'], [])

    @patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation')
    @patch.object(HyroxTrainingEngine, 'scale_volume_by_energy')
    def test_nucleo_factual_tampoco_prescribe_aunque_campana_este_activa(self, escala, adapta):
        from hyrox.services import guardar_registro_factual_hyrox_service

        self._activar_campana()
        resultado = guardar_registro_factual_hyrox_service(
            self.objetivo, self._sesion(), {'rpe_global': 7}
        )

        self.assertTrue(resultado['success'])
        escala.assert_not_called()
        adapta.assert_not_called()

    @patch.object(HyroxTrainingEngine, 'apply_continuous_adaptation', return_value=[])
    @patch.object(HyroxTrainingEngine, 'scale_volume_by_energy', return_value=None)
    def test_wrapper_existente_con_campana_activa_conserva_efectos(self, escala, adapta):
        from hyrox.services import guardar_sesion_hyrox_service

        self._activar_campana()
        sesion = self._sesion()
        resultado = guardar_sesion_hyrox_service(self.objetivo, sesion, {'rpe_global': 7})

        self.assertTrue(resultado['success'])
        escala.assert_called_once_with(sesion)
        adapta.assert_called_once_with(sesion)
