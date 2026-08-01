"""Contrato HTML de la Etapa 2 del Centro de decisiones.

Estos tests fijan claridad visual, semántica y accesibilidad sin acoplarse a
la vista ni escribir en base de datos.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase
from django.template.loader import render_to_string

from entrenos.services.centro_decisiones_service import construir_estado_plan


TEMPLATE_PATH = (
    Path(__file__).parent / "templates" / "clientes" / "plan_decisiones.html"
)


class CentroDecisionesEtapa2HTMLTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = TEMPLATE_PATH.read_text(encoding="utf-8")

    def _render_empty(self):
        return render_to_string(
            "clientes/plan_decisiones.html",
            {
                "estado_plan": {
                    "narrativa": "El plan mantiene el rumbo con la evidencia disponible.",
                },
                "preferencias_activas": [],
                "intervenciones_activas": [],
                "hipotesis_abiertas": [],
                "traces_agrupados": [],
                "decisiones_agrupadas": [],
                "traces_recientes": [],
                "decisiones_carga": [],
                "sesiones_esenciales": [],
            },
        )

    def test_landmarks_y_titulos_describen_la_pagina(self):
        source = self.source
        self.assertRegex(source, r"<header\b[^>]*class=\"dc-top\"")
        self.assertRegex(source, r"<main\b[^>]*class=\"dc-wrap\"")
        self.assertEqual(len(re.findall(r"<h1\b", source)), 1)

        for section_id, heading_id in (
            ("activo-ahora", "titulo-activo"),
            ("decisiones-recientes", "titulo-decisiones"),
            ("evidencia-tecnica", "titulo-evidencia"),
        ):
            self.assertRegex(
                source,
                rf"<section\b[^>]*id=\"{section_id}\""
                rf"[^>]*aria-labelledby=\"{heading_id}\"",
            )
            self.assertRegex(source, rf"<h2\b[^>]*id=\"{heading_id}\"")

    def test_orden_visual_separa_activo_decisiones_y_evidencia(self):
        source = self.source
        active = source.index('id="activo-ahora"')
        recent = source.index('id="decisiones-recientes"')
        evidence = source.index('id="evidencia-tecnica"')
        self.assertLess(active, recent)
        self.assertLess(recent, evidence)
        self.assertIn(">Activo ahora<", source)
        self.assertIn(">Decisiones recientes<", source)
        self.assertIn(">Evidencia técnica<", source)

    def test_resumen_superior_prioriza_estado_causa_y_contadores(self):
        source = self.source
        hero_start = source.index('class="dc-hero"')
        active_start = source.index('id="activo-ahora"')
        hero = source[hero_start:active_start]

        self.assertIn("Estado actual", hero)
        self.assertIn("Causa y evidencia", hero)
        self.assertIn("{{ estado_plan.narrativa }}", hero)
        self.assertIn("{{ preferencias_activas|length }}", hero)
        self.assertIn("{{ intervenciones_activas|length }}", hero)
        self.assertIn("{{ hipotesis_abiertas|length }}", hero)

    def test_estados_vacios_son_honestos_y_no_inventan_inactividad(self):
        html = self._render_empty().lower()
        self.assertIn(
            "el plan no necesita ninguna decisión tuya ahora",
            html,
        )
        self.assertIn(
            "seguirá observando tus sesiones y te avisará cuando exista "
            "evidencia suficiente para proponer un cambio",
            html,
        )
        self.assertIn(
            "no hay decisiones recientes registradas para este periodo",
            html,
        )
        self.assertIn(
            "no hay evidencia técnica disponible para mostrar ahora",
            html,
        )
        for inference in (
            "no has entrenado",
            "falta de entrenamiento",
            "llevas tiempo sin entrenar",
            "el sistema no tiene señales activas confirmadas",
            "sin adaptaciones persistentes activas",
        ):
            self.assertNotIn(inference, html)

    def test_tipografia_interaccion_y_movimiento_son_accesibles(self):
        source = self.source
        self.assertRegex(source, r"(?s)body\s*\{[^}]*font-size:\s*16px")
        self.assertRegex(
            source, r"(?s)\.dc-(?:card-meta|meta)\s*\{[^}]*font-size:\s*13px"
        )
        self.assertIn("min-height: 44px", source)
        self.assertIn(":focus-visible", source)
        self.assertIn("@media (prefers-reduced-motion: reduce)", source)
        self.assertRegex(source, r"--ink-muted:\s*#[0-9a-fA-F]{6}")

    def test_layout_cubre_375_y_escritorio_sin_overflow(self):
        source = self.source
        self.assertIn("@media (max-width: 640px)", source)
        self.assertIn("@media (min-width: 900px)", source)
        self.assertRegex(source, r"(?s)\.dc-wrap\s*\{[^}]*max-width:\s*1040px")
        self.assertRegex(source, r"(?s)\.dc-wrap\s*\{[^}]*width:\s*100%")
        self.assertIn("overflow-wrap: anywhere", source)
        self.assertIn("min-width: 0", source)

    def test_fab_joi_se_reubica_en_mobile_sin_tapar_contenido(self):
        source = self.source
        include_position = source.index("{% include 'includes/_joi_fab.html' %}")
        guardrail_position = source.index("dc-joi-guardrails")
        self.assertLess(include_position, guardrail_position)

        guardrails = source[guardrail_position:]
        self.assertRegex(
            guardrails,
            r"(?s)@media \(max-width:\s*640px\)\s*\{.*?"
            r"\.joi-fab\s*\{[^}]*position:\s*static\s*!important;",
        )
        self.assertRegex(
            guardrails,
            r"(?s)@media \(max-width:\s*640px\)\s*\{.*?"
            r"\.joi-fab\s*\{[^}]*inset:\s*auto\s*!important;",
        )

    def test_narrativa_no_anade_un_segundo_punto_en_presentacion(self):
        html = render_to_string(
            "clientes/plan_decisiones.html",
            {
                "estado_plan": {"narrativa": "El siguiente paso."},
                "preferencias_activas": [],
                "intervenciones_activas": [],
                "hipotesis_abiertas": [],
                "traces_agrupados": [],
                "decisiones_agrupadas": [],
                "traces_recientes": [],
                "decisiones_carga": [],
                "sesiones_esenciales": [],
            },
        )
        self.assertNotIn("El siguiente paso..", html)

    def test_pausa_real_no_produce_doble_puntuacion_en_service_ni_render(self):
        estado = construir_estado_plan(
            preferencias_activas=[],
            intervenciones_activas=[],
            hipotesis_abiertas=[],
            continuidad={"hay_pausa_significativa": True},
        )
        self.assertNotIn("..", estado["narrativa"])

        html = render_to_string(
            "clientes/plan_decisiones.html",
            {
                "estado_plan": estado,
                "preferencias_activas": [],
                "intervenciones_activas": [],
                "hipotesis_abiertas": [],
                "traces_agrupados": [],
                "decisiones_agrupadas": [],
                "traces_recientes": [],
                "decisiones_carga": [],
                "sesiones_esenciales": [],
            },
        )
        self.assertNotIn("siguiente paso..", html)

    def test_details_es_operable_y_el_template_reduce_estilos_inline(self):
        source = self.source
        self.assertIn("<details", source)
        self.assertIn("<summary", source)
        self.assertIn('aria-hidden="true"', source)
        self.assertIn(".dc-accordion summary:focus-visible", source)
        self.assertLessEqual(source.count('style="'), 2)
        for emoji in ("⚡", "✅", "❌", "🚀", "🎯", "📊"):
            self.assertNotIn(emoji, source)
