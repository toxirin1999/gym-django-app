from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.models import Interaccion, PersonaImportante, PersonaInterina


class SimbiosisEditorialTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("simbiosis-editorial")
        self.client.force_login(self.user)
        self.url = reverse("diario:simbiosis_dashboard")

    def test_portada_ordena_ahora_circulo_memoria_y_archivo(self):
        response = self.client.get(self.url)
        html = response.content.decode()

        posiciones = [
            html.index('data-section="ahora"'),
            html.index('data-section="circulo"'),
            html.index('data-section="memoria"'),
            html.index('data-section="archivo"'),
        ]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_ahora_distingue_decision_observacion_y_calma(self):
        radar = PersonaInterina.objects.create(
            usuario=self.user, nombre="Alex", estado="radar", veces_mencionada=2,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "1 vínculo requiere tu decisión")
        self.assertContains(response, f'data-id="{radar.pk}"')

        radar.delete()
        PersonaInterina.objects.create(
            usuario=self.user, nombre="Marta", estado="sombra", veces_mencionada=1,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "1 mención observada, ninguna requiere decidir")

        PersonaInterina.objects.filter(usuario=self.user).delete()
        response = self.client.get(self.url)
        self.assertContains(response, "No hay decisiones relacionales pendientes")

    def test_circulo_es_protagonista_muestra_cuatro_vinculos_y_perfiles(self):
        personas = [
            PersonaImportante.objects.create(usuario=self.user, nombre=f"Persona {i}")
            for i in range(5)
        ]

        response = self.client.get(self.url)
        html = response.content.decode()
        circulo = html.split('data-section="circulo"', 1)[1].split('data-section="memoria"', 1)[0]

        for persona in personas[:4]:
            self.assertIn(persona.nombre, circulo)
            self.assertIn(reverse("diario:persona_detalle", args=[persona.pk]), circulo)
        self.assertNotIn(personas[4].nombre, circulo)
        self.assertContains(response, "Ver los 5 perfiles")

    def test_memoria_reciente_lista_ocho_interacciones_sin_ocultar_el_total(self):
        for indice in range(22):
            Interaccion.objects.create(
                usuario=self.user,
                titulo=f"Recuerdo {indice}",
                fecha=date.today() - timedelta(days=indice),
            )

        response = self.client.get(self.url)

        self.assertEqual(response.context["n_interacciones"], 22)
        self.assertEqual(len(response.context["ultimas_interacciones"]), 8)

    def test_senales_aisladas_viven_en_details_secundario(self):
        PersonaInterina.objects.create(usuario=self.user, nombre="Marta", estado="sombra")
        response = self.client.get(self.url)
        html = response.content.decode()
        archivo = html.split('data-section="archivo"', 1)[1]

        self.assertIn("<details", archivo)
        self.assertIn("Señales aisladas", archivo)
        self.assertIn("Marta", archivo)

    def test_tokens_editoriales_y_accesibilidad(self):
        response = self.client.get(self.url)
        html = response.content.decode()

        for token in ("Crimson Pro", "Manrope", "--sim-ink", "--sim-gold", "max-width: 980px"):
            self.assertIn(token, html)
        self.assertIn("min-height: 44px", html)
        self.assertIn(":focus-visible", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("@media (max-width: 600px)", html)

    def test_conserva_acciones_y_urls_operativas(self):
        radar = PersonaInterina.objects.create(usuario=self.user, nombre="Alex", estado="radar")
        excluida = PersonaInterina.objects.create(usuario=self.user, nombre="Ruido", estado="no_persona")
        persona = PersonaImportante.objects.create(usuario=self.user, nombre="Leo", archivada=True)
        response = self.client.get(self.url)
        html = response.content.decode()

        for accion in ("promover-btn", "descartar-btn", "no-persona-btn", "restaurar-btn"):
            self.assertIn(accion, html)
        self.assertIn(f'data-id="{radar.pk}"', html)
        self.assertIn(f'data-id="{excluida.pk}"', html)
        self.assertIn(reverse("diario:restaurar_persona", args=[persona.pk]), html)
        self.assertIn(reverse("diario:persona_crear"), html)
        self.assertIn(reverse("diario:interaccion_crear"), html)


class SimbiosisResumenDiarioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("simbiosis-resumen")
        self.client.force_login(self.user)
        self.url = reverse("diario:dashboard_diario")

    def test_contexto_incluye_todas_las_micrometricas(self):
        PersonaInterina.objects.create(usuario=self.user, nombre="Sombra", estado="sombra")
        PersonaImportante.objects.create(usuario=self.user, nombre="Confirmada")
        Interaccion.objects.create(usuario=self.user, titulo="Encuentro")

        response = self.client.get(self.url)

        self.assertEqual(response.context["n_radar"], 0)
        self.assertEqual(response.context["n_sombra"], 1)
        self.assertEqual(response.context["n_confirmadas"], 1)
        self.assertEqual(response.context["n_interacciones"], 1)

    def test_copy_segun_estado_y_nunca_declara_vacio_si_hay_memoria(self):
        PersonaInterina.objects.create(usuario=self.user, nombre="Sombra", estado="sombra")
        response = self.client.get(self.url)
        self.assertContains(response, "1 mención observada, ninguna requiere decidir")
        self.assertNotContains(response, "No hay vínculos")

        PersonaInterina.objects.filter(usuario=self.user).delete()
        PersonaImportante.objects.create(usuario=self.user, nombre="Confirmada")
        response = self.client.get(self.url)
        self.assertContains(response, "Tu círculo está estable")
        self.assertNotContains(response, "No hay vínculos")

    def test_radar_pide_decision_y_vacio_real_es_honesto(self):
        PersonaInterina.objects.create(usuario=self.user, nombre="Radar", estado="radar")
        response = self.client.get(self.url)
        self.assertContains(response, "1 vínculo requiere tu decisión")

        PersonaInterina.objects.filter(usuario=self.user).delete()
        response = self.client.get(self.url)
        self.assertContains(response, "Tu mapa relacional aún está por comenzar")
        self.assertContains(response, reverse("diario:simbiosis_dashboard"))
