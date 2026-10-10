from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class LegacyLiftinExerciseScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('legacy_owner', password='x')
        self.other = User.objects.create_user('legacy_other', password='x')
        self.staff = User.objects.create_user('legacy_staff', password='x', is_staff=True)
        self.rutina = Rutina.objects.create(nombre='Rutina de importación')
        with patch('entrenos.signals.parsear_ejercicios', return_value=[], create=True):
            self.mine = EntrenoRealizado.objects.create(
                cliente=self.user.cliente_perfil,
                rutina=self.rutina,
                fecha=date.today(),
                notas_liftin='✓ Press banca: 60, 3x8',
            )
            self.theirs = EntrenoRealizado.objects.create(
                cliente=self.other.cliente_perfil,
                rutina=self.rutina,
                fecha=date.today(),
                notas_liftin='✓ Remo: 50, 3x10',
            )

    def test_table_requires_login_and_hides_other_clients_liftin_history(self):
        url = reverse('entrenos:tabla_ejercicios')
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(url)

        self.assertContains(response, 'Press Banca')
        self.assertNotContains(response, 'Remo')

    def test_staff_keeps_global_legacy_history_access(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('entrenos:tabla_ejercicios'))

        self.assertContains(response, 'Press Banca')
        self.assertContains(response, 'Remo')

    def test_exercise_detail_hides_other_clients_records(self):
        url = reverse('entrenos:detalle_ejercicio', args=['Press banca'])
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(url)

        self.assertContains(response, '60')
        self.assertNotContains(response, 'Remo')
