"""
Phase 56.13 — Semantic boundary tests: carga_alta_objetiva vs prudencia_semanal.

ARCHITECTURAL INVARIANT:
    La reducción repetida puede pedir prudencia; no puede probar por sí sola
    que la carga era alta.

CARGA_ALTA_OBJETIVA requires at least one external signal:
    - bloques_principales_parciales > 0  (user couldn't finish main block)
    - rpe_medio_semana >= 8              (physiological overload signal)
    [future: ACWR > 1.5, TSB < -20, molestias, actividad externa fuerte]

PRUDENCIA_SEMANAL:
    - sesiones_esenciales > 0 AND bloques_principales_parciales == 0
    - No external high-load signals

The tests in Group A test the PURE function _clasificar_estado (no DB).
The tests in Group B test analizar_semana_entrenamiento end-to-end (DB).
Group B tests for carga_alta_objetiva FAIL until the service adds that field.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, SesionEntrenamiento
from entrenos.services.analisis_semanal_service import (
    _clasificar_estado,
    analizar_semana_entrenamiento,
)
from rutinas.models import Rutina


# ═══════════════════════════════════════════════════════════════
# GROUP A — Pure _clasificar_estado (no DB, fast)
# ═══════════════════════════════════════════════════════════════

class ClasificarEstadoBoundaryTest(TestCase):
    """
    Validates the semantic boundary of _clasificar_estado.
    All tests are pure (no DB access).
    """

    def _clasificar(self, **kwargs):
        defaults = {
            'sesiones_completadas': 2,
            'sesiones_normales': 0,
            'sesiones_esenciales': 2,
            'bloques_principales_completos': 2,
            'bloques_principales_parciales': 0,
            'pct_principal_medio': 100,
            'pct_opcional_medio': None,
        }
        defaults.update(kwargs)
        return _clasificar_estado(**defaults)

    def test_dos_esenciales_bloques_completos_no_es_carga_alta(self):
        """
        CORE INVARIANT: Two esencial sessions with complete blocks ≠ carga_alta.
        Breaks the circular argument: plan reduces → calls it carga_alta because it reduced.
        """
        estado, _, _, _ = self._clasificar()
        self.assertNotEqual(
            estado, 'carga_alta',
            "Two esencial sessions with complete blocks must not be carga_alta. "
            "The plan reducing IS NOT evidence that load was high.",
        )

    def test_dos_esenciales_bloques_completos_es_prudencia_semanal(self):
        """Two esencial sessions, complete blocks → prudencia_semanal."""
        estado, _, _, _ = self._clasificar()
        self.assertEqual(estado, 'prudencia_semanal')

    def test_tres_esenciales_bloques_completos_es_prudencia_semanal(self):
        """Generalisation: any N esencial with zero partial blocks → prudencia_semanal."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=3, sesiones_esenciales=3,
            bloques_principales_completos=3,
        )
        self.assertEqual(estado, 'prudencia_semanal')

    def test_bloque_principal_parcial_es_carga_alta(self):
        """
        Incomplete main block IS real structural evidence of overload → carga_alta.
        This is NOT circular: the user literally could not finish the plan's minimum.
        """
        estado, _, _, _ = self._clasificar(
            bloques_principales_parciales=1,
            bloques_principales_completos=1,
        )
        self.assertEqual(estado, 'carga_alta')

    def test_un_parcial_entre_tres_esenciales_es_carga_alta(self):
        """Even one partial block among three esenciales → carga_alta."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=3, sesiones_esenciales=3,
            bloques_principales_completos=2, bloques_principales_parciales=1,
        )
        self.assertEqual(estado, 'carga_alta')

    def test_semana_normal_sin_esencial_sin_parcial_es_solida(self):
        """Full normal sessions, no esencial, no partial → solida (not carga_alta)."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=3, sesiones_normales=3, sesiones_esenciales=0,
            bloques_principales_completos=0, bloques_principales_parciales=0,
            pct_principal_medio=None, pct_opcional_medio=None,
        )
        self.assertNotEqual(estado, 'carga_alta')
        self.assertEqual(estado, 'solida')

    def test_semana_con_margen_alto_es_margen_extra_no_carga_alta(self):
        """Normal sessions + high optional completion → margen_extra, never carga_alta."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=3, sesiones_normales=3, sesiones_esenciales=0,
            bloques_principales_completos=0, bloques_principales_parciales=0,
            pct_principal_medio=None, pct_opcional_medio=80,
        )
        self.assertNotEqual(estado, 'carga_alta')
        self.assertEqual(estado, 'margen_extra')

    def test_semana_mixta_sin_parcial_no_es_carga_alta(self):
        """Normal + esencial sessions, all blocks complete → NOT carga_alta."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=3, sesiones_normales=1, sesiones_esenciales=2,
            bloques_principales_completos=2, bloques_principales_parciales=0,
        )
        self.assertNotEqual(estado, 'carga_alta')

    def test_cero_sesiones_es_sin_datos(self):
        """No sessions at all → sin_datos."""
        estado, _, _, _ = self._clasificar(
            sesiones_completadas=0, sesiones_normales=0, sesiones_esenciales=0,
            bloques_principales_completos=0, bloques_principales_parciales=0,
            pct_principal_medio=None, pct_opcional_medio=None,
        )
        self.assertEqual(estado, 'sin_datos')


