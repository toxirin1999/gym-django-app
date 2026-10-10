"""Regression coverage for legacy client-detail routes.

These routes predate the current panel, but they remain addressable by URL and
therefore must apply the same ownership boundary as the active client flows.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import ObjetivoCliente, RevisionProgreso


class LegacyClientScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('legacy_owner', password='x')
        self.other = User.objects.create_user('legacy_other', password='x')
        self.staff = User.objects.create_user(
            'legacy_staff', password='x', is_staff=True
        )
        self.owner_cliente = self.owner.cliente_perfil
        self.other_cliente = self.other.cliente_perfil
        self.revision = RevisionProgreso.objects.create(
            cliente=self.owner_cliente, peso_corporal='80.0'
        )
        self.objetivo = ObjetivoCliente.objects.create(
            cliente=self.owner_cliente, medida='peso', valor=75
        )
        self.owner_urls = [
            reverse('clientes:exportar_historial', args=[self.owner_cliente.id]),
            reverse('clientes:historial_cliente', args=[self.owner_cliente.id]),
            reverse('clientes:datos_graficas', args=[self.owner_cliente.id]),
            reverse('clientes:lista_revisiones', args=[self.owner_cliente.id]),
            reverse('clientes:agregar_revision', args=[self.owner_cliente.id]),
            reverse('clientes:definir_objetivo', args=[self.owner_cliente.id]),
            reverse('clientes:vista_educacion_helms', args=[self.owner_cliente.id]),
            reverse('clientes:memoria_entrenador', args=[self.owner_cliente.id]),
        ]

    def test_legacy_client_routes_require_login_and_hide_other_clients(self):
        for url in self.owner_urls:
            self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.other)
        for url in self.owner_urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_and_staff_keep_their_expected_access(self):
        self.client.force_login(self.owner)
        for url in self.owner_urls:
            self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff)
        for url in self.owner_urls:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_mutations_cannot_be_triggered_by_get_or_another_client(self):
        delete_revision = reverse('clientes:eliminar_revision', args=[self.revision.id])
        delete_objetivo = reverse('clientes:eliminar_objetivo', args=[self.objetivo.id])

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(delete_revision).status_code, 405)
        self.assertEqual(self.client.get(delete_objetivo).status_code, 405)
        self.assertTrue(RevisionProgreso.objects.filter(pk=self.revision.id).exists())
        self.assertTrue(ObjetivoCliente.objects.filter(pk=self.objetivo.id).exists())

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(delete_revision).status_code, 404)
        self.assertEqual(self.client.post(delete_objetivo).status_code, 404)

    def test_comparison_endpoints_are_for_staff_only(self):
        compare = reverse('clientes:comparar_clientes')
        data = reverse('clientes:datos_comparacion')

        self.assertEqual(self.client.get(compare).status_code, 302)
        self.assertEqual(self.client.get(data).status_code, 302)

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(compare).status_code, 403)
        self.assertEqual(self.client.get(data).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(compare).status_code, 200)
        self.assertEqual(
            self.client.get(data, {'ids[]': [self.owner_cliente.id]}).status_code,
            200,
        )
