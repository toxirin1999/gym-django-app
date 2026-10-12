"""Cada usuario ve solo su propia gamificación; el staff puede ver a cualquiera."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from logros.models import Arquetipo


class AccesoGamificacionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        Arquetipo.objects.create(
            nivel=1, nombre_personaje='Inicio', titulo_arquetipo='Aspirante',
            filosofia='Empezar.', puntos_requeridos=0,
        )
        # El orden importa: "otro" se crea primero para que sea Cliente.objects.first().
        self.otro_user = User.objects.create_user(username='otro', password='x')
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.user = User.objects.create_user(username='yo', password='x')
        self.yo = Cliente.objects.get(user=self.user)
        self.staff = User.objects.create_user(username='staff', password='x', is_staff=True)

    def test_sin_id_muestra_al_usuario_conectado_y_no_al_primer_cliente(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logros:perfil_gamificacion'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cliente'], self.yo)

    def test_no_puede_ver_el_perfil_de_otro_cliente(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logros:perfil_gamificacion', args=[self.otro.id]))
        self.assertEqual(response.status_code, 404)

    def test_puede_ver_su_propio_perfil_por_id(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logros:perfil_gamificacion', args=[self.yo.id]))
        self.assertEqual(response.status_code, 200)

    def test_staff_puede_ver_a_cualquier_cliente(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('logros:perfil_gamificacion', args=[self.otro.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cliente'], self.otro)

    def test_visitar_otro_cliente_no_crea_su_perfil(self):
        from logros.models import PerfilGamificacion
        PerfilGamificacion.objects.filter(cliente=self.otro).delete()
        self.client.force_login(self.user)
        self.client.get(reverse('logros:perfil_gamificacion', args=[self.otro.id]))
        self.assertFalse(PerfilGamificacion.objects.filter(cliente=self.otro).exists())

    def test_resto_de_vistas_por_cliente_rechazan_a_otro_cliente(self):
        self.client.force_login(self.user)
        urls = [
            reverse('logros:detalle_arquetipo', args=[self.otro.id, 1]),
            reverse('logros:analisis_cliente', args=[self.otro.id]),
            reverse('logros:exportar_analisis_cliente_pdf', args=[self.otro.id]),
            reverse('logros:ver_codice_completo', args=[self.otro.id]),
            reverse('logros:gamificacion_resumen_json', args=[self.otro.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_analisis_global_solo_para_staff(self):
        url = reverse('logros:analisis_global')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)
