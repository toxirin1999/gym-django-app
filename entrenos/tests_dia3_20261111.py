"""Día 3 (11-nov-2026): abducción al tope con tempo, cierre con cálculo honesto,
comparación sin la descarga, «última vez» sin descarga, textos y guardado sin red."""
from datetime import date, timedelta
from pathlib import Path

from django.test import SimpleTestCase

from entrenos.models import EjercicioRealizado, TopeMaquinaGym
from entrenos.services.cerebro_carga_service import decidir_carga, proxima_vez_texto
from entrenos.tests_ultima_sesion import Base

HOY = date(2026, 11, 11)
ACTIVO = Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html'
BRIEFING = Path(__file__).parent / 'templates' / 'entrenos' / 'briefing_entrenamiento.html'


class AbduccionAlTope(Base):
    def setUp(self):
        super().setUp()
        self.abd = EjercicioBase_crear('Abducción de Cadera en Máquina')
        TopeMaquinaGym.objects.create(
            cliente=self.cliente, ejercicio_normalizado=_norm('Abducción de Cadera en Máquina'),
            ejercicio='Abducción de Cadera en Máquina', peso_max_kg=60)

    def _ej(self):
        return {'nombre': 'Abducción de Cadera en Máquina', 'repeticiones': '15-20', 'rpe_objetivo': 8,
                'tipo_progresion': 'peso_reps'}

    def test_con_el_tope_de_reps_hechas_no_pide_mas_reps(self):
        e = self.entreno(HOY - timedelta(days=12), {'Abducción de Cadera en Máquina': '15-20'})
        self.hacer(e, self.abd, [(60, 20, 8), (60, 20, 8)])
        d = decidir_carga(self.cliente, self._ej(), HOY)
        self.assertEqual(d['regla'], 'tope')
        self.assertTrue(d['con_tempo'])

    def test_el_tope_de_reps_es_20_aunque_el_rango_del_plan_sea_menor(self):
        # En producción el rango era 12-15: el texto decía «ya haces las 12 reps».
        e = self.entreno(HOY, {'Abducción de Cadera en Máquina': '12-15'})
        self.hacer(e, self.abd, [(60, 20, 8), (60, 20, 8)])
        texto, accion = proxima_vez_texto(self.cliente, e, 'Abducción de Cadera en Máquina', 'peso_reps')
        self.assertIn('ya haces las 20 reps', texto)
        d = decidir_carga(self.cliente, dict(self._ej(), repeticiones='12-15'), HOY + timedelta(days=3))
        self.assertTrue(d['con_tempo'])

    def test_con_menos_reps_si_las_pide(self):
        e = self.entreno(HOY - timedelta(days=12), {'Abducción de Cadera en Máquina': '15-20'})
        self.hacer(e, self.abd, [(60, 16, 8), (60, 16, 8)])
        d = decidir_carga(self.cliente, self._ej(), HOY)
        self.assertFalse(d['con_tempo'])

    def test_el_cierre_habla_de_tempo_y_no_de_subir_reps(self):
        e = self.entreno(HOY, {'Abducción de Cadera en Máquina': '15-20'})
        self.hacer(e, self.abd, [(60, 20, 8), (60, 20, 8)])
        texto, accion = proxima_vez_texto(self.cliente, e, 'Abducción de Cadera en Máquina', 'peso_reps')
        self.assertIn('bajada de 3 s', texto)
        self.assertEqual(accion, 'Mantener')

    def test_la_etiqueta_del_briefing_dice_con_tempo(self):
        src = BRIEFING.read_text(encoding='utf-8')
        self.assertIn("ej.regla_carga == 'tope' and ej.tope_con_tempo %}", src)
        self.assertIn('= CON TEMPO', src)


class CierreConCalculoHonesto(Base):
    def test_subir_peso_dice_cuantas_reps_calcula_si_son_menos_que_el_minimo(self):
        base = EjercicioBase_crear('Curl con Barra Z')
        e = self.entreno(HOY, {'Curl con Barra Z': '8-12'})
        self.hacer(e, base, [(30, 12, 8), (30, 12, 8)])
        texto, accion = proxima_vez_texto(self.cliente, e, 'Curl con Barra Z', 'peso_reps')
        self.assertEqual(accion, 'Subir peso')
        self.assertIn('Subo a 35 kg'.lower(), texto.lower().replace('subo a', 'subo a'))
        self.assertIn('calculo unas', texto)
        self.assertIn('antes de las 8 reps', texto)

    def test_el_texto_del_briefing_dice_antes_de_las_reps(self):
        from pathlib import Path as P
        src = (P(__file__).parent / 'services' / 'cerebro_carga_service.py').read_text(encoding='utf-8')
        self.assertIn("f'las {minimo} reps, para ahí y apúntalo.'", src)


class ComparacionSinDescarga(SimpleTestCase):
    def test_una_sesion_de_hace_mas_de_seis_semanas_no_es_la_comparacion(self):
        src = (Path(__file__).parent / 'services' / 'cierre_entrenamiento_service.py').read_text(encoding='utf-8')
        self.assertIn('.days > 42', src)

    def test_el_cierre_salta_las_sesiones_de_descarga(self):
        src = (Path(__file__).parent / 'services' / 'cierre_entrenamiento_service.py').read_text(encoding='utf-8')
        self.assertIn('if not es_descarga_hoy:', src)
        self.assertIn('es_sesion_descarga(candidato.entreno, candidato.nombre_ejercicio)', src)


class TextosDelDia(SimpleTestCase):
    def test_el_boton_no_dice_el_al_final(self):
        src = ACTIVO.read_text(encoding='utf-8')
        self.assertIn("queda para el final", src)
        self.assertNotIn("'el '+atras[0]+', al final'", src)

    def test_el_guardado_avisa_si_tarda_y_si_falla_la_red(self):
        src = ACTIVO.read_text(encoding='utf-8')
        self.assertIn('id="saving-hint"', src)
        self.assertIn('puede que no tengas cobertura', src)
        self.assertIn('mira el historial antes de reintentar', src)

    def test_sissy_sin_jerga_de_rango_de_paso(self):
        src = (Path(__file__).parent / 'services' / 'plan_dinamico_service.py').read_text(encoding='utf-8')
        self.assertNotIn('Rango de paso', src)
        self.assertIn('pasas al siguiente escalón', src)

    def test_farmer_no_dice_a_por_5_m(self):
        src = (Path(__file__).parent / 'services' / 'plan_dinamico_service.py').read_text(encoding='utf-8')
        self.assertIn('m más que la última vez', src)

    def test_la_tarjeta_dice_mas_uno_sobre_la_media(self):
        src = (Path(__file__).parent / 'views.py').read_text(encoding='utf-8')
        self.assertIn("+1 sobre tu media de", src)


def EjercicioBase_crear(nombre):
    from rutinas.models import EjercicioBase
    return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='gluteos', tipo_progresion='peso_reps')


def _norm(nombre):
    from entrenos.services.decision_log_service import normalizar_ejercicio
    return normalizar_ejercicio(nombre)
