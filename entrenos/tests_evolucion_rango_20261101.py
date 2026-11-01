"""01-nov-2026 · Evolución: se compara el mismo tramo de reps."""

from django.test import TestCase

from entrenos.services.evolucion_muscular_service import calcular_evolucion_por_grupo, comparar_ejercicios, tramo_reps
from entrenos.tests_evolucion_muscular import _DatosEntrenoMixin


class RangoDeReps(_DatosEntrenoMixin, TestCase):
    def test_tramos(self):
        self.assertEqual([tramo_reps(r) for r in (6, 8, 9, 14, 15, 20)],
                         ['fuerza', 'fuerza', 'medio', 'medio', 'alto', 'alto'])

    def test_cambio_de_rango_no_es_retroceso(self):
        # Antes encogimientos pesados a 8; ahora 110 × 16 en un bloque de 15-20.
        self._ej(120, 'Encogimientos con Barra', 140, 8, grupo='Trapecio')
        self._ej(10, 'Encogimientos con Barra', 110, 16, grupo='Trapecio')
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertIsNone(e['pct'])
        self.assertTrue(e['cambio_rango'])
        g = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'trapecios')
        self.assertEqual(g['estado'], 'sin_datos')
        self.assertIn('Cambiaste de rango de reps', g['lectura'])

    def test_mismo_tramo_se_compara(self):
        self._ej(120, 'Encogimientos con Barra', 140, 8, grupo='Trapecio')
        self._ej(110, 'Encogimientos con Barra', 100, 15, grupo='Trapecio')  # mismo tramo que hoy
        self._ej(10, 'Encogimientos con Barra', 110, 16, grupo='Trapecio')
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertEqual((e['antes']['peso_kg'], e['ahora']['peso_kg']), (100.0, 110.0))
        self.assertEqual(e['pct'], 10.0)
