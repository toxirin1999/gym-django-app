"""2-nov-2026 · Repaso del Día 1 de la descarga."""

from datetime import date, timedelta

from django.test import SimpleTestCase

from entrenos.models import EjercicioRealizado, GymDecisionLog, SemanaPlanGym, TopeMaquinaGym
from entrenos.tests_ultima_sesion import Base
from rutinas.models import Rutina

LUNES = date(2026, 11, 2)


class Nombres(SimpleTestCase):
    def test_misma_sesion_con_o_sin_tilde(self):
        from entrenos.services.nombre_rutina import clave_rutina
        self.assertEqual(clave_rutina('Día 1 - Descarga Activa'), clave_rutina('Dia 1 - Descarga Activa'))
        self.assertEqual(clave_rutina('Dia 4 - Hipertrofia — Metabólica'),
                         clave_rutina('dia 4 - hipertrofia - metabolica'))


class Descarga(Base):
    def setUp(self):
        super().setUp()
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        self.antes = self.entreno(LUNES - timedelta(days=7), {self.gemelos.nombre: '15-20'})
        self.hacer(self.antes, self.gemelos, [(100, 17, 8)] * 3)
        self.hoy = self.entreno(LUNES, {self.gemelos.nombre: '10-15'})
        self.hacer(self.hoy, self.gemelos, [(90, 14, 6)] * 3)

    def test_nota13_la_cola_reconoce_la_sesion_con_tilde(self):
        from unittest.mock import patch
        from entrenos.services import sesion_recomendada as sr
        self.hoy.rutina = Rutina.objects.create(nombre='Día 1 - Descarga Activa')
        self.hoy.save(update_fields=['rutina'])

        class Plan:
            def generar_entrenamiento_para_fecha(self, f):
                return {'rutina_nombre': 'Dia 1 - Descarga Activa', 'ejercicios': [{'nombre': 'x'}]}
        with patch.object(sr, '_normalizar_entrenamiento', side_effect=lambda e: e), \
                patch.object(sr, '_es_descanso', return_value=False):
            cola = sr.cola_semana(self.cliente, LUNES, planificador=Plan())
        self.assertTrue(cola[0]['hecha'])

    def test_notas9_10_12_el_cierre_cuenta_lo_de_antes(self):
        from entrenos.services.cerebro_carga_service import proxima_vez_texto
        texto, accion, efecto = proxima_vez_texto(self.cliente, self.hoy, self.gemelos.nombre, 'peso_reps',
                                                  con_efecto=True)
        self.assertIn('100 kg × 17', texto)
        self.assertEqual((accion, efecto), ('Volver', 'Vuelve a 100 kg'))

    def test_la_descarga_no_toca_el_tope_ni_crea_ni_comprueba_decisiones(self):
        from entrenos.services.decision_log_service import (
            evaluar_decisiones_para_entreno, generar_decisiones_para_entreno, normalizar_ejercicio,
        )
        from entrenos.services.maquina_service import registrar_topes_de_entreno
        TopeMaquinaGym.objects.create(cliente=self.cliente, ejercicio_normalizado=normalizar_ejercicio(
            self.gemelos.nombre), ejercicio=self.gemelos.nombre, peso_max_kg=100)
        EjercicioRealizado.objects.filter(entreno=self.hoy).update(es_tope_maquina=True)
        log = GymDecisionLog.objects.create(cliente=self.cliente, ejercicio=self.gemelos.nombre.lower(),
                                            ejercicio_normalizado=normalizar_ejercicio(self.gemelos.nombre),
                                            accion='bajar_peso', peso_anterior=100, valor_cambio=10,
                                            entreno_origen=self.antes, motivo='x')
        registrar_topes_de_entreno(self.hoy)
        generar_decisiones_para_entreno(self.hoy)
        evaluar_decisiones_para_entreno(self.hoy)
        self.assertEqual(float(TopeMaquinaGym.objects.get(cliente=self.cliente).peso_max_kg), 100.0)
        self.assertFalse(GymDecisionLog.objects.filter(entreno_origen=self.hoy).exists())
        log.refresh_from_db()
        self.assertIsNone(log.resultado)

    def test_el_cierre_lista_la_descarga_sin_decisiones(self):
        from entrenos.services.cierre_entrenamiento_service import _decisiones_de_descarga
        filas = _decisiones_de_descarga(self.cliente, self.hoy)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['accion'], 'Volver')

    def test_nota1_el_briefing_no_pone_tope_en_descarga(self):
        from entrenos.services.briefing_service import get_briefing_gym
        EjercicioRealizado.objects.filter(entreno=self.antes).update(es_tope_maquina=True)
        b = get_briefing_gym(self.cliente, [{'nombre': self.gemelos.nombre, 'deload': True}], LUNES)
        alertas = b['alertas_por_ejercicio'].get(self.gemelos.nombre, [])
        self.assertFalse(any(a.get('tipo') == 'tope' for a in alertas))

    def test_nota11_propuesta_en_pausa_en_el_cierre(self):
        from entrenos.models import PropuestaZonaGym
        from entrenos.services.cierre_porque_service import lo_que_viene
        inicio = date(2026, 10, 14)
        PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona='isquios', ejercicios=['x'], series_extra=2, direccion='subir',
            semanas=4, texto='x', estado=PropuestaZonaGym.ESTADO_ACEPTADA, inicio=inicio,
            fin=inicio + timedelta(days=27))
        lineas = lo_que_viene(self.cliente, self.hoy)
        self.assertTrue(any('en pausa' in l and '17/11' in l for l in lineas), lineas)


class Comando(Base):
    def test_restaura_el_tope_y_reabre_decisiones(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        from entrenos.services.decision_log_service import normalizar_ejercicio
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        antes = self.entreno(LUNES - timedelta(days=7), {self.gemelos.nombre: '15-20'})
        self.hacer(antes, self.gemelos, [(100, 17, 8)] * 3)
        EjercicioRealizado.objects.filter(entreno=antes).update(es_tope_maquina=True)
        hoy = self.entreno(LUNES, {self.gemelos.nombre: '10-15'})
        self.hacer(hoy, self.gemelos, [(90, 14, 6)] * 3)
        clave = normalizar_ejercicio(self.gemelos.nombre)
        TopeMaquinaGym.objects.create(cliente=self.cliente, ejercicio_normalizado=clave,
                                      ejercicio=self.gemelos.nombre, peso_max_kg=90)
        log = GymDecisionLog.objects.create(cliente=self.cliente, ejercicio=clave, ejercicio_normalizado=clave,
                                            accion='bajar_peso', motivo='x', entreno_origen=antes,
                                            resultado='validada', fecha_evaluacion=timezone.now())
        GymDecisionLog.objects.filter(pk=log.pk).update(
            fecha_evaluacion=timezone.make_aware(timezone.datetime(2026, 11, 2, 11, 0)))
        call_command('corregir_sesion_descarga', self.cliente.id, '2026-11-02', '--aplicar', stdout=StringIO())
        self.assertEqual(float(TopeMaquinaGym.objects.get(cliente=self.cliente).peso_max_kg), 100.0)
        log.refresh_from_db()
        self.assertIsNone(log.resultado)
