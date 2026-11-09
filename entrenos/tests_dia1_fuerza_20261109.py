"""9-nov-2026 · Reparaciones del repaso del primer Día 1 de Fuerza — Hipertrofia."""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import SemanaPlanGym
from entrenos.services.ultima_sesion_service import dia_de_fatiga
from entrenos.tests_ultima_sesion import Base

HOY = timezone.localdate()
LUNES = HOY - timedelta(days=HOY.weekday())


class CambioDeRangoNoEsCansancio(Base):
    """Nota 26: el cierre proponía hack 20 kg y prensa 145 kg «hoy llegabas muy cansado»."""

    def test_hack_de_15_20_a_4_6_no_es_dia_de_fatiga(self):
        antes = self.entreno(HOY - timedelta(days=14), {'Sentadilla Hack': '15-20'})
        self.hacer(antes, self.hack, [(20, 14, 7), (20, 14, 7), (20, 14, 8)])
        hoy = self.entreno(HOY, {'Sentadilla Hack': '4-6'})
        self.hacer(hoy, self.hack, [(30, 6, 7), (32.5, 6, 8), (32.5, 6, 8)])
        self.assertIsNone(dia_de_fatiga(self.cliente, 'Sentadilla Hack', hoy))

    def test_mas_peso_y_menos_reps_no_es_dia_de_fatiga(self):
        antes = self.entreno(HOY - timedelta(days=14), {'Prensa de Piernas': '4-6'})
        self.hacer(antes, self.prensa, [(145, 14, 7), (145, 14, 7)])
        hoy = self.entreno(HOY, {'Prensa de Piernas': '4-6'})
        self.hacer(hoy, self.prensa, [(180, 8, 7), (180, 8, 7)])
        self.assertIsNone(dia_de_fatiga(self.cliente, 'Prensa de Piernas', hoy))

    def test_mismo_rango_y_peso_con_hundimiento_sigue_siendo_fatiga(self):
        antes = self.entreno(HOY - timedelta(days=7), {'Sentadilla Hack': '12-15'})
        self.hacer(antes, self.hack, [(40, 14, 7), (40, 14, 7)])
        hoy = self.entreno(HOY, {'Sentadilla Hack': '12-15'})
        self.hacer(hoy, self.hack, [(40, 6, 10), (40, 5, 10)])
        f = dia_de_fatiga(self.cliente, 'Sentadilla Hack', hoy)
        self.assertIsNotNone(f)
        self.assertEqual((f['peso'], f['reps_antes'], f['reps_hoy']), (40.0, 14, 6))

    def test_la_decision_siguiente_no_repite_por_cansancio(self):
        from entrenos.services.cerebro_carga_service import decidir_carga
        antes = self.entreno(HOY - timedelta(days=15), {'Sentadilla Hack': '15-20'})
        self.hacer(antes, self.hack, [(20, 14, 7), (20, 14, 7)])
        hoy = self.entreno(HOY - timedelta(days=1), {'Sentadilla Hack': '4-6'})
        self.hacer(hoy, self.hack, [(30, 6, 7), (32.5, 6, 8)])
        d = decidir_carga(self.cliente, {'nombre': 'Sentadilla Hack', 'repeticiones': '4-6', 'rpe_objetivo': 8,
                                         'tipo_progresion': 'peso_reps', 'peso_kg': 30}, HOY)
        self.assertNotEqual(d.get('regla'), 'fatiga')
        self.assertNotIn('cansado', d.get('frase') or '')
        self.assertGreaterEqual(d['peso'], 30.0)


class UltimaVezSinDescarga(Base):
    """Notas 6/10/14/17/19 e idea 14: «Última vez» no es la descarga, y lleva su fecha."""

    def setUp(self):
        super().setUp()
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES - timedelta(weeks=1), semana_plan=44,
                                     descarga=True, origen=SemanaPlanGym.ORIGEN_AVANCE)

    def test_salta_la_semana_de_descarga(self):
        from entrenos.views import obtener_ultimo_peso_ejercicio
        normal = self.entreno(LUNES - timedelta(weeks=2), {'Sentadilla Hack': '15-20'})
        self.hacer(normal, self.hack, [(20, 14, 7), (20, 14, 7)])
        descarga = self.entreno(LUNES - timedelta(weeks=1), {'Sentadilla Hack': '15-20'})
        self.hacer(descarga, self.hack, [(17.5, 14, 5), (17.5, 14, 5)])
        datos = obtener_ultimo_peso_ejercicio(self.cliente.id, 'Sentadilla Hack', LUNES, rango='15-20')
        self.assertEqual((datos['peso'], datos['fecha'], datos['descarga']), (20.0, normal.fecha, False))

    def test_si_solo_hay_descarga_la_usa_y_la_marca(self):
        from entrenos.views import obtener_ultimo_peso_ejercicio
        descarga = self.entreno(LUNES - timedelta(weeks=1), {'Sentadilla Hack': '15-20'})
        self.hacer(descarga, self.hack, [(17.5, 14, 5)])
        datos = obtener_ultimo_peso_ejercicio(self.cliente.id, 'Sentadilla Hack', LUNES, rango='15-20')
        self.assertEqual((datos['peso'], datos['descarga']), (17.5, True))


