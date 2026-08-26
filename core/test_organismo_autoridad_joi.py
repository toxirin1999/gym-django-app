from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from core.organismo import _check_protegiendo


class TestAutoridadGymSobrePresenciaJoi(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('autoridad_gym_joi', password='x')

    @patch(
        'joi.services.determinar_estado_habitacion_joi',
        return_value=('PROTEGIENDO', 'presencia_narrativa'),
    )
    def test_joi_no_eleva_estado_global_si_gym_ya_tiene_postura_operativa(self, _joi):
        for postura in ('sostener', 'empujar', 'descanso'):
            with self.subTest(postura=postura):
                resultado = _check_protegiendo(
                    self.user,
                    decision_gym={'postura': postura},
                )

                self.assertIsNone(
                    resultado,
                    'JOI puede proteger narrativamente, pero no sustituir la '
                    'autoridad ejecutiva ya resuelta por Gym.',
                )

    @patch(
        'joi.services.determinar_estado_habitacion_joi',
        return_value=('PROTEGIENDO', 'presencia_narrativa'),
    )
    def test_postura_proteger_conserva_gym_como_modulo_y_cta_de_briefing(self, _joi):
        resultado = _check_protegiendo(
            self.user,
            decision_gym={
                'postura': 'proteger',
                'causa_principal': 'fatiga_alta',
                'mensaje': 'Conviene proteger la sesión.',
                'decision_id': 'decision-test',
                'fecha': '2026-08-26',
            },
        )

        self.assertEqual(resultado['estado'], 'PROTEGIENDO')
        self.assertEqual(resultado['modulo_principal'], 'gym')
        self.assertEqual(resultado['accion_label'], 'Revisar sesión')
        self.assertIn('/entrenos/cliente/', resultado['accion_url'])
        self.assertNotEqual(resultado['accion_label'], 'Ver habitación')
        _joi.assert_not_called()

