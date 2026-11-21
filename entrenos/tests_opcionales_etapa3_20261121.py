"""Etapa 3 (21-nov-2026): opcionales y cierre parcial.

El cierre es parcial solo por lo que falta del bloque PRINCIPAL. Un opcional sin
hacer (versión reducida o pierna opcional del fútbol) no pide motivo.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class OpcionalesCierreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('opc-etapa3', password='x')
        from clientes.models import Cliente
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.rutina = Rutina.objects.create(nombre='Día opcionales')
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def _post(self, reducido=False, **extra):
        data = {
            'fecha': date.today().isoformat(), 'rutina_nombre': self.rutina.nombre,
            'modo_reducido': '1' if reducido else '0',
            'ej1_nombre': 'Sentadilla', 'ej1_tipo_progresion': 'peso_reps', 'ej1_es_principal': '1',
            'ej1_opcional': '0',
            'ej1_peso_1': '60', 'ej1_reps_1': '5', 'ej1_rpe_1': '8', 'ej1_completado_1': '1',
            'ej2_nombre': 'Curl femoral', 'ej2_tipo_progresion': 'peso_reps', 'ej2_es_principal': '0',
            'ej2_opcional': '1',
            'ej2_peso_1': '30', 'ej2_reps_1': '10',
        }
        data.update(extra)
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_reducido_con_opcional_sin_hacer_es_completa_sin_motivo(self):
        r = self._post(reducido=True)
        self.assertEqual(r.status_code, 200, r.content)
        e = EntrenoRealizado.objects.get()
        self.assertEqual(e.estado_cierre, EntrenoRealizado.ESTADO_COMPLETA)
        self.assertTrue(e.modo_reducido)
        self.assertEqual((e.principales_planificados, e.opcionales_planificados), (1, 1))

    def test_opcional_futbol_sin_hacer_es_completa_y_no_marca_reducido(self):
        r = self._post(reducido=False)
        self.assertEqual(r.status_code, 200, r.content)
        e = EntrenoRealizado.objects.get()
        self.assertEqual(e.estado_cierre, EntrenoRealizado.ESTADO_COMPLETA)
        self.assertFalse(e.modo_reducido)
        self.assertEqual((e.principales_planificados, e.opcionales_planificados), (1, 1))

    def test_principal_sin_hacer_sigue_siendo_parcial_y_pide_motivo(self):
        extra = dict(ej1_completado_1='', ej2_completado_1='1', ej2_rpe_1='8')
        r = self._post(reducido=True, **extra)
        self.assertEqual(r.status_code, 400)
        r = self._post(reducido=True, motivo_cierre='fatiga', **extra)
        self.assertEqual(r.status_code, 200, r.content)
        e = EntrenoRealizado.objects.get()
        self.assertEqual(e.estado_cierre, EntrenoRealizado.ESTADO_PARCIAL)

    def test_pagina_antigua_sin_marca_opcional_usa_es_principal_en_reducido(self):
        data = {k: v for k, v in dict(
            ej1_opcional='', ej2_opcional='').items()}
        d = {
            'fecha': date.today().isoformat(), 'rutina_nombre': self.rutina.nombre, 'modo_reducido': '1',
            'ej1_nombre': 'Sentadilla', 'ej1_tipo_progresion': 'peso_reps', 'ej1_es_principal': '1',
            'ej1_peso_1': '60', 'ej1_reps_1': '5', 'ej1_rpe_1': '8', 'ej1_completado_1': '1',
            'ej2_nombre': 'Curl femoral', 'ej2_tipo_progresion': 'peso_reps', 'ej2_es_principal': '0',
            'ej2_peso_1': '30', 'ej2_reps_1': '10',
        }
        r = self.client.post(self.url, d, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(EntrenoRealizado.objects.get().estado_cierre, EntrenoRealizado.ESTADO_COMPLETA)
