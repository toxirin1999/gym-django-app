"""
Phase Gym Peso 2.1 — Actualización prudente del RM único (one_rm_data).

Bug cerrado: estimar_1rm_con_rpe (Epley+RIR) extrapola mal cuando el RPE
objetivo es bajo y las reps son altas (RIR grande -> reps teóricas al fallo
infladas -> e1RM disparado). Esto significa que incluso obedecer
EXACTAMENTE una descarga prescrita disparaba el 1RM histórico del cliente.

Regla madre: en descarga, hacer el peso prescrito con el RPE objetivo no
debería disparar el 1RM histórico. Debería confirmar que la descarga está
bien calibrada, no demostrar una mejora de fuerza.

decidir_actualizacion_rm() es la única función que decide si una serie
puede subir cliente.one_rm_data, y con qué tope.
"""

from django.test import SimpleTestCase

from analytics.gating_rm import decidir_actualizacion_rm, FACTOR_SUAVIZADO_RM


class TestDecidirActualizacionRM(SimpleTestCase):

    def test_descarga_no_actualiza_aunque_rpe_coincida_exacto(self):
        """RM antes 92.5. Descarga prescrita y real idénticas (72.5kg x10 RPE6)."""
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=72.5, reps=10, rpe_real=6.0,
            es_descarga=True,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_no_actualizado_descarga')
        self.assertEqual(r['rm_resultante'], 92.5)

    def test_descarga_no_actualiza_aunque_real_sea_mas_pesado(self):
        """Descarga real 80kg x10 RPE6 (por encima de lo prescrito)."""
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=80.0, reps=10, rpe_real=6.0,
            es_descarga=True,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_no_actualizado_descarga')
        self.assertEqual(r['rm_resultante'], 92.5)

    def test_descarga_no_actualiza_con_rpe_alto(self):
        """Descarga real 88kg x10 RPE9 (muy por encima, RPE alto)."""
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=88.0, reps=10, rpe_real=9.0,
            es_descarga=True,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_no_actualizado_descarga')
        self.assertEqual(r['rm_resultante'], 92.5)

    def test_no_descarga_actualiza_con_tope_suavizado_no_directo(self):
        """e1RM observado muy superior al actual: sube, pero topado, no al e1RM crudo."""
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=100.0, reps=5, rpe_real=8.0,
            es_descarga=False,
        )
        self.assertTrue(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_actualizado_suavizado')
        tope_esperado = round(92.5 * FACTOR_SUAVIZADO_RM, 2)
        self.assertEqual(r['rm_resultante'], tope_esperado)
        self.assertLess(r['rm_resultante'], 92.5 * 1.10)

    def test_no_descarga_sin_rpe_real_no_actualiza(self):
        """Sin RPE real registrado: confianza baja, no se toca one_rm_data."""
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=95.0, reps=5, rpe_real=None,
            es_descarga=False,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_sin_rpe_confianza_baja')
        self.assertEqual(r['rm_resultante'], 92.5)

    def test_descarga_con_rpe_none_sigue_sin_actualizar(self):
        r = decidir_actualizacion_rm(
            rm_actual=92.5, peso=72.5, reps=10, rpe_real=None,
            es_descarga=True,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['motivo'], 'rm_no_actualizado_descarga')

    def test_e1rm_observado_por_debajo_del_actual_no_actualiza(self):
        """Si el e1RM de la serie es menor o igual al RM actual, no hay nada que subir."""
        r = decidir_actualizacion_rm(
            rm_actual=120.0, peso=80.0, reps=5, rpe_real=8.0,
            es_descarga=False,
        )
        self.assertFalse(r['actualiza'])
        self.assertEqual(r['rm_resultante'], 120.0)

    def test_sin_rm_actual_previo_primera_carga_usa_tope_relativo_a_e1rm(self):
        """Sin historial (rm_actual=0): primera carga. Se acepta el e1RM pero sigue marcado."""
        r = decidir_actualizacion_rm(
            rm_actual=0, peso=60.0, reps=8, rpe_real=8.0,
            es_descarga=False,
        )
        self.assertTrue(r['actualiza'])
        self.assertGreater(r['rm_resultante'], 0)
