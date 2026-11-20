"""21-nov-2026 (N3): cada cifra de esfuerzo dice que mide y de que periodo.

Dia 4 (20/11): 7,4 (media por serie de la sesion), 7,2 y 7,3 (media por ejercicio, hoy y 4 semanas
anteriores) y 7,0 (media por ejercicio, 2 semanas) convivian sin explicar la diferencia.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR)


def _leer(ruta):
    return (BASE / ruta).read_text(encoding='utf-8')


class EsfuerzoRotuladoTests(SimpleTestCase):
    def test_resumen_de_la_sesion_dice_por_serie(self):
        self.assertIn('RPE medio por serie', _leer('entrenos/templates/entrenos/entrenamiento_activo.html'))
        self.assertIn('RPE medio por serie', _leer('entrenos/templates/entrenos/post_entreno_resumen.html'))
        self.assertIn('RPE medio por serie · sesión', _leer('clientes/templates/clientes/plan_decisiones.html'))

    def test_preparacion_dice_por_ejercicio_y_periodo(self):
        self.assertIn('Esfuerzo medio por ejercicio · 2 semanas',
                      _leer('entrenos/templates/entrenos/briefing_entrenamiento.html'))

    def test_balance_semanal_dice_semana(self):
        self.assertIn('RPE medio · semana', _leer('clientes/templates/clientes/plan_decisiones.html'))

    def test_estado_de_carga_dice_por_ejercicio_y_ventanas(self):
        src = _leer('entrenos/services/estado_carga_service.py')
        self.assertIn('esfuerzo medio por ejercicio va en', src)
        self.assertIn('las 2 anteriores', src)

    def test_panel_del_cuerpo_dice_por_sesion(self):
        self.assertIn('esfuerzo medio por sesión', _leer('entrenos/services/panel_cuerpo_service.py'))
