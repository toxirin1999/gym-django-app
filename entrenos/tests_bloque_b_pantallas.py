"""Bloque B (13-oct-2026): arreglos de pantalla del recorrido del primer entreno."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos'


class EntrenamientoActivo(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = (BASE / 'entrenamiento_activo.html').read_text(encoding='utf-8')

    def test_aviso_de_series_pendientes_opaco(self):
        self.assertIn('.pendientes-dialog::backdrop{', self.src)
        self.assertIn('class="pendientes-dialog"', self.src)
        self.assertIn('>Lo hago después<', self.src)

    def test_energia_se_pregunta_al_empezar(self):
        self.assertLess(self.src.index('id="energia-inicio"'), self.src.index('<!-- ══ EJERCICIOS ══ -->'))
        self.assertNotIn('¿Cómo llegaste al entreno?', self.src)

    def test_sin_anillos_sin_referencia(self):
        self.assertNotIn('id="ring-series"', self.src)

    def test_pesos_con_coma_en_pantalla(self):
        self.assertIn("'🏆 NUEVO PR — '+fmtKg(peso)+' kg", self.src)
        self.assertIn("Serie '+sn+' — <strong>'+fmtKg(s.peso)+' kg × '", self.src)

    def test_numeros_para_el_js_sin_localizar(self):
        # Con el navegador en español, "15,5" llegaba al JS como 15.
        self.assertIn('{% load l10n %}', self.src)
        self.assertIn('data-pr="{{ ejercicio.pr_peso|default:0|unlocalize }}"', self.src)
        self.assertIn('data-peso-anterior="{{ ejercicio.peso_anterior_kg|default:0|unlocalize }}"', self.src)

    def test_resumen_del_ejercicio_dice_que_series_quedaron_fuera(self):
        self.assertNotIn('recuperaron el rango tras el ajuste', self.src)
        self.assertIn('series en rango`+(fuera.length?`; fuera:', self.src)


class Briefing(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = (BASE / 'briefing_entrenamiento.html').read_text(encoding='utf-8')

    def test_rpe_medio_no_se_repite_en_la_cabecera(self):
        self.assertNotIn('RPE medio 2 sem:', self.src)

    def test_acarreos_sin_tempo(self):
        self.assertIn('{% if ej.tempo and not ej.usa_distancia and not ej.usa_tiempo %}', self.src)

    def test_mantener_sin_tachado(self):
        self.assertIn('<span class="plan-objetivo-lbl">mantiene</span>', self.src)
