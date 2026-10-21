"""21-oct-2026 · Repaso del Día 3 antes de entrenar."""

from pathlib import Path

from django.test import SimpleTestCase

from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento
from entrenos.services.cierre_porque_service import es_bajada_por_hundimiento
from entrenos.views import _motivo_peso_coherente


class CalentamientoEnEscala(SimpleTestCase):
    def test_kettlebell_de_4_en_4(self):
        self.assertEqual(
            get_aproximaciones_calentamiento(20, incremento=4),
            {'peso1': 8.0, 'peso2': 12.0, 'peso3': 16.0},
        )

    def test_maquina_de_5_en_5(self):
        self.assertEqual(
            get_aproximaciones_calentamiento(60, incremento=5),
            {'peso1': 30.0, 'peso2': 40.0, 'peso3': 50.0},
        )

    def test_sin_incremento_igual_que_antes(self):
        self.assertEqual(
            get_aproximaciones_calentamiento(130),
            {'peso1': 65.0, 'peso2': 90.0, 'peso3': 110.0},
        )


class EtiquetaBajarEnElCierre(SimpleTestCase):
    def test_hundimiento(self):
        self.assertTrue(es_bajada_por_hundimiento(
            '75 kg entró, pero después 2 series se quedaron por debajo de 15 (75 × 11, 70 × 11): '
            'la próxima vez 70 kg para que entren todas.'
        ))

    def test_mantener_normal(self):
        self.assertFalse(es_bajada_por_hundimiento('Mantengo 20 kg: la próxima vez a por 17 reps.'))


class MotivoCoherente(SimpleTestCase):
    def test_sube_con_mismo_peso(self):
        ej = {'motivo_peso': {'tipo': 'sube', 'texto': 'Sube por: …'}, 'peso_inicial_kg': 130.0,
              'peso_anterior_kg': 130.0}
        _motivo_peso_coherente(ej)
        self.assertEqual(ej['motivo_peso']['tipo'], 'mantiene')
        self.assertIn('Mismo peso que la última vez (130 kg)', ej['motivo_peso']['texto'])

    def test_sube_de_verdad(self):
        ej = {'motivo_peso': {'tipo': 'sube', 'texto': 'Sube por: …'}, 'peso_inicial_kg': 32.5,
              'peso_anterior_kg': 30.0}
        _motivo_peso_coherente(ej)
        self.assertEqual(ej['motivo_peso']['tipo'], 'sube')


class PlantillaYVista(SimpleTestCase):
    def test_objetivo_con_el_peso_de_la_casilla(self):
        html = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text()
        self.assertIn('{% with peso_obj=ejercicio.peso_inicial_kg|default:ejercicio.peso_recomendado_kg %}', html)

    def test_enlace_directo_aplica_plan_dinamico(self):
        src = Path('entrenos/views.py').read_text()
        self.assertIn('plan dinámico en el enlace directo falló', src)

    def test_solo_reps_marca_mas_uno(self):
        src = Path('entrenos/views.py').read_text()
        self.assertIn('reps_anteriores + 1 if reps_anteriores < reps_min', src)

    def test_barra_z_pesa_10(self):
        src = Path('entrenos/views.py').read_text()
        self.assertIn("ejercicio['barra_kg'] = 10", src)
