from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado, GymDecisionLog


class PortalGuardarEntrenamientoCierreAprendizajeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='portal_causal', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Portal causal'},
        )
        self.client.force_login(self.user)

    def test_post_real_crea_actividad_y_una_decision_causal(self):
        response = self.client.post(
            reverse('clientes:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.pk}),
            {
                'fecha': '2026-08-09',
                'rutina_nombre': 'Push Portal',
                'duracion_minutos': '40',
                'ej1_nombre': 'Press banca',
                'ej1_peso_1': '60',
                'ej1_reps_1': '8',
                'ej1_completado_1': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertTrue(entreno.procesado_gamificacion)
        self.assertEqual(ActividadRealizada.objects.filter(entreno_gym=entreno).count(), 1)
        decisiones = GymDecisionLog.objects.filter(entreno_origen=entreno)
        self.assertEqual(decisiones.count(), 1)
        self.assertIsNone(decisiones.get().resultado)
