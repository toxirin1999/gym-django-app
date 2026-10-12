"""La ruta legacy de detalle de ejercicio exige login y dueño, y lleva a Evolución."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from rutinas.models import Rutina


class DetalleEjercicioAccesoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='dueno', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro_user = User.objects.create_user(username='ajeno', password='x')
        self.staff = User.objects.create_user(username='staff', password='x', is_staff=True)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='R'), fecha=date(2026, 10, 1),
        )
        # peso_total_kg (Decimal) hace que volumen() devuelva Decimal: antes rompía json.dumps.
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio='Curl con Barra Z', grupo_muscular='Bíceps',
            peso_kg=30, peso_total_kg=30, repeticiones=10, series=3,
        )])
        self.url = reverse('entrenos:detalle_ejercicio_especifico',
                           args=[self.cliente.id, 'Curl con Barra Z'])

    def test_anonimo_va_al_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_otro_usuario_recibe_404(self):
        self.client.force_login(self.otro_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_dueno_va_a_su_evolucion(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, reverse('entrenos:dashboard_evolucion', args=[self.cliente.id]),
            fetch_redirect_response=False,
        )

    def test_staff_tambien_es_redirigido(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 302)
