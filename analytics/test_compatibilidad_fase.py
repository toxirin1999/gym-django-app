"""
Phase Gym Peso 2 — Tests unitarios del módulo central de compatibilidad de fase.

resolver_peso_objetivo() es la única función que decide si el peso de hoy
debe recalcularse desde e1RM (bucket incompatible o descarga) o si el
caller debe seguir su propio camino de incremento fijo (bucket compatible).
"""

from django.test import SimpleTestCase

from analytics.planificador_helms.calculo.compatibilidad_fase import (
    resolver_peso_objetivo, son_rangos_compatibles,
)


class TestSonRangosCompatibles(SimpleTestCase):

    def test_sin_reps_anteriores_no_es_compatible(self):
        self.assertFalse(son_rangos_compatibles(None, '8-12'))

    def test_potencia_3_reps_vs_descarga_10_reps_incompatible(self):
        self.assertFalse(son_rangos_compatibles(3, '10-15'))

    def test_potencia_3_reps_vs_fuerza_5_reps_compatible(self):
        self.assertTrue(son_rangos_compatibles(3, '4-6'))

    def test_hipertrofia_12_reps_vs_potencia_3_reps_incompatible(self):
        self.assertFalse(son_rangos_compatibles(12, '2-4'))

    def test_hipertrofia_10_reps_vs_hipertrofia_metabolica_12_reps_compatible(self):
        self.assertTrue(son_rangos_compatibles(10, '12-15'))


class TestResolverPesoObjetivo(SimpleTestCase):

    def test_caso_a_sin_historial_no_aplica(self):
        r = resolver_peso_objetivo(
            peso_anterior=None, reps_anteriores=None, rpe_anterior=None,
            rep_range_hoy='8-12', rpe_objetivo_hoy=8,
        )
        self.assertFalse(r['aplica'])
        self.assertIsNone(r['peso'])

    def test_caso_b_bucket_compatible_no_aplica(self):
        """Fuerza 5 reps RPE8 → hoy potencia 3-5 reps: misma familia, no recalcula."""
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8,
            rep_range_hoy='3-5', rpe_objetivo_hoy=8,
        )
        self.assertFalse(r['aplica'])

    def test_caso_c_bucket_incompatible_recalcula(self):
        """107.5kg x 3 reps RPE8 (potencia) → hoy 10-15 reps (descarga/hipertrofia)."""
        r = resolver_peso_objetivo(
            peso_anterior=107.5, reps_anteriores=3, rpe_anterior=8,
            rep_range_hoy='10-15', rpe_objetivo_hoy=6, es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_descarga')
        # Debe ser sustancialmente menor que peso_anterior - incremento_fijo (105kg)
        self.assertLess(r['peso'], 90.0)
        self.assertGreater(r['peso'], 0)

    def test_caso_d_descarga_reduce_peso_incluso_con_bucket_compatible(self):
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=12, rpe_anterior=8,
            rep_range_hoy='10-15', rpe_objetivo_hoy=6, es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_descarga')
        self.assertLess(r['peso'], 100.0)
