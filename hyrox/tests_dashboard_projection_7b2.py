import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from entrenos.models import (
    ContratoBloqueGym,
    EstrategiaSemanalGym,
    GymDecisionVersion,
)
from hyrox.models import ContratoCampanaHyrox, HyroxObjective, HyroxReadinessLog


class ProyeccionDashboardHyroxTests(TestCase):
    def _gym(self, postura):
        estado = {
            'proteger': 'recuperar',
            'sostener': 'version_reducida',
            'empujar': 'entrenar',
        }[postura]
        return {
            'source': 'motor',
            'decision_id': 'gym-2026-08-22-identidad',
            'version_persistida': 7,
            'postura': postura,
            'estado': estado,
            'causa_principal': 'gym_base',
            'permitido': ['Sesión Gym autorizada'],
            'evitar': ['Límite Gym'],
        }

    def test_inactiva_es_exploracion_pura_con_identidad_gym(self):
        from hyrox.dashboard_projection import proyectar_decision_hyrox

        decision = proyectar_decision_hyrox(
            self._gym('empujar'),
            campana_activa=False,
            readiness=100,
            resumen_carga={'tsb': 20, 'acwr': 0.8},
        )
        self.assertEqual(decision['source'], 'gym_decision_version')
        self.assertTrue(decision['hyrox_es_proyeccion'])
        self.assertEqual(decision['decision_id'], 'gym-2026-08-22-identidad')
        self.assertEqual(decision['version'], 7)
        self.assertEqual(decision['gym_decision_version'], 7)
        self.assertEqual(decision['estado'], 'inactivo')
        self.assertEqual(decision['accion_label'], 'Explorar Hyrox')
        self.assertFalse(decision['puede_ejecutar_plan'])

    def test_matriz_solo_puede_aumentar_proteccion(self):
        from hyrox.dashboard_projection import proyectar_decision_hyrox

        escenarios = {
            'sin_senal': ({'readiness': 90, 'resumen_carga': {}}, {
                'proteger': 'proteger', 'sostener': 'sostener', 'empujar': 'empujar',
            }),
            'lesion': ({'readiness': 90, 'resumen_carga': {}, 'lesion_activa': object()}, {
                'proteger': 'proteger', 'sostener': 'proteger', 'empujar': 'proteger',
            }),
            'readiness': ({'readiness': 35, 'resumen_carga': {}}, {
                'proteger': 'proteger', 'sostener': 'sostener', 'empujar': 'sostener',
            }),
            'carga': ({'readiness': 90, 'resumen_carga': {'tsb': -25, 'acwr': 1.8}}, {
                'proteger': 'proteger', 'sostener': 'proteger', 'empujar': 'proteger',
            }),
        }
        estado_a_postura = {
            'recuperar': 'proteger', 'sostener': 'sostener', 'empujar': 'empujar',
        }
        for nombre, (kwargs, esperados) in escenarios.items():
            for postura_gym, esperado in esperados.items():
                with self.subTest(escenario=nombre, postura=postura_gym):
                    decision = proyectar_decision_hyrox(
                        self._gym(postura_gym), campana_activa=True, **kwargs
                    )
                    self.assertEqual(estado_a_postura[decision['estado']], esperado)
                    self.assertEqual(decision['decision_id'], 'gym-2026-08-22-identidad')
                    self.assertEqual(decision['gym_decision_version'], 7)

    def test_conserva_restricciones_gym(self):
        from hyrox.dashboard_projection import proyectar_decision_hyrox

        decision = proyectar_decision_hyrox(
            self._gym('sostener'), campana_activa=True, readiness=80,
            resumen_carga={},
        )
        self.assertEqual(decision['permitido'], ['Sesión Gym autorizada'])
        self.assertEqual(decision['evitar'], ['Límite Gym'])


class DashboardHyroxAutoridadGymTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user('dashboard_hyrox_7b2', password='test')
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=60),
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.hoy,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado='activo',
            semana_inicio=self.hoy, semanas_previstas=4,
            semana_fin_prevista=self.hoy + datetime.timedelta(days=27),
            estrategia=estrategia, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='hipertrofia', objetivos_secundarios=[],
            limites_snapshot={}, motor_nombre='Helms', motor_version='actual',
            fingerprint='d' * 64,
        )
        self.client.force_login(self.user)

    def _contrato(self, estado):
        return ContratoCampanaHyrox.objects.create(
            cliente=self.cliente, version=1, estado=estado,
            objetivo=self.objetivo if estado == 'activa' else None,
            bloque_gym=self.bloque if estado == 'activa' else None,
            objetivo_snapshot={
                'id': self.objetivo.pk,
                'fecha_evento': str(self.objetivo.fecha_evento),
            } if estado == 'activa' else {},
            fingerprint='e' * 64, aprobado_por=self.user,
        )

    def _version_gym(self, postura='empujar'):
        return GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=self.hoy, version=4,
            decision_id='gym-dashboard-identidad', schema_version=2,
            origen=GymDecisionVersion.ORIGEN_MOTOR, vigente=True,
            fingerprint='f' * 64, base_fingerprint='f' * 64,
            postura=postura, causa_principal='sesion_hoy',
            snapshot={
                'decision_id': 'gym-dashboard-identidad',
                'version_persistida': 4,
                'postura': postura,
                'estado': 'entrenar',
                'permitido': ['Plan Gym'],
                'evitar': [],
            },
        )

    def test_get_inactivo_lee_version_existente_sin_mutar(self):
        self._contrato('inactiva')
        self._version_gym()
        versiones_antes = GymDecisionVersion.objects.count()
        readiness_antes = HyroxReadinessLog.objects.count()
        with (
            patch('hyrox.views._crear_hyrox_decision', side_effect=AssertionError('autoridad paralela')),
            patch('entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym') as resolver,
        ):
            with CaptureQueriesContext(connection) as queries:
                respuesta = self.client.get(reverse('hyrox:dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        resolver.assert_not_called()
        decision = respuesta.context['hyrox_decision']
        self.assertEqual(decision['source'], 'gym_decision_version')
        self.assertEqual(decision['decision_id'], 'gym-dashboard-identidad')
        self.assertEqual(decision['estado'], 'inactivo')
        self.assertFalse(decision['puede_ejecutar_plan'])
        self.assertEqual(GymDecisionVersion.objects.count(), versiones_antes)
        self.assertEqual(HyroxReadinessLog.objects.count(), readiness_antes)
        mutaciones = [
            q['sql'] for q in queries.captured_queries
            if q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
        ]
        self.assertEqual(mutaciones, [])

    def test_get_activo_resuelve_gym_y_proyecta_misma_identidad(self):
        self._contrato('activa')
        autoridad = {
            'decision_id': 'gym-activa-identidad',
            'version_persistida': 9,
            'postura': 'sostener',
            'estado': 'version_reducida',
            'causa_principal': 'energia_baja',
            'permitido': ['Plan reducido'],
            'evitar': ['Volumen extra'],
        }
        with (
            patch('hyrox.views._crear_hyrox_decision', side_effect=AssertionError('autoridad paralela')),
            patch(
                'entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym',
                return_value=autoridad,
            ) as resolver,
        ):
            respuesta = self.client.get(reverse('hyrox:dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        resolver.assert_called_once_with(self.cliente, self.hoy)
        decision = respuesta.context['hyrox_decision']
        self.assertEqual(decision['decision_id'], 'gym-activa-identidad')
        self.assertEqual(decision['gym_decision_version'], 9)
        self.assertEqual(decision['estado'], 'sostener')
