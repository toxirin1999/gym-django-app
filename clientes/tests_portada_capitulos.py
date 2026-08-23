import re
from pathlib import Path

from django.test import SimpleTestCase


TEMPLATE = Path(__file__).parent / "templates" / "clientes" / "mockup_demo.html"


class PortadaCapitulosVisualesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = TEMPLATE.read_text(encoding="utf-8")

    def test_declara_cinco_capitulos_unicos_en_orden_editorial(self):
        chapter_ids = [
            "chapter-ahora",
            "chapter-entrenamiento",
            "chapter-plan",
            "chapter-memoria",
            "chapter-vida",
        ]

        positions = []
        for chapter_id in chapter_ids:
            marker = f'id="{chapter_id}"'
            self.assertEqual(self.source.count(marker), 1)
            positions.append(self.source.index(marker))

        self.assertEqual(positions, sorted(positions))

    def test_navegacion_compacta_enlaza_los_cinco_capitulos(self):
        self.assertIn(
            '<nav class="rb-chapter-nav" aria-label="Secciones del panel">',
            self.source,
        )
        for chapter_id in (
            "chapter-ahora",
            "chapter-entrenamiento",
            "chapter-plan",
            "chapter-memoria",
            "chapter-vida",
        ):
            self.assertEqual(self.source.count(f'href="#{chapter_id}"'), 1)

    def test_preserva_ids_operativos_sin_duplicarlos(self):
        for element_id in (
            "modeSwitcherRb",
            "rbGymContent",
            "rbHyroxContent",
            "acwr-widget-container",
            "rbAcwrModal",
        ):
            self.assertEqual(self.source.count(f'id="{element_id}"'), 1)

    def test_historial_y_acwr_son_detalles_secundarios_cerrados(self):
        for marker in ("data-recent-sessions", "data-acwr-detail"):
            match = re.search(rf"<details\b[^>]*\b{marker}\b[^>]*>", self.source)
            self.assertIsNotNone(match, marker)
            self.assertNotRegex(match.group(0), r"\sopen(?:\s|=|>)")

    def test_navegacion_es_accesible_y_respeta_movimiento_reducido(self):
        self.assertIn(".rb-chapter-nav a:focus-visible", self.source)
        self.assertIn("min-height: 44px", self.source)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.source)

