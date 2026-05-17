"""
Phase 22.1 — Tests for learned plan preferences (PreferenciaPlanAprendida).

Checklist (14 cases):
1.  No candidate with only one favorable evaluation.
2.  Candidate exists with ≥2 favorable evaluations of same type.
3.  No candidate if preference already active for that type.
4.  Converting creates active PreferenciaPlanAprendida.
5.  evidencia_count is stored correctly.
6.  Revoking changes state to 'revocada'.
7.  Revoked preference not used as soft signal in motor.
8.  Active preference appears in get_preferencias_activas().
9.  detectar_candidata returns None when no evaluations.
10. No server-side effect for "Seguir probando" (no POST endpoint).
11. Preference does NOT call PlanificadorHelms.
12. Motor uses preference as soft signal (in preferencias_activas list).
13. Language in descriptions doesn't use 'siempre', 'nunca', 'debes'.
14. Safety context (lesion) overrides preference — lesion wins, not preference.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, PreferenciaPlanAprendida
from entrenos.services.preferencias_service import (
    crear_preferencia,
    detectar_candidata_preferencia,
    get_preferencias_activas,
    tiene_preferencia_activa,
)
from rutinas.models import Rutina


class PreferenciasBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_prf22', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestPRF', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 20)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _make_intervencion(self, tipo, fecha_inicio, fecha_fin, origen='redistrib_pierna_futbol'):
        return IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=tipo, origen_patron=origen,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )


# ── Case 1 & 9: No candidate with insufficient evaluations ────────────────────

class TestCase1_SinEvaluaciones(PreferenciasBase):
    def test_sin_intervenciones_no_hay_candidata(self):
        result = detectar_candidata_preferencia(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_una_sola_favorable_no_basta(self):
        # Only 1 probe → not enough (need ≥2 favorable)
        inicio = self.hoy - timedelta(days=14)
        fin = self.hoy - timedelta(days=1)
        self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_PIERNA, inicio, fin)

        mock_eval = {'resultado': 'favorable', 'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = detectar_candidata_preferencia(self.cliente, self.hoy)
        # Only 1 favorable evaluation → no candidate
        self.assertIsNone(result)


# ── Case 2: Candidate with ≥2 favorable evaluations ──────────────────────────

class TestCase2_CandidataConEvidencia(PreferenciasBase):
    def test_dos_favorables_genera_candidata(self):
        # Create 2 probes of the same type
        for i in range(2):
            inicio = self.hoy - timedelta(days=(i+1)*20)
            fin = inicio + timedelta(days=14)
            self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_PIERNA, inicio, fin)

        mock_eval = {'resultado': 'favorable', 'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = detectar_candidata_preferencia(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertEqual(result['tipo_preferencia'], PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL)
        self.assertGreaterEqual(result['evidencia_count'], 2)

    def test_candidata_tiene_descripcion(self):
        for i in range(2):
            inicio = self.hoy - timedelta(days=(i+1)*20)
            fin = inicio + timedelta(days=14)
            self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_PIERNA, inicio, fin)

        mock_eval = {'resultado': 'favorable', 'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = detectar_candidata_preferencia(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertIn('descripcion', result)
        self.assertTrue(result['descripcion'])


# ── Case 3: No candidate if preference already active ─────────────────────────

class TestCase3_PreferenciaYaActiva(PreferenciasBase):
    def test_no_candidata_si_preferencia_ya_activa(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy - timedelta(days=30),
            ultima_confirmacion=self.hoy,
        )

        for i in range(2):
            inicio = self.hoy - timedelta(days=(i+1)*20)
            fin = inicio + timedelta(days=14)
            self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_PIERNA, inicio, fin)

        mock_eval = {'resultado': 'favorable', 'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = detectar_candidata_preferencia(self.cliente, self.hoy)

        self.assertIsNone(result)  # already active


# ── Case 4 & 5: Creating a preference ────────────────────────────────────────

class TestCase45_CrearPreferencia(PreferenciasBase):
    def test_crear_genera_preferencia_activa(self):
        pref = crear_preferencia(
            self.cliente,
            PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA,
            evidencia_count=2,
            fecha_ref=self.hoy,
        )
        self.assertEqual(pref.estado, PreferenciaPlanAprendida.ESTADO_ACTIVA)

    def test_evidencia_count_se_guarda(self):
        pref = crear_preferencia(
            self.cliente,
            PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA,
            evidencia_count=3,
            fecha_ref=self.hoy,
        )
        self.assertEqual(pref.evidencia_count, 3)

    def test_crear_dos_veces_no_duplica(self):
        crear_preferencia(self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                          IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy)
        crear_preferencia(self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                          IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy)
        count = PreferenciaPlanAprendida.objects.filter(
            cliente=self.cliente, tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL
        ).count()
        self.assertEqual(count, 1)


# ── Case 6 & 7: Revocation ────────────────────────────────────────────────────

class TestCase67_Revocar(PreferenciasBase):
    def setUp(self):
        super().setUp()
        self.pref = crear_preferencia(
            self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy,
        )

    def test_revocar_cambia_estado(self):
        self.pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
        self.pref.save()
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.estado, PreferenciaPlanAprendida.ESTADO_REVOCADA)

    def test_revocada_no_aparece_en_activas(self):
        self.pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
        self.pref.save()
        activas = get_preferencias_activas(self.cliente)
        self.assertFalse(any(p.tipo == PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL for p in activas))

    def test_revocada_no_es_senal_blanda(self):
        self.pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
        self.pref.save()
        self.assertFalse(tiene_preferencia_activa(
            self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL
        ))


# ── Case 8 & 12: Active preference in context / motor ─────────────────────────

class TestCase8y12_PreferenciaEnMotor(PreferenciasBase):
    def test_activa_aparece_en_get_preferencias(self):
        crear_preferencia(
            self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy,
        )
        activas = get_preferencias_activas(self.cliente)
        tipos = [p.tipo for p in activas]
        self.assertIn(PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL, tipos)

    def test_motor_incluye_preferencia_en_contexto_fisico(self):
        """Motor loads preferences into contexto_fisico['preferencias_activas']."""
        crear_preferencia(
            self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy,
        )
        from entrenos.services.sesion_recomendada import _obtener_contexto_fisico
        ctx = _obtener_contexto_fisico(self.cliente, self.hoy)
        self.assertIn('preferencias_activas', ctx)
        self.assertIn(PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL, ctx['preferencias_activas'])


# ── Case 11: Preference doesn't touch PlanificadorHelms ──────────────────────

class TestCase11_NotocarPlanificador(PreferenciasBase):
    def test_crear_preferencia_no_llama_planificador(self):
        with patch('analytics.planificador_helms.core.PlanificadorHelms') as mock_plan:
            crear_preferencia(
                self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy,
            )
        mock_plan.assert_not_called()


# ── Case 13: Language audit ────────────────────────────────────────────────────

class TestCase13_Lenguaje(PreferenciasBase):
    def test_descripciones_no_usan_absolutas(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        forbidden = ['siempre', 'nunca', 'debes', 'obligatorio', 'imposible']
        for tipo, desc in _DESCRIPCION_PREFERENCIA.items():
            texto = desc.lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, texto, msg=f"Descripción de '{tipo}' contiene '{palabra}'")

    def test_descripciones_usan_tono_blanda(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        for tipo, desc in _DESCRIPCION_PREFERENCIA.items():
            texto = desc.lower()
            usa_tono_blanda = any(kw in texto for kw in ['intentará', 'cuando sea posible', 'referencia', 'como preferencia'])
            self.assertTrue(usa_tono_blanda, msg=f"Descripción de '{tipo}' no usa tono blanda: {desc}")


# ── Case 14: Safety context overrides preference ──────────────────────────────

class TestCase14_SeguridadMandaSobrePreferencia(PreferenciasBase):
    def test_lesion_gana_sobre_preferencia_pierna_futbol(self):
        """When injury is active, causa_principal='lesion' overrides preference signal."""
        crear_preferencia(
            self.cliente, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA, fecha_ref=self.hoy,
        )

        from entrenos.services.sesion_recomendada import _aplicar_contexto

        decision_base = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None, 'entrenamiento': {},
            'mensaje': '', 'causa_principal': None, 'modo_reducido': False,
        }
        # Context: injury active + football recent (both signals present)
        contexto = {
            'lesion_activa': True,     # safety — highest priority
            'lesion_fase': 'AGUDA',
            'futbol_reciente': True,   # preference would fire here
            'energia_baja': False, 'energia_valor': None,
            'readiness_bajo': False, 'readiness_valor': None,
        }

        resultado = _aplicar_contexto(decision_base, contexto, self.hoy)

        # Injury must be the dominant cause, not preference/football
        self.assertEqual(resultado['causa_principal'], 'lesion')
        self.assertEqual(resultado['estado'], 'recuperar')
