"""
Briefing — tempo y calentamiento visibles antes de empezar la sesión.

Bug reportado: en /entrenos/cliente/<id>/briefing/ no aparecían ni el tempo
("3-1-1") ni el calentamiento (aproximaciones al peso de trabajo) de los
ejercicios del plan, independientemente de si la sesión era "esencial" o no.

Causa: el dict de cada ejercicio (generado por PlanificadorHelms) ya incluye
'tempo', pero el template nunca lo renderiza. 'aproximaciones' (calentamiento)
solo se calculaba en entrenamiento_activo, nunca en briefing_entrenamiento.

Fix:
  - briefing_entrenamiento (views.py) calcula ej['aproximaciones'] con
    get_aproximaciones_calentamiento, igual que entrenamiento_activo.
  - el template muestra el tempo en un <span class="plan-tempo"> y, si hay
    aproximaciones, un <div class="plan-warmup"> con los 3 pesos.

Nota: no se busca '3-1-1'/'tempo' a pelo en todo el HTML porque el botón
"Comenzar sesión" enlaza a una URL con el JSON del plan urlencodeado, que
puede contener esas mismas subcadenas sin que se hayan renderizado en el
"Plan de sesión". Por eso se comprueba contra las clases CSS específicas.

Checklist:
  1. Ejercicio con 'tempo' → aparece <span class="plan-tempo"> con "3-1-1".
  2. Ejercicio sin 'tempo' → no aparece <span class="plan-tempo">.
  3. Ejercicio con peso de trabajo > 0 → aparece <div class="plan-warmup">
     con los 3 pesos calculados por get_aproximaciones_calentamiento.
  4. Ejercicio sin peso (peso_kg=0, p.ej. peso corporal) → no aparece
     <div class="plan-warmup">.
"""

import json
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento

_FECHA = date.today().strftime('%Y-%m-%d')


class BriefingTempoCalentamientoBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('tester_briefing_tempo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def _get(self, ejercicios):
        # El nuevo mecanismo (fix 414) lee ejercicios del cache de transporte,
        # no de la query string. Poblamos la clave determinista aquí.
        _key = f"transporte_ejercicios_dia_{self.cliente.id}_{_FECHA}"
        cache.set(_key, ejercicios, 900)
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        return self.client.get(url, {'fecha': _FECHA, 'rutina_nombre': 'Día 1 - Fuerza'})


class TestTempoVisible(BriefingTempoCalentamientoBase):
    def test_muestra_tempo_cuando_existe(self):
        ejercicios = [{
            'nombre': 'Press Banca con Mancuernas',
            'series': 4, 'repeticiones': '3-5',
            'peso_kg': 102.5, 'rpe_objetivo': 8,
            'tempo': '3-1-1',
            'tipo_progresion': 'peso_reps',
        }]
        resp = self._get(ejercicios)
        self.assertEqual(resp.status_code, 200)
        contenido = resp.content.decode()
        self.assertIn('class="plan-tempo"', contenido)
        self.assertIn('3-1-1', contenido)


class TestSinTempoNoMuestraEtiqueta(BriefingTempoCalentamientoBase):
    def test_sin_tempo_no_muestra_bloque_tempo(self):
        ejercicios = [{
            'nombre': 'Press Banca con Mancuernas',
            'series': 4, 'repeticiones': '3-5',
            'peso_kg': 102.5, 'rpe_objetivo': 8,
            'tipo_progresion': 'peso_reps',
        }]
        resp = self._get(ejercicios)
        contenido = resp.content.decode()
        self.assertNotIn('class="plan-tempo"', contenido)


class TestCalentamientoVisibleConPeso(BriefingTempoCalentamientoBase):
    def test_muestra_calentamiento_con_pesos_calculados(self):
        ejercicios = [{
            'nombre': 'Press Banca con Mancuernas',
            'series': 4, 'repeticiones': '3-5',
            'peso_kg': 102.5, 'rpe_objetivo': 8,
            'tempo': '3-1-1',
            'tipo_progresion': 'peso_reps',
        }]
        resp = self._get(ejercicios)
        contenido = resp.content.decode()
        self.assertIn('class="plan-warmup"', contenido)

        esperado = get_aproximaciones_calentamiento(102.5, True)
        for peso in esperado.values():
            texto_peso = (f"{peso:.0f}" if peso == int(peso) else f"{peso:g}")
            self.assertIn(texto_peso, contenido)


class TestSinPesoNoMuestraCalentamiento(BriefingTempoCalentamientoBase):
    def test_ejercicio_peso_corporal_sin_calentamiento(self):
        ejercicios = [{
            'nombre': 'Fondos en Paralelas',
            'series': 4, 'repeticiones': '8-12',
            'peso_kg': 0, 'rpe_objetivo': 8,
            'tipo_progresion': 'peso_corporal_lastre',
        }]
        resp = self._get(ejercicios)
        contenido = resp.content.decode()
        self.assertNotIn('class="plan-warmup"', contenido)
