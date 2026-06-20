"""
Phase 36.1 — Tests para detección de hipótesis abiertas.

Una señal no captada no corrige el plan; enseña al sistema dónde mirar.

Checklist (10):
1.  Sin evaluaciones → lista vacía.
2.  Menos de MIN_OCURRENCIAS senal_no_captada → lista vacía.
3.  ≥ MIN_OCURRENCIAS del mismo estado → genera hipótesis.
4.  Estados distintos no se mezclan en la misma hipótesis.
5.  Texto usa tono tentativo ('parece', 'quizá', 'puede que').
6.  Texto no usa palabras prohibidas ('falló', 'error', 'incorrecto').
7.  Evaluaciones de otros resultados (libero_margen, neutral) no cuentan.
8.  Evaluaciones fuera de la ventana temporal no cuentan.
9.  Fallo del servicio devuelve [] silenciosamente.
10. Centro muestra sección si hay hipótesis, la oculta si no hay.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import GymDecisionTrace, GymDecisionTraceEvaluation
from entrenos.services.hipotesis_service import detectar_hipotesis_abiertas

PALABRAS_PROHIBIDAS = ['falló', 'error del', 'incorrecto', 'no cumpliste', 'acierto']
PALABRAS_TENTATIVAS = ['parece', 'quizá', 'puede que', 'puede', 'quiza']


class HipotesisBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_hip36', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestHip36', 'dias_disponibles': 4},
        )
        self.hoy = timezone.localdate()

    def _trace_eval(self, estado='posponer', resultado='senal_no_captada', dias_atras=3):
        trace = GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=self.hoy - timedelta(days=dias_atras),
            decision_estado=estado,
            causa_principal='sesion_hoy',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=[], preferencias_activas=[],
            intervenciones_activas=[], lesion_contexto={},
        )
        GymDecisionTraceEvaluation.objects.create(
            trace=trace,
            resultado=resultado,
            resumen='Señal de test.',
            senales_posteriores={},
        )
        return trace


# ── Cases 1-2: sin hipótesis ──────────────────────────────────────────────────

class TestCase1_SinEvaluaciones(HipotesisBase):
    def test_sin_evaluaciones_devuelve_vacio(self):
        resultado = detectar_hipotesis_abiertas(self.cliente, fecha_ref=self.hoy)
        self.assertEqual(resultado, [])


class TestCase2_MenosDeMinimo(HipotesisBase):
    def test_menos_de_min_ocurrencias_devuelve_vacio(self):
        for i in range(2):  # only 2, needs 3
            self._trace_eval(estado='posponer', dias_atras=i+1)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        self.assertEqual(resultado, [])


# ── Case 3: genera hipótesis ──────────────────────────────────────────────────

class TestCase3_GeneraHipotesis(HipotesisBase):
    def test_tres_senal_no_captada_mismo_estado_genera_hipotesis(self):
        for i in range(3):
            self._trace_eval(estado='posponer', dias_atras=i+2)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['estado'], 'posponer')
        self.assertEqual(resultado[0]['ocurrencias'], 3)


# ── Case 4: estados separados ─────────────────────────────────────────────────

class TestCase4_EstadosSeparados(HipotesisBase):
    def test_dos_estados_distintos_generan_hipotesis_separadas(self):
        for i in range(3):
            self._trace_eval(estado='posponer', dias_atras=i+2)
        for i in range(3):
            self._trace_eval(estado='entrenar', dias_atras=i+10)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        estados = {h['estado'] for h in resultado}
        self.assertIn('posponer', estados)
        self.assertIn('entrenar', estados)
        self.assertEqual(len(resultado), 2)


# ── Cases 5-6: lenguaje ───────────────────────────────────────────────────────

class TestCase5_TonoTentativo(HipotesisBase):
    def test_texto_usa_tono_tentativo(self):
        for i in range(3):
            self._trace_eval(estado='posponer', dias_atras=i+2)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        texto = resultado[0]['texto'].lower()
        usa_tentativo = any(k in texto for k in PALABRAS_TENTATIVAS)
        self.assertTrue(usa_tentativo, msg=f"Texto no usa tono tentativo: {texto[:150]}")


class TestCase6_SinProhibidas(HipotesisBase):
    def test_texto_sin_palabras_prohibidas(self):
        for i in range(3):
            self._trace_eval(estado='entrenar', dias_atras=i+2)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        texto = resultado[0]['texto'].lower()
        for palabra in PALABRAS_PROHIBIDAS:
            self.assertNotIn(palabra, texto, msg=f"Texto usa '{palabra}'")


# ── Case 7: solo cuenta senal_no_captada ─────────────────────────────────────

class TestCase7_SoloSenalNoCaptada(HipotesisBase):
    def test_otros_resultados_no_cuentan(self):
        for i in range(3):
            self._trace_eval(estado='posponer', resultado='libero_margen', dias_atras=i+2)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        self.assertEqual(resultado, [])

    def test_mezcla_resultados_solo_suma_senal_no_captada(self):
        for i in range(2):
            self._trace_eval(estado='posponer', resultado='senal_no_captada', dias_atras=i+2)
        self._trace_eval(estado='posponer', resultado='libero_margen', dias_atras=5)
        resultado = detectar_hipotesis_abiertas(self.cliente, min_ocurrencias=3, fecha_ref=self.hoy)
        self.assertEqual(resultado, [])  # only 2 senal_no_captada, needs 3


# ── Case 8: ventana temporal ─────────────────────────────────────────────────

class TestCase8_VentanaTemporal(HipotesisBase):
    def test_fuera_de_ventana_no_cuenta(self):
        for i in range(3):
            self._trace_eval(estado='posponer', dias_atras=40 + i)  # 40+ days ago
        resultado = detectar_hipotesis_abiertas(self.cliente, ventana_dias=30, min_ocurrencias=3, fecha_ref=self.hoy)
        self.assertEqual(resultado, [])


# ── Case 9: fallo silencioso ──────────────────────────────────────────────────

class TestCase9_FalloSilencioso(HipotesisBase):
    def test_fallo_devuelve_lista_vacia(self):
        resultado = detectar_hipotesis_abiertas(None, min_ocurrencias=3)
        self.assertIsInstance(resultado, list)
        self.assertEqual(resultado, [])


# ── Case 10: Centro muestra/oculta sección ────────────────────────────────────

class TestCase10_CentroMuestra(HipotesisBase):
    def _get_centro(self):
        c = Client()
        c.login(username='tester_hip36', password='x')
        return c.get(reverse('clientes:plan_decisiones'))

    def test_sin_hipotesis_no_muestra_seccion(self):
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Señales acumuladas')

    def test_con_hipotesis_muestra_seccion(self):
        for i in range(3):
            self._trace_eval(estado='posponer', dias_atras=i+2)
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activo ahora')
        self.assertContains(response, 'Hipótesis ·')
