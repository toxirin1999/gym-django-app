"""22-oct-2026 · Sesión aplazada/adelantada, reps de hoy y calentamientos sin repetir."""

from pathlib import Path

from django.test import SimpleTestCase

from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento


class CalentamientoSinRepetidos(SimpleTestCase):
    def test_laterales_16_en_polea(self):
        self.assertEqual(get_aproximaciones_calentamiento(16, incremento=5),
                         {'peso1': 5.0, 'peso2': 10.0, 'peso3': 15.0})

    def test_kettlebell_16(self):
        self.assertEqual(get_aproximaciones_calentamiento(16, incremento=4),
                         {'peso1': 4.0, 'peso2': 8.0, 'peso3': 12.0})


class EnlaceDirecto(SimpleTestCase):
    def setUp(self):
        self.src = Path('entrenos/views.py').read_text()

    def test_abre_lo_mismo_que_ahora(self):
        self.assertIn('_sig = _siguiente_de_cola(cliente, fecha_obj)', self.src)

    def test_peso_del_plan_y_reps_de_hoy(self):
        self.assertIn("ejercicio['peso_inicial_kg'] = peso_contractual(ejercicio) or peso_ant or peso_rec", self.src)
        self.assertGreaterEqual(self.src.count("ejercicio['reps_objetivo'] = int(ejercicio['reps_objetivo_hoy'])"), 2)
