import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.models import ContratoCampanaHyrox, HyroxObjective, UserInjury
from joi.models import NarrativaActiva
from joi.services import determinar_estado_habitacion_joi


class JoiHabitacionCampaignAuthorityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('joi-campaign-authority')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.localdate()

    def _objetivo(self, *, dias=90):
        return HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=self.hoy + datetime.timedelta(days=dias),
        )

    def _campana_activa(self, objetivo):
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=4,
            minimo_valido=3,
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
            minimo_valido=3,
            objetivo_principal='hipertrofia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='a' * 64,
        )
        return ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activa',
            objetivo=objetivo,
            bloque_gym=bloque,
            objetivo_snapshot={
                'id': objetivo.pk,
                'fecha_evento': str(objetivo.fecha_evento),
                'estado': objetivo.estado,
            },
            bloque_gym_snapshot={'estado': 'activo'},
            limites_snapshot={},
            fingerprint='b' * 64,
        )

    @patch('hyrox.pulso_service.PulsoService.determinar_pulso')
    def test_pulso_evalua_solo_objetivo_exacto_de_campana_activa(self, pulso):
        autorizado = self._objetivo(dias=60)
        legacy_mas_reciente = self._objetivo(dias=120)
        self._campana_activa(autorizado)
        pulso.return_value = {'pulso': 'silencioso'}

        determinar_estado_habitacion_joi(self.user)

        pulso.assert_called_once()
        self.assertEqual(pulso.call_args.kwargs['objetivo'], autorizado)
        self.assertNotEqual(pulso.call_args.kwargs['objetivo'], legacy_mas_reciente)

    @patch('hyrox.pulso_service.PulsoService.determinar_pulso')
    def test_objetivo_legacy_no_eclipsa_presencia_narrativa(self, pulso):
        self._objetivo()
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', capa_corta='Lectura longitudinal'
        )
        pulso.return_value = {'pulso': 'protegiendo'}

        estado, motivo = determinar_estado_habitacion_joi(self.user)

        pulso.assert_not_called()
        self.assertEqual((estado, motivo), ('PRESENTE', 'narrativa_activa'))

    @patch('hyrox.pulso_service.PulsoService.determinar_pulso')
    def test_campana_vencida_no_usa_objetivo_legacy_para_pulso(self, pulso):
        objetivo = self._objetivo(dias=30)
        contrato = self._campana_activa(objetivo)
        objetivo.fecha_evento = self.hoy
        objetivo.save(update_fields=['fecha_evento'])
        pulso.return_value = {'pulso': 'protegiendo'}

        estado, _ = determinar_estado_habitacion_joi(self.user)

        pulso.assert_not_called()
        self.assertEqual(estado, 'SILENCIO')
        self.assertIsNotNone(contrato.pk)

    def test_lesion_inactiva_aguda_no_pone_joi_protegiendo(self):
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='rodilla',
            fase='AGUDA',
            activa=False,
        )

        estado, _ = determinar_estado_habitacion_joi(self.user)

        self.assertEqual(estado, 'SILENCIO')

    def test_lesion_activa_aguda_protege_sin_campana(self):
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='tobillo',
            fase='AGUDA',
            activa=True,
        )

        estado, motivo = determinar_estado_habitacion_joi(self.user)

        self.assertEqual((estado, motivo), ('PROTEGIENDO', 'lesion_activa'))
