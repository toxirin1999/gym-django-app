"""Revisión del Día 2 de David (20-oct-2026)."""

from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from entrenos.services.ultima_sesion_service import (
    ajustar_escala_y_reps, aplicar_techo, serie_referencia, techo_peso,
)
from entrenos.tests_ultima_sesion import AYER, HOY, Base, s

PLANTILLA = Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


def lectura(series, minimo):
    return {'referencia': serie_referencia(series, minimo), 'fecha': AYER}


class RpeIgualAlObjetivo(SimpleTestCase):
    def test_crunch_75x15_a_rpe_9_con_objetivo_9_pide_una_rep_mas(self):
        techo, frase, accion = techo_peso(lectura([s(70, 15, 8)] + [s(75, 15, 9)] * 3, 15), (15, 20), 9, 5)
        self.assertEqual((techo, accion), (75, 'mantener'))
        self.assertIn('hoy a por 16 reps', frase)

    def test_por_encima_del_objetivo_si_mantiene(self):
        _, frase, _ = techo_peso(lectura([s(25, 15, 9)] * 2, 15), (15, 20), 8, 2.5)
        self.assertIn('mantengo hasta que salga con margen', frase)


class Jalon(Base):
    def test_con_caida_manda_la_regla_aunque_el_plan_traiga_menos(self):
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(50.5, 12, 7), (55.5, 12, 7), (59.5, 12, 9), (55.5, 8, 9)])
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': 50.5,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        aplicar_techo(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 57.5)  # discos de 2,5: un salto por debajo de 59,5 → 57,5


class Arnold(SimpleTestCase):
    def test_bajar_redondea_hacia_abajo_y_por_debajo_de_la_serie_corta(self):
        techo, _, accion = techo_peso(lectura([s(40, 9, 8), s(30, 12, 8), s(30, 12, 8)], 15), (15, 20), 8, 5)
        self.assertEqual((techo, accion), (25, 'bajar'))


class Escala(Base):
    def test_peso_de_la_ultima_vez_que_no_existe_se_redondea(self):
        e = self.entreno(AYER, {'Prensa de Piernas': '12-15'})
        self.hacer(e, self.prensa, [(59.5, 12, 8)] * 3)
        ej = {'nombre': 'Prensa de Piernas', 'repeticiones': '12-15', 'peso_kg': 59.5,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps', 'progresion_motivo_local': 'doble_progresion'}
        ajustar_escala_y_reps(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 60)
        self.assertEqual(ej['reps_objetivo_hoy'], 13)


class Record(Base):
    def test_la_mejor_marca_es_la_serie_mas_pesada(self):
        from entrenos.services.records_service import RecordsService
        e = self.entreno(AYER, {'Sentadilla Hack': '15-20'})
        self.hacer(e, self.hack, [(70, 15, 8), (75, 15, 9), (75, 15, 9), (75, 15, 9)])
        self.assertEqual(float(RecordsService.obtener_mejor_marca(self.cliente, 'Sentadilla Hack').peso_kg), 75.0)


class CierreTrasHundimiento(Base):
    def test_dice_lo_mismo_que_el_proximo_briefing(self):
        from entrenos.models import GymDecisionLog
        from entrenos.services.cierre_porque_service import porque_decision
        e = self.entreno(AYER, {'Sentadilla Hack': '15-20'})
        self.hacer(e, self.hack, [(75, 16, 9), (75, 16, 9), (75, 11, 10), (70, 11, 10)])
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Sentadilla Hack', entreno_origen=e, accion='mantener',
            peso_anterior=75, reps_anteriores=16, motivo='Parámetros estables',
        )
        texto = porque_decision(log, None, None, 'peso_reps')
        self.assertIn('75 kg entró, pero después 2 series se quedaron por debajo de 15', texto)
        self.assertIn('la próxima vez 72,5 kg', texto)  # discos de 2,5 en la hack de test


class PantallaEntreSeries(SimpleTestCase):
    def setUp(self):
        self.src = PLANTILLA.read_text(encoding='utf-8')

    def test_una_rep_por_punto_de_rpe(self):
        self.assertIn('Math.max(1, Math.round(rpeObj - rpe))', self.src)
        self.assertNotIn('(rpeObj - rpe) * 2', self.src)

    def test_boton_guardar_dice_lo_que_guarda(self):
        self.assertIn("return 'Guardar · '+partes.join(' ');", self.src)
