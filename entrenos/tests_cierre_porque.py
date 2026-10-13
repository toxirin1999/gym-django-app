"""Cierre del entreno con el porqué y la comprobación (13-oct-2026).

El cierre explica cada decisión con el dato (regla 3), comprueba en el
momento la decisión anterior (regla 4) y dice qué viene.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, GymDecisionLog, PropuestaZonaGym, SerieRealizada,
)
from entrenos.services.cierre_entrenamiento_service import construir_contexto_cierre
from entrenos.services.cierre_porque_service import (
    comprobaciones_de_hoy, lo_que_viene, porque_decision, texto_series,
)
from rutinas.models import EjercicioBase, Rutina

D1 = date(2026, 10, 9)
D2 = date(2026, 10, 13)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='cierre_porque', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia')
        self.prensa = EjercicioBase.objects.create(
            nombre='Prensa de piernas', grupo_muscular='cuadriceps', tipo_progresion='peso_reps',
        )
        self.farmer = EjercicioBase.objects.create(
            nombre='Farmer Walk', grupo_muscular='antebrazos', tipo_progresion='progresion_distancia',
        )
        self.addCleanup(cache.clear)

    def entreno(self, fecha):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, fecha_ejecucion=fecha,
        )

    def ejercicio(self, entreno, base, peso, reps, rpe, series=None, metros=None):
        ej = EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=base.nombre, peso_kg=peso,
            series=len(series or [reps]), repeticiones=reps, rpe=rpe, completado=True,
        )
        for i, r in enumerate(series or [reps], start=1):
            SerieRealizada.objects.create(
                entreno=entreno, ejercicio=base, serie_numero=i, repeticiones=r,
                peso_kg=peso, completado=True, distancia_metros=metros,
            )
        return ej

    def log(self, entreno, base, accion, motivo, peso=None, valor=None, **extra):
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=base.nombre.lower(), ejercicio_normalizado=base.nombre.lower(),
            entreno_origen=entreno, accion=accion, motivo=motivo, peso_anterior=peso,
            valor_cambio=valor, **extra,
        )


class TextoSeries(Base):
    def test_agrupa_por_peso(self):
        e = self.entreno(D2)
        self.ejercicio(e, self.prensa, 145, 12, 7, series=[12, 12, 10])
        self.assertEqual(texto_series(e, 'Prensa de piernas'), '145 kg × 12, 12, 10')

    def test_distancia_en_metros(self):
        e = self.entreno(D2)
        self.ejercicio(e, self.farmer, 36, 0, 7, series=[0, 0], metros=52)
        self.assertEqual(
            texto_series(e, 'Farmer Walk', 'progresion_distancia'), '36 kg × 52 m, 52 m',
        )


class PorQueConElDato(Base):
    def test_parametros_estables_con_rpe_alto(self):
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 145, 12, 8)
        log = self.log(e, self.prensa, 'mantener', 'Parámetros estables — mantener y enfocar en técnica', 145)
        self.assertEqual(
            porque_decision(log, ej, None, 'peso_reps'),
            'RPE 8 hoy: subo cuando lo hagas a RPE 7,5 o menos dos sesiones seguidas.',
        )

    def test_parametros_estables_por_la_sesion_anterior(self):
        anterior = self.ejercicio(self.entreno(D1), self.prensa, 140, 12, 9)
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 145, 12, 7)
        log = self.log(e, self.prensa, 'mantener', 'Parámetros estables — mantener y enfocar en técnica', 145)
        self.assertEqual(
            porque_decision(log, ej, anterior, 'peso_reps'),
            'Hoy RPE 7, pero la vez anterior fue RPE 9: si se repite lo de hoy, subo.',
        )

    def test_sesion_intensa(self):
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 145, 12, 9)
        log = self.log(e, self.prensa, 'mantener', 'Sesión intensa — consolidar antes de progresar', 145)
        self.assertEqual(
            porque_decision(log, ej, None, 'peso_reps'),
            'RPE 9 hoy: mantengo el peso. Si sigue en 9 o más tres sesiones seguidas, lo bajo.',
        )

    def test_subida_dice_el_peso_nuevo(self):
        anterior = self.ejercicio(self.entreno(D1), self.prensa, 140, 12, 7)
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 140, 12, 7)
        log = self.log(
            e, self.prensa, 'subir_peso',
            'Completado con éxito en 2 sesiones consecutivas con RPE controlado', 140, 5,
        )
        frase = porque_decision(log, ej, anterior, 'peso_reps')
        self.assertEqual(frase, 'RPE 7 hoy y 7 la vez anterior, sin fallo: subo el peso.')

    def test_tope_de_maquina(self):
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 100.5, 15, 7)
        log = self.log(e, self.prensa, 'subir_reps', 'Tope de máquina alcanzado — progresión por repeticiones', 100.5)
        self.assertEqual(
            porque_decision(log, ej, None, 'peso_reps'),
            '100,5 kg es el máximo de la máquina: progreso por repeticiones.',
        )

    def test_distancia_corta_frente_al_objetivo(self):
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.farmer, 36, 0, 7, series=[0, 0, 0], metros=52)
        log = self.log(
            e, self.farmer, 'mantener',
            'Distancia o margen insuficiente — consolidar carga y metros antes de progresar', 36,
            motivo_codigo='distancia_sin_margen',
        )
        with patch('entrenos.services.decision_log_service._objetivo_distancia_snapshot',
                   return_value=__import__('decimal').Decimal('53')):
            frase = porque_decision(log, ej, None, 'progresion_distancia')
        self.assertEqual(
            frase, 'El objetivo era 53 m por serie y hoy hiciste 52, 52, 52 m: subo cuando lo completes en todas.',
        )

    def test_motivo_ya_concreto_no_se_toca(self):
        e = self.entreno(D2)
        ej = self.ejercicio(e, self.prensa, 145, 10, 8)
        log = self.log(e, self.prensa, 'mantener', 'Media 10 frente al objetivo 12 — completar el objetivo antes de progresar', 145)
        self.assertIsNone(porque_decision(log, ej, None, 'peso_reps'))


class ComprobacionEnElMomento(Base):
    def test_la_subida_anterior_se_comprueba_al_cerrar(self):
        e1 = self.entreno(D1)
        self.ejercicio(e1, self.prensa, 140, 12, 7)
        self.log(e1, self.prensa, 'subir_peso', 'x', 140, 5, resultado='validada')
        e2 = self.entreno(D2)
        self.ejercicio(e2, self.prensa, 145, 12, 7)
        items = comprobaciones_de_hoy(self.cliente, e2)
        self.assertEqual(len(items), 1)
        self.assertIn('Hoy: 145 kg × 12 con RPE 7.', items[0]['texto'])
        self.assertTrue(items[0]['texto'].endswith('Funcionó.'))

    def test_no_repite_una_evaluada_por_otra_sesion(self):
        e1 = self.entreno(D1)
        self.ejercicio(e1, self.prensa, 140, 12, 7)
        self.log(e1, self.prensa, 'subir_peso', 'x', 140, 5, resultado='validada')
        e_medio = self.entreno(D1 + timedelta(days=2))
        self.ejercicio(e_medio, self.prensa, 145, 12, 7)
        e2 = self.entreno(D2)
        self.ejercicio(e2, self.prensa, 145, 12, 7)
        self.assertEqual(comprobaciones_de_hoy(self.cliente, e2), [])

    def test_mantener_no_se_cuenta(self):
        e1 = self.entreno(D1)
        self.ejercicio(e1, self.prensa, 140, 12, 8)
        self.log(e1, self.prensa, 'mantener', 'x', 140, resultado='validada')
        e2 = self.entreno(D2)
        self.ejercicio(e2, self.prensa, 140, 12, 7)
        self.assertEqual(comprobaciones_de_hoy(self.cliente, e2), [])


class LoQueViene(Base):
    def planificador(self, sesion):
        p = MagicMock()
        p.generar_entrenamiento_para_fecha.return_value = sesion
        return p

    def test_siguiente_de_la_cola_y_propuesta(self):
        e = self.entreno(D2)
        PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona='isquios', ejercicios=['Curl femoral'], series_extra=1,
            direccion='subir', semanas=4, texto='x', estado=PropuestaZonaGym.ESTADO_ACEPTADA,
            inicio=D2 + timedelta(days=1), fin=D2 + timedelta(days=28),
        )
        siguiente = {
            'fecha': D2 - timedelta(days=0), 'nombre': 'Dia 2 - Hipertrofia', 'sp': None,
            'entrenamiento': {'ejercicios': [
                {'grupo_muscular': 'pecho'}, {'grupo_muscular': 'espalda'}, {'grupo_muscular': 'pecho'},
            ]},
        }
        with patch('entrenos.services.sesion_recomendada._siguiente_de_cola', return_value=siguiente):
            lineas = lo_que_viene(self.cliente, e)
        self.assertEqual(lineas[0], 'Lo siguiente es el Día 2 (pecho, espalda), que era del martes.')
        self.assertEqual(
            lineas[1],
            'Desde el 14/10, +2 series semanales de Isquios por la propuesta que aceptaste (hasta el 10/11).',
        )

    def test_manana_descanso(self):
        e = self.entreno(D2)
        with patch('entrenos.services.sesion_recomendada._siguiente_de_cola', return_value=None), \
                patch('entrenos.services.sesion_recomendada._build_planificador',
                      return_value=self.planificador({'rutina_nombre': 'Día de Descanso', 'ejercicios': []})):
            self.assertEqual(lo_que_viene(self.cliente, e), ['Mañana toca descanso.'])

    def test_un_cierre_antiguo_no_dice_lo_que_viene(self):
        e = self.entreno(D1)
        self.entreno(D2)
        self.assertEqual(lo_que_viene(self.cliente, e), [])


class CierreCompleto(Base):
    def test_el_contexto_lleva_porque_hoy_y_comprobaciones(self):
        e1 = self.entreno(D1)
        self.ejercicio(e1, self.prensa, 140, 12, 7)
        self.log(e1, self.prensa, 'subir_peso', 'x', 140, 5, resultado='validada')
        e2 = self.entreno(D2)
        self.ejercicio(e2, self.prensa, 145, 12, 8, series=[12, 12, 12])
        self.log(e2, self.prensa, 'mantener', 'Parámetros estables — mantener y enfocar en técnica', 145)
        with patch('entrenos.services.cierre_porque_service.lo_que_viene', return_value=['Mañana toca descanso.']):
            ctx = construir_contexto_cierre(self.cliente, e2)
        decision = ctx['decisiones_entrenador'][0]
        self.assertEqual(decision['porque'], 'RPE 8 hoy: subo cuando lo hagas a RPE 7,5 o menos dos sesiones seguidas.')
        self.assertEqual(decision['hoy'], '145 kg × 12, 12, 12 · RPE 8')
        self.assertEqual(len(ctx['comprobaciones']), 1)
        self.assertEqual(ctx['que_viene'], ['Mañana toca descanso.'])

    def test_la_pagina_lo_muestra(self):
        e1 = self.entreno(D1)
        self.ejercicio(e1, self.prensa, 140, 12, 7)
        self.log(e1, self.prensa, 'subir_peso', 'x', 140, 5, resultado='validada')
        e2 = self.entreno(D2)
        self.ejercicio(e2, self.prensa, 145, 12, 8)
        self.log(e2, self.prensa, 'mantener', 'Parámetros estables — mantener y enfocar en técnica', 145)
        self.client.force_login(self.cliente.user)
        with patch('entrenos.services.cierre_porque_service.lo_que_viene', return_value=['Mañana toca descanso.']):
            r = self.client.get(f'/entrenos/cliente/{self.cliente.id}/entreno/{e2.id}/cierre/')
        html = r.content.decode()
        self.assertContains(r, 'Lo que comprobé hoy')
        self.assertIn('Hoy: 145 kg × 12 con RPE 8', html)
        self.assertIn('RPE 8 hoy: subo cuando lo hagas a RPE 7,5 o menos', html)
        self.assertContains(r, 'Lo que viene')


class ObjetivoDeMetrosSinReps(TestCase):
    """El Farmer quedaba en 'mantener' para siempre: el plan no guardaba reps_objetivo."""

    def entreno(self, ejercicio):
        from types import SimpleNamespace
        return SimpleNamespace(gym_decision_version=SimpleNamespace(
            snapshot={'entrenamiento': {'ejercicios': [ejercicio]}}))

    def test_usa_el_minimo_del_rango(self):
        from decimal import Decimal
        from entrenos.services.decision_log_service import _objetivo_distancia_snapshot
        e = self.entreno({'nombre': 'Farmer Walk', 'repeticiones': '20-30'})
        self.assertEqual(_objetivo_distancia_snapshot(e, 'farmer walk'), Decimal('20'))

    def test_reps_objetivo_manda_si_existe(self):
        from decimal import Decimal
        from entrenos.services.decision_log_service import _objetivo_distancia_snapshot
        e = self.entreno({'nombre': 'Farmer Walk', 'repeticiones': '20-30', 'reps_objetivo': 57})
        self.assertEqual(_objetivo_distancia_snapshot(e, 'farmer walk'), Decimal('57'))

    def test_sin_snapshot_no_hay_objetivo(self):
        from types import SimpleNamespace
        from entrenos.services.decision_log_service import _objetivo_distancia_snapshot
        self.assertIsNone(_objetivo_distancia_snapshot(SimpleNamespace(), 'farmer walk'))
