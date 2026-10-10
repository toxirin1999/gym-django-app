"""Contrato de accesibilidad de la navegación global inferior."""

from pathlib import Path

from django.test import SimpleTestCase


class BottomNavigationAccessibilityTests(SimpleTestCase):
    def setUp(self):
        self.template = Path("templates/includes/bottom_nav.html").read_text(
            encoding="utf-8"
        )

    def test_nav_expone_nombre_estado_actual_y_destinos_principales(self):
        self.assertIn('aria-label="Navegación principal"', self.template)
        self.assertIn('aria-current="page"', self.template)
        for label in ("Ahora", "Rutina", "Plan", "Memoria", "Vida"):
            self.assertIn(f"<strong>{label}</strong>", self.template)

    def test_enlaces_cumplen_area_tactil_y_foco_visible(self):
        self.assertIn("min-height:44px", self.template)
        self.assertIn("a:focus-visible", self.template)
        self.assertIn("outline:2px solid #f0c84b", self.template)
        self.assertIn("prefers-reduced-motion:no-preference", self.template)
