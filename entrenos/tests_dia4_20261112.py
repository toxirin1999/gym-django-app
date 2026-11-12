"""Día 4 (12-nov-2026): escala 2 kg en laterales/Y-raises, aviso de RPE una vez, rango visible, texto en segundos."""
from django.test import SimpleTestCase
from pathlib import Path

from entrenos.services.maquina_service import salto_fisico


class EscalaPoleaConDiscos(SimpleTestCase):
    def test_laterales_e_y_raises_van_de_2_en_2(self):
        self.assertEqual(salto_fisico('Elevaciones laterales en polea'), 2.0)
        self.assertEqual(salto_fisico('Y-Raises'), 2.0)


class PlantillasYServicios(SimpleTestCase):
    base = Path(__file__).resolve().parent

    def test_template_planweight_y_peso_en_cierre_de_ejercicio(self):
        t = (self.base / 'templates/entrenos/entrenamiento_activo.html').read_text()
        self.assertIn('dataset.planWeight = String(Number((plan.peso)', t)
        self.assertIn('mismo peso', t)

    def test_margen_usa_rpe_rebajado_del_dia(self):
        s = (self.base / 'services/cerebro_carga_service.py').read_text()
        self.assertIn("rpe_dia = min(float(rpe_dia), _bajado)", s)

    def test_aprendizaje_usa_unidad_y_salta_descarga(self):
        s = (self.base / 'services/aprendizaje_decisiones_service.py').read_text()
        self.assertIn('_unidad_ejercicio', s)
        self.assertIn('es_sesion_descarga', s)

    def test_acotar_rango_visible_existe(self):
        s = (self.base / 'views.py').read_text()
        self.assertIn('def _acotar_rango_visible', s)
