from pathlib import Path

from django.test import SimpleTestCase


TEMPLATE = Path(__file__).parent / "templates" / "diario" / "presencia_cierre.html"


class CierreAccesibilidadTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_campos_del_cierre_tienen_nombre_accesible(self):
        self.assertIn('aria-label="Reflexión del día"', self.html)
        self.assertIn('aria-label="Fricción de los límites de hoy"', self.html)
        self.assertIn('aria-label="Estado de ánimo al cerrar"', self.html)

    def test_gestos_son_botones_con_estado_inicial(self):
        self.assertIn('<button type="button"\n                class="habito-chip', self.html)
        self.assertIn('aria-pressed="{% if item.completado %}true{% else %}false{% endif %}"', self.html)
        self.assertIn('</button>', self.html)

    def test_javascript_sincroniza_estado_accesible_de_gestos(self):
        self.assertIn("chip.setAttribute('aria-pressed', String(completados.has(id)));", self.html)

    def test_cuerpo_es_un_grupo_y_sus_botones_exponen_estado(self):
        self.assertIn('id="cuerpo-cierre-label"', self.html)
        self.assertIn('role="group" aria-labelledby="cuerpo-cierre-label"', self.html)
        self.assertIn('aria-pressed="{% if vires.cuerpo_cierre == val %}true{% else %}false{% endif %}"', self.html)

    def test_javascript_sincroniza_estado_accesible_del_cuerpo(self):
        self.assertIn("c.setAttribute('aria-pressed', String(c === chip));", self.html)
