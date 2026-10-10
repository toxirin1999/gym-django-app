"""Contrato del estado inicial de la cronología del atleta."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class TimelineEmptyStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cronologia-vacia", password="secreto"
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse("entrenos:timeline_atleta", args=[self.cliente.id])

    def test_sin_actividad_ni_bitacora_muestra_inicio_y_dos_salidas(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["tiene_registros_timeline"])
        self.assertContains(response, "AÚN NO HAY ACTIVIDAD NI BITÁCORA EN ESTE PERIODO")
        self.assertContains(
            response,
            reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id]),
        )
        self.assertContains(
            response,
            reverse("entrenos:registrar_actividad_libre", args=[self.cliente.id]),
        )
