from pathlib import Path

from django.test import TestCase


class RecomendacionesUITests(TestCase):
    def test_estado_sin_recomendaciones_lleva_directamente_a_actualizar_analisis(self):
        """El estado sano confirma la situación y conserva una única siguiente acción."""
        plantilla = Path('analytics/templates/analytics/recomendaciones.html').read_text()

        self.assertIn('class="recommendations-empty"', plantilla)
        self.assertIn('Todo está al día por ahora.', plantilla)
        self.assertIn('href="#generate-form"', plantilla)
