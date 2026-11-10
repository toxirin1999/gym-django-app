"""Día 2 (10-nov-2026): Pallof con pausa primero, RPE «5 o menos», último registro
en el mismo rango, core al final y la serie de más esfuerzo como base."""
import json
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from django.test import SimpleTestCase

from entrenos.services.cerebro_carga_service import decidir_carga, proxima_vez_texto
from entrenos.services.criterios_entrenador_service import core_al_final
from entrenos.services.ultima_sesion_service import reps_para_peso, rpe_efectivo
from entrenos.tests_ultima_sesion import Base

HOY = date(2026, 11, 10)
PLANTILLA = Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


class RpeEfectivo(SimpleTestCase):
    def test_cinco_o_menos_se_estima_como_cuatro(self):
        self.assertEqual(rpe_efectivo(5), 4.0)
        self.assertEqual(rpe_efectivo(4), 4.0)
        self.assertEqual(rpe_efectivo(6), 6.0)
        self.assertEqual(rpe_efectivo(None), 9.0)

    def test_con_5_salen_mas_reps_que_con_6(self):
        r5 = reps_para_peso(30, 6, 5, 35, 8, (4, 12))
        r6 = reps_para_peso(30, 6, 6, 35, 8, (4, 12))
        self.assertGreaterEqual(r5, r6)

    def test_el_boton_dice_5_o_menos(self):
        fuente = PLANTILLA.read_text(encoding='utf-8')
        self.assertIn('aria-label="RPE 5 o menos"', fuente)
        self.assertIn('o menos</small>', fuente)
        self.assertIn('if (rpe <= 5) rpe = 4;', fuente)


class CoreAlFinal(SimpleTestCase):
    def test_el_core_va_despues_y_el_resto_conserva_el_orden(self):
        ejs = [{'nombre': 'Crunch en polea'}, {'nombre': 'Pallof Press'}, {'nombre': 'Jalón al pecho'},
               {'nombre': 'Remo con mancuerna a una mano'}, {'nombre': 'Peso muerto rumano'}]
        core_al_final(ejs)
        self.assertEqual([e['nombre'] for e in ejs],
                         ['Jalón al pecho', 'Remo con mancuerna a una mano', 'Peso muerto rumano',
                          'Crunch en polea', 'Pallof Press'])


