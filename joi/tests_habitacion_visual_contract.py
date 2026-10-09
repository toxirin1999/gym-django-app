"""Contrato visual mínimo para que la presencia de JOI siga siendo legible."""

from pathlib import Path

from django.test import SimpleTestCase


class HabitacionVisualContractTests(SimpleTestCase):
    def test_el_mensaje_principal_no_usa_el_panel_transparente_original(self):
        plantilla = Path("joi/templates/joi/habitacion.html").read_text()

        self.assertIn("--ink: #f2fbff", plantilla)
        self.assertIn("background: rgba(6, 11, 18, 0.76)", plantilla)
        self.assertIn("border: 1px solid rgba(140, 195, 230, 0.28)", plantilla)
        self.assertIn(".postura-zona", plantilla)
        self.assertIn("opacity: 0.84", plantilla)
