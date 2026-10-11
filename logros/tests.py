from pathlib import Path

from django.test import TestCase


class ListaMisionesUITests(TestCase):
    def test_cada_mision_es_un_enlace_semantico_navegable_con_teclado(self):
        """Una tarjeta accionable no puede depender únicamente de onclick."""
        plantilla = Path('logros/templates/logros/lista_misiones.html').read_text()

        self.assertIn('<a class="mission-card" href="{% url \'logros:detalle_mision\' mision.id %}">', plantilla)
        self.assertNotIn('<div class="mission-card" onclick=', plantilla)
