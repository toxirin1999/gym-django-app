"""Doble progresión, "+X kg hoy" coherente y calculadora de discos sin barra en máquinas."""

from datetime import date
from unittest.mock import patch

from django.urls import reverse

from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.plan_dinamico_service import _tope_rango_reps, aplicar_plan_dinamico
from entrenos.tests_progresion_ejecutiva import (
    PERMISO_PERMITIDO, ProgresionEjecutivaBase, _DELOAD_PATH, _PERMISO_PATH,
)
from rutinas.models import Rutina


class TopeRangoTests(ProgresionEjecutivaBase):
    def test_lee_el_tope(self):
        self.assertEqual(_tope_rango_reps('15-20'), 20)
        self.assertEqual(_tope_rango_reps('8'), 8)
        self.assertEqual(_tope_rango_reps('12–15'), 15)
        self.assertIsNone(_tope_rango_reps('AMRAP'))


class DobleProgresionTests(ProgresionEjecutivaBase):
    def _aplicar(self, reps_anteriores, rango):
        log = self._log_pendiente(
            'subir_peso', ejercicio='Jalón Brazos Rectos', peso_anterior=72.5,
            valor_cambio=2.5, reps_anteriores=reps_anteriores,
        )
        ej = self._ejercicio(nombre='Jalón Brazos Rectos', peso_kg=75.0)
        ej['repeticiones'] = rango
        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), patch(_DELOAD_PATH, return_value=False):
            mod, cambios = aplicar_plan_dinamico(self.cliente, [ej], self.hoy)
        log.refresh_from_db()
        return mod[0], cambios, log

    def test_sin_llegar_al_tope_no_sube_peso(self):
        ej, cambios, log = self._aplicar(11, '15-20')
        self.assertEqual(ej['peso_kg'], 72.5)
        self.assertTrue(ej['progresion_pospuesta'])
        self.assertIn('Doble progresión', ej['progresion_motivo'])
        self.assertIn('20 reps', ej['progresion_motivo'])
        self.assertEqual(log.estado_aplicacion, 'pospuesta')

    def test_en_el_tope_si_sube(self):
        ej, _, log = self._aplicar(20, '15-20')
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertGreater(ej['peso_kg'], 72.5)
        self.assertEqual(log.estado_aplicacion, 'aplicada')


class DeltaYCalculadoraTests(ProgresionEjecutivaBase):
    def _get(self, ejercicios):
        import json
        self.client.force_login(self.user)
        return self.client.get(
            reverse('entrenos:entrenamiento_activo', args=[self.cliente.id]),
            {'fecha': self.hoy.isoformat(), 'rutina_nombre': '', 'ejercicios': json.dumps(ejercicios)},
        )

    def test_mismo_peso_no_anuncia_kg_de_mas(self):
        rutina = Rutina.objects.create(nombre='R')
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=date(2026, 6, 4))
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Sentadilla Hack', peso_kg=22.0,
            series=3, repeticiones=12, completado=True,
        )
        ej = self._ejercicio(nombre='Sentadilla Hack', peso_kg=27.5)
        ej['peso_recomendado_kg'] = 27.5
        ej['repeticiones'] = '12-15'
        response = self._get([ej])
        plan = response.context['ejercicios_planificados'][0]
        self.assertEqual(plan['diferencia_peso'], round(plan['peso_inicial_kg'] - 22.0, 2))
        if plan['peso_inicial_kg'] == 22.0:
            self.assertNotContains(response, 'kg hoy')

    def test_sentadilla_hack_es_maquina_de_discos_sin_barra(self):
        response = self._get([self._ejercicio(nombre='Sentadilla Hack', peso_kg=40.0)])
        plan = response.context['ejercicios_planificados'][0]
        self.assertEqual(plan['tipo_equipo'], 'maquina_discos')
        self.assertEqual(plan['barra_kg'], 0)
