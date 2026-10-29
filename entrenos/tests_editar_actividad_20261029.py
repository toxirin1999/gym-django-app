"""29-oct-2026 · Editar una actividad importada (fútbol apuntado como pesas)."""

from datetime import date

from django.contrib.auth.models import User
from django.test import Client as DjangoClient, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada


class EditarActividad(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='edit_act', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'Edit', 'dias_disponibles': 4})
        self.act = ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', titulo='Entrenamiento con pesas vespertino',
            fecha=date(2026, 10, 28), duracion_minutos=79, rpe_medio=8.0, fuente='strava',
        )
        self.http = DjangoClient()
        self.http.force_login(self.user)

    def test_cambiar_a_futbol_guarda(self):
        url = reverse('entrenos:editar_actividad_libre', args=[self.cliente.id, self.act.id])
        r = self.http.post(url, {
            'tipo': 'futbol', 'titulo': 'Fútbol', 'fecha': '2026-10-28', 'hora_inicio': '',
            'duracion_minutos': '79', 'distancia_metros': '', 'rpe_medio': '8.0', 'calorias': '', 'notas': '',
        })
        self.assertEqual(r.status_code, 302)
        self.act.refresh_from_db()
        self.assertEqual(self.act.tipo, 'futbol')
        self.assertEqual(self.act.duracion_minutos, 79)
        self.assertEqual(self.act.carga_ua, 632.0)

    def test_rpe_con_coma(self):
        url = reverse('entrenos:editar_actividad_libre', args=[self.cliente.id, self.act.id])
        self.http.post(url, {'tipo': 'futbol', 'titulo': 'F', 'fecha': '2026-10-28',
                             'duracion_minutos': '60', 'rpe_medio': '7,5'})
        self.act.refresh_from_db()
        self.assertEqual(self.act.rpe_medio, 7.5)
        self.assertEqual(self.act.carga_ua, 450.0)
