from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class EntrenosFiltradosScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner_filtered', password='x')
        self.other = User.objects.create_user('other_filtered', password='x')
        self.staff = User.objects.create_user('staff_filtered', password='x', is_staff=True)
        self.rutina = Rutina.objects.create(nombre='Rutina filtrada')
        self.mine = EntrenoRealizado.objects.create(cliente=self.user.cliente_perfil, rutina=self.rutina, fecha=date.today())
        self.theirs = EntrenoRealizado.objects.create(cliente=self.other.cliente_perfil, rutina=self.rutina, fecha=date.today())
        self.url = reverse('entrenos:entrenos_filtrados_rango', args=['hoy'])

    def test_requires_login_and_scopes_regular_user_to_own_sessions(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertContains(response, self.user.cliente_perfil.nombre)
        self.assertNotContains(response, self.other.cliente_perfil.nombre)

    def test_staff_can_review_all_sessions(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertContains(response, self.user.cliente_perfil.nombre)
        self.assertContains(response, self.other.cliente_perfil.nombre)

    def test_empty_range_offers_safe_actions_to_regular_user(self):
        EntrenoRealizado.objects.all().delete()
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.context['historial_filtrado_cliente_id'],
            self.user.cliente_perfil.id,
        )
        self.assertContains(response, 'Ver rutina disponible')
        self.assertContains(response, 'Registrar actividad libre')
