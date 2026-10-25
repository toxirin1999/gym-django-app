"""25-oct-2026 · Repaso del Día 5: notas 2-24 (arreglos de la app)."""

from datetime import timedelta
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from entrenos.models import EjercicioRealizado
from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento
from entrenos.services.cerebro_carga_service import decidir_carga, proxima_vez_texto
from entrenos.services.descanso_service import get_descanso_sugerido
from entrenos.services.maquina_service import salto_fisico, tipo_equipo_carga
from entrenos.services.peso_semantica_service import normalizar_semantica_carga
from entrenos.services.ultima_sesion_service import anotar_ultima_vez, dia_de_fatiga
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


def _ej(nombre, rango, rpe=8):
    return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': rpe, 'tipo_progresion': 'peso_reps'}


class ReglaDeCarga(Base):
    def base(self, nombre, equipo=None):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='x', tipo_progresion='peso_reps', equipo=equipo)

    def test_nota10_peso_real_fuera_de_escala_se_respeta(self):
        b = self.base('Bayesian Curl', equipo='Polea')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(22.5, 15, 8), (22.5, 15, 8)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (22.5, 16, 'mantener'))

    def test_nota7_mancuernas_si_van_a_su_escala(self):
        b = self.base('Press Inclinado con Mancuernas')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(46, 15, 8), (46, 15, 8)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['reps']), (45, 16))

    def test_nota19_dia_de_fatiga_repite_el_peso(self):
        b = self.base('Extensiones sobre la Cabeza con Mancuerna')
        e1 = self.entreno(HOY - timedelta(days=8), {b.nombre: '15-20'})
        self.hacer(e1, b, [(15, 15, 7), (15, 15, 7)])
        e2 = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self.hacer(e2, b, [(15, 4, 10), (10, 7, 9)])
        self.assertEqual(dia_de_fatiga(self.cliente, b.nombre, e2, 15)['reps_hoy'], 4)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (15, 15, 'fatiga'))
        self.assertIn('llegaste muy cansado', d['frase'])
        texto, accion, efecto = proxima_vez_texto(self.cliente, e2, b.nombre, 'peso_reps', con_efecto=True)
        self.assertEqual(accion, 'Mantener')
        self.assertIn('repetimos 15 kg', texto)
        self.assertEqual(efecto, 'Repite 15 kg')

    def test_dos_dias_malos_seguidos_si_bajan(self):
        b = self.base('Extensiones sobre la Cabeza con Mancuerna')
        e1 = self.entreno(HOY - timedelta(days=15), {b.nombre: '15-20'})
        self.hacer(e1, b, [(15, 15, 7)])
        e2 = self.entreno(HOY - timedelta(days=8), {b.nombre: '15-20'})
        self.hacer(e2, b, [(15, 4, 10)])
        e3 = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self.hacer(e3, b, [(15, 5, 10)])
        self.assertIsNone(dia_de_fatiga(self.cliente, b.nombre, e3, 15))

    def test_nota20_margen_de_sobra_dos_reps_mas(self):
        b = self.base('Fondos en Paralelas (con lastre)')
        e = self.entreno(HOY - timedelta(days=3), {b.nombre: '15-20'})
        self.hacer(e, b, [(75, 15, 6), (75, 16, 6)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20', rpe=7), HOY)
        self.assertEqual((d['peso'], d['reps']), (75, 18))
        self.assertIn('por debajo del 7', d['frase'])

    def test_con_el_rpe_justo_sigue_siendo_una(self):
        b = self.base('Dips (Fondos en Pecho)')
        e = self.entreno(HOY - timedelta(days=3), {b.nombre: '15-20'})
        self.hacer(e, b, [(80, 16, 7)] * 3)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20', rpe=7), HOY)
        self.assertEqual((d['peso'], d['reps']), (80, 17))

    def test_nota7_tanteo_corto_no_dispara_el_aviso(self):
        b = self.base('Press Inclinado con Mancuernas')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(45, 10, 8), (47.5, 15, 8), (47.5, 15, 8)])
        ej = _ej(b.nombre, '15-20')
        ej['peso_kg'] = 45
        anotar_ultima_vez(self.cliente, ej, HOY)
        self.assertNotIn('aviso_coherencia', ej)

    def test_aviso_sigue_si_no_hubo_series_buenas_despues(self):
        b = self.base('Press Inclinado con Mancuernas')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(45, 10, 8), (40, 15, 8)])
        ej = _ej(b.nombre, '15-20')
        ej['peso_kg'] = 45
        anotar_ultima_vez(self.cliente, ej, HOY)
        self.assertIn('Si no llegas, baja el peso', ej['aviso_coherencia'])


