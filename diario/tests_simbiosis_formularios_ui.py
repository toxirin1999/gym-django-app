from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from diario.forms import InteraccionForm
from diario.models import Interaccion, PersonaImportante


class FormulariosSimbiosisUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="formularios-simbiosis", password="test-pass",
        )
        self.other_user = get_user_model().objects.create_user(
            username="formularios-ajeno", password="test-pass",
        )
        self.client.force_login(self.user)
        self.ana = PersonaImportante.objects.create(usuario=self.user, nombre="Ana")
        self.archivada = PersonaImportante.objects.create(
            usuario=self.user, nombre="Clara", archivada=True,
        )
        self.ajena = PersonaImportante.objects.create(
            usuario=self.other_user, nombre="Persona ajena",
        )

    def test_personas_se_eligen_con_checkboxes_tactiles_y_aislados_por_usuario(self):
        form = InteraccionForm(usuario=self.user)

        self.assertIsInstance(form.fields["personas"].widget, forms.CheckboxSelectMultiple)
        self.assertQuerySetEqual(form.fields["personas"].queryset, [self.ana])
        html = str(form["personas"])
        self.assertIn('type="checkbox"', html)
        self.assertNotIn("Persona ajena", html)
        self.assertNotIn("Clara", html)

    def test_edicion_solo_recupera_archivadas_que_ya_forman_parte_de_la_interaccion(self):
        otra_archivada = PersonaImportante.objects.create(
            usuario=self.user, nombre="Otra archivada", archivada=True,
        )
        interaccion = Interaccion.objects.create(
            usuario=self.user, titulo="Conversación", descripcion="Algo", fecha=date.today(),
        )
        interaccion.personas.add(self.archivada)

        form = InteraccionForm(instance=interaccion, usuario=self.user)

        self.assertIn(self.archivada, form.fields["personas"].queryset)
        self.assertNotIn(otra_archivada, form.fields["personas"].queryset)
        self.assertNotIn(self.ajena, form.fields["personas"].queryset)

    def test_post_invalido_conserva_datos_seleccion_y_muestra_errores_accesibles(self):
        response = self.client.post(reverse("diario:interaccion_crear"), data={
            "titulo": "Conversación pendiente",
            "fecha": "fecha-invalida",
            "personas": [str(self.ana.pk)],
            "tipo_interaccion": "positiva",
            "descripcion": "Contexto conservado",
            "mi_sentir": "En calma",
            "aprendizaje": "Escuchar",
        })

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.data["titulo"], "Conversación pendiente")
        self.assertEqual(form.data.getlist("personas"), [str(self.ana.pk)])
        self.assertContains(response, "Introduce una fecha válida")
        self.assertContains(response, 'id="id_fecha_error"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_fecha_error"')
        self.assertContains(response, 'value="Conversación pendiente"')
        self.assertContains(response, 'value="%s"' % self.ana.pk, html=False)
        self.assertContains(response, 'id="id_personas_0" checked', html=False)

    def test_persona_invalida_muestra_errores_de_campo_y_resumen_no_global(self):
        response = self.client.post(reverse("diario:persona_crear"), data={
            "nombre": "",
            "tipo_relacion": "amigo",
            "salud_relacion": "9",
            "notas": "Texto que no debe perderse",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo es obligatorio")
        self.assertContains(response, "Elige Sin valorar o un valor entre 1 y 5")
        self.assertContains(response, 'id="id_nombre_error"')
        self.assertContains(response, 'id="id_salud_relacion_error"')
        self.assertContains(response, "Texto que no debe perderse")

    def test_templates_explican_origen_opcionalidad_y_contrato_visual(self):
        interaccion = self.client.get(reverse("diario:interaccion_crear"))
        persona = self.client.get(reverse("diario:persona_crear"))
        html = interaccion.content.decode()
        persona_html = persona.content.decode()

        self.assertContains(interaccion, "Registrar una interacción es opcional")
        self.assertContains(interaccion, "registrada manualmente")
        self.assertNotIn("Ctrl", html)
        self.assertNotIn("Cmd", html)
        for contract in (
            "#13111A", "#1E1B27", "#A78BFA", "min-height: 44px",
            ":focus-visible", "@media (max-width: 560px)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(contract, html)
            self.assertIn(contract, persona_html)
        self.assertIn("max-width: 680px", html)
        self.assertIn("max-width: 680px", persona_html)

    def test_urls_de_cancelacion_y_formulario_son_validas(self):
        for url in (
            reverse("diario:persona_crear"),
            reverse("diario:persona_editar", args=[self.ana.pk]),
            reverse("diario:interaccion_crear"),
        ):
            self.assertEqual(self.client.get(url).status_code, 200)

        dashboard_url = reverse("diario:simbiosis_dashboard")
        self.assertContains(self.client.get(reverse("diario:persona_crear")), dashboard_url)
        self.assertContains(self.client.get(reverse("diario:interaccion_crear")), dashboard_url)
