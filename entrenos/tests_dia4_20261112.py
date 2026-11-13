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


# ── Panel «Cómo responde tu cuerpo» (13-nov-2026) ────────────────────────────
from django.urls import reverse

from entrenos.tests_estado_carga_20261025 import HOY, Base


class PanelCuerpoMejoras(Base):
    HOY = HOY

    def setUp(self):
        super().setUp()
        for i in range(1, 9):
            self.reloj(i, hrv=70, fc=57, sueno=7.5)
        self.reloj(0, hrv=42, fc=52, sueno=6.7)

    def test_sueno_con_decimales_y_ejes(self):
        from entrenos.services.panel_cuerpo_service import sueno
        s = sueno(self.cliente, self.HOY)
        self.assertEqual(s['hoy_valor'], '6,7')
        self.assertIn('eje_max', s)
        self.assertIn('eje_min', s)

    def test_lectura_cruzada_hrv_baja_con_pulso_bajo(self):
        from entrenos.services.panel_cuerpo_service import lectura_cruzada, pulso, variabilidad
        txt = lectura_cruzada(variabilidad(self.cliente, self.HOY), pulso(self.cliente, self.HOY))
        self.assertIn('se compensan', txt)

    def test_lectura_cruzada_dos_senales(self):
        from entrenos.services.panel_cuerpo_service import lectura_cruzada
        txt = lectura_cruzada({'hoy_valor': 40, 'media': 70}, {'hoy_valor': 64, 'media': 57})
        self.assertIn('cansancio', txt)
        self.assertIsNone(lectura_cruzada({'hoy_valor': 70, 'media': 70}, {'hoy_valor': 57, 'media': 57}))

    def test_aviso_hoy_solo_si_amaneces_por_debajo_y_el_titular_es_tranquilo(self):
        from entrenos.services.panel_cuerpo_service import aviso_hoy
        dias = [{'nivel': 'rojo', 'nombre': 'Por debajo', 'detalle': 'Variabilidad baja.'}]
        self.assertIn('Esta mañana amaneces por debajo', aviso_hoy({'respuesta': 'vas_bien'}, dias))
        self.assertIsNone(aviso_hoy({'respuesta': 'descansa'}, dias))
        self.assertIsNone(aviso_hoy({'respuesta': 'vas_bien'}, [{'nivel': 'normal', 'nombre': 'Normal'}]))

    def test_dias_con_detalle_y_hoy(self):
        from entrenos.services.estado_carga_service import estado_carga
        from entrenos.services.panel_cuerpo_service import dias_recientes
        dias = dias_recientes(estado_carga(self.cliente, self.HOY), self.cliente)
        self.assertTrue(dias[-1]['hoy'])
        self.assertTrue(dias[-1]['detalle'])

    def test_pagina_tiene_sueno_pestanas_y_pie_corregido(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:cuerpo'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="tab-sueno"', html)
        self.assertIn('data-tab="pulso"', html)
        self.assertIn('Toca un día para ver qué lo marcó', html)
        self.assertNotIn('no cambia tu plan', html)
        self.assertIn('Ver qué significa para el entreno de hoy', html)

    def test_todavia_no_explica_carga_baja_y_es_pendiente(self):
        from entrenos.services.panel_cuerpo_service import tres_preguntas
        est = {'respuesta': 'vas_bien', 'carga': {'ratio': 0.63}, 'malos_5': 1, 'dias_5': 5, 'buenos_14': 12,
               'dias_14': 14, 'esfuerzo': {'subiendo': False}, 'molestias': []}
        mas = tres_preguntas(est)[2]
        self.assertEqual(mas['tono'], 'pendiente')
        self.assertIn('37 % por debajo', mas['porque'])
