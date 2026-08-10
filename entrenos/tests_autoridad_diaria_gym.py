from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente


class AutoridadDiariaGymContratoTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='autoridad_gym', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user,
            defaults={'nombre': 'Autoridad Gym'},
        )
        self.fecha = date(2026, 8, 10)
        self.decision_base = {
            'tipo': 'programada_hoy',
            'estado': 'entrenar',
            'causa_principal': 'sesion_hoy',
            'capas_suprimidas': ['distribucion_aviso'],
            'sesion_programada': None,
            'mensaje': 'Esta es la sesión prevista para hoy.',
            'entrenamiento': {
                'rutina_nombre': 'Push',
                'ejercicios': [{
                    'nombre': 'Press banca',
                    'series': 3,
                    'repeticiones': 8,
                    'peso_recomendado_kg': 60,
                }],
            },
        }

    def tearDown(self):
        cache.clear()

    def _resolver(self):
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym

        return resolver_autoridad_diaria_gym(self.cliente, self.fecha)

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_materializa_una_sola_sesion_ejecutable_con_identidad_estable(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (
            [{
                'nombre': 'Press banca',
                'series': 3,
                'repeticiones': 8,
                'peso_recomendado_kg': 62.5,
            }],
            [{'tipo': 'progresion', 'ejercicio': 'Press banca'}],
        )

        primera = self._resolver()
        segunda = self._resolver()

        self.assertEqual(primera, segunda)
        self.assertEqual(primera['schema_version'], 1)
        self.assertEqual(primera['postura'], 'empujar')
        self.assertEqual(primera['fecha'], '2026-08-10')
        self.assertEqual(primera['vigente_hasta'], '2026-08-10')
        self.assertTrue(primera['decision_id'].startswith('gym-2026-08-10-'))
        self.assertEqual(
            primera['entrenamiento']['ejercicios'][0]['peso_recomendado_kg'],
            62.5,
        )
        self.assertEqual(primera['cambios_materializados'][0]['tipo'], 'progresion')
        self.assertEqual(aplicar_plan.call_count, 1)

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_proteger_conserva_causa_principal_secundarias_y_capas_suprimidas(
        self, obtener_base, aplicar_plan,
    ):
        decision = dict(self.decision_base)
        decision.update({
            'estado': 'recuperar',
            'causa_principal': 'lesion',
            'contexto_fisico': {
                'energia_baja': True,
                'futbol_reciente': True,
                'readiness_bajo': False,
            },
        })
        obtener_base.return_value = decision

        autoridad = self._resolver()

        self.assertEqual(autoridad['postura'], 'proteger')
        self.assertEqual(autoridad['causa_principal'], 'lesion')
        self.assertEqual(
            autoridad['causas_secundarias'],
            ['energia_baja', 'futbol_reciente'],
        )
        self.assertEqual(autoridad['capas_suprimidas'], ['distribucion_aviso'])
        self.assertEqual(autoridad['cambios_materializados'], [])
        aplicar_plan.assert_not_called()

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_version_reducida_se_traduce_a_postura_sostener(
        self, obtener_base, aplicar_plan,
    ):
        decision = dict(self.decision_base)
        decision.update({'estado': 'version_reducida', 'causa_principal': 'energia_baja'})
        obtener_base.return_value = decision
        aplicar_plan.return_value = (
            decision['entrenamiento']['ejercicios'],
            [{'tipo': 'version_esencial'}],
        )

        autoridad = self._resolver()

        self.assertEqual(autoridad['postura'], 'sostener')
        self.assertEqual(autoridad['causa_principal'], 'energia_baja')

    def test_dashboard_consume_la_autoridad_y_no_el_motor_base(self):
        source = Path('clientes/views.py').read_text(encoding='utf-8')
        bloque = source[source.index('def _get_dashboard_context_data'):source.index('def mockup_demo')]

        self.assertIn('resolver_autoridad_diaria_gym', bloque)
        self.assertNotIn(
            'obtener_sesion_recomendada_hoy as _get_sesion_hoy',
            bloque,
        )

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_deload_materializado_no_se_vuelve_a_aplicar_en_sesion_activa(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = self.decision_base
        ejercicios = [dict(self.decision_base['entrenamiento']['ejercicios'][0], series=2)]
        aplicar_plan.return_value = (ejercicios, [{'tipo': 'deload'}])

        autoridad = self._resolver()

        self.assertTrue(
            autoridad['entrenamiento']['ejercicios'][0]['_deload_aplicado']
        )

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_declara_capa_suprimida_aunque_el_motor_no_la_serialice(
        self, obtener_base, aplicar_plan,
    ):
        decision = dict(self.decision_base)
        decision.pop('capas_suprimidas')
        decision['distribucion_aviso'] = {'tipo': 'redistrib_pierna_futbol'}
        decision['preferencia_aplicada'] = {'tipo': 'evitar_pierna_tras_futbol'}
        obtener_base.return_value = decision
        aplicar_plan.return_value = (decision['entrenamiento']['ejercicios'], [])

        autoridad = self._resolver()

        self.assertEqual(autoridad['capas_suprimidas'], ['distribucion_aviso'])

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_descanso_planificado_sostiene_sin_simular_alarma(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = {
            'tipo': 'descanso',
            'estado': 'descanso',
            'causa_principal': 'descanso_planificado',
            'mensaje': 'Hoy el plan marca descanso.',
            'entrenamiento': None,
            'sesion_programada': None,
        }

        autoridad = self._resolver()

        self.assertEqual(autoridad['postura'], 'sostener')
        aplicar_plan.assert_not_called()
