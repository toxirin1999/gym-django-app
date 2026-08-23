from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from rutinas.models import Programa, Rutina


class GestionClientesAuthTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        self.superuser_only = User.objects.create_user(
            "superuser_only", password="pw", is_superuser=True, is_staff=False
        )
        self.owner = User.objects.create_user("owner", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.cliente = self.owner.cliente_perfil
        self.cliente.nombre = "Propietario"
        self.cliente.email = "owner@example.com"
        self.cliente.telefono = "1"
        self.cliente.save(update_fields=["nombre", "email", "telefono"])
        self.programa = Programa.objects.create(nombre="Programa seguro")
        self.rutina = Rutina.objects.create(nombre="Rutina segura", programa=self.programa)

    def _management_urls(self):
        return [
            reverse("clientes:lista_clientes"),
            reverse("clientes:panel_entrenador"),
            reverse("clientes:api_lista_clientes"),
            reverse("clientes:agregar_cliente"),
            reverse("clientes:editar_cliente", args=[self.cliente.pk]),
            reverse("clientes:eliminar_cliente", args=[self.cliente.pk]),
            reverse("clientes:asignar_programa", args=[self.cliente.pk]),
            reverse("clientes:asignar_rutina", args=[self.cliente.pk]),
            reverse("clientes:asignar_programa_a_cliente", args=[self.programa.pk]),
        ]

    def test_anonymous_management_access_redirects_to_login(self):
        initial_users = User.objects.count()
        initial_clients = Cliente.objects.count()
        for url in self._management_urls():
            with self.subTest(url=url):
                response = self.client.get(url) if "api/" in url else self.client.post(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)
        self.cliente.refresh_from_db()
        self.assertEqual(User.objects.count(), initial_users)
        self.assertEqual(Cliente.objects.count(), initial_clients)
        self.assertIsNone(self.cliente.programa_id)
        self.assertIsNone(self.cliente.rutina_actual_id)

    def test_nonstaff_management_access_is_forbidden_without_mutation(self):
        self.client.force_login(self.other)
        initial_users = User.objects.count()
        initial_clients = Cliente.objects.count()

        posts = {
            reverse("clientes:agregar_cliente"): {
                "username": "intruso", "password": "pw", "nombre": "Intruso",
                "email": "intruso@example.com", "telefono": "9",
            },
            reverse("clientes:editar_cliente", args=[self.cliente.pk]): {
                "username": "mutado", "nombre": "Mutado",
                "email": "mutado@example.com", "telefono": "9",
            },
            reverse("clientes:eliminar_cliente", args=[self.cliente.pk]): {},
            reverse("clientes:asignar_programa", args=[self.cliente.pk]): {
                "programa_id": self.programa.pk
            },
            # La vista usa hoy un campo posiblemente incorrecto. Este test solo
            # exige que autorización corte antes de intentar esa mutación.
            reverse("clientes:asignar_rutina", args=[self.cliente.pk]): {
                "rutina_id": self.rutina.pk
            },
            reverse("clientes:asignar_programa_a_cliente", args=[self.programa.pk]): {
                "cliente_id": self.cliente.pk
            },
        }
        for url, data in posts.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data).status_code, 403)

        for url in self._management_urls()[:3]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                if url == reverse("clientes:api_lista_clientes"):
                    self.assertEqual(response.json(), {"error": "Acceso no autorizado"})

        self.cliente.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(User.objects.count(), initial_users)
        self.assertEqual(Cliente.objects.count(), initial_clients)
        self.assertEqual(self.owner.username, "owner")
        self.assertEqual(self.cliente.nombre, "Propietario")
        self.assertIsNone(self.cliente.programa_id)
        self.assertIsNone(self.cliente.rutina_actual_id)

    @patch("clientes.views.render", return_value=HttpResponse("ok"))
    def test_staff_and_superuser_without_staff_can_open_management(self, _render):
        urls = [
            reverse("clientes:lista_clientes"),
            reverse("clientes:agregar_cliente"),
            reverse("clientes:editar_cliente", args=[self.cliente.pk]),
        ]
        for user in (self.staff, self.superuser_only):
            self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    @patch("clientes.views.render_to_string", return_value="")
    def test_superuser_without_staff_can_open_client_list_api(self, _render_rows):
        self.client.force_login(self.superuser_only)
        response = self.client.get(reverse("clientes:api_lista_clientes"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", response.json())

    def test_staff_and_superuser_can_assign_programa(self):
        for user in (self.staff, self.superuser_only):
            self.cliente.programa = None
            self.cliente.save(update_fields=["programa"])
            self.client.force_login(user)
            response = self.client.post(
                reverse("clientes:asignar_programa", args=[self.cliente.pk]),
                {"programa_id": self.programa.pk},
            )
            self.assertEqual(response.status_code, 302)
            self.cliente.refresh_from_db()
            self.assertEqual(self.cliente.programa_id, self.programa.pk)


class DetalleClienteAuthTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        self.owner = User.objects.create_user("owner", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.cliente = self.owner.cliente_perfil
        self.cliente.nombre = "Propietario"
        self.cliente.email = "owner@example.com"
        self.cliente.telefono = "1"
        self.cliente.save(update_fields=["nombre", "email", "telefono"])
        self.url = reverse("clientes:detalle_cliente", args=[self.cliente.pk])

    def test_anonymous_detail_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("clientes.views.render", return_value=HttpResponse("ok"))
    def test_owner_and_staff_can_access_detail(self, _render):
        for user in (self.owner, self.staff):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_user_cannot_distinguish_existing_and_missing_detail(self):
        self.client.force_login(self.other)
        existing = self.client.get(self.url)
        missing = self.client.get(reverse("clientes:detalle_cliente", args=[999999]))
        self.assertEqual(existing.status_code, missing.status_code)
        self.assertIn(existing.status_code, (403, 404))

    def test_edit_link_is_visible_only_to_staff_or_superuser(self):
        for user, visible in ((self.owner, False), (self.staff, True)):
            self.client.force_login(user)
            response = self.client.get(self.url)
            edit_url = reverse("clientes:editar_cliente", args=[self.cliente.pk])
            assertion = self.assertContains if visible else self.assertNotContains
            assertion(response, edit_url)
