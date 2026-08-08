import uuid
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from diario.forms import PersonaImportanteForm
from diario.models import AliasSimbiosis, Interaccion, OperacionIdentidadSimbiosis, PersonaImportante
from diario.services.identidad_simbiosis_service import fusionar_personas
from diario.services.lectura_relacional_service import construir_lectura_relacional


class LecturaRelacionalServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('lectura', password='x')
        self.persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', tipo_entidad='persona', tipo_relacion='amigo',
        )

    def interaccion(self, titulo, fecha, tipo='neutra', personas=None, descripcion=''):
        item = Interaccion.objects.create(
            usuario=self.user, titulo=titulo, fecha=fecha, tipo_interaccion=tipo,
            descripcion=descripcion,
        )
        item.personas.set(personas or [self.persona])
        return item

    def test_hechos_son_exactos_y_patrones_declaran_muestra_umbral(self):
        self.interaccion('Café', date(2026, 8, 1), 'positiva')
        self.interaccion('Paseo', date(2026, 8, 3), 'apoyo')
        self.interaccion('Llamada', date(2026, 8, 5), 'positiva')

        lectura = construir_lectura_relacional(self.persona, usuario=self.user)

        self.assertEqual(lectura['hechos']['total_interacciones'], 3)
        self.assertEqual(lectura['hechos']['primera_fecha'], date(2026, 8, 1))
        self.assertEqual(lectura['hechos']['ultima_fecha'], date(2026, 8, 5))
        self.assertEqual(lectura['hechos']['tipos'], {'positiva': 2, 'apoyo': 1})
        self.assertFalse(lectura['patrones']['datos_insuficientes'])
        self.assertEqual(lectura['patrones']['muestra'], 3)
        self.assertEqual(lectura['patrones']['umbral'], 3)
        self.assertIn('En esta muestra', lectura['patrones']['texto'])

    def test_datos_insuficientes_no_inventa_patron_ni_temas(self):
        self.interaccion('Una conversación', date(2026, 8, 1), descripcion='Trabajo y familia')
        lectura = construir_lectura_relacional(self.persona, usuario=self.user)
        self.assertTrue(lectura['patrones']['datos_insuficientes'])
        self.assertEqual(lectura['temas'], [])
        self.assertIn('Aún no hay muestra suficiente', lectura['patrones']['texto'])

    def test_raiz_agrega_absorbidas_sin_duplicar_interaccion_m2m(self):
        alias = PersonaImportante.objects.create(
            usuario=self.user, nombre='Anita', tipo_entidad='persona', tipo_relacion='amigo',
        )
        compartida = self.interaccion('Juntas', date(2026, 8, 1), personas=[self.persona, alias])
        fusionar_personas(alias, self.persona)
        lectura_alias = construir_lectura_relacional(alias, usuario=self.user)
        self.assertEqual(lectura_alias['persona_raiz'], self.persona)
        self.assertEqual(lectura_alias['hechos']['total_interacciones'], 1)
        self.assertEqual(list(lectura_alias['interacciones']), [compartida])
        self.assertEqual(list(lectura_alias['identidades_absorbidas']), [alias])

    def test_no_permite_lectura_multiusuario(self):
        ajeno = User.objects.create_user('ajeno')
        with self.assertRaises(PersonaImportante.DoesNotExist):
            construir_lectura_relacional(self.persona, usuario=ajeno)


class SimbiosisIdentidadViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('propietario', password='x')
        self.client.force_login(self.user)
        self.origen = PersonaImportante.objects.create(
            usuario=self.user, nombre='Anita', tipo_entidad='persona', tipo_relacion='amigo',
        )
        self.destino = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', tipo_entidad='persona', tipo_relacion='amigo',
        )
        self.merge_url = reverse('diario:persona_fusionar', args=[self.origen.pk])

    def test_fusion_es_post_only_exige_confirmacion_y_uuid(self):
        self.assertEqual(self.client.get(self.merge_url).status_code, 405)
        self.assertEqual(self.client.post(self.merge_url, {'destino_id': self.destino.pk}).status_code, 400)
        response = self.client.post(self.merge_url, {
            'destino_id': self.destino.pk, 'confirmar': '1', 'operacion_id': str(uuid.uuid4()),
        })
        self.assertRedirects(response, reverse('diario:persona_detalle', args=[self.destino.pk]))
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.fusionada_en, self.destino)

    def test_deshacer_es_post_only_y_solo_propietario(self):
        operacion = fusionar_personas(self.origen, self.destino)
        url = reverse('diario:identidad_deshacer', args=[operacion.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {'confirmar': '1', 'operacion_id': str(uuid.uuid4())})
        self.assertRedirects(response, reverse('diario:persona_detalle', args=[self.origen.pk]))
        self.origen.refresh_from_db()
        self.assertIsNone(self.origen.fusionada_en)

        ajeno = User.objects.create_user('otro', password='x')
        self.client.force_login(ajeno)
        self.assertEqual(self.client.post(url, {'confirmar': '1', 'operacion_id': str(uuid.uuid4())}).status_code, 404)

    def test_dashboard_oculta_absorbida_y_muestra_auditoria(self):
        fusionar_personas(self.origen, self.destino)
        response = self.client.get(reverse('diario:simbiosis_dashboard'))
        self.assertNotContains(response, f'href="{reverse("diario:persona_detalle", args=[self.origen.pk])}" class="circulo-item"')
        self.assertContains(response, 'Identidades absorbidas')
        self.assertContains(response, 'Anita')

    def test_detalle_tiene_copy_no_causal_timeline_y_accesibilidad(self):
        response = self.client.get(reverse('diario:persona_detalle', args=[self.destino.pk]))
        self.assertContains(response, 'Hechos registrados')
        self.assertContains(response, 'Patrones observados')
        self.assertContains(response, 'No explica causas ni define la relación')
        self.assertContains(response, 'min-height: 44px')
        self.assertContains(response, ':focus-visible')
        self.assertContains(response, 'prefers-reduced-motion')
        self.assertNotContains(response, 'significa que')

    def test_form_nuevo_ofrece_persona_o_grupo_y_legacy_sigue_editable(self):
        form = PersonaImportanteForm(data={
            'nombre': 'Equipo', 'tipo_relacion': 'otro', 'salud_relacion': '', 'notas': '',
            'tipo_entidad': 'grupo',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['tipo_entidad'], 'grupo')
        self.assertEqual(
            {valor for valor, _ in form.fields['tipo_entidad'].choices if valor},
            {'persona', 'grupo'},
        )
        legacy = PersonaImportante.objects.create(usuario=self.user, nombre='Legacy')
        legacy_form = PersonaImportanteForm(data={
            'nombre': 'Legacy', 'tipo_relacion': 'amigo', 'salud_relacion': '', 'notas': '',
            'tipo_entidad': 'sin_clasificar',
        }, instance=legacy)
        self.assertTrue(legacy_form.is_valid())

    def test_editar_nombre_desde_ui_conserva_alias_y_registra_operacion(self):
        response = self.client.post(
            reverse('diario:persona_editar', args=[self.destino.pk]),
            {
                'nombre': 'Ana María', 'tipo_entidad': 'persona',
                'tipo_relacion': 'familia', 'salud_relacion': '',
                'notas': 'Contexto actualizado',
            },
        )
        self.assertRedirects(response, reverse('diario:simbiosis_dashboard'))
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.nombre, 'Ana María')
        self.assertTrue(AliasSimbiosis.objects.filter(
            usuario=self.user, persona_confirmada=self.destino,
            nombre_normalizado='ana', activo=True,
        ).exists())
        self.assertTrue(OperacionIdentidadSimbiosis.objects.filter(
            usuario=self.user, tipo='corregir', origen=self.destino,
        ).exists())
