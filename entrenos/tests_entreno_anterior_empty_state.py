from pathlib import Path

from django.test import SimpleTestCase


class EntrenoAnteriorEmptyStateTests(SimpleTestCase):
    def test_first_execution_state_leads_to_active_training(self):
        template = (Path(__file__).parent / 'templates/entrenos/entreno_anterior.html').read_text()

        self.assertIn('Este cliente aún no ha realizado esta rutina.', template)
        self.assertIn('Empezar esta rutina', template)
        self.assertIn("{% url 'entrenos:entrenamiento_activo' cliente.id %}", template)
