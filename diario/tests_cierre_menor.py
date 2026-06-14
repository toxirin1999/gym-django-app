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

from django.contrib.auth.models import User
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


class TestCierreRenderSinTextoTecnico(TestCase):
    """
    Phase Diario UI 3B — un {# #} de Django mal cerrado en varias líneas no se
    interpreta como comentario y se renderiza como texto literal en la UI.
    Esto comprueba el HTML renderizado, no solo el código fuente del template.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='cierre_render', password='x')
        self.client.force_login(self.user)

    def test_render_no_contiene_restos_tecnicos(self):
        resp = self.client.get('/diario/presencia/cierre/', SERVER_NAME='127.0.0.1')
        html = resp.content.decode('utf-8')
        for forbidden in ('Phase Cierre Menor', '{#', '#}', '{% comment %}', '{% endcomment %}'):
            self.assertNotIn(forbidden, html,
                              f"el cierre renderizado contiene texto técnico: '{forbidden}'")

    def test_render_conserva_saludo_propio(self):
        resp = self.client.get('/diario/presencia/cierre/', SERVER_NAME='127.0.0.1')
        html = resp.content.decode('utf-8')
        self.assertIn('El día termina. Qué quedó en pie.', html)
