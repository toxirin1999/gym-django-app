from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.models import ReflexionLibre


class LogosFlujoUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logos-flujo",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo="Una certeza provisional",
            contenido="La claridad apareció cuando dejé de forzar una respuesta.",
            etiquetas="claridad, decisiones",
            estado_animo_post=4,
        )

    def test_escritura_prioriza_contenido_y_tiene_una_sola_accion_de_envio(self):
        response = self.client.get(reverse("diario:logos_escritura_libre"))
        html = response.content.decode()

        self.assertContains(response, 'class="diario-dark logos-page"')
        self.assertIn('data-logos-view="write"', html)
        self.assertIn('<h1', html)
        self.assertIn('for="contenido"', html)
        self.assertIn('name="contenido"', html)
        self.assertIn('for="titulo"', html)
        self.assertIn("Título opcional", html)
        self.assertIn('fieldset', html)
        self.assertIn('legend', html)
        self.assertEqual(html.count('type="submit"'), 1)
        self.assertContains(response, reverse("diario:logos_dashboard"))
        self.assertNotIn('class="card', html)
        self.assertNotIn("completamente privadas", html)

    def test_lectura_presenta_texto_metadatos_y_solo_dos_destinos(self):
        response = self.client.get(
            reverse("diario:logos_ver_reflexion", args=[self.reflexion.pk])
        )
        html = response.content.decode()

        self.assertIn('data-logos-view="read"', html)
        self.assertContains(response, self.reflexion.titulo)
        self.assertContains(response, self.reflexion.contenido)
        self.assertIn('<time', html)
        self.assertIn('data-logos-meta="type"', html)
        self.assertIn('data-logos-meta="tags"', html)
        self.assertIn('data-logos-meta="mood"', html)
        self.assertEqual(html.count('data-logos-action="edit"'), 1)
        self.assertEqual(html.count('data-logos-action="archive"'), 1)
        self.assertContains(
            response,
            reverse("diario:logos_editar_reflexion", args=[self.reflexion.pk]),
        )
        self.assertContains(response, reverse("diario:logos_lista_reflexiones"))
        self.assertNotIn('class="card', html)
        self.assertNotIn(">Dashboard<", html)

    def test_edicion_repite_el_lenguaje_del_editor_y_expone_errores_globales(self):
        response = self.client.get(
            reverse("diario:logos_editar_reflexion", args=[self.reflexion.pk])
        )
        html = response.content.decode()

        self.assertIn('data-logos-view="edit"', html)
        self.assertIn('aria-describedby="logos-form-errors"', html)
        self.assertIn('id="logos-form-errors"', html)
        self.assertIn('for="titulo"', html)
        self.assertIn('for="contenido"', html)
        self.assertIn('fieldset', html)
        self.assertEqual(html.count('type="submit"'), 1)
        self.assertContains(
            response,
            reverse("diario:logos_ver_reflexion", args=[self.reflexion.pk]),
        )
        self.assertNotIn('class="card', html)

    def test_flujo_declara_focus_responsive_y_reduccion_de_movimiento(self):
        for url in (
            reverse("diario:logos_escritura_libre"),
            reverse("diario:logos_ver_reflexion", args=[self.reflexion.pk]),
            reverse("diario:logos_editar_reflexion", args=[self.reflexion.pk]),
        ):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn(':focus-visible', html)
                self.assertIn('@media (max-width:720px)', html)
                self.assertIn('@media (prefers-reduced-motion: reduce)', html)
                self.assertEqual(html.count('<script'), 1)
