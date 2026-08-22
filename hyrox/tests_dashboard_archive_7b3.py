from unittest.mock import patch

from django.urls import reverse

from hyrox.tests_dashboard_projection_7b2 import DashboardHyroxAutoridadGymTests


class DashboardHyroxArchivoVisualTests(DashboardHyroxAutoridadGymTests):
    def test_campana_inactiva_muestra_archivo_y_oculta_prescripcion(self):
        self._contrato('inactiva')
        self._version_gym()

        with (
            patch(
                'hyrox.views._crear_hyrox_decision',
                side_effect=AssertionError('autoridad paralela'),
            ),
            patch(
                'entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym'
            ) as resolver,
        ):
            respuesta = self.client.get(reverse('hyrox:dashboard'))

        self.assertEqual(respuesta.status_code, 200)
        resolver.assert_not_called()
        self.assertFalse(respuesta.context['campana_hyrox_activa'])
        self.assertContains(respuesta, 'HYROX EN PAUSA')
        self.assertContains(respuesta, 'SIN CAMPAÑA ACTIVA')
        self.assertContains(respuesta, 'Gym dirige tu entrenamiento')
        self.assertContains(respuesta, 'Historial preservado')
        self.assertContains(respuesta, '>ARCHIVO</div>')
        self.assertNotContains(respuesta, '>LIVE</div>')
        self.assertContains(respuesta, 'STRAVA DISPONIBLE')
        self.assertNotContains(respuesta, 'STRAVA CONECTADO')
        self.assertContains(respuesta, 'Panel')
        self.assertContains(respuesta, 'Strava')
        self.assertContains(respuesta, 'Lesión y recuperación')

        self.assertNotContains(respuesta, 'Race<span')
        self.assertNotContains(respuesta, 'Race Command')
        self.assertNotContains(respuesta, 'Estaciones a reforzar esta semana')
        self.assertNotContains(respuesta, 'Fases del macrociclo')
        self.assertNotContains(respuesta, 'Hitos del macrociclo')
        self.assertNotContains(respuesta, 'Lo que aprendió el plan esta semana')
        self.assertNotContains(
            respuesta,
            reverse('hyrox:registrar_entrenamiento', args=[self.objetivo.pk]),
        )

    def test_campana_activa_conserva_dashboard_competitivo(self):
        self._contrato('activa')
        autoridad = {
            'decision_id': 'gym-activa-visual',
            'version_persistida': 2,
            'postura': 'empujar',
            'estado': 'entrenar',
            'causa_principal': 'sesion_hoy',
            'permitido': ['Plan autorizado'],
            'evitar': [],
        }

        with patch(
            'entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym',
            return_value=autoridad,
        ):
            respuesta = self.client.get(reverse('hyrox:dashboard'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['campana_hyrox_activa'])
        self.assertContains(respuesta, '>LIVE</div>')
        self.assertNotContains(respuesta, '>ARCHIVO</div>')
        self.assertContains(respuesta, 'Race<span')
        self.assertContains(respuesta, 'Macrociclo')
        self.assertNotContains(respuesta, 'HYROX EN PAUSA')
