from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class AutoridadDiariaGymContratoTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='autoridad_gym', password='x')
        self.user = user
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
        self.assertEqual(primera['schema_version'], 2)
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


class AutoridadDiariaGymHistorialTests(AutoridadDiariaGymContratoTests):
    def _versiones(self):
        from entrenos.models import GymDecisionVersion

        return GymDecisionVersion.objects.filter(
            cliente=self.cliente,
            fecha=self.fecha,
        ).order_by('version')

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_repetir_la_misma_decision_no_crea_otra_version(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (self.decision_base['entrenamiento']['ejercicios'], [])

        primera = self._resolver()
        segunda = self._resolver()

        self.assertEqual(primera['decision_id'], segunda['decision_id'])
        self.assertEqual(self._versiones().count(), 1)
        version = self._versiones().get()
        self.assertEqual(version.origen, 'motor')
        self.assertTrue(version.vigente)
        self.assertEqual(version.version, 1)

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_cambio_de_evidencia_crea_version_y_conserva_la_anterior(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (self.decision_base['entrenamiento']['ejercicios'], [])
        primera = self._resolver()

        nueva = dict(self.decision_base)
        nueva['estado'] = 'version_reducida'
        nueva['causa_principal'] = 'energia_baja'
        obtener_base.return_value = nueva
        segunda = self._resolver()

        self.assertNotEqual(primera['decision_id'], segunda['decision_id'])
        self.assertEqual(self._versiones().count(), 2)
        self.assertFalse(self._versiones()[0].vigente)
        self.assertTrue(self._versiones()[1].vigente)
        self.assertEqual(self._versiones()[1].version, 2)
        self.assertEqual(self._versiones()[1].reemplaza, self._versiones()[0])

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_correccion_supervisada_crea_version_y_se_reaplica_sobre_la_misma_base(
        self, obtener_base, aplicar_plan,
    ):
        from entrenos.services.autoridad_diaria_gym_service import corregir_autoridad_diaria_gym

        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (self.decision_base['entrenamiento']['ejercicios'], [])
        original = self._resolver()

        corregida = corregir_autoridad_diaria_gym(
            self.cliente,
            self.fecha,
            decision_id_esperada=original['decision_id'],
            ajustes={'postura': 'sostener', 'modo_reducido': True},
            motivo='Hoy prefiero conservar margen.',
        )
        releida = self._resolver()

        self.assertEqual(corregida['postura'], 'sostener')
        self.assertEqual(releida['decision_id'], corregida['decision_id'])
        self.assertEqual(releida['origen_decision'], 'correccion_manual')
        self.assertEqual(self._versiones().count(), 2)
        self.assertEqual(self._versiones()[1].motivo_correccion, 'Hoy prefiero conservar margen.')

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_rechaza_correccion_obsoleta_o_menos_segura(
        self, obtener_base, aplicar_plan,
    ):
        from entrenos.services.autoridad_diaria_gym_service import (
            AutoridadGymCorreccionInvalida,
            corregir_autoridad_diaria_gym,
        )

        protegida = dict(self.decision_base)
        protegida.update({'estado': 'recuperar', 'causa_principal': 'lesion'})
        obtener_base.return_value = protegida
        actual = self._resolver()

        with self.assertRaises(AutoridadGymCorreccionInvalida):
            corregir_autoridad_diaria_gym(
                self.cliente, self.fecha,
                decision_id_esperada='gym-obsoleta',
                ajustes={'postura': 'sostener'},
                motivo='Corrección vieja',
            )
        with self.assertRaises(AutoridadGymCorreccionInvalida):
            corregir_autoridad_diaria_gym(
                self.cliente, self.fecha,
                decision_id_esperada=actual['decision_id'],
                ajustes={'postura': 'empujar'},
                motivo='Ignorar protección',
            )

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_endpoint_autenticado_aplica_correccion_supervisada(
        self, obtener_base, aplicar_plan,
    ):
        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (self.decision_base['entrenamiento']['ejercicios'], [])
        actual = self._resolver()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('entrenos:corregir_autoridad_gym', args=[self.cliente.pk]),
            {
                'fecha': self.fecha.isoformat(),
                'decision_id': actual['decision_id'],
                'postura': 'sostener',
                'motivo': 'Hoy quiero dejar margen.',
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['decision']['postura'], 'sostener')
        self.assertEqual(payload['decision']['origen_decision'], 'correccion_manual')

    def test_portada_expone_control_supervisado_sin_duplicar_accion_principal(self):
        from pathlib import Path

        template = Path('clientes/templates/clientes/mockup_demo.html').read_text(
            encoding='utf-8'
        )
        bloque = template[
            template.index('<!-- ── DECISIÓN ÚNICA HOY'):
            template.index('<!-- ── TOGGLE GYM / HYROX')
        ]

        self.assertIn('data-gym-correction', bloque)
        self.assertIn("entrenos:corregir_autoridad_gym", bloque)
        self.assertIn('Prefiero dejar margen', bloque)
        self.assertEqual(bloque.count('data-primary-action'), 3)

    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_revertir_correccion_crea_otra_version_sin_borrar_historial(
        self, obtener_base, aplicar_plan,
    ):
        from entrenos.services.autoridad_diaria_gym_service import (
            corregir_autoridad_diaria_gym,
            revertir_correccion_autoridad_diaria_gym,
        )

        obtener_base.return_value = self.decision_base
        aplicar_plan.return_value = (self.decision_base['entrenamiento']['ejercicios'], [])
        original = self._resolver()
        corregida = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=original['decision_id'],
            ajustes={'postura': 'sostener'},
            motivo='Dejar margen.',
        )

        restaurada = revertir_correccion_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=corregida['decision_id'],
            motivo='Vuelvo a la propuesta del motor.',
        )

        self.assertEqual(restaurada['postura'], 'empujar')
        self.assertEqual(restaurada['origen_decision'], 'reversion_manual')
        self.assertEqual(self._versiones().count(), 3)
        self.assertEqual(self._versiones()[2].reemplaza, self._versiones()[1])
