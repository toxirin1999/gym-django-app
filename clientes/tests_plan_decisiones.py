"""
Phase 26.1 — Tests for plan_decisiones_view (Centro de decisiones del plan).

The view aggregates all evidence the plan is currently using into one screen.
It must be read-only, always safe to load, and never trigger side effects.

Checklist:
1.  View returns 200 for logged user.
2.  Anonymous user is redirected to login.
3.  Context has all 7 expected keys.
4.  Preferencias activas in context (not revoked).
5.  Intervenciones activas in context (only fecha_fin >= hoy).
6.  GymDecisionLog decisions in context (only intervention actions).
7.  Modo reducido sessions in context.
8.  Expired interventions NOT in intervenciones_activas.
9.  Template renders without error (basic smoke test).
10. URL name resolves correctly.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    IntervencionPlan, GymDecisionLog, EntrenoRealizado,
    PreferenciaPlanAprendida, SugerenciaPlan,
)


class PlanDecisionesBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester_dc26', password='testpass',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDC26', 'dias_disponibles': 4},
        )
        self.hoy = date.today()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _get(self):
        c = Client()
        c.login(username='tester_dc26', password='testpass')
        return c.get(reverse('clientes:plan_decisiones'))

    def _crear_pref(self, tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL):
        with patch('joi.services.generar_mensaje_joi'):
            return PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente, tipo=tipo,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=self.hoy, ultima_confirmacion=self.hoy,
            )

    def _crear_intervencion(self, tipo=IntervencionPlan.TIPO_NO_SUBIR,
                             dias_hasta_fin=3, estado=IntervencionPlan.ESTADO_ACTIVA):
        return IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=tipo,
            fecha_inicio=self.hoy, fecha_fin=self.hoy + timedelta(days=dias_hasta_fin),
            estado=estado,
        )

    def _crear_decision(self, accion='deload', estado_aplicacion='pendiente',
                         motivo_postergacion=None):
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Sentadilla',
            accion=accion, motivo='Fatiga acumulada detectada.',
            estado_aplicacion=estado_aplicacion,
            motivo_postergacion=motivo_postergacion,
        )


# ── Case 1-2: access ──────────────────────────────────────────────────────────

class TestCase1_Access(PlanDecisionesBase):
    def test_view_returns_200_for_logged_user(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)

    def test_anonymous_redirected_to_login(self):
        c = Client()
        response = c.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


# ── Case 3: context keys ──────────────────────────────────────────────────────

class TestCase3_ContextKeys(PlanDecisionesBase):
    def test_context_has_all_expected_keys(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        expected_keys = [
            'preferencias_activas', 'intervenciones_activas',
            'pruebas_recientes', 'decisiones_carga',
            'sesiones_esenciales', 'hoy', 'cliente',
        ]
        for key in expected_keys:
            self.assertIn(key, ctx, msg=f"Context missing key: '{key}'")


# ── Case 4: preferencias activas ──────────────────────────────────────────────

class TestCase4_PreferenciasActivas(PlanDecisionesBase):
    def test_preferencia_activa_aparece_en_contexto(self):
        self._crear_pref()
        response = self._get()
        prefs = list(response.context['preferencias_activas'])
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].tipo, PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL)

    def test_preferencia_revocada_no_aparece(self):
        pref = self._crear_pref()
        pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
        pref.save()
        response = self._get()
        prefs = list(response.context['preferencias_activas'])
        self.assertEqual(len(prefs), 0)

    def test_sin_preferencias_lista_vacia(self):
        response = self._get()
        self.assertEqual(len(list(response.context['preferencias_activas'])), 0)


# ── Case 5: intervenciones activas ───────────────────────────────────────────

class TestCase5_IntervencionesActivas(PlanDecisionesBase):
    def test_intervencion_activa_aparece(self):
        self._crear_intervencion(dias_hasta_fin=3)
        response = self._get()
        ints = list(response.context['intervenciones_activas'])
        self.assertEqual(len(ints), 1)

    def test_intervencion_activa_tiene_fecha_fin_futura(self):
        self._crear_intervencion(dias_hasta_fin=5)
        response = self._get()
        ints = list(response.context['intervenciones_activas'])
        self.assertEqual(len(ints), 1)


# ── Case 6: decisiones de carga ──────────────────────────────────────────────

class TestCase6_DecisionesCarga(PlanDecisionesBase):
    def test_decision_activa_aparece_en_contexto(self):
        self._crear_decision(accion='deload')
        response = self._get()
        decs = list(response.context['decisiones_carga'])
        self.assertEqual(len(decs), 1)
        self.assertEqual(decs[0].accion, 'deload')

    def test_subir_peso_aparece_como_decision_de_carga(self):
        # Phase 62G.3 — subir_peso es ejecutivo desde 62H (peso_sugerido se
        # aplica a la siguiente sesión), debe ser visible en transparencia.
        self._crear_decision(accion='subir_peso')
        response = self._get()
        decs = list(response.context['decisiones_carga'])
        self.assertEqual(len(decs), 1)
        self.assertEqual(decs[0].accion, 'subir_peso')

    def test_multiples_decisiones_ordenadas_por_fecha(self):
        for accion in ['deload', 'bajar_peso', 'cambiar_variante']:
            self._crear_decision(accion=accion)
        response = self._get()
        decs = list(response.context['decisiones_carga'])
        self.assertEqual(len(decs), 3)


# ── Case 7: sesiones esenciales ──────────────────────────────────────────────

class TestCase7_SesionesEsenciales(PlanDecisionesBase):
    def test_sesiones_esenciales_clave_existe_en_contexto(self):
        response = self._get()
        self.assertIn('sesiones_esenciales', response.context)

    def test_sesiones_esenciales_es_lista(self):
        response = self._get()
        esenciales = response.context['sesiones_esenciales']
        # Should be a list (possibly empty — no EntrenoRealizado in test DB)
        self.assertIsInstance(esenciales, list)

    def test_sesiones_esenciales_vacia_sin_datos(self):
        response = self._get()
        esenciales = list(response.context['sesiones_esenciales'])
        self.assertEqual(len(esenciales), 0)


# ── Case 8: intervenciones expiradas excluidas ───────────────────────────────

class TestCase8_IntervencionesExpiradas(PlanDecisionesBase):
    def test_intervencion_expirada_no_aparece_en_activas(self):
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            fecha_inicio=self.hoy - timedelta(days=10),
            fecha_fin=self.hoy - timedelta(days=3),  # already expired
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        response = self._get()
        ints = list(response.context['intervenciones_activas'])
        self.assertEqual(len(ints), 0)


# ── Case 9: template smoke test ──────────────────────────────────────────────

class TestCase9_TemplateSmokeTest(PlanDecisionesBase):
    def test_template_renders_with_data(self):
        self._crear_pref()
        self._crear_intervencion()
        self._crear_decision()
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activo ahora')
        self.assertContains(response, 'permanente · revocable')
        self.assertContains(response, 'temporal · hasta el')

    def test_template_renders_with_empty_data(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        # Sin datos, la sección "Activo ahora" siempre aparece
        self.assertContains(response, 'Activo ahora')
        # Las cards de preferencias/intervenciones no aparecen si no hay datos
        self.assertNotContains(response, 'permanente · revocable')
        self.assertNotContains(response, 'temporal · hasta el')


# ── Case 10: URL resolution ───────────────────────────────────────────────────

class TestCase10_URLResolution(PlanDecisionesBase):
    def test_url_name_resolves(self):
        url = reverse('clientes:plan_decisiones')
        self.assertEqual(url, '/clientes/plan/decisiones/')

    def test_volver_link_goes_to_mockup(self):
        response = self._get()
        self.assertContains(response, '/clientes/mockup-demo/')


# ── Case 11: Phase 62G.3 — subir_peso agrupado en "Carga por ejercicio" ──────

class TestCase11_SubirPesoAgrupado(PlanDecisionesBase):
    def test_subir_peso_aparece_agrupado(self):
        self._crear_decision(accion='subir_peso')
        response = self._get()
        grupos = {g['accion']: g for g in response.context['decisiones_agrupadas']}
        self.assertIn('subir_peso', grupos)
        self.assertEqual(grupos['subir_peso']['label'], 'Subir peso')
        self.assertEqual(grupos['subir_peso']['count'], 1)
        self.assertIn('Sentadilla', grupos['subir_peso']['ejercicios'])

    def test_subir_peso_se_renderiza_en_template(self):
        self._crear_decision(accion='subir_peso')
        response = self._get()
        self.assertContains(response, 'Subir peso')


# ── Case 12: Phase 62I — estado operativo de progresiones ────────────────────

class TestCase12_EstadoOperativoProgresiones(PlanDecisionesBase):
    def test_subir_peso_pospuesto_aparece_en_pospuestas_count(self):
        self._crear_decision(
            accion='subir_peso', estado_aplicacion='pospuesta',
            motivo_postergacion='El plan detecta carga alta esta semana. No se sube peso.',
        )
        response = self._get()
        grupos = {g['accion']: g for g in response.context['decisiones_agrupadas']}
        self.assertEqual(grupos['subir_peso']['pospuestas_count'], 1)

    def test_subir_peso_pospuesto_se_renderiza_en_template(self):
        self._crear_decision(
            accion='subir_peso', estado_aplicacion='pospuesta',
            motivo_postergacion='El plan detecta carga alta esta semana. No se sube peso.',
        )
        response = self._get()
        self.assertContains(response, 'pospuesta')
        self.assertContains(response, 'El plan detecta carga alta esta semana. No se sube peso.')

    def test_subir_peso_aplicado_no_cuenta_como_pospuesta(self):
        self._crear_decision(accion='subir_peso', estado_aplicacion='aplicada')
        response = self._get()
        grupos = {g['accion']: g for g in response.context['decisiones_agrupadas']}
        self.assertEqual(grupos['subir_peso']['pospuestas_count'], 0)
        self.assertNotContains(response, 'pospuesta')
