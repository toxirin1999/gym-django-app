"""
Phase 37.1 — Tests para hipótesis acumulada → sugerencia experimental.

Una hipótesis acumulada no corrige el sistema; pide permiso para convertirse
en experimento.

Checklist (15):
1.  ≥ 3 senal_no_captada genera SugerenciaPlan pendiente.
2.  < 3 ocurrencias no genera sugerencia.
3.  Si hay varias hipótesis, se elige la más repetida.
4.  Si ya hay sugerencia pendiente, no se duplica.
5.  Si hay IntervencionPlan vigilar_senal activa, no se crea sugerencia.
6.  Aceptar sugerencia crea IntervencionPlan vigilar_senal de 14 días.
7.  Ignorar sugerencia aplica cooldown de 7 días.
8.  Texto de sugerencia no usa 'fallo', 'error', 'equivocó'.
9.  Texto usa vocabulario experimental: 'probar', 'vigilar', 'observar'.
10. La intervención vigilar_senal no modifica cargas (tipo solo observación).
11. La intervención aparece en Centro como "experimento activo" en intervenciones.
12. evaluar_fin_experimento: si señal baja → 'atenuada'.
13. evaluar_fin_experimento: si señal persiste → 'persiste'.
14. evaluar_fin_experimento: sin datos anteriores → 'insuficiente'.
15. Aceptar sugerencia desde Centro devuelve redirect correcto.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    SugerenciaPlan, IntervencionPlan,
    GymDecisionTrace, GymDecisionTraceEvaluation,
)
from entrenos.services.hipotesis_service import (
    generar_sugerencia_hipotesis, aceptar_sugerencia_hipotesis,
    get_sugerencia_hipotesis_activa, evaluar_fin_experimento_hipotesis,
)

PALABRAS_PROHIBIDAS = ['fallo', 'error del', 'equivocó', 'incorrecto', 'no cumpliste']
PALABRAS_EXPERIMENTALES = ['probar', 'vigilar', 'observar', 'durante', 'semana']


class HipotesisSugerenciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_h37', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestH37', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)

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
            trace=trace, resultado=resultado,
            resumen='Test.', senales_posteriores={},
        )
        return trace

    def _crear_3_senal(self, estado='posponer'):
        for i in range(3):
            self._trace_eval(estado=estado, dias_atras=i+2)


# ── Cases 1-5: generar sugerencia ────────────────────────────────────────────

class TestCase1_GeneraSugerencia(HipotesisSugerenciaBase):
    def test_tres_senal_no_captada_genera_sugerencia(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(sugerencia)
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)


class TestCase2_MenosDe3NoGenera(HipotesisSugerenciaBase):
    def test_dos_senal_no_captada_no_genera(self):
        for i in range(2):
            self._trace_eval(dias_atras=i+2)
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNone(sugerencia)


class TestCase3_EligeLaMasRepetida(HipotesisSugerenciaBase):
    def test_elige_estado_con_mas_ocurrencias(self):
        for i in range(4):
            self._trace_eval(estado='posponer', dias_atras=i+2)
        for i in range(3):
            self._trace_eval(estado='entrenar', dias_atras=i+10)
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(sugerencia)
        self.assertIn('posponer', sugerencia.patron)  # 4 > 3 → posponer wins


class TestCase4_NoDuplica(HipotesisSugerenciaBase):
    def test_no_crea_segunda_sugerencia_si_hay_pendiente(self):
        self._crear_3_senal()
        s1 = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        s2 = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(s1)
        self.assertIsNone(s2)
        self.assertEqual(SugerenciaPlan.objects.filter(
            cliente=self.cliente, patron__startswith='hipotesis_senal_',
        ).count(), 1)


class TestCase5_NoGenSiIntervencionActiva(HipotesisSugerenciaBase):
    def test_no_genera_si_hay_intervencion_vigilar_activa(self):
        self._crear_3_senal()
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=14),
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNone(sugerencia)


# ── Case 6-7: aceptar / ignorar ──────────────────────────────────────────────

class TestCase6_AceptarCreaIntervencion(HipotesisSugerenciaBase):
    def test_aceptar_crea_intervencion_vigilar_senal_14_dias(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        intervencion = aceptar_sugerencia_hipotesis(sugerencia, self.hoy)
        self.assertEqual(intervencion.tipo, IntervencionPlan.TIPO_VIGILAR_SENAL)
        self.assertEqual((intervencion.fecha_fin - intervencion.fecha_inicio).days, 14)
        self.assertEqual(intervencion.estado, IntervencionPlan.ESTADO_ACTIVA)

    def test_sugerencia_cambia_a_aceptada(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        aceptar_sugerencia_hipotesis(sugerencia, self.hoy)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_ACEPTADA)


class TestCase7_IgnorarCooldown(HipotesisSugerenciaBase):
    def test_ignorar_aplica_cooldown_7_dias(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        # Simulate ignore via view
        sugerencia.estado = SugerenciaPlan.ESTADO_IGNORADA
        sugerencia.cooldown_hasta = self.hoy + timedelta(days=7)
        sugerencia.save()
        # Try to generate again — should be blocked by cooldown
        nueva = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        self.assertIsNone(nueva)


# ── Cases 8-9: lenguaje ───────────────────────────────────────────────────────

class TestCase8_SinProhibidas(HipotesisSugerenciaBase):
    def test_texto_sin_palabras_prohibidas(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        texto = sugerencia.texto.lower()
        for palabra in PALABRAS_PROHIBIDAS:
            self.assertNotIn(palabra, texto, msg=f"Texto usa '{palabra}'")


class TestCase9_VocabularioExperimental(HipotesisSugerenciaBase):
    def test_texto_usa_vocabulario_experimental(self):
        self._crear_3_senal()
        sugerencia = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        texto = sugerencia.texto.lower()
        usa_experimental = any(k in texto for k in PALABRAS_EXPERIMENTALES)
        self.assertTrue(usa_experimental, msg=f"Texto no usa vocabulario experimental: {texto[:150]}")


# ── Case 10: intervención no cambia cargas ────────────────────────────────────

class TestCase10_IntervencionNoModificaCargas(HipotesisSugerenciaBase):
    def test_tipo_vigilar_senal_no_esta_en_freno_contextual(self):
        """vigilar_senal must not trigger evaluar_permiso_progresion brake."""
        from entrenos.services.sugerencias_service import get_intervencion_activa
        from entrenos.models import IntervencionPlan
        self._crear_3_senal()
        sug = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        aceptar_sugerencia_hipotesis(sug, self.hoy)
        # get_intervencion_activa checks for load-affecting intervention types
        intervencion = get_intervencion_activa(self.cliente, self.hoy)
        # Should not return vigilar_senal (it doesn't affect loads)
        if intervencion:
            self.assertNotEqual(intervencion.tipo, IntervencionPlan.TIPO_VIGILAR_SENAL)


# ── Case 11: Centro muestra experimento activo ────────────────────────────────

class TestCase11_CentroMuestraExperimento(HipotesisSugerenciaBase):
    def test_centro_muestra_propuesta_experimento(self):
        self._crear_3_senal()
        c = Client()
        c.login(username='tester_h37', password='x')
        response = c.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Propuesta de experimento')
        self.assertContains(response, 'Probar 2 semanas')


# ── Cases 12-14: evaluar fin de experimento ───────────────────────────────────

class TestCase12_ExperimentoAtenuado(HipotesisSugerenciaBase):
    def test_señal_baja_resultado_atenuada(self):
        # 3 senal_no_captada before experiment
        for i in range(3):
            self._trace_eval(dias_atras=20+i)
        # Create expired intervention
        intervencion = IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            fecha_inicio=self.hoy - timedelta(days=14),
            fecha_fin=self.hoy - timedelta(days=1),
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        # 1 senal_no_captada during experiment (40%+ reduction)
        self._trace_eval(dias_atras=7)
        resultado = evaluar_fin_experimento_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['resultado'], 'atenuada')


class TestCase13_ExperimentoPersiste(HipotesisSugerenciaBase):
    def test_señal_persiste_resultado_persiste(self):
        # 2 before + 2 during = no reduction
        for i in range(2):
            self._trace_eval(dias_atras=20+i)
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            fecha_inicio=self.hoy - timedelta(days=14),
            fecha_fin=self.hoy - timedelta(days=1),
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        for i in range(2):
            self._trace_eval(dias_atras=7+i)
        resultado = evaluar_fin_experimento_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['resultado'], 'persiste')


class TestCase14_SinDatosAnteriores(HipotesisSugerenciaBase):
    def test_sin_datos_previos_resultado_insuficiente(self):
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            fecha_inicio=self.hoy - timedelta(days=14),
            fecha_fin=self.hoy - timedelta(days=1),
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        resultado = evaluar_fin_experimento_hipotesis(self.cliente, self.hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['resultado'], 'insuficiente')


# ── Case 15: redirect correcto ────────────────────────────────────────────────

class TestCase15_RedirectCorrecto(HipotesisSugerenciaBase):
    def test_aceptar_hipotesis_view_redirige_a_centro(self):
        self._crear_3_senal()
        sug = generar_sugerencia_hipotesis(self.cliente, self.hoy)
        c = Client()
        c.login(username='tester_h37', password='x')
        response = c.post(reverse('clientes:aceptar_hipotesis', args=[sug.id]))
        self.assertRedirects(response, reverse('clientes:plan_decisiones'))
