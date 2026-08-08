import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import Gesto, RegistroGesto


class PortadaGestosContratoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='gestos', password='x')
        self.client.force_login(self.user)
        self.cultivo = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.suelto = Gesto.objects.create(usuario=self.user, nombre='Pantallas', tipo='suelto')

    def test_portada_es_lectura_y_no_calendario_de_marcado(self):
        response = self.client.get(reverse('diario:habitos_dashboard'))
        html = response.content.decode()
        self.assertContains(response, 'Se registra al cerrar el día')
        self.assertNotIn('dia-toggle', html)
        self.assertNotIn('Días del mes', html)
        self.assertNotIn('wizard-4leyes', html)
        self.assertNotIn('fa-magic', html)
        self.assertNotIn('fa-calendar', html)

    def test_orden_editorial_y_ctas(self):
        html = self.client.get(reverse('diario:habitos_dashboard')).content.decode()
        posiciones = [html.index(texto) for texto in ('01 Hoy', '02 Cultivo', '03 Suelto', '04 Archivo')]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIn(reverse('diario:presencia_cierre'), html)
        self.assertIn(reverse('diario:habito_registrar_trigger', args=[self.suelto.id]), html)
        self.assertIn('Nuevo gesto', html)

    def test_estetica_accesible_y_responsive(self):
        html = self.client.get(reverse('diario:habitos_dashboard')).content.decode()
        for token in ('max-width: 980px', "'Crimson Pro'", "'Manrope'", 'min-height: 44px', ':focus-visible', '@media (max-width: 600px)', 'prefers-reduced-motion'):
            self.assertIn(token, html)


class RetiradaRecuperableTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='x')
        self.other = User.objects.create_user(username='other', password='x')
        self.gesto = Gesto.objects.create(usuario=self.owner, nombre='Caminar', tipo='cultivo')
        self.registro = RegistroGesto.objects.create(
            gesto=self.gesto, fecha=timezone.localdate() - timedelta(days=1), estado='cumplido'
        )
        self.client.force_login(self.owner)

    def test_retirar_y_restaurar_son_post_only_idempotentes_y_preservan_historial(self):
        retirar = reverse('diario:retirar_gesto', args=[self.gesto.id])
        restaurar = reverse('diario:restaurar_gesto', args=[self.gesto.id])
        self.assertEqual(self.client.get(retirar).status_code, 405)
        self.assertEqual(self.client.get(restaurar).status_code, 405)
        self.assertEqual(self.client.post(retirar).status_code, 302)
        self.assertEqual(self.client.post(retirar).status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'cerrado')
        self.assertEqual(self.gesto.fecha_cierre, timezone.localdate())
        self.assertTrue(RegistroGesto.objects.filter(pk=self.registro.pk).exists())
        self.assertEqual(self.client.post(restaurar).status_code, 302)
        self.assertEqual(self.client.post(restaurar).status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'activo')
        self.assertIsNone(self.gesto.fecha_cierre)
        self.assertTrue(RegistroGesto.objects.filter(pk=self.registro.pk).exists())

    def test_otro_usuario_no_puede_retirar_ni_restaurar(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('diario:retirar_gesto', args=[self.gesto.id])).status_code, 404)
        self.gesto.estado = 'cerrado'
        self.gesto.save(update_fields=['estado'])
        self.assertEqual(self.client.post(reverse('diario:restaurar_gesto', args=[self.gesto.id])).status_code, 404)

    def test_no_se_puede_pausar_un_gesto_retirado(self):
        self.gesto.estado = 'cerrado'
        self.gesto.save(update_fields=['estado'])
        self.assertEqual(self.client.post(reverse('diario:habito_pausar', args=[self.gesto.id])).status_code, 404)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'cerrado')


class ArchivoYToggleFuturoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='archivo', password='x')
        self.client.force_login(self.user)

    def test_archivo_incluye_pausados_y_retirados_de_ambos_tipos(self):
        gestos = [
            Gesto.objects.create(usuario=self.user, nombre='Cultivo pausado', tipo='cultivo', estado='pausado'),
            Gesto.objects.create(usuario=self.user, nombre='Suelto pausado', tipo='suelto', estado='pausado'),
            Gesto.objects.create(usuario=self.user, nombre='Cultivo retirado', tipo='cultivo', estado='cerrado'),
            Gesto.objects.create(usuario=self.user, nombre='Suelto retirado', tipo='suelto', estado='cerrado'),
        ]
        response = self.client.get(reverse('diario:habitos_dashboard'))
        for gesto in gestos:
            self.assertContains(response, gesto.nombre)
        html = response.content.decode()
        self.assertIn(reverse('diario:habito_reactivar', args=[gestos[0].id]), html)
        self.assertIn(reverse('diario:restaurar_gesto', args=[gestos[2].id]), html)

    def test_toggle_legacy_rechaza_fecha_futura(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Activo', tipo='cultivo')
        manana = timezone.localdate() + timedelta(days=1)
        response = self.client.post(
            reverse('diario:habito_toggle_dia'),
            data=json.dumps({'habito_id': gesto.id, 'dia': manana.day}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(gesto.registros.exists())
