"""
Phase Métrica Perfección 1 — Renombrar porcentaje_perfeccion a "Completitud
de sesión".

`porcentaje_perfeccion` no mide excelencia del entrenamiento: mide si la
sesión quedó estructuralmente completa (series_completadas == series_totales).
Tras Phase Evolución Data 5B, la mayoría de sesiones marcan 100% — un nombre
como "Eficiencia"/"Perfección" se leería como "entrenaste óptimamente", lo
que no es lo que mide.

Cubre:
1. `CalculoPorcentajePerfeccionSinCambiosTest`: el cálculo de
   sesiones_perfectas/porcentaje_perfeccion (estadisticas_service.py) no
   cambia — esta fase es solo de copy/contrato visible.
2. `DashboardCompletitudLabelTest`: el dashboard ya no muestra "Eficiencia"
   como etiqueta de esa métrica; muestra "Completitud".
3. `DashboardCompletitudTextoAclaratorioTest`: aparece un texto aclaratorio
   que explica qué mide ("sesiones completas"... "no mide carga, RPE ni
   ejecución").
4. `DashboardSinLenguajePerfeccionVisibleTest`: no queda "perfección"/
   "perfecta" visible en el dashboard.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.estadisticas_service import EstadisticasService
from entrenos.tests_dashboard_evolucion_historial import DashboardEvolucionHistorialBase
from rutinas.models import Rutina


class CalculoPorcentajePerfeccionSinCambiosTest(TestCase):
    """Test 1: la fórmula de sesiones_perfectas/porcentaje_perfeccion no cambia."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_metrica_completitud', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestMetricaCompletitud', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_metrica_completitud')

    def test_sesion_completa_cuenta_como_perfecta(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Sentadilla',
            peso_kg=100, series=3, repeticiones=5, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 300
        entreno.duracion_minutos = 30
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        call_command('backfill_sesion_entrenamiento', stdout=StringIO())

        stats = EstadisticasService.calcular_estadisticas_globales(self.cliente, rango='todo')

        self.assertEqual(stats['sesiones_perfectas'], 1)
        self.assertEqual(stats['porcentaje_perfeccion'], 100.0)


class DashboardCompletitudLabelTest(DashboardEvolucionHistorialBase):
    """Test 2: el dashboard ya no muestra "Eficiencia" para esta métrica; muestra "Completitud"."""

    def test_label_completitud_no_eficiencia(self):
        self._add_entreno_normal(dias_offset=0)
        _, html = self._get_html()

        self.assertIn('Completitud', html)
        self.assertNotIn('>Eficiencia<', html)


class DashboardCompletitudTextoAclaratorioTest(DashboardEvolucionHistorialBase):
    """Test 3/4: aparece texto aclaratorio sobre qué mide la completitud."""

    def test_texto_aclaratorio_presente(self):
        self._add_entreno_normal(dias_offset=0)
        _, html = self._get_html()

        self.assertIn('sesiones completas', html.lower())
        self.assertIn('no mide carga, rpe ni ejecución', html.lower())


class DashboardSinLenguajePerfeccionVisibleTest(DashboardEvolucionHistorialBase):
    """Test 4: no queda "perfección"/"perfecta" visible en el dashboard."""

    def test_sin_perfeccion_visible(self):
        self._add_entreno_normal(dias_offset=0)
        _, html = self._get_html()

        html_lower = html.lower()
        self.assertNotIn('perfecci', html_lower)
        self.assertNotIn('perfecta', html_lower)
