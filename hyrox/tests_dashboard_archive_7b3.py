from unittest.mock import patch

from django.urls import reverse

from hyrox.tests_dashboard_projection_7b2 import DashboardHyroxAutoridadGymTests


class DashboardHyroxArchivoVisualTests(DashboardHyroxAutoridadGymTests):
    def test_campana_inactiva_muestra_dashboard_desacoplado_sin_prescribir(self):
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
        self.assertTrue(respuesta.context['hyrox_desacoplado'])
        self.assertContains(respuesta, 'GYM PRIORITARIO')
        self.assertContains(respuesta, 'HYROX DESACOPLADO')
        self.assertContains(
            respuesta,
            'Gym dirige el panel principal y Hyrox solo opera aquí.',
        )
        self.assertNotContains(respuesta, '>ARCHIVO</div>')
        self.assertNotContains(respuesta, '>LIVE</div>')
        self.assertContains(respuesta, 'Race<span')
        self.assertContains(respuesta, 'Race Command')
        self.assertContains(
            respuesta,
            reverse('hyrox:registrar_entrenamiento', args=[self.objetivo.pk]),
        )
        self.assertNotContains(respuesta, 'HYROX EN PAUSA')
        self.assertNotContains(respuesta, 'SIN CAMPAÑA ACTIVA')

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
        self.assertFalse(respuesta.context['hyrox_desacoplado'])
        self.assertContains(respuesta, '>LIVE</div>')
        self.assertNotContains(respuesta, '>ARCHIVO</div>')
        self.assertContains(respuesta, 'Race<span')
        self.assertContains(respuesta, 'Macrociclo')
        self.assertNotContains(respuesta, 'HYROX EN PAUSA')
