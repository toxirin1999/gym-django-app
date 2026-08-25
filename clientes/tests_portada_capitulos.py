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

    def test_nav_principal_tiene_contrato_responsive_y_nombres_accesibles(self):
        for css_class in (
            "rb-nav-joi",
            "rb-nav-tools",
            "rb-nav-tool",
            "rb-nav-tool-label",
        ):
            self.assertIn(css_class, self.source)

        self.assertIn("--rb-nav-height:", self.source)
        self.assertIn("top: var(--rb-nav-height)", self.source)
        self.assertRegex(
            self.source,
            r"@media \(max-width: 520px\)[\s\S]*?\.rb-nav-tool-label\s*\{\s*display:\s*none",
        )
        compact = re.search(
            r"@media \(max-width: 520px\)\s*\{([\s\S]*?)\n\}",
            self.source,
        )
        self.assertIsNotNone(compact)
        self.assertRegex(compact.group(1), r"\.rb-nav\s*\{[^}]*overflow-x:\s*hidden")
        self.assertRegex(compact.group(1), r"\.rb-nav-tool\s*\{[^}]*padding-inline:\s*0")
        self.assertRegex(compact.group(1), r"\.rb-live\s*\{[^}]*overflow:\s*hidden")
        self.assertRegex(self.source, r'class="rb-nav-tool[^\"]*"[^>]+aria-label="Mi cuerpo"')
        self.assertRegex(self.source, r'class="rb-nav-tool[^\"]*"[^>]+aria-label="Strava"')
        self.assertRegex(self.source, r'class="rb-nav-tool[^\"]*"[^>]+aria-label="Rehab"')
        main_nav = re.search(r'<nav class="rb-nav">([\s\S]*?)</nav>', self.source)
        self.assertIsNotNone(main_nav)
        self.assertNotIn("onmouseover=", main_nav.group(1))
        self.assertNotIn("onmouseout=", main_nav.group(1))

    def test_navegacion_de_capitulos_expone_estado_activo_accesible(self):
        links = re.findall(r'<a\b[^>]*data-chapter-link[^>]*href="#chapter-[^"]+"[^>]*>', self.source)
        self.assertEqual(len(links), 5)
        self.assertIn("is-active", self.source)
        self.assertIn("aria-current", self.source)
        self.assertIn("location.hash", self.source)
        self.assertIn(".rb-chapter-nav a.is-active::after", self.source)

    def test_scrollspy_usa_linea_de_lectura_y_ultimo_heading_visible(self):
        self.assertNotIn("new IntersectionObserver", self.source)
        self.assertIn("function getChapterReadingLine()", self.source)
        self.assertIn("window.innerHeight * 0.18", self.source)
        self.assertIn("heading.getBoundingClientRect().top <= readingLine", self.source)
        self.assertIn("selectedChapter = section.id", self.source)
        self.assertIn("section.offsetParent !== null", self.source)
        self.assertIn("document.documentElement.scrollHeight", self.source)
        self.assertIn("visibleSections[visibleSections.length - 1].id", self.source)

    def test_scrollspy_se_sincroniza_sin_saturar_el_scroll(self):
        self.assertIn("requestAnimationFrame(syncActiveChapterFromScroll)", self.source)
        self.assertIn("addEventListener('scroll', requestChapterSync, { passive: true })", self.source)
        for event_name in ("load", "resize", "hashchange"):
            self.assertIn(
                f"addEventListener('{event_name}', requestChapterSync)",
                self.source,
            )

    def test_modo_hyrox_oculta_capitulos_gym_y_reubica_el_activo(self):
        self.assertIn("querySelectorAll('[data-gym-chapter]')", self.source)
        self.assertIn("chapterLink.hidden = isHyrox", self.source)
        self.assertIn("activeChapter === 'chapter-plan'", self.source)
        self.assertIn("activeChapter === 'chapter-memoria'", self.source)
        self.assertIn("setActiveChapter('chapter-entrenamiento')", self.source)

    def test_senales_secundarias_siempre_son_un_details_cerrado(self):
        signals = re.search(
            r"\{% if alertas_sistema %\}([\s\S]*?)\{% endif %\}\s*\n\s*<section id=\"chapter-plan\"",
            self.source,
        )
        self.assertIsNotNone(signals)
        block = signals.group(1)
        opening = re.search(r"<details\b[^>]*data-secondary-signals[^>]*>", block)
        self.assertIsNotNone(opening)
        self.assertNotRegex(opening.group(0), r"\sopen(?:\s|=|>)")
        self.assertNotIn("{% if portada_hoy %}", block)
        self.assertEqual(block.count("<details data-secondary-signals"), 1)
        self.assertEqual(block.count("</details>"), 2)  # señales + lista de señales extra
