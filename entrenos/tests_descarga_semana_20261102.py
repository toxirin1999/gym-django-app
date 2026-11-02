"""2-nov-2026 · Semana de descarga: mismos ejercicios, mitad de series, sin progresar."""

from datetime import date, timedelta

from django.test import TestCase

from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.test_planificador_helms_x4 import PERFIL_DAVID, _build_planner
from entrenos.models import SemanaPlanGym
from entrenos.tests_ultima_sesion import Base

LUNES = date(2026, 11, 2)


class Planificador(TestCase):
    def setUp(self):
        per = GeneradorPeriodizacion.generar_periodizacion_anual()
        j = next(i for i, b in enumerate(per) if b['fase'] == 'descarga' and i > 2)
        p = _build_planner(PERFIL_DAVID)
        self.normal = p._generar_semana_especifica(dict(per[j - 1]), j)
        self.descarga = p._generar_semana_especifica(per[j], j + 1)

    @staticmethod
    def _por_dia(semana, campo):
        return {d: {e[campo] for e in ejs} for d, ejs in semana.items()}

    def test_mismos_ejercicios_que_el_bloque(self):
        normales = {e['nombre'] for ejs in self.normal.values() for e in ejs}
        for ejs in self.descarga.values():
            for e in ejs:
                self.assertIn(e['nombre'], normales)

    def test_cada_musculo_los_mismos_dias(self):
        self.assertEqual(self._por_dia(self.descarga, 'grupo_muscular'),
                         self._por_dia(self.normal, 'grupo_muscular'))

    def test_mas_o_menos_la_mitad_de_series(self):
        total = lambda s: sum(e['series'] for ejs in s.values() for e in ejs)
        ratio = total(self.descarga) / total(self.normal)
        self.assertTrue(0.4 <= ratio <= 0.62, ratio)
        for ejs in self.descarga.values():
            for e in ejs:
                self.assertGreaterEqual(e['series'], 2, e['nombre'])
                self.assertEqual(e['rpe_objetivo'], 6, e['nombre'])


class PesoYReps(Base):
    def _ej(self, base, rango, **extra):
        return dict({'nombre': base.nombre, 'repeticiones': rango, 'tipo_progresion': 'peso_reps',
                     'rpe_objetivo': 6, 'peso_kg': 999}, **extra)

    def test_menos_peso_y_no_mas_reps(self):
        from entrenos.services.sesion_descarga_service import ajustar_a_descarga
        e = self.entreno(LUNES - timedelta(days=3), {self.hack.nombre: '10-15'})
        self.hacer(e, self.hack, [(100, 12, 8), (100, 12, 8), (100, 11, 9)])
        ej = self._ej(self.hack, '10-15')
        frase = ajustar_a_descarga(self.cliente, ej, LUNES)
        self.assertEqual((ej['peso_kg'], ej['reps_objetivo_hoy']), (90.0, 12))
        self.assertIn('Semana de descarga: 90 kg', frase)
        self.assertTrue(ej['deload'])
        self.assertFalse(ej.get('progresion_pospuesta'))

    def test_otro_rango_estima_el_peso_para_el_minimo(self):
        from entrenos.services.sesion_descarga_service import ajustar_a_descarga
        e = self.entreno(LUNES - timedelta(days=3), {self.prensa.nombre: '6-8'})
        self.hacer(e, self.prensa, [(200, 7, 8)] * 3)
        ej = self._ej(self.prensa, '10-15')
        ajustar_a_descarga(self.cliente, ej, LUNES)
        self.assertEqual(ej['reps_objetivo_hoy'], 10)
        self.assertLess(ej['peso_kg'], 180)

    def test_solo_en_semana_de_descarga_y_quita_la_progresion(self):
        from entrenos.services.sesion_descarga_service import aplicar_semana_descarga
        e = self.entreno(LUNES - timedelta(days=3), {self.hack.nombre: '10-15'})
        self.hacer(e, self.hack, [(100, 12, 8)] * 3)
        cambios = [{'tipo': 'progresion_pospuesta', 'ejercicio_original': self.hack.nombre}]
        ej = self._ej(self.hack, '10-15')
        self.assertFalse(aplicar_semana_descarga(self.cliente, [ej], LUNES, cambios))
        self.assertEqual(ej['peso_kg'], 999)
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=8, descarga=True,
                                     origen='descarga_programada')
        self.assertTrue(aplicar_semana_descarga(self.cliente, [ej], LUNES + timedelta(days=1), cambios))
        self.assertEqual([c['tipo'] for c in cambios], ['deload'])
