"""
Phase Evolución UI 1 — Jerarquía analítica mínima.

Principio: Dashboard Evolución es memoria analítica, no un segundo panel
operativo. Se sustituye "01 Coach IA" + "02 Próxima acción" por
"01 · Lectura del periodo" (3 cards + derivado del análisis + detalle
técnico colapsable) y "02 · Resumen ejecutivo" (cards de KPIs), antes
de "03 Dashboard" (tabs, sin cambios).
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from rutinas.models import Rutina


class DashboardEvolucionJerarquiaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_evoui1', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEvoUI1', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_evoui1')
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


class ContextoCalculosTest(DashboardEvolucionJerarquiaBase):
    """El contexto debe incluir los nuevos valores calculados en la vista."""

    def test_contexto_incluye_grupos_volumen_bajo_y_lectura_periodo(self):
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('grupos_volumen_bajo', response.context)
        self.assertIn('lectura_periodo', response.context)

        self.assertIsInstance(response.context['grupos_volumen_bajo'], int)

        lectura = response.context['lectura_periodo']
        self.assertIsInstance(lectura, str)
        self.assertTrue(lectura.strip())


class EstructuraSeccionesTest(DashboardEvolucionJerarquiaBase):
    """Las secciones 01 y 02 deben tener los nuevos títulos."""

    def setUp(self):
        super().setUp()
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)
        self.response = self.client.get(self.url)
        self.html = self.response.content.decode('utf-8')

    def test_seccion_01_es_lectura_del_periodo(self):
        self.assertIn('Lectura del periodo', self.html)

    def test_seccion_02_es_resumen_ejecutivo(self):
        self.assertIn('Resumen ejecutivo', self.html)

    def test_no_quedan_titulos_coach_ia_ni_proxima_accion_de_primer_nivel(self):
        """
        'Coach IA' y 'Próxima acción' pueden seguir existiendo como texto
        dentro de <details> (detalle técnico / plan completo), pero no
        deben renderizarse como rb-section-title de primer nivel.
        """
        import re

        section_titles = re.findall(r'<h2 class="rb-section-title">(.*?)</h2>', self.html, re.DOTALL)
        section_titles = [t.strip() for t in section_titles]

        self.assertNotIn('Coach IA', section_titles)
        self.assertNotIn('Próxima acción', section_titles)


class DetailsBlocksTest(DashboardEvolucionJerarquiaBase):
    """Los bloques de detalle deben estar dentro de <details> colapsables."""

    def setUp(self):
        super().setUp()
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)
        self.response = self.client.get(self.url)
        self.html = self.response.content.decode('utf-8')

    def test_existe_details_detalle_tecnico(self):
        self.assertIn('<details', self.html)
        self.assertIn('Ver detalle técnico del análisis', self.html)

    def test_existe_details_plan_de_accion_completo_si_plan_accion_truthy(self):
        plan_accion = self.response.context['plan_accion']
        if plan_accion:
            self.assertIn('Ver plan de acción completo', self.html)


class PrecisionSistemaCardTest(DashboardEvolucionJerarquiaBase):
    """La card de precisión del sistema solo aparece si hay datos significativos."""

    def test_card_precision_no_aparece_si_totales_es_cero(self):
        self._add_entreno(dias_offset=2)
        self._add_entreno(dias_offset=9)

        response = self.client.get(self.url)
        html = response.content.decode('utf-8')

        precision_sistema = response.context['precision_sistema']
        self.assertEqual(precision_sistema['totales'], 0)

        # No debe renderizarse el chip de precisión del sistema.
        self.assertNotIn('Precisión {{ precision_sistema.precision }}%', html)
        import re
        self.assertNotIn('Precisión 0%', html)
