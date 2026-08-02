from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import ReflexionGuiadaTema, ReflexionLibre


class LogosDashboardUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logos-portada",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.url = reverse("diario:logos_dashboard")

    def _tema_de_hoy(self):
        return ReflexionGuiadaTema.objects.create(
            titulo="Lo que merece atención",
            slug="lo-que-merece-atencion",
            fecha_activacion=timezone.localdate(),
            contexto="Una invitación concreta a mirar con cuidado.",
            cita_filosofica="La atención ordena la experiencia.",
            autor_cita="Simone Weil",
            pregunta_1="¿Qué merece hoy tu atención?",
            accion_sugerida="Nombrarlo sin prisa.",
        )

    def _crear_tema(self, slug, fecha, **overrides):
        datos = {
            "titulo": slug.replace("-", " ").title(),
            "slug": slug,
            "fecha_activacion": fecha,
            "contexto": "Contexto",
            "cita_filosofica": "Cita",
            "autor_cita": "Autor",
            "pregunta_1": "Pregunta",
            "accion_sugerida": "Acción",
        }
        datos.update(overrides)
        return ReflexionGuiadaTema.objects.create(**datos)

    def _dashboard_en(self, fecha):
        with patch("diario.services.logos_service.timezone.localdate", return_value=fecha):
            return self.client.get(self.url)

    def test_selector_exacto_gana_a_recurrente(self):
        hoy = date(2026, 8, 15)
        recurrente = self._crear_tema(
            "recurrente", hoy.replace(year=hoy.year - 1), es_recurrente=True,
        )
        exacto = self._crear_tema("exacto", hoy, es_recurrente=False)

        response = self._dashboard_en(hoy)

        self.assertEqual(response.context["reflexion_del_dia"], exacto)
        self.assertNotEqual(response.context["reflexion_del_dia"], recurrente)

    def test_selector_recurrente_cruza_de_ano(self):
        hoy = date(2026, 8, 15)
        recurrente = self._crear_tema(
            "recurrente-otro-ano", hoy.replace(year=hoy.year - 2), es_recurrente=True,
        )
        self.assertEqual(self._dashboard_en(hoy).context["reflexion_del_dia"], recurrente)

    def test_selector_no_muestra_no_recurrente_antiguo(self):
        hoy = date(2026, 8, 15)
        self._crear_tema(
            "antiguo-no-recurrente", hoy.replace(year=hoy.year - 1), es_recurrente=False,
        )
        self.assertIsNone(self._dashboard_en(hoy).context["reflexion_del_dia"])

    def test_selector_no_muestra_tema_anterior_del_mismo_mes(self):
        hoy = date(2026, 8, 15)
        fecha_anterior = hoy - timedelta(days=1)
        self._crear_tema("anterior-del-mes", fecha_anterior, es_recurrente=True)
        self.assertIsNone(self._dashboard_en(hoy).context["reflexion_del_dia"])

    def test_selector_excluye_inactivos(self):
        hoy = date(2026, 8, 15)
        self._crear_tema("exacto-inactivo", hoy, activa=False)
        self._crear_tema(
            "recurrente-inactivo", hoy.replace(year=hoy.year - 1),
            activa=False, es_recurrente=True,
        )
        self.assertIsNone(self._dashboard_en(hoy).context["reflexion_del_dia"])

    def test_portada_tiene_estructura_editorial_accesible_sin_cards_genericas(self):
        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertContains(response, 'class="diario-dark logos-page"')
        self.assertIn('<main id="contenido-diario"', html)
        self.assertIn('id="logos-main"', html)
        for region in ("primary", "memory", "signals", "navigation"):
            self.assertIn(f'data-logos-region="{region}"', html)
        self.assertIn('aria-labelledby="logos-memory-title"', html)
        self.assertIn(':focus-visible', html)
        self.assertIn('@media (max-width: 720px)', html)
        self.assertNotIn('class="card', html)
        self.assertNotIn('progress-bar', html)
        self.assertNotIn('Racha Máxima', html)

    def test_sin_guiada_hay_una_sola_accion_principal_para_escribir(self):
        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertEqual(html.count('data-logos-primary-action'), 1)
        self.assertContains(response, "Escribir una reflexión")
        self.assertContains(response, reverse("diario:logos_escritura_libre"))
        self.assertContains(response, "Pon en palabras lo que todavía no tiene forma.")

    def test_guiada_del_dia_asume_la_unica_accion_principal(self):
        tema = self._tema_de_hoy()

        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertEqual(html.count('data-logos-primary-action'), 1)
        self.assertContains(response, "La pregunta de hoy")
        self.assertContains(response, tema.titulo)
        self.assertContains(response, "Abrir la reflexión guiada")
        self.assertContains(
            response,
            reverse("diario:logos_reflexion_guiada", args=[tema.slug]),
        )

    def test_memoria_reciente_es_legible_y_enlaza_cada_reflexion(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo="Una decisión sin ruido",
            contenido="Hoy entendí que sostener un límite también es cuidar.",
        )

        response = self.client.get(self.url)

        self.assertContains(response, "Memoria reciente")
        self.assertContains(response, reflexion.titulo)
        self.assertContains(response, "Hoy entendí que sostener un límite")
        self.assertContains(
            response,
            reverse("diario:logos_ver_reflexion", args=[reflexion.pk]),
        )

    def test_senales_son_secundarias_y_la_racha_cero_se_nombra_sin_presion(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Días escritos")
        self.assertContains(response, "La racha está en pausa")
        self.assertContains(response, "Total de reflexiones")
        self.assertNotContains(response, "puntos")
        self.assertNotContains(response, "insignia")

    def test_archivo_y_calendario_son_accesos_secundarios_sin_duplicar_cta(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Abrir el archivo")
        self.assertContains(response, "Explorar el calendario")
        self.assertContains(response, reverse("diario:logos_lista_reflexiones"))
        self.assertContains(response, reverse("diario:logos_calendario"))
        self.assertEqual(response.content.decode().count('data-logos-primary-action'), 1)
