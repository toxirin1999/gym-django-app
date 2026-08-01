from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase


class PreguntaSimbiosisJOITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pregunta-simbiosis')

    @patch('joi.services._llamar_haiku', return_value='¿Qué cambia cuando dejas de esperar?')
    @patch('joi.services._bloque_manual', return_value='MANUAL')
    @patch('joi.services._bloque_narrativa', return_value='NARRATIVA')
    @patch('joi.services._historial_simbiosis', return_value='HISTORIAL DE ANA')
    def test_prompt_prioriza_narrativa_manual_e_historial_del_trigger(
        self, _historial, _narrativa, manual, llamar,
    ):
        from joi.services import generar_pregunta_simbiosis

        resultado = generar_pregunta_simbiosis(self.user, 'Ana')

        self.assertEqual(resultado, '¿Qué cambia cuando dejas de esperar?')
        manual.assert_called_once_with(self.user, incluir_narrativa=False)
        prompt = llamar.call_args.args[0]
        self.assertLess(prompt.index('NARRATIVA'), prompt.index('MANUAL'))
        self.assertLess(prompt.index('MANUAL'), prompt.index('HISTORIAL DE ANA'))
        self.assertEqual(prompt.count('NARRATIVA'), 1)

    @patch('joi.services._llamar_haiku', side_effect=RuntimeError('IA caída'))
    def test_fallo_ia_no_inventa_una_pregunta_joi(self, _llamar):
        from joi.services import generar_pregunta_simbiosis

        self.assertEqual(generar_pregunta_simbiosis(self.user, 'Ana'), '')
