from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.utils import get_cliente_actual
from diario.forms import InteraccionForm
from diario.models import Interaccion, PersonaImportante, PersonaInterina
from joi.context_builders.life_context import build_life_context


class ArchivadoPersonaSimbiosisTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="simbiosis-archivado", password="test-pass",
        )
        self.other_user = get_user_model().objects.create_user(
            username="otra-persona", password="test-pass",
        )
        self.client.force_login(self.user)
        self.persona = PersonaImportante.objects.create(
            usuario=self.user, nombre="Ana", tipo_relacion="amigo",
        )
        self.interina = PersonaInterina.objects.create(
            usuario=self.user,
            nombre="Ana",
            estado="promovida",
            veces_mencionada=3,
            persona_importante=self.persona,
        )
        self.interaccion = Interaccion.objects.create(
            usuario=self.user,
            titulo="Conversación importante",
            descripcion="Contexto que debe conservarse",
        )
        self.interaccion.personas.add(self.persona)

    def test_archivar_por_post_conserva_persona_e_interacciones_y_desvincula_interina(self):
        response = self.client.post(
            reverse("diario:eliminar_persona", args=[self.persona.pk]),
        )

        self.assertRedirects(response, reverse("diario:simbiosis_dashboard"))
        self.persona.refresh_from_db()
        self.interina.refresh_from_db()
        self.assertTrue(self.persona.archivada)
        self.assertTrue(Interaccion.objects.filter(pk=self.interaccion.pk).exists())
        self.assertTrue(self.interaccion.personas.filter(pk=self.persona.pk).exists())
        self.assertEqual(self.interina.estado, "sombra")
        self.assertIsNone(self.interina.persona_importante)

    def test_archivar_rechaza_get_y_persona_de_otro_usuario(self):
        ajena = PersonaImportante.objects.create(usuario=self.other_user, nombre="Ajena")
        url_propia = reverse("diario:eliminar_persona", args=[self.persona.pk])
        url_ajena = reverse("diario:eliminar_persona", args=[ajena.pk])

        self.assertEqual(self.client.get(url_propia).status_code, 405)
        self.assertEqual(self.client.post(url_ajena).status_code, 404)
        self.persona.refresh_from_db()
        ajena.refresh_from_db()
        self.assertFalse(self.persona.archivada)
        self.assertFalse(ajena.archivada)

    def test_dashboard_separa_circulo_activo_y_archivado(self):
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])

        response = self.client.get(reverse("diario:simbiosis_dashboard"))

        self.assertNotIn(self.persona, response.context["personas"])
        self.assertIn(self.persona, response.context["personas_archivadas"])
        self.assertEqual(response.context["n_confirmadas"], 0)
        self.assertContains(response, "Vínculos archivados")
        self.assertContains(
            response, reverse("diario:restaurar_persona", args=[self.persona.pk]),
        )

    def test_archivada_no_aparece_en_selector_de_interacciones(self):
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])

        form = InteraccionForm(usuario=self.user)

        self.assertNotIn(self.persona, form.fields["personas"].queryset)

    def test_editar_interaccion_conserva_como_opcion_su_persona_archivada(self):
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])

        form = InteraccionForm(instance=self.interaccion, usuario=self.user)

        self.assertIn(self.persona, form.fields["personas"].queryset)

    def test_archivada_deja_de_alimentar_el_contexto_relacional_de_joi(self):
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])
        cliente = get_cliente_actual(self.user)
        hoy = date.today()

        contexto = build_life_context(cliente, hoy, hoy - timedelta(days=7))

        self.assertNotIn("presencia_relacional", contexto)

    def test_restaurar_por_post_reactiva_y_reconecta_la_interina(self):
        self.client.post(reverse("diario:eliminar_persona", args=[self.persona.pk]))

        response = self.client.post(
            reverse("diario:restaurar_persona", args=[self.persona.pk]),
        )

        self.assertRedirects(response, reverse("diario:persona_detalle", args=[self.persona.pk]))
        self.persona.refresh_from_db()
        self.interina.refresh_from_db()
        self.assertFalse(self.persona.archivada)
        self.assertEqual(self.interina.estado, "promovida")
        self.assertEqual(self.interina.persona_importante, self.persona)
        self.assertTrue(Interaccion.objects.filter(pk=self.interaccion.pk).exists())

    def test_restaurar_es_post_idempotente_y_respeta_propiedad(self):
        ajena = PersonaImportante.objects.create(
            usuario=self.other_user, nombre="Ajena", archivada=True,
        )
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])
        url = reverse("diario:restaurar_persona", args=[self.persona.pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(reverse("diario:restaurar_persona", args=[ajena.pk])).status_code,
            404,
        )
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(PersonaImportante.objects.filter(pk=self.persona.pk).count(), 1)

    def test_detalle_explica_archivado_sin_atribuir_copy_a_joi(self):
        self.persona.archivada = True
        self.persona.save(update_fields=["archivada"])

        response = self.client.get(reverse("diario:persona_detalle", args=[self.persona.pk]))
        html = response.content.decode()

        self.assertContains(response, "Vínculo archivado")
        self.assertContains(response, "Conservas todo su historial")
        self.assertNotIn("JOI", html)

    def test_reconfirmar_desde_radar_reactiva_la_persona_archivada(self):
        self.client.post(reverse("diario:eliminar_persona", args=[self.persona.pk]))

        response = self.client.post(
            reverse("diario:promover_persona_interina"),
            data='{"id": %d, "accion": "promover"}' % self.interina.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.persona.refresh_from_db()
        self.interina.refresh_from_db()
        self.assertFalse(self.persona.archivada)
        self.assertEqual(self.interina.persona_importante, self.persona)
