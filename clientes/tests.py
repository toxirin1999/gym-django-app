from pathlib import Path

from django.test import SimpleTestCase


class TarjetaProximoEntrenamientoTemplateTests(SimpleTestCase):
    def test_details_control_is_a_real_modal_button_without_href(self):
        template = Path(
            "clientes/templates/clientes/includes/tarjeta_proximo_entrenamiento.html"
        ).read_text(encoding="utf-8")

        self.assertIn('type="button"', template)
        self.assertIn('aria-haspopup="dialog"', template)
        self.assertNotIn('<button href=', template)
