"""24-oct-2026 · Un solo camino para abrir el entreno."""

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento


class EntradaDirecta(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='uncamino', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'U'})
        self.client.login(username='uncamino', password='x')
        self.url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])

    def _decision(self):
        return GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=timezone.localdate(), version=1,
            decision_id='gym-hoy-abc', origen=GymDecisionVersion.ORIGEN_MOTOR, vigente=True,
            fingerprint='abc', base_fingerprint='abc', postura='empujar',
            snapshot={'entrenamiento': {'rutina_nombre': 'Dia 4 - Hipertrofia', 'ejercicios': []}},
        )

    def test_con_decision_de_hoy_va_a_ella(self):
        self._decision()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('decision_id=gym-hoy-abc', r['Location'])
        self.assertIn('rutina_nombre=Dia+4', r['Location'])

    def test_sin_decision_lleva_a_ahora(self):
        r = self.client.get(self.url)
        self.assertEqual((r.status_code, r['Location']), (302, '/'))
        self.assertFalse(GymDecisionVersion.objects.exists())  # no calcula ni guarda nada

    def test_con_plan_transportado_no_redirige_a_ahora(self):
        r = self.client.get(self.url, {'fecha': timezone.localdate().isoformat()})
        self.assertNotEqual(r.get('Location'), '/')


class CalentamientoLigero(SimpleTestCase):
    def test_curl_inclinado_10_kg(self):
        self.assertIsNone(get_aproximaciones_calentamiento(10, incremento=5))

    def test_laterales_16_kg_se_mantiene(self):
        self.assertEqual(get_aproximaciones_calentamiento(16, incremento=5),
                         {'peso1': 5.0, 'peso2': 10.0, 'peso3': 15.0})
