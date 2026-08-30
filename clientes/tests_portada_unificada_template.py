from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import get_template
from django.urls import reverse
from unittest.mock import patch


class PortadaUnificadaTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("portada-unificada", password="x")
        self.client.force_login(self.user)

    def test_contrato_visual_tiene_como_maximo_una_accion_y_una_voz(self):
        response = self.client.get(reverse("clientes:mockup_demo"))
        html = response.content.decode()
        self.assertLessEqual(html.count("data-primary-action"), 1)
        self.assertLessEqual(html.count("data-joi-voice"), 1)
        self.assertNotIn("joi_narrativa_plan", html)
        if 'data-primary-action' in html and 'Completar check-in' in html:
            self.assertNotIn('<button data-checkin-badge', html)

    def test_portada_expone_compositor_y_limites(self):
        response = self.client.get(reverse("clientes:mockup_demo"))
        self.assertIn("portada_hoy", response.context)
        html = response.content.decode()
        self.assertLessEqual(html.count("data-causal-signal"), 3)
        self.assertLessEqual(html.count("data-learning"), 3)
        template_source = get_template(
            "clientes/mockup_demo.html"
        ).template.source
        self.assertIn('data-decision-detail', template_source)
        self.assertIn('data-session-detail', template_source)
        self.assertIn('data-secondary-signals', template_source)
        self.assertNotIn('Completar ahora', template_source)
        self.assertIn('Tu trayectoria', html)

    def test_trayectoria_superior_expone_contexto_y_cta_accesible(self):
        template_source = get_template(
            "clientes/mockup_demo.html"
        ).template.source
        inicio = template_source.index('>Tu trayectoria</summary>')
        fin = template_source.index('</details>', inicio)
        bloque_trayectoria = template_source[inicio:fin]

        self.assertIn('Sigue la evolución prevista de tu plan', bloque_trayectoria)
        self.assertIn("{% url 'clientes:trayectoria_plan' %}", bloque_trayectoria)
        self.assertIn('Ver trayectoria del plan', bloque_trayectoria)
        self.assertIn('aria-label="Ver trayectoria del plan"', bloque_trayectoria)
        self.assertIn('min-height:44px', bloque_trayectoria)

    def _render_con_accion_principal(self, accion):
        portada = {
            "decision": {"estado": "SILENCIO", "frase": "Decisión de prueba"},
            "accion_principal": accion,
            "sesion_dominante": None,
            "senales": [],
            "aprendizajes": [],
        }
        with patch(
            "clientes.portada_hoy_service.construir_portada_hoy",
            return_value=portada,
        ):
            return self.client.get(reverse("clientes:mockup_demo")).content.decode()

    def test_contrato_antiguo_de_descanso_no_renderiza_accion_principal(self):
        for label in ("Día de Descanso", "Hoy: día de descanso"):
            with self.subTest(label=label):
                html = self._render_con_accion_principal(
                    {"tipo": "enlace", "label": label, "url": "/entrenos/plan/"}
                )
                self.assertNotIn("data-primary-action", html)
                self.assertIn("<button data-checkin-badge", html)
                self.assertIn('onclick="rbOpenCheckin(this)"', html)

    def test_checkin_pendiente_no_duplica_el_cta_principal_de_checkin(self):
        html = self._render_con_accion_principal(
            {"tipo": "modal_checkin", "label": "Completar check-in", "url": ""}
        )

        self.assertEqual(html.count("data-primary-action"), 1)
        self.assertNotIn("<button data-checkin-badge", html)
        self.assertEqual(html.count('onclick="rbOpenCheckin(this)"'), 1)

    def test_acciones_principales_operativas_siguen_renderizandose(self):
        acciones = (
            {"tipo": "modal_checkin", "label": "Completar check-in", "url": ""},
            {"tipo": "diario", "label": "Escribir en el diario", "url": "/diario/"},
            {"tipo": "enlace", "label": "Empezar entreno", "url": "/entrenos/"},
        )

        for accion in acciones:
            with self.subTest(tipo=accion["tipo"]):
                html = self._render_con_accion_principal(accion)
                self.assertEqual(html.count("data-primary-action"), 1)
                self.assertIn(accion["label"], html)
