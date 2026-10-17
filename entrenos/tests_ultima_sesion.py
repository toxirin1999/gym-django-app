"""Bloque A1 (13-oct-2026): la última vez se lee de las series reales.

Casos sacados del entreno del 13-oct de David: pirámides, una serie más
pesada que se queda corta, series por debajo del rango, y la doble
progresión que el briefing promete y el cierre debe respetar.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, GymDecisionLog, GymDecisionVersion, SerieRealizada,
)
from entrenos.services.decision_log_service import generar_decisiones_para_entreno
from entrenos.services.ultima_sesion_service import (
    aplicar_techo, serie_referencia, techo_peso, ultima_sesion,
)
from rutinas.models import EjercicioBase, Rutina

AYER = date(2026, 10, 13)
HOY = date(2026, 10, 15)


def s(peso, reps, rpe=None):
    return {'peso': float(peso), 'reps': reps, 'rpe': rpe, 'metros': None}


class SerieReferencia(TestCase):
    def test_piramide_toma_la_mas_pesada_en_rango(self):
        ref = serie_referencia([s(15.5, 12, 7), s(18, 12, 7), s(20, 12, 7)], 12)
        self.assertEqual((ref['peso'], ref['reps'], ref['rpe']), (20.0, Decimal(12), 7))
        self.assertTrue(ref['en_rango'])
        self.assertIsNone(ref['superior'])

    def test_serie_pesada_corta_no_es_la_referencia(self):
        ref = serie_referencia([s(79, 8, 10), s(60, 15, 7)], 15)
        self.assertEqual((ref['peso'], ref['reps'], ref['rpe']), (60.0, Decimal(15), 7))
        self.assertEqual(ref['superior']['peso'], 79.0)

    def test_todas_cortas_toma_la_mas_pesada(self):
        ref = serie_referencia([s(22, 8, 8), s(22, 8, 8)], 12)
        self.assertEqual(ref['peso'], 22.0)
        self.assertFalse(ref['en_rango'])

    def test_sin_rango_es_la_mas_pesada(self):
        ref = serie_referencia([s(62.5, 12, 7), s(60, 12, 7), s(60, 12, 8)])
        self.assertEqual(ref['peso'], 62.5)


def lectura(series, minimo):
    return {'referencia': serie_referencia(series, minimo), 'fecha': AYER}


class TechoPeso(TestCase):
    def test_muy_corto_baja_por_e1rm(self):
        # Sentadilla Hack: 22 kg × 8 con rango 12-15 → 20 kg, no 25.
        techo, frase, accion = techo_peso(lectura([s(22, 8, 8)], 12), (12, 15), 8, 2)
        self.assertEqual(techo, 20)
        self.assertEqual(accion, 'bajar')
        self.assertEqual(frase, 'La última vez 22 kg × 8; para 12-15, hoy 20 kg.')

    def test_poco_corto_mantiene(self):
        # Gemelos sentado: 67 × 14 con rango 15-20 → no sube a 79.
        techo, frase, accion = techo_peso(lectura([s(67, 14, 9)], 15), (15, 20), 9, 5)
        self.assertEqual((techo, accion), (67, 'mantener'))
        self.assertEqual(frase, 'La última vez 67 kg × 14: mantengo el peso hasta llegar a 15.')

    def test_minimo_con_rpe_alto_mantiene(self):
        # Fly: 14 × 12 a RPE 9 con rango 12-15 → 14, no 17,5.
        techo, frase, _ = techo_peso(lectura([s(14, 12, 9)], 12), (12, 15), 9, 5)
        self.assertEqual(techo, 14)
        self.assertIn('a RPE 9', frase)

    def test_bien_permite_un_salto(self):
        techo, frase, _ = techo_peso(lectura([s(20, 12, 7)] * 3, 12), (12, 15), 9, 2.5)
        self.assertEqual(techo, 22.5)
        self.assertIsNone(frase)

    def test_serie_superior_corta_fija_la_referencia(self):
        techo, frase, _ = techo_peso(
            lectura([s(110, 15, 8), s(114, 10, 9), s(90, 15, 9)], 15), (15, 20), 9, 2,
        )
        self.assertEqual(techo, 110)
        self.assertEqual(
            frase, 'La última vez 114 kg se quedó en 10 reps y 110 kg × 15 sí entró en 15-20: hoy 110 kg.',
        )


    def test_back_off_no_ancla_el_peso(self):
        # Curl femoral 13-oct: 45 × 6 (RPE 8) y después bajó a 26 × 12.
        techo, frase, accion = techo_peso(lectura([s(45, 6, 8), s(26, 12, 8)], 12), (12, 15), 8, 2.5)
        self.assertEqual((techo, accion), (37.5, 'mantener'))
        self.assertEqual(frase, 'La última vez 45 kg × 6 y después 26 kg × 12; para 12-15, hoy 37,5 kg.')

    def test_back_off_nunca_pasa_de_la_serie_pesada(self):
        techo, _, _ = techo_peso(lectura([s(30, 11, 6), s(20, 12, 8)], 12), (12, 15), 8, 2.5)
        self.assertEqual(techo, 27.5)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='ultima_sesion', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'U'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia')
        self.hack = EjercicioBase.objects.create(
            nombre='Sentadilla Hack', grupo_muscular='cuadriceps', tipo_progresion='peso_reps',
        )
        self.prensa = EjercicioBase.objects.create(
            nombre='Prensa de Piernas', grupo_muscular='cuadriceps', tipo_progresion='peso_reps',
        )
        self.gemelos = EjercicioBase.objects.create(
            nombre='Elevación de Gemelos Sentado (Máquina)', grupo_muscular='gemelos',
            tipo_progresion='peso_reps',
        )
        self.addCleanup(cache.clear)

    def entreno(self, fecha, rangos):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        e.gym_decision_version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=fecha, version=1, decision_id=f'd-{fecha}',
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
            postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': nombre, 'repeticiones': rango} for nombre, rango in rangos.items()
            ]}},
        )
        e.save(update_fields=['gym_decision_version'])
        return e

    def hacer(self, entreno, base, series):
        pesos = [p for p, _, _ in series]
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=base.nombre, peso_kg=sum(pesos) / len(pesos),
            series=len(series), repeticiones=sum(r for _, r, _ in series) // len(series),
            rpe=round(sum(x for _, _, x in series) / len(series)), completado=True,
        )
        for i, (peso, reps, rpe) in enumerate(series, start=1):
            SerieRealizada.objects.create(
                entreno=entreno, ejercicio=base, serie_numero=i, repeticiones=reps,
                peso_kg=peso, rpe_real=rpe, completado=True,
            )


class UltimaVezEnPantalla(Base):
    def test_ultima_vez_es_la_serie_de_referencia_no_la_media(self):
        from entrenos.views import obtener_ultimo_peso_ejercicio
        e = self.entreno(AYER, {'Elevación de Gemelos Sentado (Máquina)': '15-20'})
        self.hacer(e, self.gemelos, [(79, 8, 10), (60, 15, 7)])
        datos = obtener_ultimo_peso_ejercicio(self.cliente.id, self.gemelos.nombre, HOY, rango='15-20')
        self.assertEqual((datos['peso'], datos['repeticiones'], datos['rpe']), (60.0, 15, 7))

    def test_lectura_de_la_ultima_sesion(self):
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(21, 12, 8), (21, 12, 7), (20, 12, 7), (20, 12, 8)])
        lec = ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)
        self.assertEqual((lec['referencia']['peso'], lec['referencia']['rpe']), (21.0, 8))


class TechoEnElPlan(Base):
    def test_el_plan_no_propone_25_tras_22_por_8(self):
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(22, 8, 8), (22, 8, 8)])
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': 25.0,
              'peso_recomendado_kg': 25.0, 'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        cambio = aplicar_techo(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 20)
        self.assertEqual(ej['peso_recomendado_kg'], 20)
        self.assertEqual(ej['peso_kg_anterior'], 25.0)
        self.assertEqual(ej['progresion_accion'], 'bajar_peso')
        self.assertEqual(ej['progresion_motivo'], 'La última vez 22 kg × 8; para 12-15, hoy 20 kg.')
        self.assertEqual(cambio['accion'], 'bajar_peso')

    def test_no_toca_un_peso_razonable(self):
        e = self.entreno(AYER, {'Prensa de Piernas': '12-15'})
        self.hacer(e, self.prensa, [(145, 12, 7), (140, 12, 7), (140, 12, 7)])
        ej = {'nombre': 'Prensa de Piernas', 'repeticiones': '12-15', 'peso_kg': 145.0,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        self.assertIsNone(aplicar_techo(self.cliente, ej, HOY))
        self.assertEqual(ej['peso_kg'], 145.0)

    def test_sesion_antigua_no_limita(self):
        e = self.entreno(HOY - timedelta(days=60), {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(22, 8, 8)])
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': 25.0,
              'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}
        self.assertIsNone(aplicar_techo(self.cliente, ej, HOY))


class DecisionConSeries(Base):
    def decision(self, base):
        return GymDecisionLog.objects.get(cliente=self.cliente, ejercicio_normalizado=base.nombre.lower())

    def test_doble_progresion_no_sube_con_12_de_15(self):
        anterior = self.entreno(AYER - timedelta(days=7), {'Prensa de Piernas': '12-15'})
        self.hacer(anterior, self.prensa, [(145, 12, 7)] * 3)
        e = self.entreno(AYER, {'Prensa de Piernas': '12-15'})
        self.hacer(e, self.prensa, [(145, 12, 7), (140, 12, 7), (140, 12, 7)])
        generar_decisiones_para_entreno(e)
        log = self.decision(self.prensa)
        self.assertEqual(log.accion, 'mantener')
        self.assertIn('frente al objetivo 15', log.motivo)
        self.assertEqual(log.peso_anterior, 145.0)

    def test_serie_a_rpe_10_por_encima_no_es_la_referencia(self):
        e = self.entreno(AYER, {'Elevación de Gemelos Sentado (Máquina)': '15-20'})
        self.hacer(e, self.gemelos, [(79, 8, 10), (60, 15, 7)])
        generar_decisiones_para_entreno(e)
        log = self.decision(self.gemelos)
        self.assertEqual(log.accion, 'mantener')
        self.assertEqual(log.peso_anterior, 60.0)
        self.assertEqual(log.rpe_anterior, 7)

    def test_muy_por_debajo_del_rango_baja(self):
        e = self.entreno(AYER, {'Sentadilla Hack': '12-15'})
        self.hacer(e, self.hack, [(22, 8, 8), (22, 8, 8)])
        generar_decisiones_para_entreno(e)
        log = self.decision(self.hack)
        self.assertEqual(log.accion, 'bajar_peso')
        self.assertIn('lejos de 12-15 reps', log.motivo)
        self.assertLess(log.peso_sugerido, 22)


class CierreConRPEPorSerie(Base):
    def test_el_cierre_muestra_el_rpe_de_cada_serie(self):
        from entrenos.services.cierre_porque_service import texto_series
        e = self.entreno(AYER, {'Elevación de Gemelos Sentado (Máquina)': '15-20'})
        self.hacer(e, self.gemelos, [(79, 8, 10), (60, 15, 7)])
        self.assertEqual(texto_series(e, self.gemelos.nombre), '79 kg × 8 @10 · 60 kg × 15 @7')
