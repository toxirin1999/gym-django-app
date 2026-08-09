from unittest.mock import patch

from django.test import SimpleTestCase

from hyrox.decision_service import calcular_hyrox_decision
from hyrox.views import _crear_hyrox_decision


class DecisionServiceCompatibilityTests(SimpleTestCase):
    def test_readiness_cero_nunca_se_interpreta_como_estado_normal(self):
        decision = calcular_hyrox_decision(current_score=0)

        self.assertEqual(decision['causa'], 'readiness_bajo')
        self.assertEqual(decision['estado'], 'sostener')

    def test_wrapper_historico_delega_en_servicio_publico(self):
        esperada = {'puede_ejecutar_plan': False, 'estado': 'recuperar'}

        with patch(
            'hyrox.decision_service.calcular_hyrox_decision',
            return_value=esperada,
        ) as autoridad:
            resultado = _crear_hyrox_decision(
                current_score=82,
                resumen_semanal={'tsb': 1, 'acwr': 1},
            )

        self.assertIs(resultado, esperada)
        autoridad.assert_called_once_with(
            current_score=82,
            resumen_semanal={'tsb': 1, 'acwr': 1},
            lesion_activa=None,
            es_descanso_plan=False,
            estado_entreno=None,
            senales_secundarias=None,
        )
