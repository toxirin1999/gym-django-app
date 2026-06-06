"""
Phase Cierre Menor 1 — el cierre del diario no muestra el mensaje de mañana.

Bug: presencia_cierre buscaba el MensajeJOI con trigger='apertura_manana' y lo
mostraba como saludo nocturno → incoherencia temporal (mensaje matutino en la
pantalla de cierre).

Criterio de cierre:
  - La vista presencia_cierre no busca el trigger 'apertura_manana'.
  - El template no renderiza la variable apertura_manana.
  - El cierre conserva su saludo propio si no hay lectura de cierre.
"""

import inspect

from django.test import TestCase

from diario import views


class TestCierreNoUsaMensajeMatutino(TestCase):
    def test_vista_cierre_no_busca_apertura_manana(self):
        src = inspect.getsource(views.presencia_cierre)
        self.assertNotIn("apertura_manana", src,
                         "presencia_cierre no debe traer el mensaje matutino")

    def test_template_cierre_no_renderiza_apertura_manana(self):
        with open('diario/templates/diario/presencia_cierre.html', encoding='utf-8') as f:
            tpl = f.read()
        self.assertNotIn('apertura_manana', tpl,
                         "el template de cierre no debe renderizar apertura_manana")

    def test_template_cierre_conserva_saludo_propio(self):
        with open('diario/templates/diario/presencia_cierre.html', encoding='utf-8') as f:
            tpl = f.read()
        self.assertIn('El día termina. Qué quedó en pie.', tpl)
