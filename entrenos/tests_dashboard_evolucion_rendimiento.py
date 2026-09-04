from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from rutinas.models import Rutina


class DashboardRendimientoGlobalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rendimiento_global', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Rendimiento', 'dias_disponibles': 5},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_rendimiento_global')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:dashboard_evolucion', args=[self.cliente.id])

    def _entreno(self, dias, peso, rpe):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=dias),
            duracion_minutos=50,
            volumen_total_kg=peso * 24,
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Press banca',
            peso_kg=peso,
            series=3,
            repeticiones=8,
            rpe=rpe,
            completado=True,
            fuente_datos='manual',
        )

    def test_expone_lectura_observada_y_comparacion(self):
        self._entreno(24, 60, 8)
        self._entreno(20, 62.5, 8)
        self._entreno(9, 65, 8)
        self._entreno(3, 67.5, 7)

        response = self.client.get(self.url, {'rango': '30d'})

        self.assertEqual(response.status_code, 200)
        lectura = response.context['rendimiento_global']
        self.assertEqual(lectura['sesiones_observadas'], 4)
        self.assertEqual(lectura['progresion']['estado'], 'mejora')
        self.assertEqual(lectura['progresion']['ejercicio'], 'Press banca')
        self.assertGreater(lectura['progresion']['cambio_pct'], 0)
        self.assertEqual(lectura['esfuerzo']['rpe_reciente'], 7.5)

    def test_renderiza_jerarquia_y_enlace_a_trayectoria(self):
        self._entreno(3, 60, 7)
        html = self.client.get(self.url).content.decode()

        self.assertIn('Rendimiento global', html)
        self.assertIn('Progresión observada', html)
        self.assertIn('Esfuerzo sostenible', html)
        self.assertIn('Constancia', html)
        self.assertIn('Trayectoria del plan', html)
        self.assertNotIn('Nivel y recompensas', html)

    def test_estado_vacio_no_inventa_tendencias(self):
        response = self.client.get(self.url)
        lectura = response.context['rendimiento_global']

        self.assertEqual(lectura['sesiones_observadas'], 0)
        self.assertEqual(lectura['progresion']['estado'], 'sin_evidencia')
        self.assertContains(response, 'Aún no hay sesiones suficientes')

