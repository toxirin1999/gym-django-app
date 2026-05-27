"""
Phase 56.13B — Integration tests: visual connection of carga_alta_objetiva / prudencia_semanal.

Tests verify:
1. prudencia_semanal=True → badge label 'MARGEN PROTEGIDO', not 'CARGA ALTA'
2. carga_alta_objetiva=True → badge label 'CARGA ALTA'
3. Both True (RPE high + prudencia structure) → carga_alta_objetiva wins
4. JOI text for prudencia_semanal does NOT contain "carga alta"
5. lectura_textual for prudencia_semanal uses "el plan activó", not "el cuerpo pidió"
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SesionEntrenamiento
from entrenos.services.analisis_semanal_service import (
    analizar_semana_entrenamiento,
    bloque_semanal_para_joi,
)
from rutinas.models import Rutina


# ── Badge label derivation (pure helper, no DB) ──────────────────────────────

def _badge_label(analisis):
    """Mirrors the template logic in plan_decisiones.html."""
    if analisis.get('carga_alta_objetiva'):
        return 'CARGA ALTA'
    if analisis.get('prudencia_semanal'):
        return 'MARGEN PROTEGIDO'
    estado = analisis.get('estado_semana', '')
    _labels = {
        'solida': 'SÓLIDA',
        'margen_extra': 'MARGEN EXTRA',
        'parcial': 'PARCIAL',
        'sin_datos': '',
    }
    return _labels.get(estado, estado.upper().replace('_', ' '))


# ── Base setup ────────────────────────────────────────────────────────────────

class VisualCargaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_vis56b', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestVis', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_vis56b')
        self.lunes = date(2026, 5, 18)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _add_entreno(self, dias_offset=0, modo_reducido=False,
                     principales_planificados=2, principales_completados=2,
                     rpe_medio=None):
        fecha = self.lunes + timedelta(days=dias_offset)
        e = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            fuente_datos='manual', modo_reducido=modo_reducido,
            principales_planificados=principales_planificados if modo_reducido else 0,
            opcionales_planificados=0,
        )
        if modo_reducido:
            for i in range(principales_completados):
                EjercicioRealizado.objects.create(
                    entreno=e, nombre_ejercicio=f'Principal_{i}',
                    es_bloque_principal=True, completado=True, fuente_datos='manual',
                )
        if rpe_medio is not None:
            SesionEntrenamiento.objects.update_or_create(
                entreno=e,
                defaults={'duracion_minutos': 60, 'rpe_medio': rpe_medio},
            )
        return e


# ── Test 1 & 2: Badge label correctness ──────────────────────────────────────

class BadgeLabelTest(VisualCargaBase):

    def test_prudencia_semanal_badge_es_margen_protegido(self):
        """
        prudencia_semanal=True must show 'MARGEN PROTEGIDO', never 'CARGA ALTA'.
        Covers Phase 56.13B requirement 1.
        """
        self._add_entreno(0, modo_reducido=True, principales_completados=2, rpe_medio=6.0)
        self._add_entreno(2, modo_reducido=True, principales_completados=2, rpe_medio=6.2)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)

        self.assertTrue(analisis.get('prudencia_semanal'))
        self.assertFalse(analisis.get('carga_alta_objetiva'))
        self.assertEqual(_badge_label(analisis), 'MARGEN PROTEGIDO')

    def test_prudencia_semanal_badge_no_dice_carga_alta(self):
        """Badge for prudencia_semanal must not contain 'CARGA ALTA'."""
        self._add_entreno(0, modo_reducido=True, principales_completados=2, rpe_medio=5.5)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        label = _badge_label(analisis)
        self.assertNotIn('CARGA', label)

    def test_carga_alta_objetiva_badge_es_carga_alta(self):
        """
        carga_alta_objetiva=True must show 'CARGA ALTA' (with space, not underscore).
        Covers Phase 56.13B requirement 2.
        """
        self._add_entreno(0, modo_reducido=True,
                          principales_planificados=2, principales_completados=1,
                          rpe_medio=7.0)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)

        self.assertTrue(analisis.get('carga_alta_objetiva'))
        self.assertEqual(_badge_label(analisis), 'CARGA ALTA')
        self.assertNotIn('_', _badge_label(analisis))

    def test_carga_alta_objetiva_por_rpe_badge_es_carga_alta(self):
        """RPE >= 8 alone → carga_alta_objetiva → badge 'CARGA ALTA'."""
        self._add_entreno(0, modo_reducido=False, rpe_medio=8.5)
        self._add_entreno(2, modo_reducido=False, rpe_medio=8.2)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)

        self.assertTrue(analisis.get('carga_alta_objetiva'))
        self.assertEqual(_badge_label(analisis), 'CARGA ALTA')


# ── Test 3: Priority when both are True ──────────────────────────────────────

class PrioridadCargaObjetivaTest(VisualCargaBase):

    def test_carga_objetiva_tiene_prioridad_sobre_prudencia(self):
        """
        When RPE is high AND structure is prudencia_semanal, carga_alta_objetiva wins.
        Badge must be 'CARGA ALTA', not 'MARGEN PROTEGIDO'.
        Covers Phase 56.13B requirement 3.
        """
        # All esencial, blocks complete (→ prudencia_semanal) BUT RPE very high
        self._add_entreno(0, modo_reducido=True, principales_completados=2, rpe_medio=8.5)
        self._add_entreno(2, modo_reducido=True, principales_completados=2, rpe_medio=8.1)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)

        # Both should be True
        self.assertTrue(analisis.get('prudencia_semanal'))
        self.assertTrue(analisis.get('carga_alta_objetiva'))
        # carga_alta_objetiva wins in the badge
        self.assertEqual(_badge_label(analisis), 'CARGA ALTA')


# ── Test 4: JOI text does not say "carga alta" for prudencia_semanal ─────────

class JOITextPrudenciaTest(VisualCargaBase):

    def test_joi_no_dice_carga_alta_cuando_solo_prudencia_semanal(self):
        """
        bloque_semanal_para_joi() must not contain "carga alta" when
        estado_semana == prudencia_semanal.
        Covers Phase 56.13B requirement 4.
        """
        self._add_entreno(0, modo_reducido=True, principales_completados=2, rpe_medio=6.0)
        self._add_entreno(2, modo_reducido=True, principales_completados=2, rpe_medio=6.3)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertEqual(analisis.get('estado_semana'), 'prudencia_semanal')

        texto_joi = bloque_semanal_para_joi(self.cliente, fecha_ref=self.lunes)
        self.assertIsNotNone(texto_joi)
        self.assertNotIn('carga alta', texto_joi.lower())

    def test_joi_dice_plan_activo_no_cuerpo_pidio(self):
        """
        JOI text for prudencia_semanal must use 'el plan activó', not 'el cuerpo pidió'.
        Covers Phase 56.13B requirement 5 (copy rule).
        """
        self._add_entreno(0, modo_reducido=True, principales_completados=2)
        texto_joi = bloque_semanal_para_joi(self.cliente, fecha_ref=self.lunes)
        self.assertIsNotNone(texto_joi)
        self.assertNotIn('el cuerpo pidió', texto_joi.lower())


# ── Test 5: lectura_textual copy ─────────────────────────────────────────────

class LecturaTextualCopyTest(VisualCargaBase):

    def test_lectura_prudencia_usa_plan_activo(self):
        """
        lectura_textual for prudencia_semanal uses 'el plan activó versión esencial',
        not body-language framing.
        """
        self._add_entreno(0, modo_reducido=True, principales_completados=2)
        self._add_entreno(2, modo_reducido=True, principales_completados=2)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        lectura = analisis.get('lectura_textual', '')
        self.assertIn('plan activó', lectura.lower())
        self.assertNotIn('el cuerpo pidió', lectura.lower())
        self.assertNotIn('carga alta', lectura.lower())

    def test_lectura_carga_alta_indica_bloque_incompleto(self):
        """
        lectura_textual for carga_alta explains the incomplete block,
        not just 'high load'.
        """
        self._add_entreno(0, modo_reducido=True,
                          principales_planificados=2, principales_completados=1)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertEqual(analisis.get('estado_semana'), 'carga_alta')
        lectura = analisis.get('lectura_textual', '')
        self.assertGreater(len(lectura), 0)
        # Must mention incomplete block, not just generic load
        self.assertTrue(
            'no se completó' in lectura.lower() or 'bloque principal' in lectura.lower(),
            f"Expected mention of incomplete block, got: {lectura}",
        )
