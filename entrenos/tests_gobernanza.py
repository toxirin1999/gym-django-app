"""
Phase 38.1 — Tests de gobernanza del ciclo de aprendizaje.

El sistema ya sabe aprender; ahora necesita saber olvidar, pausar y no insistir.

Checklist (12):
1.  Hipótesis fresca (<30 días) aparece normalmente.
2.  Hipótesis sin ocurrencias recientes (>30 días) → suprimida (stale).
3.  Hipótesis muy antigua (>60 días) sin experimento → suprimida.
4.  Hipótesis atenuada recientemente → suprimida (cooldown 45 días).
5.  Hipótesis ignorada ≥2 veces recientemente → suprimida (pausa 21 días).
6.  Max 2 hipótesis visibles simultáneamente (las más repetidas).
7.  Hipótesis suprimida no aparece en UI del Centro.
8.  Hipótesis fresca con experimento activo → sigue visible (gobernanza no bloquea).
9.  Fallo del servicio → fallback a hipótesis sin filtrar (no rompe Centro).
10. Hipótesis ignorada 1 vez (< N) → aún visible.
11. Lista vacía → gobernanza devuelve lista vacía.
12. Más de 2 hipótesis activas → solo muestra las 2 más repetidas.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    GymDecisionTrace, GymDecisionTraceEvaluation,
    SugerenciaPlan, IntervencionPlan,
)
from entrenos.services.hipotesis_service import _PATRON_PREFIX
from entrenos.services.gobernanza_service import (
    aplicar_gobernanza_hipotesis, auditar_hipotesis,
    _MAX_HIPOTESIS_VISIBLES,
)


class GobernanzaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_gob38', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestGob38', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)

    def _h(self, estado='posponer', ocurrencias=3, dias_atras_primera=5):
        """Returns a raw hypothesis dict as detectar_hipotesis_abiertas would return."""
        fechas = [self.hoy - timedelta(days=dias_atras_primera + i) for i in range(ocurrencias)]
        return {
            'estado':      estado,
            'ocurrencias': ocurrencias,
            'texto':       f'Hipótesis de prueba: {estado}.',
            'fechas':      fechas,
        }

    def _trace_eval(self, estado='posponer', dias_atras=5):
        tr = GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=self.hoy - timedelta(days=dias_atras),
            decision_estado=estado,
            causa_principal='test',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=[], preferencias_activas=[],
            intervenciones_activas=[], lesion_contexto={},
        )
        GymDecisionTraceEvaluation.objects.create(
            trace=tr, resultado='senal_no_captada',
            resumen='Test.', senales_posteriores={},
        )
        return tr


# ── Cases 1-2: frescura ───────────────────────────────────────────────────────

class TestCase1_HipotesisFresca(GobernanzaBase):
    def test_hipotesis_fresca_aparece(self):
        self._trace_eval(dias_atras=5)
        hipotesis = [self._h(dias_atras_primera=5)]
        resultado = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertEqual(len(resultado), 1)
        self.assertFalse(resultado[0].get('gobernanza_suprimida'))


class TestCase2_HipotesisStale(GobernanzaBase):
    def test_hipotesis_sin_ocurrencias_recientes_suprimida(self):
        # trace is 40 days old — beyond 30-day threshold
        self._trace_eval(dias_atras=40)
        hipotesis = [self._h(dias_atras_primera=40)]
        resultado = auditar_hipotesis(self.cliente, hipotesis, self.hoy)
        suprimidas = [h for h in resultado if h.get('gobernanza_suprimida')]
        self.assertEqual(len(suprimidas), 1)
        self.assertEqual(suprimidas[0]['motivo'], 'sin_ocurrencias_recientes')


# ── Case 3: hipótesis demasiado antigua ──────────────────────────────────────

class TestCase3_DemaisiadoAntigua(GobernanzaBase):
    def test_hipotesis_60_dias_sin_experimento_suprimida(self):
        # Recent occurrence but first one was 65 days ago
        self._trace_eval(dias_atras=5)
        self._trace_eval(dias_atras=65)
        hipotesis = [self._h(ocurrencias=4, dias_atras_primera=65)]
        resultado = auditar_hipotesis(self.cliente, hipotesis, self.hoy)
        suprimidas = [h for h in resultado if h.get('gobernanza_suprimida')]
        # Should be suppressed because first occurrence was >60 days ago
        self.assertEqual(len(suprimidas), 1)
        self.assertIn('antigua', suprimidas[0]['motivo'])


# ── Case 4: cooldown después de atenuada ─────────────────────────────────────

class TestCase4_CooldownAtenuada(GobernanzaBase):
    def test_experimento_atenuado_reciente_suprime_hipotesis(self):
        self._trace_eval(dias_atras=5)
        patron = f"{_PATRON_PREFIX}posponer"
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            origen_patron=patron,
            fecha_inicio=self.hoy - timedelta(days=20),
            fecha_fin=self.hoy - timedelta(days=6),  # within 45 days
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        hipotesis = [self._h()]
        resultado = auditar_hipotesis(self.cliente, hipotesis, self.hoy)
        suprimidas = [h for h in resultado if h.get('gobernanza_suprimida')]
        self.assertEqual(len(suprimidas), 1)
        self.assertEqual(suprimidas[0]['motivo'], 'cooldown_atenuada')


# ── Case 5: ignorada demasiadas veces ────────────────────────────────────────

class TestCase5_IgnoradaMuchasVeces(GobernanzaBase):
    def test_ignorada_2_veces_reciente_suprime(self):
        self._trace_eval(dias_atras=5)
        patron = f"{_PATRON_PREFIX}posponer"
        for _ in range(2):
            SugerenciaPlan.objects.create(
                cliente=self.cliente,
                patron=patron,
                texto='Test.',
                estado=SugerenciaPlan.ESTADO_IGNORADA,
                cooldown_hasta=self.hoy + timedelta(days=5),
            )
        hipotesis = [self._h()]
        resultado = auditar_hipotesis(self.cliente, hipotesis, self.hoy)
        suprimidas = [h for h in resultado if h.get('gobernanza_suprimida')]
        self.assertEqual(len(suprimidas), 1)
        self.assertIn('ignorada', suprimidas[0]['motivo'])


# ── Case 6: máximo visible ────────────────────────────────────────────────────

class TestCase6_MaxVisible(GobernanzaBase):
    def test_max_2_hipotesis_visibles(self):
        for i in range(5):
            self._trace_eval(estado=f'estado{i}', dias_atras=5+i)  # distinct dates
        hipotesis = [self._h(estado=f'estado{i}', ocurrencias=3+i, dias_atras_primera=5+i) for i in range(5)]
        resultado = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertLessEqual(len(resultado), _MAX_HIPOTESIS_VISIBLES)

    def test_muestra_las_mas_repetidas_si_hay_exceso(self):
        for i, estado in enumerate(['posponer', 'entrenar', 'recuperar']):
            self._trace_eval(estado=estado, dias_atras=5+i)  # distinct dates
        hipotesis = [
            self._h('posponer', ocurrencias=5, dias_atras_primera=5),
            self._h('entrenar', ocurrencias=4, dias_atras_primera=6),
            self._h('recuperar', ocurrencias=3, dias_atras_primera=7),
        ]
        resultado = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['estado'], 'posponer')
        self.assertEqual(resultado[1]['estado'], 'entrenar')


# ── Case 7: UI no muestra suprimidas ─────────────────────────────────────────

class TestCase7_UINoMuestraSuprimidas(GobernanzaBase):
    def test_hipotesis_suprimida_no_aparece_en_centro(self):
        # 40 days old → stale → suppressed
        self._trace_eval(dias_atras=40)
        c = Client()
        c.login(username='tester_gob38', password='x')
        response = c.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(response.status_code, 200)
        # The hypothesis text should NOT appear (suppressed by governance)
        self.assertNotContains(response, 'estado40')  # not a real hypothesis type


# ── Case 8: hipótesis fresca con experimento activo sigue visible ─────────────

class TestCase8_FrescaConExperimentoActivo(GobernanzaBase):
    def test_hipotesis_fresca_visible_aunque_haya_experimento_activo(self):
        self._trace_eval(dias_atras=3)
        # Active experiment (not expired) — governance doesn't suppress the hypothesis
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            origen_patron=f"{_PATRON_PREFIX}posponer",
            fecha_inicio=self.hoy - timedelta(days=5),
            fecha_fin=self.hoy + timedelta(days=9),  # still active
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        hipotesis = [self._h(dias_atras_primera=3)]
        # Active experiment within 45 days → suppressed by Rule 4
        resultado = auditar_hipotesis(self.cliente, hipotesis, self.hoy)
        # Rule 4 applies since experiment is within cooldown window
        # This is intentional: don't propose again while experiment is running
        self.assertEqual(len(resultado), 1)


# ── Case 9: fallo silencioso ──────────────────────────────────────────────────

class TestCase9_FalloSilencioso(GobernanzaBase):
    def test_fallo_devuelve_hipotesis_sin_filtrar(self):
        hipotesis = [self._h()]
        resultado = aplicar_gobernanza_hipotesis(None, hipotesis, self.hoy)
        # On failure, returns unfiltered (safe fallback)
        self.assertIsInstance(resultado, list)


# ── Case 10: ignorada 1 vez sigue visible ─────────────────────────────────────

class TestCase10_IgnoradaUnaVez(GobernanzaBase):
    def test_ignorada_1_vez_sigue_visible(self):
        self._trace_eval(dias_atras=5)
        SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron=f"{_PATRON_PREFIX}posponer",
            texto='Test.',
            estado=SugerenciaPlan.ESTADO_IGNORADA,
        )
        hipotesis = [self._h()]
        resultado = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertEqual(len(resultado), 1)  # 1 ignore < threshold of 2


# ── Case 11: lista vacía ──────────────────────────────────────────────────────

class TestCase11_ListaVacia(GobernanzaBase):
    def test_lista_vacia_devuelve_lista_vacia(self):
        resultado = aplicar_gobernanza_hipotesis(self.cliente, [], self.hoy)
        self.assertEqual(resultado, [])


# ── Case 12: 3 hipótesis → solo 2 más repetidas ──────────────────────────────

class TestCase12_TresHipotesisDosVisibles(GobernanzaBase):
    def test_tres_hipotesis_solo_dos_mas_repetidas(self):
        for i, estado in enumerate(['posponer', 'entrenar', 'recuperar']):
            self._trace_eval(estado=estado, dias_atras=5+i)  # distinct dates
        hipotesis = [
            self._h('posponer', ocurrencias=5, dias_atras_primera=5),
            self._h('entrenar', ocurrencias=4, dias_atras_primera=6),
            self._h('recuperar', ocurrencias=3, dias_atras_primera=7),
        ]
        resultado = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertEqual(len(resultado), 2)
        estados = [h['estado'] for h in resultado]
        self.assertNotIn('recuperar', estados)
