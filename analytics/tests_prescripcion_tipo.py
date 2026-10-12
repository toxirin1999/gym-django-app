"""Prescripción por tipo de ejercicio (decisiones del 12-oct-2026)."""

from django.test import SimpleTestCase

from analytics.planificador_helms.calculo.prescripcion_tipo import (
    FARMER_KG_POR_MANO, carga_por_tipo, rango_por_tipo, rpe_por_tipo, unidad_por_tipo,
)


class RpePorTipoTests(SimpleTestCase):
    def test_compuesto_se_queda_entre_7_y_8(self):
        self.assertEqual(rpe_por_tipo(9, 'compuesto_principal'), 8)
        self.assertEqual(rpe_por_tipo(8, 'compuesto_secundario'), 8)
        self.assertEqual(rpe_por_tipo(6, 'compuesto_principal'), 7)

    def test_aislamiento_va_entre_8_y_9(self):
        self.assertEqual(rpe_por_tipo(8, 'aislamiento'), 9)
        self.assertEqual(rpe_por_tipo(7, 'aislamiento'), 8)
        self.assertEqual(rpe_por_tipo(6, 'aislamiento'), 8)
        self.assertEqual(rpe_por_tipo(9, 'aislamiento'), 9)

    def test_descarga_no_se_toca(self):
        self.assertEqual(rpe_por_tipo(6, 'aislamiento', es_descarga=True), 6)
        self.assertEqual(rpe_por_tipo(6, 'compuesto_principal', es_descarga=True), 6)


class UnidadRealTests(SimpleTestCase):
    def test_tiempo_en_segundos_sin_carga(self):
        self.assertEqual(rango_por_tipo('progresion_tiempo', '15-20'), '20-40')
        self.assertEqual(unidad_por_tipo('progresion_tiempo'), 's')
        self.assertEqual(carga_por_tipo('progresion_tiempo', 'Aguante en Barra (Dead Hang)', 32.5), 0.0)

    def test_farmer_en_metros_con_su_carga_por_mano(self):
        self.assertEqual(rango_por_tipo('progresion_distancia', '15-20'), '20-30')
        self.assertEqual(unidad_por_tipo('progresion_distancia'), 'm')
        self.assertEqual(
            carga_por_tipo('progresion_distancia', 'Farmer Walk (Paseo del Granjero)', 2.5),
            FARMER_KG_POR_MANO,
        )

    def test_otra_distancia_usa_historial_o_nada(self):
        self.assertEqual(carga_por_tipo('progresion_distancia', 'Trineo', 2.5, 40), 40.0)
        self.assertEqual(carga_por_tipo('progresion_distancia', 'Trineo', 2.5, None), 0.0)

    def test_progresion_por_reps_sin_carga(self):
        self.assertEqual(rango_por_tipo('progresion_reps', '15-20'), '15-20')
        self.assertEqual(unidad_por_tipo('progresion_reps'), 'reps')
        self.assertEqual(carga_por_tipo('progresion_reps', 'Sissy Squat', 27.5), 0.0)

    def test_kg_y_lastre_conservan_el_peso_calculado(self):
        self.assertEqual(carga_por_tipo('peso_reps', 'Prensa', 145), 145)
        self.assertEqual(carga_por_tipo('peso_corporal_lastre', 'Dips (Fondos en Pecho)', 77.5), 77.5)

    def test_descarga_acorta_los_rangos(self):
        self.assertEqual(rango_por_tipo('progresion_tiempo', '10-15', es_descarga=True), '15-25')
        self.assertEqual(rango_por_tipo('progresion_distancia', '10-15', es_descarga=True), '15-20')
