from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class HistorialDetalladoEmptyStateTests(TestCase):
    def test_sin_entrenamientos_explicita_el_estado_y_lleva_al_panel(self):
        user = User.objects.create_user('historial_vacio', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Todavía no hay entrenamientos registrados')
        self.assertContains(
            response,
            'Cuando completes una sesión aparecerá aquí con sus series y esfuerzo.',
        )
        self.assertContains(response, 'Ver rutina de hoy')
        self.assertContains(
            response,
            reverse('clientes:dashboard_silencioso_preview'),
        )

    def test_requires_login(self):
        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertEqual(response.status_code, 302)

    def test_regular_user_only_sees_own_history(self):
        owner = User.objects.create_user('historial_owner', password='x')
        other = User.objects.create_user('historial_other', password='x')
        rutina = Rutina.objects.create(nombre='Rutina historial')
        EntrenoRealizado.objects.create(cliente=owner.cliente_perfil, rutina=rutina)
        EntrenoRealizado.objects.create(cliente=other.cliente_perfil, rutina=rutina)
        self.client.force_login(owner)

        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertContains(response, owner.cliente_perfil.nombre)
        self.assertNotContains(response, other.cliente_perfil.nombre)
        self.assertNotContains(response, 'Filtrar')
