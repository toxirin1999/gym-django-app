import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.forms import PersonaImportanteForm
from diario.models import PersonaImportante, PersonaInterina


class SaludRelacionSinValorarTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="simbiosis-salud", password="test-pass",
        )
        self.client.force_login(self.user)

    def test_nueva_persona_no_inventa_una_valoracion(self):
        persona = PersonaImportante.objects.create(usuario=self.user, nombre="Nora")

        self.assertIsNone(persona.salud_relacion)

    def test_formulario_permite_dejar_salud_sin_valorar(self):
        form = PersonaImportanteForm({
            "nombre": "Nora",
            "tipo_relacion": "amigo",
            "salud_relacion": "",
            "notas": "",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["salud_relacion"])
        self.assertIn("Sin valorar", str(form["salud_relacion"]))
        for valor in range(1, 6):
            self.assertIn(f'value="{valor}"', str(form["salud_relacion"]))

    def test_formulario_rechaza_valor_fuera_de_escala_y_muestra_el_error(self):
        response = self.client.post(reverse("diario:persona_crear"), data={
            "nombre": "Nora",
            "tipo_relacion": "amigo",
            "salud_relacion": "6",
            "notas": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_salud_relacion_error"')
        self.assertContains(response, "Elige Sin valorar o un valor entre 1 y 5.")
        self.assertFalse(PersonaImportante.objects.exists())

    def test_alta_manual_vacia_guarda_sin_valorar(self):
        response = self.client.post(reverse("diario:persona_crear"), data={
            "nombre": "Nora",
            "tipo_relacion": "amigo",
            "salud_relacion": "",
            "notas": "",
        })

        self.assertRedirects(response, reverse("diario:simbiosis_dashboard"))
        self.assertIsNone(PersonaImportante.objects.get().salud_relacion)

    def test_promocion_guarda_salud_sin_valorar(self):
        interina = PersonaInterina.objects.create(
            usuario=self.user, nombre="Nora", estado="radar",
        )

        response = self.client.post(
            reverse("diario:promover_persona_interina"),
            data=json.dumps({"id": interina.pk, "accion": "promover"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(PersonaImportante.objects.get().salud_relacion)

    def test_dashboard_muestra_sin_valorar_sin_barra_ficticia(self):
        persona = PersonaImportante.objects.create(usuario=self.user, nombre="Nora")

        response = self.client.get(reverse("diario:simbiosis_dashboard"))
        html = response.content.decode()

        self.assertContains(response, "Sin valorar")
        self.assertNotIn(f'id="salud-bar-{persona.pk}"', html)
        self.assertNotIn("width:60%", html)

    def test_dashboard_y_detalle_conservan_valoraciones_existentes(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre="Nora", salud_relacion=4,
        )

        dashboard = self.client.get(reverse("diario:simbiosis_dashboard"))
        detalle = self.client.get(reverse("diario:persona_detalle", args=[persona.pk]))

        self.assertContains(dashboard, f'id="salud-bar-{persona.pk}"')
        self.assertContains(dashboard, "width:80.0%")
        self.assertContains(detalle, "4/5")

    def test_detalle_muestra_sin_valorar(self):
        persona = PersonaImportante.objects.create(usuario=self.user, nombre="Nora")

        response = self.client.get(reverse("diario:persona_detalle", args=[persona.pk]))

        self.assertContains(response, "Sin valorar")
