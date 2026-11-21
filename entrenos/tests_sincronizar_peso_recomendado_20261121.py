from django.test import SimpleTestCase

from entrenos.services.ultima_sesion_service import peso_contractual, sincronizar_peso_recomendado


class SincronizarPesoRecomendadoTests(SimpleTestCase):
    def test_dips_decision_fija_100_y_planificador_proponia_102_5(self):
        ej = {'peso_kg': 100, 'peso_recomendado_kg': 102.5, 'progresion_pospuesta': True}
        self.assertTrue(sincronizar_peso_recomendado(ej))
        self.assertEqual(ej['peso_recomendado_kg'], 100.0)
        self.assertEqual(peso_contractual(ej), 100.0)

    def test_sin_decision_no_toca_el_peso_recomendado(self):
        ej = {'peso_kg': 100, 'peso_recomendado_kg': 102.5}
        self.assertFalse(sincronizar_peso_recomendado(ej))
        self.assertEqual(ej['peso_recomendado_kg'], 102.5)

    def test_progresion_aplicada_alinea(self):
        ej = {'peso_kg': 70, 'peso_recomendado_kg': 65, 'progresion_aplicada': True}
        self.assertTrue(sincronizar_peso_recomendado(ej))
        self.assertEqual(ej['peso_recomendado_kg'], 70.0)

    def test_sin_clave_o_peso_cero_no_hace_nada(self):
        self.assertFalse(sincronizar_peso_recomendado({'peso_kg': 50}))
        self.assertFalse(sincronizar_peso_recomendado({'peso_kg': 0, 'peso_recomendado_kg': 10, 'progresion_aplicada': True}))

    def test_conserva_la_propuesta_original_para_trazabilidad(self):
        ej = {'peso_kg': 100, 'peso_recomendado_kg': 102.5, 'progresion_pospuesta': True}
        sincronizar_peso_recomendado(ej)
        self.assertEqual(ej['peso_propuesto_planificador_kg'], 102.5)
        sincronizar_peso_recomendado(ej)
        self.assertEqual(ej['peso_propuesto_planificador_kg'], 102.5)

    def test_briefing_calentamiento_y_activo_parten_de_100(self):
        from entrenos.views import get_aproximaciones_calentamiento
        ej = {'peso_kg': 100, 'peso_recomendado_kg': 102.5, 'progresion_pospuesta': True, 'incremento_kg': 2.5}
        sincronizar_peso_recomendado(ej)
        briefing = float(ej['peso_recomendado_kg'] or ej['peso_kg'])
        activo = peso_contractual(ej)
        self.assertEqual((briefing, activo), (100.0, 100.0))
        self.assertEqual(
            get_aproximaciones_calentamiento(briefing, True, incremento=2.5),
            get_aproximaciones_calentamiento(activo, True, incremento=2.5),
        )
        self.assertNotEqual(get_aproximaciones_calentamiento(100.0, True, incremento=2.5),
                            get_aproximaciones_calentamiento(102.5, True, incremento=2.5))
