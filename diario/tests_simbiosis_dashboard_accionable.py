from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.models import Interaccion, PersonaImportante, PersonaInterina


class SimbiosisDashboardAccionableTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="simbiosis-ui",
            password="test-pass",
        )
        self.client.force_login(self.user)
        self.url = reverse("diario:simbiosis_dashboard")

    def test_metrica_cuenta_todas_las_interacciones_pero_lista_solo_ocho(self):
        for indice in range(10):
            Interaccion.objects.create(
                usuario=self.user,
                titulo=f"Interacción {indice}",
                descripcion="Contexto",
                fecha=date.today() - timedelta(days=indice),
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["n_interacciones"], 10)
        self.assertEqual(len(response.context["ultimas_interacciones"]), 8)

    def test_sombra_informa_y_solo_radar_solicita_una_decision(self):
        sombra = PersonaInterina.objects.create(
            usuario=self.user,
            nombre="Marta",
            estado="sombra",
            veces_mencionada=1,
        )
        radar = PersonaInterina.objects.create(
            usuario=self.user,
            nombre="Alex",
            estado="radar",
            veces_mencionada=3,
        )

        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertQuerySetEqual(response.context["personas_sombra"], [sombra])
        self.assertQuerySetEqual(response.context["personas_radar"], [radar])
        self.assertEqual(response.context["n_radar"], 1)
        self.assertContains(response, 'id="sombra-%s"' % sombra.pk)
        self.assertNotIn('data-id="%s"' % sombra.pk, html)
        self.assertContains(response, 'id="radar-%s"' % radar.pk)
        self.assertIn('data-id="%s"' % radar.pk, html)

    def test_copy_no_atribuye_una_voz_hardcodeada_a_joi(self):
        PersonaImportante.objects.create(usuario=self.user, nombre="Leo")

        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertNotIn("JOI", html)
        self.assertContains(response, "Señales detectadas en tus cierres")
        self.assertContains(response, "Personas que has confirmado")

    def test_acciones_declaran_feedback_accesible_y_no_ocultan_fallos(self):
        PersonaInterina.objects.create(
            usuario=self.user,
            nombre="Nora",
            estado="radar",
            veces_mencionada=2,
        )

        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertContains(response, 'id="radar-feedback"')
        self.assertContains(response, 'role="status"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertIn("if (!response.ok || !data.ok)", html)
        self.assertIn("mostrarFeedback", html)
        self.assertNotIn("catch(() => location.reload())", html)

    def test_controles_tienen_foco_visible_y_layout_movil(self):
        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertIn(".radar-btn:focus-visible", html)
        self.assertIn(".sim-cta:focus-visible", html)
        self.assertIn("@media (max-width: 560px)", html)

