from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.models import ReflexionGuiadaTema, ReflexionLibre, Virtud
from diario.services.logos_service import completar_reflexion_guiada, normalizar_etiquetas


class LogosIntegridadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logos-integridad",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.tema = ReflexionGuiadaTema.objects.create(
            titulo="Distinguir lo controlable",
            slug="distinguir-lo-controlable",
            fecha_activacion=date(2026, 8, 2),
            contexto="Contexto de prueba",
            cita_filosofica="Una cita",
            autor_cita="Epicteto",
            pregunta_1="¿Qué depende de ti?",
            accion_sugerida="Actuar sobre lo controlable",
        )

    def test_alta_libre_crea_sabiduria_si_no_existe(self):
        Virtud.objects.filter(usuario=self.user, tipo="sabiduria").delete()
        response = self.client.post(
            reverse("diario:logos_escritura_libre"),
            {"contenido": "Una reflexión válida", "estado_animo_post": "4"},
        )

        reflexion = ReflexionLibre.objects.get(usuario=self.user)
        self.assertRedirects(
            response,
            reverse("diario:logos_ver_reflexion", args=[reflexion.pk]),
        )
        virtud = Virtud.objects.get(usuario=self.user, tipo="sabiduria")
        self.assertEqual(virtud.puntos, 5)

    def test_alta_libre_rechaza_mood_no_entero_o_fuera_de_rango(self):
        url = reverse("diario:logos_escritura_libre")

        for mood in ("abc", "0", "6"):
            with self.subTest(mood=mood):
                response = self.client.post(
                    url,
                    {"contenido": "No debe guardarse", "estado_animo_post": mood},
                )
                self.assertEqual(response.status_code, 302)

        self.assertFalse(ReflexionLibre.objects.filter(usuario=self.user).exists())

    def test_edicion_rechaza_mood_no_entero_o_fuera_de_rango(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo="Original",
            contenido="Contenido original",
            estado_animo_post=3,
        )
        url = reverse("diario:logos_editar_reflexion", args=[reflexion.pk])

        for mood in ("abc", "0", "6"):
            with self.subTest(mood=mood):
                response = self.client.post(
                    url,
                    {"titulo": "Alterado", "contenido": "Alterado", "estado_animo_post": mood},
                )
                self.assertEqual(response.status_code, 302)

        reflexion.refresh_from_db()
        self.assertEqual(reflexion.titulo, "Original")
        self.assertEqual(reflexion.contenido, "Contenido original")
        self.assertEqual(reflexion.estado_animo_post, 3)

    def test_guiada_rechaza_mood_no_entero_o_fuera_de_rango(self):
        url = reverse("diario:logos_reflexion_guiada", args=[self.tema.slug])

        for mood in ("abc", "0", "6"):
            with self.subTest(mood=mood):
                response = self.client.post(
                    url,
                    {"contenido": "No debe guardarse", "estado_animo_post": mood},
                )
                self.assertEqual(response.status_code, 302)

        self.assertFalse(ReflexionLibre.objects.filter(usuario=self.user).exists())

    def test_edicion_no_admite_contenido_vacio(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo="Original",
            contenido="Contenido original",
        )

        response = self.client.post(
            reverse("diario:logos_editar_reflexion", args=[reflexion.pk]),
            {"titulo": "Alterado", "contenido": "   ", "estado_animo_post": "4"},
        )

        self.assertRedirects(
            response,
            reverse("diario:logos_editar_reflexion", args=[reflexion.pk]),
        )
        reflexion.refresh_from_db()
        self.assertEqual(reflexion.titulo, "Original")
        self.assertEqual(reflexion.contenido, "Contenido original")

    def test_repetir_guiada_completada_es_idempotente(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            titulo=self.tema.titulo,
            contenido="Primera respuesta",
            tipo="guiada",
            reflexion_guiada=self.tema,
            estado_animo_post=3,
        )
        ReflexionGuiadaTema.objects.filter(pk=self.tema.pk).update(veces_completada=1)
        Virtud.objects.update_or_create(
            usuario=self.user,
            tipo="sabiduria",
            defaults={"puntos": 55, "nivel": "practicante"},
        )

        response = self.client.post(
            reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]),
            {"contenido": "Segunda respuesta", "estado_animo_post": "5"},
        )

        self.assertRedirects(
            response,
            reverse("diario:logos_ver_reflexion", args=[reflexion.pk]),
        )
        self.assertEqual(
            ReflexionLibre.objects.filter(usuario=self.user, reflexion_guiada=self.tema).count(),
            1,
        )
        self.tema.refresh_from_db()
        self.assertEqual(self.tema.veces_completada, 1)
        self.assertEqual(
            Virtud.objects.get(usuario=self.user, tipo="sabiduria").puntos,
            55,
        )

    def test_servicio_guiado_es_idempotente_y_recompensa_una_sola_vez(self):
        primera, creada_primera = completar_reflexion_guiada(
            usuario=self.user,
            tema=self.tema,
            contenido="Primera respuesta",
            estado_animo_post=4,
        )
        segunda, creada_segunda = completar_reflexion_guiada(
            usuario=self.user,
            tema=self.tema,
            contenido="Respuesta repetida",
            estado_animo_post=5,
        )

        self.assertTrue(creada_primera)
        self.assertFalse(creada_segunda)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(ReflexionLibre.objects.filter(usuario=self.user).count(), 1)
        self.tema.refresh_from_db()
        self.assertEqual(self.tema.veces_completada, 1)
        virtud = Virtud.objects.get(usuario=self.user, tipo="sabiduria")
        self.assertEqual(virtud.puntos, 10)
        self.assertIn(virtud.nivel, dict(Virtud.NIVEL_CHOICES))

    def test_post_guiado_delega_en_servicio_y_recompensa_una_sola_vez(self):
        with patch(
            "diario.services.logos_service.completar_reflexion_guiada",
            wraps=completar_reflexion_guiada,
        ) as completar:
            response = self.client.post(
                reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]),
                {"contenido": "Respuesta", "estado_animo_post": "4"},
            )

        self.assertEqual(response.status_code, 302)
        completar.assert_called_once()
        self.client.post(
            reverse("diario:logos_reflexion_guiada", args=[self.tema.slug]),
            {"contenido": "Repetida", "estado_animo_post": "5"},
        )
        self.assertEqual(ReflexionLibre.objects.filter(usuario=self.user).count(), 1)
        self.assertEqual(Virtud.objects.get(usuario=self.user, tipo="sabiduria").puntos, 10)
        self.tema.refresh_from_db()
        self.assertEqual(self.tema.veces_completada, 1)

    def test_normalizador_etiquetas_casefold_trim_dedupe_y_sin_vacios(self):
        self.assertEqual(
            normalizar_etiquetas("  Amor, FOCO, amor ,, Foco , Decisión "),
            "Amor,FOCO,Decisión",
        )

    def test_altas_y_ediciones_guardan_etiquetas_normalizadas(self):
        self.client.post(
            reverse("diario:logos_escritura_libre"),
            {"contenido": "Texto", "etiquetas": " Amor, amor,  FOCO ,,"},
        )
        reflexion = ReflexionLibre.objects.get(usuario=self.user)
        self.assertEqual(reflexion.etiquetas, "Amor,FOCO")

        self.client.post(
            reverse("diario:logos_editar_reflexion", args=[reflexion.pk]),
            {"contenido": "Editado", "etiquetas": " foco, Calma,FOCO "},
        )
        reflexion.refresh_from_db()
        self.assertEqual(reflexion.etiquetas, "foco,Calma")

    def test_filtro_etiqueta_es_por_token_exacto_y_opciones_sin_duplicados(self):
        amor = ReflexionLibre.objects.create(
            usuario=self.user, titulo="Amor", contenido="A", etiquetas="Amor,FOCO",
        )
        ReflexionLibre.objects.create(
            usuario=self.user, titulo="Desamor", contenido="B", etiquetas="desamor,foco",
        )

        response = self.client.get(
            reverse("diario:logos_lista_reflexiones"), {"etiqueta": "amor"},
        )

        self.assertEqual([r.pk for r in response.context["reflexiones"]], [amor.pk])
        self.assertEqual(response.context["etiquetas_disponibles"], ["amor", "desamor", "foco"])