import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from django.test import SimpleTestCase

PLANTILLA = Path(__file__).parent / 'templates/entrenos/entrenamiento_activo.html'


def _funcion_js(fuente, nombre):
    i = fuente.index(f'function {nombre}(')
    j = fuente.index('{', i)
    nivel = 0
    for k in range(j, len(fuente)):
        if fuente[k] == '{':
            nivel += 1
        elif fuente[k] == '}':
            nivel -= 1
            if nivel == 0:
                return fuente[i:k + 1]
    raise AssertionError(nombre)


@unittest.skipUnless(shutil.which('node'), 'sin node')
class SiguienteSeriePorEstimacion(SimpleTestCase):
    """Notas 2, 3, 8, 9, 16, 18, 20, 24: salto y reps estimados entre series."""

    def plan(self, salto, peso, rpe, reps, rpe_obj, rmin, rmax, tope=''):
        fuente = PLANTILLA.read_text(encoding='utf-8')
        js = '\n'.join(_funcion_js(fuente, n) for n in ('aEscalaJS', 'estimarSerieJS', 'planSiguienteSerie'))
        prog = (
            f"const document={{getElementById:(id)=>id.startsWith('card-')?{{dataset:{{topeKg:'{tope}'}}}}:"
            f"(id.startsWith('peso-')?{{value:'{peso}',dataset:{{planWeight:''}}}}:null)}};"
            f"function incrementoPeso(){{return {salto}}}"
            "function fmtKg(x){return String(+(+x).toFixed(2)).replace('.',',')}"
            + js +
            f"console.log(JSON.stringify(planSiguienteSerie('x',{peso},{rpe},{reps},{rpe_obj},{rmin},{rmax})));"
        )
        salida = subprocess.run(['node', '-e', prog], capture_output=True, text=True, check=True).stdout
        return json.loads(salida)

    def test_prensa_por_encima_del_rango_a_rpe_objetivo_sube(self):
        p = self.plan(5, 180, 7, 8, 7, 4, 6)
        self.assertEqual((p['tipo'], p['peso'], p['reps']), ('subir', 190, 5))

    def test_convergent_con_mucho_margen_sube_de_una_vez(self):
        p = self.plan(2.5, 62.5, 5, 8, 8, 6, 8)
        self.assertEqual((p['tipo'], p['peso'], p['reps']), ('subir', 67.5, 7))

    def test_tras_subir_las_reps_no_son_siempre_el_minimo(self):
        p = self.plan(5, 60, 6, 20, 8, 15, 20)
        self.assertEqual((p['peso'], p['reps']), (65, 17))

    def test_bajar_lo_justo_y_reps_estimadas(self):
        p = self.plan(2.5, 40, 9, 5, 8, 8, 12)
        self.assertEqual((p['tipo'], p['peso'], p['reps']), ('bajar', 35, 9))

    def test_tope_de_maquina_limita_la_subida(self):
        p = self.plan(5, 95, 6, 20, 8, 15, 20, tope=100)
        self.assertEqual(p['peso'], 100)

    def test_con_margen_dentro_del_rango_mismo_peso(self):
        p = self.plan(2.5, 40, 6, 9, 8, 8, 12)
        self.assertEqual((p['tipo'], p['peso'], p['reps']), ('reps', 40, 11))


class TextosDeLaSesion(SimpleTestCase):
    def test_fuerza_maxima_fuera_de_la_sesion(self):
        fuente = PLANTILLA.read_text(encoding='utf-8')
        self.assertNotIn("'Fuerza máxima estimada: '", _funcion_js(fuente, 'actualizarORM'))

    def test_sin_vuelta_al_minimo_tras_subir(self):
        self.assertNotIn('vuelves al mínimo del rango', PLANTILLA.read_text(encoding='utf-8'))

    def test_regla_de_parada_en_la_tarjeta(self):
        self.assertIn('ejercicio.regla_parada', PLANTILLA.read_text(encoding='utf-8'))


class CierreDiceLasRepsCalculadas(Base):
    """Cierre del 9-nov en producción: «subo a 182,5 kg y vuelvo a 4 reps» mientras la decisión calculaba 6."""

    def test_subir_en_el_cierre_lleva_las_reps_de_la_decision(self):
        from entrenos.services.cerebro_carga_service import decidir_carga, proxima_vez_texto
        e = self.entreno(HOY - timedelta(days=1), {'Sentadilla Hack': '4-6'})
        self.hacer(e, self.hack, [(30, 8, 7), (30, 6, 7), (30, 6, 7)])
        texto, accion = proxima_vez_texto(self.cliente, e, 'Sentadilla Hack', 'peso_reps')
        d = decidir_carga(self.cliente, {'nombre': 'Sentadilla Hack', 'repeticiones': '4-6', 'rpe_objetivo': 8,
                                         'tipo_progresion': 'peso_reps'}, HOY)
        self.assertEqual(accion, 'Subir peso')
        self.assertNotIn('vuelvo a', texto)
        self.assertIn(f"a por {d['reps']} reps", texto)
