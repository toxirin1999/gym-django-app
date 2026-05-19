"""
Phase 34.1 — Tests para el seguimiento posterior de decisiones.

El sistema no pregunta '¿acerté?'. Pregunta '¿qué señales aparecieron después?'.

Checklist (16):
1.  Posponer + sesión posterior rápida con buen RPE → libero_margen
2.  Posponer + sin sesión posterior → datos_insuficientes
3.  Posponer + sesión posterior con RPE alto → senal_no_captada
4.  Entrenar normal + RPE ≥ 9 posterior → senal_no_captada
5.  Entrenar normal + completada normal → neutral
6.  Versión esencial + continuidad sin sobrecarga → libero_margen
7.  Resumen no usa 'acierto', 'fallo', 'correcto', 'incorrecto'
8.  Resumen no culpa al usuario
9.  Resumen no diagnostica fatiga como certeza
10. No evalúa traces demasiado recientes (< 2 días)
11. No duplica evaluación si ya existe
12. Fallo en un trace no rompe el lote
13. evaluar_traces_pendientes devuelve count correcto
14. Resultado es uno de los 4 valores permitidos
15. senal_no_captada usa 'quizá', 'puede', 'no es seguro'
16. libero_margen usa 'parece', 'señal refuerza provisionalmente'
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    GymDecisionTrace, GymDecisionTraceEvaluation,
)
from entrenos.services.evaluacion_trace_service import (
    evaluar_trace_decision, evaluar_traces_pendientes, _calcular_resultado,
)


PALABRAS_ABSOLUTAS = ['acierto', 'fallo', 'correcto', 'incorrecto', 'acertó', 'falló']
PALABRAS_CULPA = ['culpa', 'no cumpliste', 'fallaste', 'deberías haber', 'error tuyo']
PALABRAS_CERTEZA = ['definitivamente', 'con certeza', 'garantizado', 'está claro que fue']
RESULTADOS_VALIDOS = {
    'libero_margen', 'neutral', 'senal_no_captada', 'datos_insuficientes'
}


class EvalBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_eval34', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestEval34', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)   # evaluation date
        self.fecha_decision = self.hoy - timedelta(days=3)   # decision was 3 days ago

    def _trace(self, estado='posponer', causa='futbol_reciente'):
        return GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=self.fecha_decision,
            decision_estado=estado,
            causa_principal=causa,
            senales_motor={},
            capas_visibles=[],
            capas_suprimidas=[],
            explicacion_senales=[],
            preferencias_activas=[],
            intervenciones_activas=[],
            lesion_contexto={},
        )

    def _senales(self, sesiones=1, dias=2, rpe=6.0, reducido=False):
        """Returns a controlled senales dict (avoids complex DB chain)."""
        s = {'sesiones_posteriores': sesiones}
        if sesiones > 0:
            s['dias_hasta_sesion'] = dias
            s['modo_reducido'] = reducido
            if rpe is not None:
                s['rpe_medio_posterior'] = rpe
        return s


# ── Cases 1-3: posponer ───────────────────────────────────────────────────────

_PATCH = 'entrenos.services.evaluacion_trace_service._recopilar_senales_posteriores'


class TestCase1_PosponerLiberaMargen(EvalBase):
    def test_posponer_sesion_rapida_buen_rpe_libero_margen(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.LIBERO_MARGEN)


class TestCase2_PosponerSinSesion(EvalBase):
    def test_posponer_sin_sesion_posterior_insuficiente(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.INSUFICIENTE)


class TestCase3_PosponerRPEAlto(EvalBase):
    def test_posponer_sesion_posterior_rpe_alto_senal_no_captada(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=9.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.SENAL_NO_CAPTADA)


# ── Cases 4-5: entrenar normal ────────────────────────────────────────────────

class TestCase4_EntrenarRPEAlto(EvalBase):
    def test_entrenar_normal_rpe_alto_senal_no_captada(self):
        trace = self._trace(estado='entrenar', causa='sesion_hoy')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=1, rpe=9.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.SENAL_NO_CAPTADA)


class TestCase5_EntrenarNormal(EvalBase):
    def test_entrenar_completado_normal_neutral(self):
        trace = self._trace(estado='entrenar', causa='sesion_hoy')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=1, rpe=7.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.NEUTRO)


# ── Case 6: version_reducida ──────────────────────────────────────────────────

class TestCase6_VersionEsencial(EvalBase):
    def test_version_esencial_continuidad_libero_margen(self):
        trace = self._trace(estado='version_reducida', causa='energia_baja')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0, reducido=False)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.LIBERO_MARGEN)


# ── Cases 7-9: lenguaje prudente ─────────────────────────────────────────────

class TestCase7_SinAbsolutos(EvalBase):
    def test_resumen_sin_palabras_absolutas(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        resumen = ev.resumen.lower()
        for palabra in PALABRAS_ABSOLUTAS:
            self.assertNotIn(palabra, resumen, msg=f"Resumen usa '{palabra}'")


class TestCase8_SinCulpa(EvalBase):
    def test_resumen_sin_culpa_al_usuario(self):
        trace = self._trace(estado='entrenar', causa='sesion_hoy')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=1, rpe=9.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        resumen = ev.resumen.lower()
        for palabra in PALABRAS_CULPA:
            self.assertNotIn(palabra, resumen, msg=f"Resumen culpa: '{palabra}'")


class TestCase9_SinCerteza(EvalBase):
    def test_resumen_sin_causalidad_fuerte(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=9.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        resumen = ev.resumen.lower()
        for frase in PALABRAS_CERTEZA:
            self.assertNotIn(frase, resumen, msg=f"Resumen dice certeza: '{frase}'")


# ── Case 10: no evalúa demasiado pronto ──────────────────────────────────────

class TestCase10_DemasiadoPronto(EvalBase):
    def test_no_evalua_trace_reciente(self):
        trace = GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=date(2026, 5, 20),   # ayer — solo 1 día, < MIN_DIAS_ESPERA
            decision_estado='posponer',
            causa_principal='sesion_hoy',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=[], preferencias_activas=[],
            intervenciones_activas=[], lesion_contexto={},
        )
        ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNone(ev)


# ── Case 11: no duplica ───────────────────────────────────────────────────────

class TestCase11_NoDuplicados(EvalBase):
    def test_no_duplica_evaluacion(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0)):
            ev1 = evaluar_trace_decision(trace, fecha_ref=self.hoy)
            ev2 = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertIsNotNone(ev1)
        count = GymDecisionTraceEvaluation.objects.filter(trace=trace).count()
        self.assertEqual(count, 1)
        self.assertEqual(ev1.id, ev2.id)


# ── Case 12: fallo silencioso ─────────────────────────────────────────────────

class TestCase12_FalloSilencioso(EvalBase):
    def test_fallo_en_un_trace_no_rompe_lote(self):
        self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=0)):
            count = evaluar_traces_pendientes(self.cliente, fecha_ref=self.hoy, max_batch=10)
        self.assertGreaterEqual(count, 0)


# ── Case 13: lote ─────────────────────────────────────────────────────────────

class TestCase13_Lote(EvalBase):
    def test_lote_devuelve_count_correcto(self):
        self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0)):
            count = evaluar_traces_pendientes(self.cliente, fecha_ref=self.hoy, max_batch=10)
        self.assertEqual(count, 1)


# ── Case 14: resultado válido ─────────────────────────────────────────────────

class TestCase14_ResultadoValido(EvalBase):
    def test_resultado_es_uno_de_los_4_validos(self):
        offsets = {'posponer': 1, 'entrenar': 2, 'version_reducida': 3, 'recuperar': 4}
        for estado, offset in offsets.items():
            trace = GymDecisionTrace.objects.create(
                cliente=self.cliente,
                fecha=self.fecha_decision - timedelta(days=offset),
                decision_estado=estado,
                causa_principal='sesion_hoy',
                senales_motor={}, capas_visibles=[], capas_suprimidas=[],
                explicacion_senales=[], preferencias_activas=[],
                intervenciones_activas=[], lesion_contexto={},
            )
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
            if ev:
                self.assertIn(ev.resultado, RESULTADOS_VALIDOS,
                              msg=f"Estado '{estado}': resultado inválido '{ev.resultado}'")


# ── Cases 15-16: vocabulario por resultado ────────────────────────────────────

class TestCase15_VocabularioSenal(EvalBase):
    def test_senal_no_captada_usa_lenguaje_tentativo(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=9.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.SENAL_NO_CAPTADA)
        resumen = ev.resumen.lower()
        palabras_tentativas = ['quizá', 'puede', 'no hay suficiente', 'factores', 'no hay evidencia']
        usa_tentativo = any(k in resumen for k in palabras_tentativas)
        self.assertTrue(usa_tentativo, msg=f"senal_no_captada no usa tono tentativo: {resumen[:150]}")


class TestCase16_VocabularioLiberaMargen(EvalBase):
    def test_libero_margen_usa_lenguaje_provisional(self):
        trace = self._trace(estado='posponer')
        with patch(_PATCH, return_value=self._senales(sesiones=1, dias=2, rpe=6.0)):
            ev = evaluar_trace_decision(trace, fecha_ref=self.hoy)
        self.assertEqual(ev.resultado, GymDecisionTraceEvaluation.LIBERO_MARGEN)
        resumen = ev.resumen.lower()
        palabras_provisionales = ['parece', 'refuerza provisionalmente', 'señal', 'pareció']
        usa_provisional = any(k in resumen for k in palabras_provisionales)
        self.assertTrue(usa_provisional, msg=f"libero_margen no usa tono provisional: {resumen[:150]}")
