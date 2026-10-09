"""Contrato de jerarquía para los avisos globales del Diario."""

from pathlib import Path

from django.test import SimpleTestCase


class DiarioFeedbackLayoutTests(SimpleTestCase):
    def test_bases_agrupan_los_avisos_secundarios_sin_ocultarlos(self):
        for template_name in ('base.html', 'base_stoic.html'):
            template = Path('diario/templates/diario', template_name).read_text()

            self.assertIn('diario-feedback', template)
            self.assertIn('Ver {{ forloop.revcounter }} avisos más', template)
            self.assertIn('<details class="diario-feedback__more">', template)
