"""Prescripción por tipo de ejercicio (decisiones del 12-oct-2026)."""

from django.test import SimpleTestCase

from analytics.planificador_helms.calculo.prescripcion_tipo import (
    FARMER_KG_POR_MANO, carga_por_tipo, es_multiarticular, rango_por_tipo, rpe_por_tipo,
    unidad_por_tipo,
)


class RpePorTipoTests(SimpleTestCase):
    def test_multiarticular_se_queda_entre_7_y_8(self):
        self.assertEqual(rpe_por_tipo(9, 'rodilla', 'Sentadilla Hack'), 8)
        self.assertEqual(rpe_por_tipo(8, 'empuje_horizontal', 'Convergent Machine Press'), 8)
        self.assertEqual(rpe_por_tipo(6, 'traccion_vertical', 'Jalón al Pecho'), 7)

    def test_aislamiento_va_entre_8_y_9(self):
        self.assertEqual(rpe_por_tipo(8, 'flexion_codo', 'Curl con Barra Z'), 9)
        self.assertEqual(rpe_por_tipo(7, 'aislamiento', 'Abducción de Cadera en Máquina'), 8)
        self.assertEqual(rpe_por_tipo(6, 'gemelos', 'Elevación de Gemelos de Pie'), 8)
        self.assertEqual(rpe_por_tipo(9, 'extension_codo', 'Press Francés con Barra Z'), 9)

    def test_categoria_principal_de_un_grupo_pequeno_no_es_multiarticular(self):
        # En la base de datos "Curl con Barra Z" es el compuesto_principal de bíceps.
        self.assertFalse(es_multiarticular('flexion_codo', 'Curl con Barra Z'))

    def test_excepciones_por_nombre(self):
        self.assertFalse(es_multiarticular('traccion_vertical', 'Jalon brazos rectos'))
        self.assertFalse(es_multiarticular('rodilla', 'Sissy Squat'))
        self.assertTrue(es_multiarticular('extension_codo', 'Press Cerrado en Banca'))
        self.assertTrue(es_multiarticular('extension_codo', 'Fondos en Paralelas (con lastre)'))

    def test_saltos_y_agarre_no_van_al_fallo(self):
        self.assertEqual(rpe_por_tipo(8, 'pleometrico', 'Salto al Cajón (Box Jump)'), 8)
        self.assertEqual(rpe_por_tipo(8, 'agarre', 'Farmer Walk (Paseo del Granjero)'), 8)

    def test_descarga_no_se_toca(self):
        self.assertEqual(rpe_por_tipo(6, 'aislamiento', es_descarga=True), 6)
        self.assertEqual(rpe_por_tipo(6, 'rodilla', es_descarga=True), 6)


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
