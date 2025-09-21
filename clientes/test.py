# tests.py - Tests unitarios para validar la implementación
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Cliente


class TestClienteHelmsFields(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.cliente = Cliente.objects.create(
            user=self.user,
            nombre='Cliente Test',
            experiencia_años=2.5,
            objetivo_principal='hipertrofia'
        )

    def test_valores_por_defecto(self):
        """Verificar que los valores por defecto se asignan correctamente"""
        self.assertEqual(self.cliente.dias_disponibles, 4)
        self.assertEqual(self.cliente.tiempo_por_sesion, 90)
        self.assertEqual(self.cliente.nivel_estres, 5)
        self.assertEqual(self.cliente.calidad_sueño, 7)
        self.assertEqual(self.cliente.nivel_energia, 7)
        self.assertTrue(self.cliente.flexibilidad_horario)

    def test_nivel_experiencia(self):
        """Verificar cálculo correcto del nivel de experiencia"""
        self.assertEqual(self.cliente.get_nivel_experiencia(), 'intermedio')

        # Cambiar experiencia y verificar
        self.cliente.experiencia_años = 0.5
        self.assertEqual(self.cliente.get_nivel_experiencia(), 'principiante')

        self.cliente.experiencia_años = 5
        self.assertEqual(self.cliente.get_nivel_experiencia(), 'avanzado')

    def test_factor_recuperacion(self):
        """Verificar cálculo del factor de recuperación"""
        # Estado óptimo
        self.cliente.nivel_estres = 3
        self.cliente.calidad_sueño = 9
        self.cliente.nivel_energia = 8
        factor = self.cliente.get_factor_recuperacion()
        self.assertGreater(factor, 0.8)  # Debería ser alto

        # Estado de fatiga
        self.cliente.nivel_estres = 9
        self.cliente.calidad_sueño = 3
        self.cliente.nivel_energia = 2
        factor = self.cliente.get_factor_recuperacion()
        self.assertLess(factor, 0.5)  # Debería ser bajo

    def test_necesita_descarga(self):
        """Verificar detección de necesidad de descarga"""
        # Estado que requiere descarga
        self.cliente.nivel_estres = 9
        self.cliente.calidad_sueño = 3
        self.cliente.nivel_energia = 2
        self.assertTrue(self.cliente.necesita_descarga())

        # Estado normal
        self.cliente.nivel_estres = 5
        self.cliente.calidad_sueño = 7
        self.cliente.nivel_energia = 7
        self.assertFalse(self.cliente.necesita_descarga())

    def test_ejercicios_permitidos(self):
        """Verificar filtrado de ejercicios"""
        self.cliente.ejercicios_evitar = ['sentadilla', 'peso_muerto']
        ejercicios = self.cliente.get_ejercicios_permitidos()
        self.assertNotIn('sentadilla', ejercicios)
        self.assertNotIn('peso_muerto', ejercicios)
        self.assertIn('press_banca', ejercicios)

# Ejecutar tests con:
# python manage.py test tu_app.tests.TestClienteHelmsFields
