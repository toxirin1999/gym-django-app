from django.test import TestCase
from django.urls import reverse


class HistorialDetalladoEmptyStateTests(TestCase):
    def test_sin_entrenamientos_explicita_el_estado_y_lleva_al_panel(self):
        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Todavía no hay entrenamientos registrados')
        self.assertContains(
            response,
            'Cuando completes una sesión aparecerá aquí con sus series y esfuerzo.',
        )
        self.assertContains(response, 'Ver rutina de hoy')
        self.assertContains(
            response,
            reverse('clientes:dashboard_silencioso_preview'),
        )