# ═══════════════════════════════════════════════════════════════
# GROUP B — analizar_semana_entrenamiento end-to-end (DB tests)
# These tests for carga_alta_objetiva FAIL until the service adds
# that field and RPE computation.
# ═══════════════════════════════════════════════════════════════

class CargaAltaObjetivaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_carga56', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCarga', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_carga56')
        # Pin to a Monday so fecha_ref is deterministic
        self.lunes = date(2026, 5, 18)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _add_entreno(self, dias_offset=0, modo_reducido=False,
                     principales_planificados=2, principales_completados=2,
                     opcionales_planificados=1, opcionales_completados=0,
                     rpe_medio=None):
        """
        Creates EntrenoRealizado + EjercicioRealizado records.
        calcular_bloque_esencial counts EjercicioRealizado with es_bloque_principal=True
        and compares against EntrenoRealizado.principales_planificados.
        """
        fecha = self.lunes + timedelta(days=dias_offset)
        e = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=fecha,
            fuente_datos='manual',
            modo_reducido=modo_reducido,
            principales_planificados=principales_planificados if modo_reducido else 0,
            opcionales_planificados=opcionales_planificados if modo_reducido else 0,
        )
        # Create principal exercise records for calcular_bloque_esencial
        if modo_reducido:
            for i in range(principales_completados):
                EjercicioRealizado.objects.create(
                    entreno=e,
                    nombre_ejercicio=f'Principal_{i}',
                    es_bloque_principal=True,
                    completado=True,
                    fuente_datos='manual',
                )
            for i in range(opcionales_completados):
                EjercicioRealizado.objects.create(
                    entreno=e,
                    nombre_ejercicio=f'Opcional_{i}',
                    es_bloque_principal=False,
                    completado=True,
                    fuente_datos='manual',
                )
        if rpe_medio is not None:
            SesionEntrenamiento.objects.update_or_create(
                entreno=e,
                defaults={'duracion_minutos': 60, 'rpe_medio': rpe_medio},
            )
        return e


class CargaAltaObjetivaCampoExisteTest(CargaAltaObjetivaBase):
    """
    analizar_semana_entrenamiento must return 'carga_alta_objetiva' and
    'prudencia_semanal' as explicit boolean fields.
    These tests FAIL until the service adds those fields.
    """

    def test_retorno_contiene_campo_carga_alta_objetiva(self):
        """
        analizar_semana_entrenamiento must include 'carga_alta_objetiva' bool.
        FAILS until the field is added to the return dict.
        """
        self._add_entreno(dias_offset=0, modo_reducido=True)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertIn(
            'carga_alta_objetiva', analisis,
            "analizar_semana_entrenamiento must return 'carga_alta_objetiva'.",
        )

    def test_retorno_contiene_campo_prudencia_semanal(self):
        """
        analizar_semana_entrenamiento must include 'prudencia_semanal' bool.
        FAILS until the field is added.
        """
        self._add_entreno(dias_offset=0, modo_reducido=True)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertIn(
            'prudencia_semanal', analisis,
            "analizar_semana_entrenamiento must return 'prudencia_semanal'.",
        )

    def test_retorno_contiene_motivo_carga(self):
        """
        analizar_semana_entrenamiento must include 'motivo_carga' (str|None).
        FAILS until the field is added.
        """
        self._add_entreno(dias_offset=0, modo_reducido=True)
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertIn('motivo_carga', analisis)


