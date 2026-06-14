"""
Phase 63.1 — vista "Mi cuerpo": entrada única de peso/cintura/grasa, enlazada
desde el dashboard, que actualiza el snapshot del Cliente, alimenta PesoDiario
y sincroniza RevisionProgreso cuando cambian las medidas.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente, PesoDiario, RevisionProgreso


class MiCuerpoViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_mi_cuerpo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.login(username='tester_mi_cuerpo', password='x')
        self.url = reverse('clientes:mi_cuerpo', args=[self.cliente.id])

    def test_get_renderiza_formulario(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mi cuerpo')

    def test_guardar_cintura_actualiza_cliente_y_crea_revision(self):
        response = self.client.post(self.url, {
            'peso_corporal': '', 'cintura': '84.0', 'grasa_corporal': '',
        })

        self.assertEqual(response.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.cintura, 84.0)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 1)
        revision = RevisionProgreso.objects.get(cliente=self.cliente)
        self.assertEqual(revision.cintura, Decimal('84.00'))

    def test_guardar_peso_actualiza_cliente_y_crea_peso_diario(self):
        response = self.client.post(self.url, {
            'peso_corporal': '81.5', 'cintura': '', 'grasa_corporal': '',
        })

        self.assertEqual(response.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.peso_corporal, 81.5)

        peso_diario = PesoDiario.objects.get(cliente=self.cliente, fecha=date.today())
        self.assertEqual(peso_diario.peso_kg, Decimal('81.50'))

    def test_guardar_de_nuevo_mismo_dia_actualiza_peso_diario_sin_duplicar(self):
        self.client.post(self.url, {'peso_corporal': '81.5', 'cintura': '', 'grasa_corporal': ''})
        self.client.post(self.url, {'peso_corporal': '82.0', 'cintura': '', 'grasa_corporal': ''})

        self.assertEqual(PesoDiario.objects.filter(cliente=self.cliente, fecha=date.today()).count(), 1)
        peso_diario = PesoDiario.objects.get(cliente=self.cliente, fecha=date.today())
        self.assertEqual(peso_diario.peso_kg, Decimal('82.00'))

    def test_guardar_sin_datos_no_crea_revision_ni_peso_diario(self):
        response = self.client.post(self.url, {
            'peso_corporal': '', 'cintura': '', 'grasa_corporal': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 0)
        self.assertEqual(PesoDiario.objects.filter(cliente=self.cliente).count(), 0)

    def test_dashboard_enlaza_a_mi_cuerpo(self):
        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)
