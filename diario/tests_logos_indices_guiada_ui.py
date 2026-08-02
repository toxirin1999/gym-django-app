from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import ReflexionGuiadaTema, ReflexionLibre


class LogosIndicesGuiadaUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logos-indices", password="test-password"
        )
        self.client.force_login(self.user)
        self.tema = ReflexionGuiadaTema.objects.create(
            titulo="La atención disponible",
            slug="la-atencion-disponible",
            fecha_activacion=date(2026, 8, 2),
            contexto="La atención permite distinguir lo urgente de lo importante.",
            cita_filosofica="Aquello a lo que atiendes toma forma.",
            autor_cita="Epicteto",
            pregunta_1="¿Qué merece hoy tu atención?",
            pregunta_2="¿Qué ruido puedes soltar?",
            accion_sugerida="Reserva diez minutos sin interrupciones.",
        )

    def test_archivo_es_editorial_filtrable_y_sin_cards_genericas(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo="Una página localizable",
            contenido="Texto suficientemente singular para encontrarlo.",
            etiquetas="atención, decisión",
        )
        response = self.client.get(
            reverse("diario:logos_lista_reflexiones"),
            {"q": "localizable", "tipo": "espontanea", "etiqueta": "atención"},
        )
        html = response.content.decode()

        self.assertContains(response, 'class="diario-dark logos-page"')
        self.assertIn('data-logos-view="archive"', html)
        self.assertIn('role="search"', html)
        self.assertIn('for="busqueda"', html)
        self.assertIn('for="tipo"', html)
        self.assertIn('for="etiqueta"', html)
        self.assertContains(response, reflexion.titulo)
        self.assertContains(response, reverse("diario:logos_ver_reflexion", args=[reflexion.pk]))
        self.assertEqual(html.count('data-logos-action="write"'), 1)
        self.assertNotIn('class="card', html)

    def test_archivo_vacio_distingue_ausencia_de_resultados_y_conserva_paginacion(self):
        for index in range(13):
            ReflexionLibre.objects.create(
                usuario=self.user,
                titulo=f"Página {index:02d}",
                contenido="Contenido del archivo",
                fecha=timezone.now() - timedelta(days=index),
            )

        page = self.client.get(reverse("diario:logos_lista_reflexiones"), {"page": 2})
        self.assertIn('aria-label="Paginación del archivo"', page.content.decode())

        empty = self.client.get(reverse("diario:logos_lista_reflexiones"), {"q": "inexistente"})
        self.assertContains(empty, "Ninguna página coincide")
        self.assertContains(empty, "Limpiar filtros")

    def test_calendario_es_indice_tematico_ordenado_con_estado_de_completado(self):
        tema_anterior = ReflexionGuiadaTema.objects.create(
            titulo="Tema anterior",
            slug="tema-anterior",
            fecha_activacion=date(2026, 1, 10),
            contexto="Contexto anterior",
            cita_filosofica="Cita anterior",
            autor_cita="Séneca",
            pregunta_1="¿Primera pregunta?",
            accion_sugerida="Una acción",
        )
        ReflexionLibre.objects.create(
            usuario=self.user,
            titulo=tema_anterior.titulo,
            contenido="Respuesta ya escrita",
            tipo="guiada",
            reflexion_guiada=tema_anterior,
        )

        response = self.client.get(reverse("diario:logos_calendario"))
        html = response.content.decode()

        self.assertIn('data-logos-view="guided-index"', html)
        self.assertContains(response, "Índice de preguntas guiadas")
        self.assertLess(html.index("Tema anterior"), html.index(self.tema.titulo))
        self.assertIn('data-logos-status="completed"', html)
        self.assertIn('data-logos-status="available"', html)
        self.assertContains(response, reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]))
        self.assertNotContains(response, "vista mensual")
        self.assertNotIn('class="card', html)

    def test_guiada_no_completada_tiene_un_formulario_y_una_accion_submit(self):
        response = self.client.get(
            reverse("diario:logos_reflexion_guiada", args=[self.tema.slug])
        )
        html = response.content.decode()

        self.assertIn('data-logos-view="guided-write"', html)
        self.assertContains(response, self.tema.contexto)
        self.assertContains(response, self.tema.cita_filosofica)
        self.assertContains(response, self.tema.pregunta_1)
        self.assertIn('for="contenido"', html)
        self.assertIn('<fieldset', html)
        self.assertEqual(html.count('type="submit"'), 1)
        self.assertNotIn('class="card', html)

    def test_guiada_completada_es_estado_de_lectura_sin_formulario(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo=self.tema.titulo,
            contenido="Una respuesta existente",
            tipo="guiada",
            reflexion_guiada=self.tema,
        )

        response = self.client.get(
            reverse("diario:logos_reflexion_guiada", args=[self.tema.slug])
        )
        html = response.content.decode()

        self.assertIn('data-logos-state="completed"', html)
        self.assertContains(response, "Esta pregunta ya forma parte de tu archivo")
        self.assertContains(response, reverse("diario:logos_ver_reflexion", args=[reflexion.pk]))
        self.assertNotIn('<form', html)
        self.assertNotIn('type="submit"', html)

    def test_tres_vistas_declaran_focus_responsive_y_reduced_motion(self):
        for url in (
            reverse("diario:logos_lista_reflexiones"),
            reverse("diario:logos_calendario"),
            reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]),
        ):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn(":focus-visible", html)
                self.assertIn("@media (max-width:720px)", html)
                self.assertIn("@media (prefers-reduced-motion: reduce)", html)
                self.assertEqual(html.count("<script"), 1)

    def test_vistas_no_anidan_main_y_conservan_su_contenedor_identificable(self):
        expected_views = (
            (reverse("diario:logos_lista_reflexiones"), "archive"),
            (reverse("diario:logos_calendario"), "guided-index"),
            (
                reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]),
                "guided-write",
            ),
        )

        for url, view_name in expected_views:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertEqual(html.count("<main"), 1)
                self.assertIn(
                    f'<div class="logos-shell" data-logos-view="{view_name}"',
                    html,
                )
