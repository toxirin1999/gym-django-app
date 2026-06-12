"""
Phase Evolución UI 3 — Historial fiable y sesiones incompletas.

Cubre:
1-2. `EntrenoRealizado.es_sesion_incompleta` (property).
3-5. Render del tab Historial: chip neutro para sesiones incompletas,
     sin chips normales, sin regresión para sesiones normales.
6. Contrato: sesiones incompletas no contaminan progresion_ejercicios,
   estancamientos/coach_data ni decision_logs.
7-8. `actividad_anual_data` como lista de dicts + empty state del heatmap.
"""

import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SesionEntrenamiento
from rutinas.models import Rutina


class EsSesionIncompletaModelTest(TestCase):
    """Tests 1 y 2: la property `es_sesion_incompleta`."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_evoui3_model', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEvoUI3Model', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_evoui3_model')

    def test_sesion_sin_ejercicios_es_incompleta(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=0, volumen_total_kg=0,
        )
        self.assertTrue(entreno.es_sesion_incompleta)

    def test_sesion_con_ejercicios_no_es_incompleta(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press banca',
            peso_kg=40, series=3, repeticiones=8, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = entreno.calcular_volumen_total()
        entreno.save()

        self.assertFalse(entreno.es_sesion_incompleta)


class DashboardEvolucionHistorialBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_evoui3', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEvoUI3', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_evoui3')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:dashboard_evolucion', kwargs={'cliente_id': self.cliente.id})

    def _add_entreno_normal(self, dias_offset=0, ejercicio='Press banca', peso=40, series=3, reps=8, rpe=7):
        fecha = date.today() - timedelta(days=dias_offset)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=ejercicio,
            peso_kg=peso, series=series, repeticiones=reps, rpe=rpe,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = entreno.calcular_volumen_total()
        entreno.save()
        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={
                'duracion_minutos': 45,
                'ejercicios_completados': 1,
                'ejercicios_totales': 1,
                'volumen_sesion': entreno.volumen_total_kg,
                'rpe_medio': rpe,
            },
        )
        return entreno

    def _add_entreno_incompleto(self, dias_offset=0):
        fecha = date.today() - timedelta(days=dias_offset)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, fuente_datos='manual',
            numero_ejercicios=0, volumen_total_kg=0,
        )
        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={
                'duracion_minutos': 0,
                'ejercicios_completados': 0,
                'ejercicios_totales': 0,
                'volumen_sesion': 0,
            },
        )
        return entreno

    def _get_html(self):
        response = self.client.get(self.url)
        return response, response.content.decode('utf-8')

    def _extraer_tab(self, html, tab_id):
        pattern = re.compile(
            r'<div id="' + re.escape(tab_id) + r'" class="rb-tab-panel".*?'
            r'(?=<!-- (?:CARGA|PROGRESIÓN|RÉCORDS|HISTORIAL) -->|<!-- ── GLOSARIO ── -->)',
            re.DOTALL,
        )
        match = pattern.search(html)
        self.assertIsNotNone(match, f"No se encontró el tab {tab_id}")
        return match.group(0)


class ChipSesionIncompletaTest(DashboardEvolucionHistorialBase):
    """Tests 3 y 4: render del chip neutro para sesiones incompletas."""

    def test_muestra_chip_sesion_abierta_sin_ejercicios(self):
        self._add_entreno_incompleto(dias_offset=0)
        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')
        self.assertIn('Sesión abierta sin ejercicios registrados', tab_historial)

    def test_no_muestra_chips_normales_para_sesion_incompleta(self):
        self._add_entreno_incompleto(dias_offset=0)
        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        # No deben aparecer los chips de duración/ejercicios/volumen como si fuera normal
        self.assertNotIn('0/0', tab_historial)
        self.assertNotIn('0 min', tab_historial)
        self.assertNotIn('fa-dumbbell', tab_historial)
        self.assertNotIn('fa-weight-hanging', tab_historial)


class ChipSesionNormalSinRegresionTest(DashboardEvolucionHistorialBase):
    """Test 5: las sesiones normales siguen mostrando sus chips habituales."""

    def test_sesion_normal_muestra_chips_habituales(self):
        self._add_entreno_normal(dias_offset=0)
        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        self.assertIn('fa-clock', tab_historial)
        self.assertIn('fa-dumbbell', tab_historial)
        self.assertIn('fa-weight-hanging', tab_historial)
        self.assertIn('1/1', tab_historial)
        self.assertNotIn('Sesión abierta sin ejercicios registrados', tab_historial)


class NoContaminacionContratoTest(TestCase):
    """Test 6: una sesión incompleta no altera progresion_ejercicios,
    estancamientos/coach_data ni decision_logs."""

    def _build_cliente(self, username):
        user = User.objects.create_user(username=username, password='x')
        cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': username, 'dias_disponibles': 3},
        )
        rutina, _ = Rutina.objects.get_or_create(nombre='_test_evoui3_contrato')
        return user, cliente, rutina

    def _poblar_datos_normales(self, cliente, rutina):
        for offset in (2, 9, 16):
            entreno = EntrenoRealizado.objects.create(
                cliente=cliente, rutina=rutina,
                fecha=date.today() - timedelta(days=offset),
                fuente_datos='manual',
            )
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio='Press banca',
                peso_kg=40, series=3, repeticiones=8, rpe=7,
                completado=True, fuente_datos='manual',
            )
            entreno.numero_ejercicios = 1
            entreno.volumen_total_kg = entreno.calcular_volumen_total()
            entreno.save()

    def test_sesion_incompleta_no_altera_contexto_analitico(self):
        # Cliente A: solo sesiones normales
        _, cliente_a, rutina_a = self._build_cliente('tester_evoui3_a')
        self._poblar_datos_normales(cliente_a, rutina_a)

        # Cliente B: mismas sesiones normales + una sesión incompleta extra
        _, cliente_b, rutina_b = self._build_cliente('tester_evoui3_b')
        self._poblar_datos_normales(cliente_b, rutina_b)
        EntrenoRealizado.objects.create(
            cliente=cliente_b, rutina=rutina_b, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=0, volumen_total_kg=0,
        )

        client_a = self.client_class()
        client_a.force_login(cliente_a.user)
        url_a = reverse('entrenos:dashboard_evolucion', kwargs={'cliente_id': cliente_a.id})
        resp_a = client_a.get(url_a)

        client_b = self.client_class()
        client_b.force_login(cliente_b.user)
        url_b = reverse('entrenos:dashboard_evolucion', kwargs={'cliente_id': cliente_b.id})
        resp_b = client_b.get(url_b)

        self.assertEqual(resp_a.context['progresion_ejercicios'], resp_b.context['progresion_ejercicios'])
        self.assertEqual(resp_a.context['estancamientos'], resp_b.context['estancamientos'])
        self.assertEqual(
            resp_a.context['coach_data']['ejercicios_estancados'],
            resp_b.context['coach_data']['ejercicios_estancados'],
        )

        decision_logs_a = list(resp_a.context['decision_logs'])
        decision_logs_b = list(resp_b.context['decision_logs'])
        self.assertEqual(len(decision_logs_a), len(decision_logs_b))


class ActividadAnualDataTest(DashboardEvolucionHistorialBase):
    """Tests 7 y 8: actividad_anual_data como lista de dicts + empty state."""

    def test_actividad_anual_data_es_lista_de_dicts(self):
        self._add_entreno_normal(dias_offset=0)
        response, html = self._get_html()

        actividad = response.context['actividad_anual_data']
        self.assertIsInstance(actividad, list)
        for item in actividad:
            self.assertIn('fecha', item)
            self.assertIn('count', item)

        # No debe lanzar error al renderizar
        self.assertEqual(response.status_code, 200)

    def test_actividad_anual_data_renderiza_heatmap_cuando_hay_actividad(self):
        self._add_entreno_normal(dias_offset=0)
        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')
        self.assertIn('id="ev-heatmap"', tab_historial)
        self.assertNotIn('Sin actividad registrada este año', tab_historial)

    def test_empty_state_sin_actividad_en_el_ano(self):
        # Sin ningún EntrenoRealizado en los últimos 365 días
        response, html = self._get_html()

        self.assertEqual(response.context['actividad_anual_data'], [])

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')
        self.assertIn('Sin actividad registrada este año', tab_historial)
        self.assertNotIn('id="ev-heatmap"', tab_historial)
