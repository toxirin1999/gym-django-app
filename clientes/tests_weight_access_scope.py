from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class WeightAccessScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('weight_owner', password='x')
        self.other = User.objects.create_user('weight_other', password='x')
        self.staff = User.objects.create_user('weight_staff', password='x', is_staff=True)
        self.urls = [
            reverse('clientes:control_peso_cliente', args=[self.owner.cliente_perfil.id]),
            reverse('clientes:registrar_peso', args=[self.owner.cliente_perfil.id]),
            reverse('clientes:mi_cuerpo', args=[self.owner.cliente_perfil.id]),
            reverse('clientes:establecer_objetivo_peso', args=[self.owner.cliente_perfil.id]),
        ]

    def test_weight_routes_require_login_and_hide_other_clients(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.other)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_staff_can_open_weight_dashboard_for_a_client(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.urls[0])

        self.assertEqual(response.status_code, 200)

    def test_empty_weight_dashboard_explains_the_first_action(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.urls[0])

        self.assertContains(response, 'Registra tu referencia, no una tendencia todavía')
        self.assertContains(response, 'Registrar primer peso')
        self.assertContains(response, 'Añadir objetivo opcional')
