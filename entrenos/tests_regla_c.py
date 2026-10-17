"""Revisión del entreno del 17-oct-2026: regla C y escala real de carga.

Casos sacados del Día 2 de David: remo y peso muerto rumano idénticos a la
vez anterior (sin progresión), jalón que se hunde en la última serie, Press
Arnold sin ninguna serie en rango y pesos que no existen en la máquina.
"""

from datetime import date

from django.test import SimpleTestCase

from entrenos.services.maquina_service import a_escala, salto_fisico, tipo_equipo_carga
from entrenos.services.peso_semantica_service import normalizar_semantica_carga
from entrenos.services.ultima_sesion_service import (
    ajustar_escala_y_reps, objetivo_reps_hoy, peso_contractual, serie_referencia, techo_peso,
    texto_doble_progresion,
)
from entrenos.tests_ultima_sesion import Base, HOY, AYER, s


def lectura(series, minimo):
    return {'referencia': serie_referencia(series, minimo), 'fecha': AYER}


class EscalaReal(SimpleTestCase):
    def test_tipos_de_equipo_de_david(self):
        self.assertEqual(salto_fisico('Jalón al Pecho'), 5)
        self.assertEqual(salto_fisico('Machine Shoulder Press'), 5)
        self.assertEqual(salto_fisico('Crunch en Polea (Cable Crunch)'), 5)
        self.assertEqual(salto_fisico('Curl Femoral Tumbado'), 5)
        self.assertEqual(salto_fisico('Peso Muerto Rumano'), 2.5)
        self.assertEqual(salto_fisico('Remo con Mancuerna a una mano'), 2.5)
        # Dos mancuernas en "peso total": de 5 en 5 (37,5 no se puede montar).
        self.assertEqual(salto_fisico('Press Arnold'), 5)
        self.assertEqual(tipo_equipo_carga('Press banca con mancuernas'), 'mancuerna_dos')

    def test_a_escala(self):
        self.assertEqual(a_escala(59.5, 5), 60)
        self.assertEqual(a_escala(37.5, 5), 35)          # empate: hacia abajo
        self.assertEqual(a_escala(37.5, 5, 'arriba'), 40)
        self.assertEqual(a_escala(39.9, 5), 40)
        self.assertEqual(a_escala(59.5, 2.5), 60)


class ReglaC(SimpleTestCase):
    def test_reps_de_hoy(self):
        self.assertEqual(objetivo_reps_hoy(12, (12, 15)), 13)
        self.assertEqual(objetivo_reps_hoy(15, (12, 15)), 15)
        self.assertEqual(objetivo_reps_hoy(10, (12, 15)), 12)
        self.assertEqual(objetivo_reps_hoy(12, (12, 15), mismo_peso=False), 12)

    def test_con_12_de_12_15_no_sube_el_peso(self):
        # Remo: 20 × 12, 12, 12 a RPE 8 → mismo peso, a por 13.
        techo, frase, accion = techo_peso(lectura([s(20, 12, 8)] * 3, 12), (12, 15), 8, 2.5)
        self.assertEqual((techo, accion), (20, 'mantener'))
        self.assertEqual(frase, texto_doble_progresion(12, (12, 15)))
        self.assertIn('hoy a por 13 reps', frase)

    def test_arriba_del_rango_sube_un_salto(self):
        techo, frase, _ = techo_peso(lectura([s(20, 15, 7)] * 3, 12), (12, 15), 8, 2.5)
        self.assertEqual(techo, 22.5)
        self.assertIsNone(frase)

    def test_ninguna_en_rango_usa_todas_las_series(self):
        # Arnold: 40 × 9 y después 30 × 12, rango 15-20, mancuernas de 5 en 5.
        techo, frase, accion = techo_peso(
            lectura([s(40, 9, 8), s(30, 12, 8), s(30, 12, 8)], 15), (15, 20), 8, 5,
        )
        self.assertEqual(accion, 'bajar')
        self.assertEqual(techo, 30)
        self.assertIn('40 kg × 9 y 30 kg × 12', frase)

    def test_la_ultima_serie_se_hunde(self):
        # Jalón: 50,5 · 55,5 · 59,5 × 12 y después 55,5 × 8.
        series = [s(50.5, 12, 7), s(55.5, 12, 7), s(59.5, 12, 9), s(55.5, 8, 9)]
        techo, frase, accion = techo_peso(lectura(series, 12), (12, 15), 8, 5)
        self.assertEqual((techo, accion), (55, 'bajar'))
        self.assertIn('pero después 55,5 kg × 8', frase)


class PesoContractual(SimpleTestCase):
    def test_con_bajada_arranca_en_el_peso_del_briefing(self):
        ej = {'peso_kg': 37.5, 'peso_recomendado_kg': 40, 'progresion_aplicada': True,
              'progresion_accion': 'bajar_peso'}
        self.assertEqual(peso_contractual(ej), 37.5)
        self.assertEqual(peso_contractual({'peso_kg': 30, 'peso_recomendado_kg': 32.5}), 32.5)


class PorLado(SimpleTestCase):
    def test_pallof_se_cuenta_por_lado(self):
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Pallof Press'})['peso_formato'], 'por_lado')
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Jalón al Pecho'})['peso_formato'], 'total')


class AjusteFinalDelPlan(Base):
    def test_remo_arranca_con_una_rep_mas_y_mismo_peso(self):
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 12, 8)] * 3)
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': 60.0,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        ajustar_escala_y_reps(self.cliente, ej, HOY)
        self.assertEqual(ej['reps_objetivo_hoy'], 13)
        self.assertEqual(ej['incremento_kg'], 2.5)

    def test_peso_raro_se_lleva_a_la_escala(self):
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': 59.5,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        ajustar_escala_y_reps(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 60)
        self.assertEqual(ej['reps_objetivo_hoy'], 12)

    def test_pallof_rpe_8(self):
        ej = {'nombre': 'Pallof Press', 'repeticiones': '15-20', 'peso_kg': 25.0,
              'rpe_objetivo': 9, 'tipo_progresion': 'peso_reps'}
        ajustar_escala_y_reps(self.cliente, ej, HOY)
        self.assertEqual(ej['rpe_objetivo'], 8)


class DecisionCierre(Base):
    def decision(self, base):
        from entrenos.models import GymDecisionLog
        return GymDecisionLog.objects.get(cliente=self.cliente, ejercicio_normalizado=base.nombre.lower())

    def test_12_de_12_15_dice_peso_y_reps_de_la_proxima(self):
        from entrenos.services.cierre_porque_service import porque_decision
        from entrenos.services.decision_log_service import generar_decisiones_para_entreno
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 12, 8)] * 3)
        generar_decisiones_para_entreno(e)
        log = self.decision(self.hack)
        self.assertEqual(log.accion, 'mantener')
        texto = porque_decision(log, None, None, 'peso_reps')
        self.assertEqual(
            texto, 'Mantengo 60 kg: la próxima vez a por 13 reps. Con 15 en todas las series, subo el peso.',
        )

    def test_15_de_12_15_sube(self):
        from entrenos.services.decision_log_service import generar_decisiones_para_entreno
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(60, 15, 8)] * 3)
        generar_decisiones_para_entreno(e)
        self.assertEqual(self.decision(self.hack).accion, 'subir_peso')
