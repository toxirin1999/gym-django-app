"""5-nov-2026 · Repaso de paneles (Plan, Rutina, Ahora, Cuerpo, Memoria)."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from entrenos.services.cambios_semana_service import frases_cambio

CLIENTES = Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes'


def _src(nombre):
    return (CLIENTES / nombre).read_text(encoding='utf-8')


class QueCambiaEstaSemana(SimpleTestCase):
    def test_la_mitad_solo_si_es_la_mitad(self):
        lineas = frases_cambio((40, 6.0), (80, 7.8), descarga=True)
        self.assertEqual(lineas[0], 'Series: la mitad, 40 frente a 80 la semana pasada.')
        self.assertEqual(lineas[1], 'Esfuerzo: RPE 6 de media (la semana pasada, 7,8).')
        self.assertIn('10 % menos', lineas[2])
        lineas = frases_cambio((50, 6.0), (80, 7.8), descarga=True)
        self.assertEqual(lineas[0], 'Series: 50 frente a 80 la semana pasada (-38 %).')

    def test_semana_normal(self):
        lineas = frases_cambio((80, 7.8), (80, 7.8), descarga=False)
        self.assertEqual(lineas[0], 'Series: las mismas que la semana pasada (80).')
        self.assertEqual(lineas[1], 'Esfuerzo: el mismo, RPE 7,8 de media.')

    def test_plantilla_plan(self):
        src = _src('trayectoria_plan.html')
        self.assertIn('Qué cambia esta semana', src)
        self.assertIn('Series de esta semana de descarga', src)
        self.assertIn('· referencia {{ f.plan|floatformat:"-1" }}', src)
        self.assertIn('{% if trayectoria.periodizacion.rpe_fin != trayectoria.periodizacion.rpe_inicio %}', src)


class OtrosPaneles(SimpleTestCase):
    def test_isquios_en_pausa_destaca_la_pausa(self):
        self.assertIn('<strong>En pausa hasta el lunes</strong>', _src('dashboard_silencioso_preview.html'))

    def test_cuerpo_mas_contraste(self):
        src = _src('cuerpo.html')
        self.assertNotIn('fill="#a3ada7" font-size="10"', src)
        self.assertIn('fill="#d3dad6" font-size="11"', src)

    def test_memoria_resultados_arriba_y_conclusion_rpe_primero(self):
        src = _src('memoria_entrenador.html')
        self.assertLess(src.index('id="memoria-acierto-title"'), src.index('id="memoria-hoy-title"'))
        self.assertLess(src.index('Tu RPE cuadra con lo que haces después'), src.index('no cuadraron.</p>'))
        self.assertNotIn('veces que no cuadró', src)
