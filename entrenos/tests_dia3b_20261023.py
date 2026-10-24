"""23-oct-2026 · Cierre del Día 3 (aplazado al viernes)."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from entrenos.services.decision_log_service import _decidir_accion
from entrenos.services.ultima_sesion_service import serie_referencia, techo_peso


def _s(peso, reps, rpe):
    return {'peso': peso, 'reps': reps, 'rpe': rpe}


class HundimientoAlMismoPeso(SimpleTestCase):
    def test_curl_martillo_30_x_15_13_8(self):
        ref = serie_referencia([_s(30, 15, 7), _s(30, 13, 9), _s(30, 8, 9)], 15)
        self.assertEqual(ref['caida'], _s(30, 8, 9))
        techo, frase, accion = techo_peso({'referencia': ref}, (15, 20), 8, 5)
        self.assertEqual((techo, accion), (25, 'bajar'))
        self.assertIn('30 kg × 8', frase)

    def test_una_rep_corta_es_fatiga_normal(self):
        ref = serie_referencia([_s(30, 15, 7), _s(30, 15, 8), _s(30, 14, 9)], 15)
        self.assertIsNone(ref['caida'])


class PesoCorporalReglaC(SimpleTestCase):
    def _decidir(self, rpe, objetivo=8, tipo='progresion_reps'):
        ej = SimpleNamespace(fallo_intencional=None)
        return _decidir_accion(ej, [], None, rpe, False, False, tipo, rpe_objetivo=objetivo)

    def test_sissy_9_a_rpe_8_con_objetivo_8(self):
        self.assertEqual(self._decidir(8)[0], 'subir_reps')

    def test_por_encima_del_objetivo_mantiene(self):
        self.assertEqual(self._decidir(9)[0], 'mantener')

    def test_con_carga_no_cambia(self):
        self.assertEqual(self._decidir(8, tipo='peso_reps')[0], 'mantener')


class PesoCorporalSoloSiTodasLlegan(SimpleTestCase):
    def _decidir(self, series, objetivo, tipo='progresion_tiempo'):
        ej = SimpleNamespace(fallo_intencional=None)
        return _decidir_accion(ej, [], None, 8, False, False, tipo, rpe_objetivo=8,
                               series_reps=series, objetivo_sesion=objetivo)

    def test_dead_hang_36_y_31_repite(self):
        accion, _, motivo = self._decidir([36, 31], 36)
        self.assertEqual(accion, 'mantener')
        self.assertIn('(36 s)', motivo)

    def test_sissy_9_9_9_sube(self):
        self.assertEqual(self._decidir([9, 9, 9], 9, 'progresion_reps')[0], 'subir_reps')

    def test_porque_del_cierre(self):
        from entrenos.services.cierre_porque_service import porque_decision
        log = SimpleNamespace(motivo='Objetivo no alcanzado en todas las series (36 s) — repetir',
                              rpe_anterior=8, peso_anterior=None, motivo_codigo='')
        self.assertEqual(
            porque_decision(log, None, None, 'progresion_tiempo'),
            'No todas las series llegaron a 36 s: la próxima vez, otra vez a por 36 s.',
        )


class TopeConMargen(SimpleTestCase):
    def _reps(self, series, objetivo_rpe, sugeridas):
        from unittest.mock import patch
        from entrenos.services.progreso_service import reps_tope_con_margen
        lectura = {'series': series, 'entreno': object()}
        with patch('entrenos.services.ultima_sesion_service.ultima_sesion', return_value=lectura), \
                patch('entrenos.services.decision_log_service._rpe_objetivo_snapshot', return_value=objetivo_rpe):
            return reps_tope_con_margen(None, 'Abducción de Cadera en Máquina', None, sugeridas)

    def test_abduccion_21_a_rpe_6_con_objetivo_9(self):
        reps, aviso = self._reps([_s(60, 21, 8), _s(60, 21, 6), _s(60, 21, 6)], 9, 22)
        self.assertEqual((reps, aviso), (24, None))

    def test_mas_de_25_endurece_la_serie(self):
        reps, aviso = self._reps([_s(60, 25, 6)], 9, 26)
        self.assertEqual(reps, 25)
        self.assertIn('baja en 3 s', aviso)


class PlantillaDia3b(SimpleTestCase):
    def setUp(self):
        from pathlib import Path
        self.html = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text()

    def test_cambios_visibles(self):
        for trozo in (
            '.contingencia-grid.sin-tope{grid-template-columns:repeat(3,1fr);}',   # 7
            '@media (hover:none){',                                               # 3
            "|stringformat:'g' }}",                                               # 4
            "{% elif sn == 1 and ejercicio.reps_objetivo > ejercicio.repeticiones_anterior %}",  # 12
            'ejercicio.aviso_tope_tempo',                                         # 21
            'Tope de la máquina y RPE',                                           # 18
            'La próxima vez, a por ${mejor+1}',                                   # 16
            'La próxima vez, a por ${objTD+1}${uni}',                             # 10
            'aproximaciones and not ejercicio.usa_distancia',                     # 9
            '.exname-toprow{padding-right:96px;}',                                # 5
            'ejercicio.repeticiones_plan|default:ejercicio.repeticiones',         # 8 y 17
            'ejercicio.ultima_vez_series',                                        # 6
        ):
            self.assertIn(trozo, self.html)
        self.assertNotIn("kg</span> | '", self.html)                             # 4