class EquipoYEtiquetas(SimpleTestCase):
    def test_nota6_fondos_y_dips_son_de_discos(self):
        self.assertEqual(salto_fisico('Dips (Fondos en Pecho)'), 2.5)
        self.assertEqual(salto_fisico('Fondos en Paralelas (con lastre)'), 2.5)
        self.assertEqual(get_aproximaciones_calentamiento(80, incremento=2.5), {'peso1': 40.0, 'peso2': 55.0, 'peso3': 67.5})

    def test_nota8_sin_escalones_repetidos(self):
        self.assertIsNone(get_aproximaciones_calentamiento(15, incremento=5))
        cal = get_aproximaciones_calentamiento(15, incremento=2.5)
        self.assertTrue(cal['peso1'] < cal['peso2'] < cal['peso3'] < 15)

    def test_nota18_una_mancuerna(self):
        nombre = 'Extensiones sobre la Cabeza con Mancuerna'
        self.assertEqual(tipo_equipo_carga(nombre), 'mancuerna_una')
        self.assertEqual(normalizar_semantica_carga({'nombre': nombre, 'peso_kg': 15})['peso_formato'], 'una_mancuerna')
        self.assertEqual(tipo_equipo_carga('Press Inclinado con Mancuernas'), 'mancuerna_dos')
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Curl Inclinado con Mancuernas', 'peso_kg': 10})['peso_formato'], 'total_ambas')

    def test_notas12_17_unilaterales(self):
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Bayesian Curl'})['reps_unidad'], 'por brazo')
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Patada de Glúteo en Polea'})['reps_unidad'], 'por pierna')
        self.assertEqual(normalizar_semantica_carga({'nombre': 'Bayesian Curl'})['peso_formato'], 'total')

    def test_nota14_descanso_de_la_bulgara(self):
        d = get_descanso_sugerido('aislamiento', nombre='Sentadilla Búlgara', reps='8-12')
        self.assertEqual(d['label'], '2:30')
        self.assertEqual(get_descanso_sugerido(nombre='Patada de Glúteo en Polea', reps='15-20')['label'], '1:30')

    def test_kettlebell_de_2_en_2(self):
        self.assertEqual(salto_fisico('Sentadilla Búlgara'), 2)

    def test_nota21_nombre_visible(self):
        from entrenos.services.nombres_visibles import nombre_visible
        self.assertEqual(nombre_visible('Fondos en Paralelas (con lastre)'), 'Fondos en Máquina (sentado)')
        self.assertEqual(nombre_visible('Dips (Fondos en Pecho)'), 'Dips (Fondos en Pecho)')
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('{{ ejercicio.nombre|nombre_visible }}', activo)

    def test_plantillas(self):
        briefing = Path('entrenos/templates/entrenos/briefing_entrenamiento.html').read_text(encoding='utf-8')
        self.assertIn('Cómo vienes', briefing)
        self.assertNotIn('<span class="sec-tag">Readiness</span>', briefing)
        self.assertIn('NUEVO RANGO', briefing)
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('sin peso apuntado', activo)
        self.assertIn("una_mancuerna", activo)


class CierreEjecucion(Base):
    def test_nota24_salen_los_tres_y_con_su_lectura(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        bul = EjercicioBase.objects.create(nombre='Sentadilla Búlgara', grupo_muscular='c', tipo_progresion='peso_reps')
        ext = EjercicioBase.objects.create(nombre='Extensiones sobre la Cabeza con Mancuerna', grupo_muscular='t',
                                           tipo_progresion='peso_reps')
        pat = EjercicioBase.objects.create(nombre='Patada de Glúteo en Polea', grupo_muscular='g', tipo_progresion='peso_reps')
        e1 = self.entreno(HOY - timedelta(days=7), {bul.nombre: '8-12', ext.nombre: '15-20'})
        self.hacer(e1, bul, [(8, 8, 8)] * 3)
        self.hacer(e1, ext, [(15, 15, 7)] * 2)
        e0 = self.entreno(HOY - timedelta(days=32), {pat.nombre: '15-20'})
        self.hacer(e0, pat, [(0, 11, 6), (0, 10, 6)])
        e2 = self.entreno(HOY, {bul.nombre: '8-12', ext.nombre: '15-20', pat.nombre: '15-20'})
        self.hacer(e2, bul, [(10, 8, 8)] * 3)
        self.hacer(e2, ext, [(15, 4, 10), (10, 7, 9)])
        self.hacer(e2, pat, [(20, 15, 8)] * 2)
        # El historial con otra grafía del nombre también cuenta.
        EjercicioRealizado.objects.filter(entreno=e1, nombre_ejercicio=bul.nombre).update(nombre_ejercicio='sentadilla búlgara')
        cambios = {c['nombre']: c for c in _cambios_relevantes(
            self.cliente, e2, list(EjercicioRealizado.objects.filter(entreno=e2)))}
        self.assertIn('+2 kg', cambios['Sentadilla Búlgara']['detalle'])
        self.assertEqual(cambios['Extensiones sobre la Cabeza con Mancuerna']['tipo'], 'mantenida')
        self.assertIn('día de cansancio', cambios['Extensiones sobre la Cabeza con Mancuerna']['detalle'])
        self.assertIn('sin peso apuntado', cambios['Patada de Glúteo en Polea']['detalle'])

    def test_nota23_vuelta_a_un_rango_no_es_bajada(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        b = EjercicioBase.objects.create(nombre='Fondos en Paralelas (con lastre)', grupo_muscular='p',
                                         tipo_progresion='peso_reps')
        e0 = self.entreno(HOY - timedelta(days=40), {b.nombre: '15-20'})
        self.hacer(e0, b, [(80, 15, 7)] * 2)
        e1 = self.entreno(HOY - timedelta(days=30), {b.nombre: '6-8'})
        self.hacer(e1, b, [(92.5, 8, 9)] * 2)
        e2 = self.entreno(HOY, {b.nombre: '15-20'})
        self.hacer(e2, b, [(75, 15, 6), (75, 16, 6)])
        c = _cambios_relevantes(self.cliente, e2, list(EjercicioRealizado.objects.filter(entreno=e2)))[0]
        self.assertEqual(c['tipo'], 'mantenida')
        self.assertIn('vuelves a este rango', c['detalle'])
