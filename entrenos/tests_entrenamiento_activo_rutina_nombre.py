"""
Microfix: vista_entrenamiento_activo crasheaba con 500 cuando la URL no
incluía `?rutina_nombre=...` (bookmark viejo / URL pegada a mano).

`request.GET.get('rutina_nombre')` devolvía None, y mas abajo
`' - ' in rutina_nombre` lanzaba TypeError: argument of type 'NoneType'
is not iterable. El fix normaliza a '' en el punto de lectura.
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente


class VistaEntrenamientoActivoRutinaNombreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_rutina_nombre', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='tester_rutina_nombre', password='x')
        self.url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])

    def test_sin_query_param_rutina_nombre_no_crashea(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (200, 302))

    def test_con_rutina_nombre_vacio_no_crashea(self):
        response = self.client.get(self.url, {'rutina_nombre': ''})
        self.assertIn(response.status_code, (200, 302))

    def test_con_rutina_nombre_informado_sigue_partiendo_header_correctamente(self):
        response = self.client.get(self.url, {'rutina_nombre': 'DÍA 3 - DESCARGA ACTIVA'})
        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 200:
            self.assertEqual(response.context['rutina_dia'], 'DÍA 3')
            self.assertEqual(response.context['rutina_tipo'], 'DESCARGA ACTIVA')
            self.assertEqual(response.context['rutina_nombre'], 'DÍA 3 - DESCARGA ACTIVA')
