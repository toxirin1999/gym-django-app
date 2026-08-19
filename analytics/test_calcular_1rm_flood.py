"""
Regresión: BlockingIOError en producción (/analytics/explicacion-plan/) por
print() flood en CalculadoraEjerciciosTabla.calcular_1rm_estimado_por_ejercicio().

El mapeo directo a movimiento principal solo cubre ~5 levantamientos base
(Remo, Press Banca, Press Militar, Peso Muerto, Sentadilla). Un cliente con
meses de historial tiene decenas/cientos de EjercicioRealizado con nombres
que no matchean ese mapeo — cada uno disparaba un print() individual. Bajo
uWSGI, stdout es un pipe no bloqueante: suficientes prints seguidos llenan
el buffer del pipe y la siguiente escritura lanza BlockingIOError, tirando
la vista entera con un 500.

Fix: los prints por-iteración se convirtieron a logger.debug()/warning()
(no escriben nada salvo que el logger esté en modo DEBUG explícito). Este
test no reproduce el BlockingIOError real (requiere un pipe de uWSGI lleno),
pero congela el contrato: por muchos ejercicios no mapeados que haya, la
función no debe usar print() en absoluto.
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina
from analytics.views import CalculadoraEjerciciosTabla


class TestCalcular1RMSinPrintFlood(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_1rm_flood', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Test1RMFlood', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina Test 1RM Flood')

    def _crear_ejercicio(self, nombre, peso=40.0, reps=10, fecha=None):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha or date(2026, 1, 1),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=nombre, peso_kg=peso,
            series=3, repeticiones=reps, completado=True,
        )

    def test_muchos_ejercicios_no_mapeados_no_usan_print(self):
        # 60 ejercicios con nombres que no están en el mapeo directo — el
        # volumen real que causó el BlockingIOError en producción.
        for i in range(60):
            self._crear_ejercicio(f'Ejercicio Accesorio No Mapeado {i}', fecha=date(2026, 1, 1))
        # Uno sí mapeado, para confirmar que el resultado sigue siendo correcto.
        self._crear_ejercicio('Press Banca con Barra', peso=80.0, reps=5, fecha=date(2026, 1, 2))

        calc = CalculadoraEjerciciosTabla(self.cliente)
        with patch('builtins.print') as mock_print:
            resultado = calc.calcular_1rm_estimado_por_ejercicio()

        mock_print.assert_not_called()
        self.assertIn('Press Banca', resultado)

    def test_ejercicio_con_dato_invalido_no_usa_print(self):
        """La rama except (ValueError/TypeError) tampoco debe usar print()."""
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 1, 1),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press Banca con Barra',
            peso_kg=80.0, series=3, repeticiones=5, completado=True,
        )

        calc = CalculadoraEjerciciosTabla(self.cliente)
        # Forzar la rama except sin depender de datos corruptos reales en BD.
        with patch.object(CalculadoraEjerciciosTabla, 'obtener_ejercicios_tabla',
                           return_value=[{'nombre': 'Press Banca con Barra', 'peso': 'no-es-un-numero', 'repeticiones': 5}]):
            with patch('builtins.print') as mock_print:
                resultado = calc.calcular_1rm_estimado_por_ejercicio()

        mock_print.assert_not_called()
        self.assertEqual(resultado, {})
