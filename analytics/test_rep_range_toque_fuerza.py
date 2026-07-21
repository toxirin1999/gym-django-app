# analytics/test_rep_range_toque_fuerza.py
"""
Bugfix: REP_RANGE_TOQUE (config.py) no cubría '4-6', el rep_range del
bloque de periodización "Fuerza — Base". Verificado en producción real
(cliente david, semana 9 del plan): cuádriceps y espalda alcanzan freq=2
en fase fuerza y el ejercicio SÍ varía correctamente entre toque 1 y 2
(distinto nombre) y el RPE SÍ baja (-1), pero el rep_range se quedaba
en '4-6' en ambos toques — el escalón hacia más repeticiones no se
aplicaba para grupos grandes en esta fase (los grupos pequeños ya
interceptan '4-6'→'8-12' antes, vía REP_RANGE_AJUSTE_PEQUENOS, así que
a ellos no les afectaba).

Fix: añadidas las entradas '4-6' a REP_RANGE_TOQUE[2] y [3], siguiendo
la misma escalera de un peldaño (toque 2) y dos peldaños (toque 3) que
ya usan el resto de rangos.
"""

from django.test import TestCase

from analytics.planificador_helms.config import REP_RANGE_TOQUE
from analytics.planificador_helms.ejercicios.variacion import derivar_rep_rpe_toque


class TestRepRangeToqueCubreFuerza(TestCase):
    def test_toque_1_identidad(self):
        self.assertEqual(derivar_rep_rpe_toque('4-6', 7, 1), ('4-6', 7))

    def test_toque_2_sube_un_peldano(self):
        rep_range, rpe = derivar_rep_rpe_toque('4-6', 7, 2)
        self.assertEqual(rep_range, '6-8')
        self.assertEqual(rpe, 6)

    def test_toque_3_sube_dos_peldanos(self):
        rep_range, rpe = derivar_rep_rpe_toque('4-6', 7, 3)
        self.assertEqual(rep_range, '8-10')

    def test_clave_presente_en_tabla_toque_2_y_3(self):
        self.assertIn('4-6', REP_RANGE_TOQUE[2])
        self.assertIn('4-6', REP_RANGE_TOQUE[3])
        self.assertEqual(REP_RANGE_TOQUE[2]['4-6'], '6-8')
        self.assertEqual(REP_RANGE_TOQUE[3]['4-6'], '8-10')
