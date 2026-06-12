"""
Phase Evolución UI 2 — Tabs como relatos separados.

Reordena el contenido dentro de cada tab del dashboard de evolución
para que cada uno cuente una historia clara, sin tocar cálculos,
colores ni estética global.
"""

import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog
from rutinas.models import Rutina


class DashboardEvolucionTabsBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_evoui2', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEvoUI2', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_evoui2')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:dashboard_evolucion', kwargs={'cliente_id': self.cliente.id})

    def _add_entreno(self, dias_offset=0, ejercicio='Press banca', peso=40, series=3, reps=8, rpe=7):
        fecha = date.today() - timedelta(days=dias_offset)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=ejercicio,
            peso_kg=peso, series=series, repeticiones=reps, rpe=rpe,
            completado=True, fuente_datos='manual',
        )
        return entreno

    def _get_html(self):
        response = self.client.get(self.url)
        return response, response.content.decode('utf-8')

    def _extraer_tab(self, html, tab_id):
        """Extrae el fragmento HTML de un div#<tab_id> hasta el siguiente bloque de mismo nivel."""
        pattern = re.compile(
            r'<div id="' + re.escape(tab_id) + r'" class="rb-tab-panel".*?'
            r'(?=<!-- (?:CARGA|PROGRESIÓN|RÉCORDS|HISTORIAL) -->|<!-- ── GLOSARIO ── -->)',
            re.DOTALL,
        )
        match = pattern.search(html)
        self.assertIsNotNone(match, f"No se encontró el tab {tab_id}")
        return match.group(0)


class ContextoNuevasLecturasTest(DashboardEvolucionTabsBase):
    """El contexto debe incluir las nuevas lecturas por tab."""

    def test_contexto_incluye_lectura_carga_tab_y_progresion_tab(self):
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)

        response, _ = self._get_html()

        self.assertIn('lectura_carga_tab', response.context)
        self.assertIn('lectura_progresion_tab', response.context)

        lectura_carga = response.context['lectura_carga_tab']
        lectura_progresion = response.context['lectura_progresion_tab']

        self.assertIsInstance(lectura_carga, str)
        self.assertTrue(lectura_carga.strip())

        self.assertIsInstance(lectura_progresion, str)
        self.assertTrue(lectura_progresion.strip())


class LecturasEnTabsTest(DashboardEvolucionTabsBase):
    """Cada lectura debe aparecer dentro de su tab correspondiente."""

    def setUp(self):
        super().setUp()
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)
        self.response, self.html = self._get_html()

    def test_lectura_periodo_en_tab_general(self):
        lectura_periodo = self.response.context['lectura_periodo']
        tab_general = self._extraer_tab(self.html, 'rb-tab-overview')
        self.assertIn(lectura_periodo, tab_general)

    def test_lectura_carga_tab_en_tab_carga(self):
        lectura_carga_tab = self.response.context['lectura_carga_tab']
        tab_carga = self._extraer_tab(self.html, 'rb-tab-carga')
        self.assertIn(lectura_carga_tab, tab_carga)

    def test_lectura_progresion_tab_en_tab_progresion(self):
        lectura_progresion_tab = self.response.context['lectura_progresion_tab']
        tab_progresion = self._extraer_tab(self.html, 'rb-tab-progresion')
        self.assertIn(lectura_progresion_tab, tab_progresion)


class OrdenTabCargaTest(DashboardEvolucionTabsBase):
    """Dentro del tab Carga, 'Series Semanales por Grupo' debe ir antes de 'Equilibrio Muscular'."""

    def test_series_semanales_antes_de_equilibrio_muscular(self):
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)
        _, html = self._get_html()

        tab_carga = self._extraer_tab(html, 'rb-tab-carga')

        idx_series = tab_carga.find('Series Semanales por Grupo')
        idx_equilibrio = tab_carga.find('Equilibrio Muscular')

        self.assertNotEqual(idx_series, -1)
        self.assertNotEqual(idx_equilibrio, -1)
        self.assertLess(idx_series, idx_equilibrio)


class OrdenTabProgresionTest(DashboardEvolucionTabsBase):
    """Dentro del tab Progresión: tabla -> ejercicios a vigilar -> [ajustes] -> proyecciones IA."""

    def setUp(self):
        super().setUp()
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)
        GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='Press banca',
            accion='subir_peso',
            valor_cambio=2.5,
            motivo='Progresión estable en las últimas sesiones',
            confianza='alta',
        )
        self.response, self.html = self._get_html()

    def test_orden_cards_progresion(self):
        tab_progresion = self._extraer_tab(self.html, 'rb-tab-progresion')

        idx_tabla = tab_progresion.find('Progresión de Ejercicios')
        idx_vigilar = tab_progresion.find('Ejercicios a Vigilar')
        idx_proyecciones = tab_progresion.find('Proyecciones IA')

        self.assertNotEqual(idx_tabla, -1)
        self.assertNotEqual(idx_vigilar, -1)
        self.assertNotEqual(idx_proyecciones, -1)

        self.assertLess(idx_tabla, idx_vigilar)
        self.assertLess(idx_vigilar, idx_proyecciones)

        decision_logs = self.response.context['decision_logs']
        self.assertTrue(decision_logs)
        idx_ajustes = tab_progresion.find('Últimos ajustes automáticos')
        self.assertNotEqual(idx_ajustes, -1)
        self.assertLess(idx_ajustes, idx_proyecciones)

    def test_detector_de_estancamientos_renombrado(self):
        self.assertNotIn('Detector de Estancamientos', self.html)
        self.assertIn('Ejercicios a Vigilar', self.html)


class GlosarioColapsableTest(DashboardEvolucionTabsBase):
    """El Glosario Muscular debe aparecer una sola vez, dentro de un <details>."""

    def test_glosario_aparece_una_vez_dentro_de_details(self):
        self._add_entreno(dias_offset=2)
        _, html = self._get_html()

        ocurrencias = [m.start() for m in re.finditer('Glosario Muscular', html)]
        self.assertEqual(len(ocurrencias), 1)

        idx_glosario = ocurrencias[0]
        idx_details = html.rfind('<details', 0, idx_glosario)
        idx_closing_details = html.rfind('</details>', 0, idx_glosario)

        self.assertNotEqual(idx_details, -1, "Glosario Muscular no está dentro de un <details>")
        self.assertGreater(
            idx_details, idx_closing_details,
            "Hay un </details> entre el <details> más cercano y 'Glosario Muscular'"
        )


class LogrosDesbloqueadosColapsableTest(DashboardEvolucionTabsBase):
    """'Ver logros desbloqueados' debe ser un <summary> dentro de <details class="rb-details-plan">."""

    def test_ver_logros_desbloqueados_es_summary_en_details_plan(self):
        self._add_entreno(dias_offset=2)
        _, html = self._get_html()

        match = re.search(
            r'<details class="rb-details-plan"[^>]*>\s*<summary>\s*Ver logros desbloqueados',
            html,
        )
        self.assertIsNotNone(match)


class DesafiosSemanalesVaciosTest(DashboardEvolucionTabsBase):
    """Si no hay desafíos activos, la card 'Desafíos Semanales' no se renderiza."""

    def test_desafios_semanales_no_aparece_sin_desafios_activos(self):
        self._add_entreno(dias_offset=2)
        response, html = self._get_html()

        self.assertEqual(list(response.context['desafios_activos']), [])
        self.assertNotIn('Desafíos Semanales', html)
