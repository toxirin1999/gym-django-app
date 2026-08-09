from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import get_template
from django.urls import reverse


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