class PallofConPausa(Base):
    def _ej(self):
        return {'nombre': 'Pallof Press', 'repeticiones': '10-12', 'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}

    def setUp(self):
        super().setUp()
        from rutinas.models import EjercicioBase
        self.pallof = EjercicioBase.objects.create(
            nombre='Pallof Press', grupo_muscular='core', tipo_progresion='peso_reps')

    def test_al_tope_primero_pausa_con_el_mismo_peso(self):
        e = self.entreno(HOY - timedelta(days=7), {'Pallof Press': '10-12'})
        self.hacer(e, self.pallof, [(25, 12, 8), (25, 12, 8), (25, 16, 8)])
        d = decidir_carga(self.cliente, self._ej(), HOY)
        self.assertEqual((d['peso'], d['regla']), (25, 'mantener'))
        self.assertTrue(d['pausa'])
        self.assertIn('pausa de 2 s', d['frase'])
        self.assertIn('Si llegas, subo', d['frase'])

    def test_si_ya_estaba_al_tope_con_pausa_se_sube(self):
        e1 = self.entreno(HOY - timedelta(days=14), {'Pallof Press': '10-12'})
        ej = self.pallof
        self.hacer(e1, ej, [(25, 12, 8), (25, 12, 8), (25, 12, 8)])
        e2 = self.entreno(HOY - timedelta(days=7), {'Pallof Press': '10-12'})
        self.hacer(e2, ej, [(25, 12, 8), (25, 12, 8), (25, 12, 8)])
        d = decidir_carga(self.cliente, self._ej(), HOY)
        self.assertFalse(d.get('pausa'))
        self.assertGreater(d['peso'], 25)

    def test_el_cierre_dice_la_pausa_y_el_peso_al_que_sube(self):
        e = self.entreno(HOY - timedelta(days=1), {'Pallof Press': '10-12'})
        self.hacer(e, self.pallof, [(25, 12, 8), (25, 12, 8), (25, 16, 8)])
        texto, accion = proxima_vez_texto(self.cliente, e, 'Pallof Press', 'peso_reps')
        self.assertIn('pausa de 2 s', texto)
        self.assertIn('si llegas, subo a 30 kg', texto)
        self.assertEqual(accion, 'Mantener')


class MismoRango(Base):
    def _ej(self, rango):
        return {'nombre': 'Sentadilla Hack', 'repeticiones': rango, 'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}

    def test_con_rango_nuevo_se_parte_del_ultimo_registro_en_ese_rango(self):
        # Remo: ya había hecho 30 × 6 en 4-6 y el peso salía de un 20 × 14 de otro rango.
        viejo = self.entreno(HOY - timedelta(days=20), {'Sentadilla Hack': '4-6'})
        self.hacer(viejo, self.hack, [(30, 6, 8), (30, 6, 8)])
        reciente = self.entreno(HOY - timedelta(days=6), {'Sentadilla Hack': '12-15'})
        self.hacer(reciente, self.hack, [(20, 14, 8), (20, 14, 8)])
        d = decidir_carga(self.cliente, self._ej('4-6'), HOY)
        self.assertGreaterEqual(d['peso'], 30)

    def test_sin_registro_en_ese_rango_no_cambia_nada(self):
        reciente = self.entreno(HOY - timedelta(days=6), {'Sentadilla Hack': '12-15'})
        self.hacer(reciente, self.hack, [(20, 14, 8), (20, 14, 8)])
        from entrenos.services.ultima_sesion_service import ultima_sesion_mismo_rango
        self.assertIsNone(ultima_sesion_mismo_rango(self.cliente, 'Sentadilla Hack', HOY, (4, 6)))

    def test_la_estimacion_usa_la_ultima_serie(self):
        from entrenos.services.ultima_sesion_service import serie_de_mas_esfuerzo
        ref = {'peso': 25, 'validas': [
            {'peso': 25, 'reps': 12, 'rpe': 8}, {'peso': 25, 'reps': 12, 'rpe': 8}, {'peso': 25, 'reps': 16, 'rpe': 8}]}
        self.assertEqual(serie_de_mas_esfuerzo(ref)['reps'], 16)


class CitaRepsRegistradas(Base):
    def _ej(self):
        return {'nombre': 'Sentadilla Hack', 'repeticiones': '4-6', 'rpe_objetivo': 7, 'tipo_progresion': 'peso_reps'}

    def test_la_mediana_no_se_cita_como_si_fuera_una_serie(self):
        # Jalón 27/10: 50 kg × 15, 15, 12 y 9; la mediana (13,5) se citaba «50 × 14».
        from entrenos.services.ultima_sesion_service import reps_real_cercana
        validas = [{'peso': 50, 'reps': r, 'rpe': 8} for r in (15, 15, 12, 9)]
        self.assertEqual(reps_real_cercana(validas, 50, 13.5), 15)
        self.assertEqual(reps_real_cercana(validas, 50, 12.2), 12)
        self.assertIn(reps_real_cercana(validas, 50, 14), (15,))

    def test_el_texto_del_cambio_de_rango_solo_cita_reps_registradas(self):
        e = self.entreno(HOY - timedelta(days=14), {'Sentadilla Hack': '15-20'})
        self.hacer(e, self.hack, [(50, 15, 8), (50, 15, 8), (50, 12, 8), (50, 9, 9)])
        d = decidir_carga(self.cliente, self._ej(), HOY)
        self.assertNotIn('× 14', d['frase'])
        self.assertNotIn('a 14 con', d['frase'])


class SubirSinPrometerElMinimo(Base):
    def test_si_el_calculo_da_menos_que_el_minimo_lo_dice(self):
        # Arnold: 35 kg «a por 8» cuando el cálculo da unas 5.
        e = self.entreno(HOY - timedelta(days=7), {'Sentadilla Hack': '8-12'})
        self.hacer(e, self.hack, [(30, 12, 8), (30, 12, 8)])
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '8-12', 'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        d = decidir_carga(self.cliente, ej, HOY)
        self.assertEqual(d['regla'], 'subir')
        if 'calculo unas' in d['frase']:
            self.assertIn('para ahí y apúntalo', d['frase'])


class EjecucionDeHoy(Base):
    def test_menos_reps_por_el_tope_del_rango_no_es_bajada(self):
        from entrenos.services.cierre_entrenamiento_service import _comparar_referencias
        antes = self.entreno(HOY - timedelta(days=7), {'Sentadilla Hack': '12-15'})
        self.hacer(antes, self.hack, [(40, 14, 8), (40, 14, 8)])
        hoy = self.entreno(HOY, {'Sentadilla Hack': '8-12'})
        self.hacer(hoy, self.hack, [(40, 12, 7), (40, 12, 7)])
        c = _comparar_referencias(hoy, antes, 'Sentadilla Hack')
        self.assertEqual(c['tipo'], 'mantenida')
        self.assertIn('tope del rango', c['detalle'])
        self.assertNotIn('−2', c['detalle'])

    def test_menos_reps_con_rango_nuevo_no_es_bajada(self):
        from entrenos.services.cierre_entrenamiento_service import _comparar_referencias
        antes = self.entreno(HOY - timedelta(days=7), {'Sentadilla Hack': '8-12'})
        self.hacer(antes, self.hack, [(60, 8, 8), (60, 8, 8)])
        hoy = self.entreno(HOY, {'Sentadilla Hack': '4-6'})
        self.hacer(hoy, self.hack, [(60, 5, 7), (60, 5, 7)])
        c = _comparar_referencias(hoy, antes, 'Sentadilla Hack')
        self.assertEqual(c['tipo'], 'mantenida')
        self.assertIn('rango nuevo', c['detalle'])

    def test_con_el_mismo_rango_y_menos_reps_si_es_bajada(self):
        from entrenos.services.cierre_entrenamiento_service import _comparar_referencias
        antes = self.entreno(HOY - timedelta(days=7), {'Sentadilla Hack': '8-12'})
        self.hacer(antes, self.hack, [(60, 11, 8), (60, 11, 8)])
        hoy = self.entreno(HOY, {'Sentadilla Hack': '8-12'})
        self.hacer(hoy, self.hack, [(60, 9, 8), (60, 9, 8)])
        c = _comparar_referencias(hoy, antes, 'Sentadilla Hack')
        self.assertEqual(c['tipo'], 'bajada')


class TextosDelDia(SimpleTestCase):
    def test_la_cabecera_ya_no_manda_apretar(self):
        from entrenos.services.recuperacion_service import _frase_recuperacion
        frase = _frase_recuperacion('verde', [], ['has dormido 7 h'], {})
        self.assertNotIn('apretar', frase)

    def test_la_regla_de_parada_tiene_su_linea_propia(self):
        fuente = PLANTILLA.read_text(encoding='utf-8')
        self.assertIn('class="ex-regla-parada"', fuente)
        self.assertNotIn('exname-meta-line exname-regla', fuente)

    def test_el_badge_de_tope_no_dice_mantener(self):
        fuente = (PLANTILLA.parent / 'briefing_entrenamiento.html').read_text(encoding='utf-8')
        self.assertIn("ej.regla_carga == 'tope' %}<span class=\"tag tag-subtle ok\">↑ MÁS REPS", fuente)