class DosEsencialesMetricasEstablesTest(CargaAltaObjetivaBase):
    """
    CORE SCENARIO: Two esencial sessions, blocks complete, RPE < 7.
    → carga_alta_objetiva = False
    → prudencia_semanal   = True
    """

    def setUp(self):
        super().setUp()
        # Two esencial sessions, main block complete, RPE comfortable
        self._add_entreno(dias_offset=0, modo_reducido=True,
                          principales_planificados=2, principales_completados=2,
                          rpe_medio=6.0)
        self._add_entreno(dias_offset=2, modo_reducido=True,
                          principales_planificados=2, principales_completados=2,
                          rpe_medio=6.2)

    def test_dos_esenciales_no_carga_alta_objetiva(self):
        """
        INVARIANT: Two esencial sessions + RPE 6 + blocks complete
        must NOT produce carga_alta_objetiva.
        FAILS until the field exists in the service.
        """
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertFalse(
            analisis.get('carga_alta_objetiva'),
            "Two esencial sessions with stable metrics must not flag carga_alta_objetiva.",
        )

    def test_dos_esenciales_si_prudencia_semanal(self):
        """
        Two esencial sessions + blocks complete → prudencia_semanal = True.
        FAILS until the field exists.
        """
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertTrue(
            analisis.get('prudencia_semanal'),
            "Two esencial sessions with complete blocks must set prudencia_semanal=True.",
        )

    def test_estado_semana_es_prudencia_semanal(self):
        """estado_semana must be 'prudencia_semanal' (existing field, already passing)."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertEqual(analisis['estado_semana'], 'prudencia_semanal')


class RPEAltoGeneraCargaAltaObjetivaTest(CargaAltaObjetivaBase):
    """
    RPE >= 8 is an external physiological signal.
    Even if session structure looks solid, high RPE → carga_alta_objetiva = True.
    All tests FAIL until RPE computation is added to the service.
    """

    def setUp(self):
        super().setUp()
        # Two normal sessions, blocks complete — but RPE is high
        self._add_entreno(dias_offset=0, modo_reducido=False, rpe_medio=8.5)
        self._add_entreno(dias_offset=2, modo_reducido=False, rpe_medio=8.0)

    def test_rpe_alto_genera_carga_alta_objetiva(self):
        """RPE medio semana >= 8 → carga_alta_objetiva = True."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertTrue(
            analisis.get('carga_alta_objetiva'),
            "RPE >= 8 must set carga_alta_objetiva=True regardless of session structure.",
        )

    def test_rpe_alto_motivo_es_rpe_alto(self):
        """When carga_alta_objetiva is caused by RPE, motivo_carga must be 'rpe_alto'."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        if analisis.get('carga_alta_objetiva'):
            self.assertEqual(analisis.get('motivo_carga'), 'rpe_alto')


class RPEBajoNoGeneraCargaAltaTest(CargaAltaObjetivaBase):
    """
    RPE < 7.5 + no structural evidence → carga_alta_objetiva = False.
    All tests FAIL until the field is added.
    """

    def setUp(self):
        super().setUp()
        self._add_entreno(dias_offset=0, modo_reducido=True,
                          principales_completados=2, rpe_medio=6.0)
        self._add_entreno(dias_offset=2, modo_reducido=True,
                          principales_completados=2, rpe_medio=5.8)

    def test_rpe_bajo_no_carga_alta_objetiva(self):
        """RPE 6 + esencial + blocks complete → carga_alta_objetiva = False."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertFalse(analisis.get('carga_alta_objetiva'))

    def test_rpe_bajo_prudencia_semanal_true(self):
        """RPE 6 + esencial + blocks complete → prudencia_semanal = True."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertTrue(analisis.get('prudencia_semanal'))

    def test_rpe_bajo_motivo_carga_es_none(self):
        """No carga_alta_objetiva → motivo_carga must be None."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        if not analisis.get('carga_alta_objetiva'):
            self.assertIsNone(analisis.get('motivo_carga'))


class BloqueParcialesCargaAltaObjetivaTest(CargaAltaObjetivaBase):
    """
    bloques_principales_parciales > 0 is a structural external signal.
    It represents the user not completing even the minimum plan.
    → carga_alta_objetiva = True (already implied by estado_semana == 'carga_alta').
    These tests verify the new field mirrors the existing semantic.
    FAIL until the field is added.
    """

    def setUp(self):
        super().setUp()
        # One esencial session where the main block was NOT completed
        self._add_entreno(dias_offset=0, modo_reducido=True,
                          principales_planificados=2, principales_completados=1,
                          rpe_medio=7.0)

    def test_bloque_parcial_carga_alta_objetiva_true(self):
        """Incomplete main block → carga_alta_objetiva = True."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertTrue(
            analisis.get('carga_alta_objetiva'),
            "Incomplete main block must set carga_alta_objetiva=True.",
        )

    def test_bloque_parcial_prudencia_semanal_false(self):
        """With incomplete main block, prudencia_semanal must be False."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        self.assertFalse(analisis.get('prudencia_semanal'))

    def test_bloque_parcial_motivo_es_bloque_incompleto(self):
        """motivo_carga must identify the structural reason."""
        analisis = analizar_semana_entrenamiento(self.cliente, fecha_ref=self.lunes)
        if analisis.get('carga_alta_objetiva'):
            self.assertEqual(analisis.get('motivo_carga'), 'bloque_incompleto')
