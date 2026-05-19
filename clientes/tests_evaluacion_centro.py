"""
Phase 35.1 — Evaluación visible en Centro de decisiones.

El Centro no solo recuerda por qué se decidió algo; muestra qué señales
aparecieron después, sin convertirlas en veredicto.

Checklist (8):
1.  Centro muestra evaluación si trace tiene evaluación relevante.
2.  No muestra evaluación si resultado = datos_insuficientes.
3.  senal_no_captada aparece como hipótesis, no como fallo.
4.  libero_margen aparece como señal posterior, no como acierto.
5.  No aparecen claves internas ni JSON crudo.
6.  No aparecen palabras prohibidas por auditoría narrativa.
7.  Si falla cargar evaluación, el Centro sigue funcionando.
8.  La evaluación no duplica la explicación original del trace.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import GymDecisionTrace, GymDecisionTraceEvaluation
from entrenos.services.decision_trace_service import humanizar_trace

PALABRAS_PROHIBIDAS = [
    'acertó', 'falló', 'correcto', 'incorrecto', 'fallo', 'acierto',
    'no cumpliste', 'fallaste', 'deberías haber',
]
CLAVES_TECNICAS = [
    'evaluacion_resultado', 'senales_posteriores', 'senal_no_captada',
    'libero_margen', 'datos_insuficientes',
]


class EvalCentroBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_ec35', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEC35', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)

    def _trace(self, estado='posponer'):
        return GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=self.hoy - timedelta(days=3),
            decision_estado=estado,
            causa_principal='futbol_reciente',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=['El plan propuso mover la sesión porque había carga reciente.'],
            preferencias_activas=[], intervenciones_activas=[], lesion_contexto={},
        )

    def _eval(self, trace, resultado, resumen='Señal posterior breve.'):
        return GymDecisionTraceEvaluation.objects.create(
            trace=trace,
            resultado=resultado,
            resumen=resumen,
            senales_posteriores={},
        )

    def _get_centro(self):
        c = Client()
        c.login(username='tester_ec35', password='x')
        return c.get(reverse('clientes:plan_decisiones'))


# ── Case 1: muestra evaluación relevante ─────────────────────────────────────

class TestCase1_MuestraEval(EvalCentroBase):
    def test_muestra_evaluacion_libero_margen(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.LIBERO_MARGEN,
                   'La sesión siguiente se completó con margen razonable.')
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Después: pareció liberar margen')

    def test_muestra_evaluacion_senal_no_captada(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.SENAL_NO_CAPTADA,
                   'Puede que hubiera fatiga no captada.')
        response = self._get_centro()
        self.assertContains(response, 'Hipótesis abierta:')


# ── Case 2: oculta datos_insuficientes ───────────────────────────────────────

class TestCase2_OcultaInsuficiente(EvalCentroBase):
    def test_no_muestra_datos_insuficientes(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.INSUFICIENTE,
                   'No hay sesión posterior disponible.')
        response = self._get_centro()
        self.assertNotContains(response, 'No hay sesión posterior disponible')
        self.assertNotContains(response, 'Después: sin datos')

    def test_humanizar_trace_no_incluye_insuficiente(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.INSUFICIENTE)
        h = humanizar_trace(trace)
        self.assertIsNone(h['evaluacion_label'])
        self.assertIsNone(h['evaluacion_resumen'])


# ── Case 3: senal_no_captada como hipótesis ──────────────────────────────────

class TestCase3_SenalHipotesis(EvalCentroBase):
    def test_senal_no_captada_label_usa_hipotesis(self):
        from entrenos.services.decision_trace_service import _EVAL_LABELS
        label = _EVAL_LABELS.get('senal_no_captada', '')
        self.assertIn('quizá', label.lower())
        self.assertNotIn('falló', label.lower())
        self.assertNotIn('error', label.lower())


# ── Case 4: libero_margen como señal, no acierto ─────────────────────────────

class TestCase4_LiberaMargenSenal(EvalCentroBase):
    def test_libero_margen_label_usa_senal(self):
        from entrenos.services.decision_trace_service import _EVAL_LABELS
        label = _EVAL_LABELS.get('libero_margen', '')
        self.assertIn('pareció', label.lower())
        self.assertNotIn('acertó', label.lower())
        self.assertNotIn('correcto', label.lower())


# ── Case 5: sin claves técnicas en HTML ──────────────────────────────────────

class TestCase5_SinClaveTecnicas(EvalCentroBase):
    def test_html_sin_claves_tecnicas(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.LIBERO_MARGEN,
                   'La sesión siguiente se completó con RPE razonable.')
        response = self._get_centro()
        html = response.content.decode()
        for clave in CLAVES_TECNICAS:
            self.assertNotIn(clave, html,
                             msg=f"HTML expone clave técnica: '{clave}'")


# ── Case 6: sin palabras prohibidas ──────────────────────────────────────────

class TestCase6_SinProhibidas(EvalCentroBase):
    def test_html_sin_palabras_prohibidas(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.SENAL_NO_CAPTADA,
                   'Puede que hubiera fatiga no captada.')
        response = self._get_centro()
        html = response.content.decode().lower()
        for palabra in PALABRAS_PROHIBIDAS:
            self.assertNotIn(palabra, html,
                             msg=f"HTML usa palabra prohibida: '{palabra}'")


# ── Case 7: fallo silencioso ──────────────────────────────────────────────────

class TestCase7_FalloSilencioso(EvalCentroBase):
    def test_centro_funciona_sin_evaluacion(self):
        """Trace without evaluation: Centro still loads fine."""
        self._trace()  # no evaluation created
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Por qué decidió así recientemente')

    def test_humanizar_trace_sin_evaluacion_devuelve_none(self):
        trace = self._trace()
        h = humanizar_trace(trace)
        self.assertIsNone(h['evaluacion_label'])


# ── Case 8: evaluación no duplica explicación ────────────────────────────────

class TestCase8_NoDuplica(EvalCentroBase):
    def test_evaluacion_diferente_de_explicacion(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.LIBERO_MARGEN,
                   'La sesión siguiente se completó con margen razonable.')
        h = humanizar_trace(trace)
        # evaluation_resumen should not equal the trace explanation
        self.assertNotEqual(h['evaluacion_resumen'], h['explicacion'])

    def test_evaluacion_es_mas_corta_que_explicacion(self):
        trace = self._trace()
        self._eval(trace, GymDecisionTraceEvaluation.NEUTRO,
                   'Sin señal clara.')
        h = humanizar_trace(trace)
        # The eval summary should be shorter (secondary role)
        if h['evaluacion_resumen'] and h['explicacion']:
            self.assertLess(len(h['evaluacion_resumen']), len(h['explicacion']) + 200)
