from django.test import TestCase
from django.urls import reverse

from .models import EstiramientoPlan


class PanelEstiramientosTests(TestCase):
    def test_estado_vacio_explica_el_limite_y_ofrece_salida_al_panel(self):
        """Sin planes activos, el atleta no queda atrapado en una pantalla muerta."""
        EstiramientoPlan.objects.update(activo=False)
        response = self.client.get(reverse('estiramientos:panel'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aún no hay sesiones de recuperación disponibles')
        self.assertContains(response, 'Volver al panel')
        self.assertContains(response, reverse('clientes:dashboard_silencioso_preview'))
