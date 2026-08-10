from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from core.daily_decision import DailyDecisionEngine


class SemaforoDesdeAutoridadGymTests(TestCase):
    def test_proyecta_sostener_sin_recalcular_senales(self):
        autoridad = {
            'postura': 'sostener',
            'causa_principal': 'energia_baja',
            'mensaje': 'Hoy basta con la versión esencial.',
            'contexto_fisico': {'energia_valor': 3, 'hrv_ms': 51},
        }

        semaforo = DailyDecisionEngine.desde_autoridad_gym(autoridad)

        self.assertEqual(semaforo['estado'], 'sostener')
        self.assertEqual(semaforo['causa'], 'energia_baja')
        self.assertEqual(semaforo['titulo'], 'SOSTENER')
        self.assertIn('Versión esencial', semaforo['recomendacion_gym'])
        self.assertEqual(semaforo['decision_id'], None)

    def test_descanso_planificado_no_se_narra_como_version_esencial(self):
        semaforo = DailyDecisionEngine.desde_autoridad_gym({
            'postura': 'sostener',
            'causa_principal': 'descanso_planificado',
            'mensaje': 'Hoy el plan marca descanso.',
        })

        self.assertIn('descanso', semaforo['recomendacion_gym'].lower())
        self.assertNotIn('versión esencial', semaforo['recomendacion_gym'].lower())


class OrganismoRespetaAutoridadGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='organismo_autoridad', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    @patch('core.organismo._check_observando', return_value=None)
    @patch('core.organismo._check_en_margen')
    @patch('core.organismo._check_protegiendo', return_value=None)
    def test_pasa_la_decision_a_las_dos_guardas(
        self, protegiendo, en_margen, _observando,
    ):
        from core.organismo import resolver_estado_sistema_hoy

        decision = {'postura': 'empujar', 'estado': 'entrenar'}
        en_margen.return_value = {
            'estado': 'EN_MARGEN',
            'motivo': 'gym_sesion_viable',
        }

        resultado = resolver_estado_sistema_hoy(self.user, decision_gym=decision)

        protegiendo.assert_called_once_with(self.user, decision_gym=decision)
        en_margen.assert_called_once_with(self.user, decision_gym=decision)
        self.assertEqual(resultado['estado'], 'EN_MARGEN')
