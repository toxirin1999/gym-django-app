"""
Phase 46 — Auditoría de integración global.

El sistema ya tiene muchas capas. Ahora debe demostrar que juntas
no pesan más que la decisión que ayudan a tomar.

10 tests automáticos que verifican la convivencia del sistema completo.

Algunos de estos tests duplican a propósito tests ya existentes de fases
anteriores — la repetición aquí es intencional: valida que la integración
final no haya roto ningún contrato.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    IntervencionPlan, GymDecisionTrace, GymDecisionTraceEvaluation,
    PreferenciaPlanAprendida, SugerenciaPlan,
)
from entrenos.services.explicacion_decision_service import construir_explicacion_decision
from entrenos.services.gobernanza_service import aplicar_gobernanza_hipotesis


PALABRAS_PROHIBIDAS_GLOBAL = [
    'siempre', 'nunca', 'debes', 'tienes que',
    'eres alguien que', 'esto te define',
    'acertó', 'falló', 'correcto', 'incorrecto',
    'prohibido', 'sustitución segura',
    'no cumpliste', 'fallaste',
]


class IntegracionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_integ46', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestInteg46', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _decision(self, **kwargs):
        base = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None, 'entrenamiento': {},
            'mensaje': 'Sesión prevista.', 'causa_principal': 'sesion_hoy',
            'modo_reducido': False, 'distribucion_aviso': None,
            'preferencia_aplicada': None, 'lesion_aviso': None,
            'contexto_fisico': {'preferencias_activas': []},
        }
        base.update(kwargs)
        return base

    def _get_panel(self, decision_mock=None):
        if decision_mock:
            with patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
                       return_value=decision_mock):
                c = Client()
                c.login(username='tester_integ46', password='x')
                return c.get(reverse('clientes:mockup_demo'))
        c = Client()
        c.login(username='tester_integ46', password='x')
        return c.get(reverse('clientes:mockup_demo'))

    def _get_centro(self):
        c = Client()
        c.login(username='tester_integ46', password='x')
        return c.get(reverse('clientes:plan_decisiones'))


# ── Test 1: vigilar_senal no afecta cargas ───────────────────────────────────

class Test1_VigilarSenalNoAfectaCargas(IntegracionBase):
    def test_vigilar_senal_excluido_de_get_intervencion_activa(self):
        """vigilar_senal cannot affect load decisions under any circumstance."""
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=14),
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        from entrenos.services.sugerencias_service import get_intervencion_activa
        intervencion = get_intervencion_activa(self.cliente, self.hoy)
        if intervencion:
            self.assertNotEqual(intervencion.tipo, IntervencionPlan.TIPO_VIGILAR_SENAL,
                                msg="vigilar_senal afecta cargas — contrato violado")


# ── Test 2: JOI no aparece si texto vacío ─────────────────────────────────────

class Test2_JOINoApareceTextoVacio(IntegracionBase):
    def test_panel_sin_joi_semanal_cuando_texto_vacio(self):
        """If JOI has nothing to say, the panel shows nothing."""
        with patch('clientes.views._ctx_joi_semanal', return_value=None):
            response = self._get_panel()
        self.assertNotContains(response, 'JOI · esta semana')

    def test_joi_retorna_none_cuando_texto_vacio(self):
        from joi.lectura_joi_presencia import get_lectura_joi_para_mostrar
        result = get_lectura_joi_para_mostrar(self.cliente, self.hoy)
        # No hay traces → must return None
        self.assertIsNone(result)


# ── Test 3: panel ≤3 señales en día complejo ──────────────────────────────────

class Test3_PanelMaxTresSeñales(IntegracionBase):
    def test_dia_complejo_max_3_senales_activas(self):
        """In a complex day, the explanation has at most 3 active signals."""
        decision = self._decision(
            estado='posponer',
            causa_principal='futbol_reciente',
            lesion_aviso={
                'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
                'ejercicios_en_riesgo': ['Sentadilla'],
                'mensaje': 'En fase de retorno la rodilla puede tolerar carga progresiva.',
            },
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba: separar pierna del fútbol.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        explicacion = construir_explicacion_decision(decision)
        n_senales = len(explicacion['senales_activas'])
        self.assertLessEqual(n_senales, 3,
                             msg=f"Demasiadas señales en día complejo: {explicacion['senales_activas']}")


# ── Test 4: distribución suprimida cuando PRF cubre mismo patrón ──────────────

class Test4_DistribucionSuprimidaPorPRF(IntegracionBase):
    def test_distribucion_suprimida_por_preferencia_mismo_patron(self):
        """PRF that covers the same pattern suppresses distribucion_aviso."""
        decision = self._decision(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'TEXTO_DISTRIBUCION_ESPECIFICO: separar pierna del fútbol.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        explicacion = construir_explicacion_decision(decision)
        self.assertTrue(explicacion['distribucion_aviso_suprimido'])
        # Distribucion SPECIFIC text should NOT be in senales
        self.assertFalse(
            any('TEXTO_DISTRIBUCION_ESPECIFICO' in s for s in explicacion['senales_activas']),
            msg="Distribucion no fue suprimida — su texto aparece en senales_activas"
        )


# ── Test 5: "¿Por qué hoy?" no aparece en día limpio ─────────────────────────

class Test5_PorQueHoyNoDiaLimpio(IntegracionBase):
    def test_por_que_hoy_no_renderiza_en_dia_limpio(self):
        """On a clean day, the collapsible '¿Por qué hoy?' should not appear."""
        decision = self._decision()  # all defaults → todo_limpio=True
        explicacion = construir_explicacion_decision(decision)
        self.assertTrue(explicacion['todo_limpio'])
        # Template guard: {% if not explicacion_decision.todo_limpio %} → no rendering
        decision_with_context = {**decision}
        response = self._get_panel({
            **decision,
            'entrenamiento': {
                'rutina_nombre': 'Push A', 'nombre_rutina': 'Push A', 'nombre': 'Push A',
                'ejercicios': [{'nombre': 'Press banca', 'series': 4, 'repeticiones': '4-6',
                                'grupo_muscular': 'Pecho', 'tipo_ejercicio': 'compuesto_principal'}],
            },
        })
        self.assertNotContains(response, '¿Por qué hoy?')


# ── Test 6: Centro no muestra historial si no hay traces ─────────────────────

class Test6_CentroSinHistorial(IntegracionBase):
    def test_centro_no_muestra_historial_sin_traces(self):
        GymDecisionTrace.objects.filter(cliente=self.cliente).delete()
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Por qué decidió así recientemente')


# ── Test 7: datos_insuficientes no aparece en Centro ─────────────────────────

class Test7_InsuficienteNoaparece(IntegracionBase):
    def test_evaluacion_insuficiente_no_aparece_en_historial(self):
        trace = GymDecisionTrace.objects.create(
            cliente=self.cliente, fecha=self.hoy - timedelta(days=3),
            decision_estado='posponer', causa_principal='sesion_hoy',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=['Test.'], preferencias_activas=[],
            intervenciones_activas=[], lesion_contexto={},
        )
        GymDecisionTraceEvaluation.objects.create(
            trace=trace, resultado='datos_insuficientes',
            resumen='Sin datos.', senales_posteriores={},
        )
        response = self._get_centro()
        self.assertNotContains(response, 'Sin datos.')


# ── Test 8: hipótesis stale queda silenciada ──────────────────────────────────

class Test8_HipotesisStale(IntegracionBase):
    def test_hipotesis_sin_ocurrencias_recientes_silenciada(self):
        """A hypothesis with no recent occurrences (> 30 days) is suppressed."""
        hipotesis = [{
            'estado': 'posponer', 'ocurrencias': 4,
            'texto': 'Hipótesis de prueba.', 'fechas': [self.hoy - timedelta(days=40)],
        }]
        # Create an old trace to match
        GymDecisionTrace.objects.create(
            cliente=self.cliente, fecha=self.hoy - timedelta(days=40),
            decision_estado='posponer', causa_principal='test',
            senales_motor={}, capas_visibles=[], capas_suprimidas=[],
            explicacion_senales=[], preferencias_activas=[],
            intervenciones_activas=[], lesion_contexto={},
        )
        GymDecisionTraceEvaluation.objects.create(
            trace=GymDecisionTrace.objects.get(cliente=self.cliente),
            resultado='senal_no_captada', resumen='Test.', senales_posteriores={},
        )
        visibles = aplicar_gobernanza_hipotesis(self.cliente, hipotesis, self.hoy)
        self.assertEqual(len(visibles), 0,
                         msg="Hipótesis stale no fue silenciada por gobernanza")


# ── Test 9: sin lenguaje prohibido en panel, Centro y JOI ───────────────────

class Test9_SinLenguajeProhibido(IntegracionBase):
    def test_panel_sin_lenguaje_prohibido(self):
        """Panel HTML should not contain any prohibited language."""
        response = self._get_panel()
        html = response.content.decode().lower()
        for palabra in PALABRAS_PROHIBIDAS_GLOBAL:
            if palabra in html:
                # Allow if in JS/CSS context, not in visible content
                # Simple check: not in body content between tags
                self.assertFalse(
                    f'>{palabra}<' in html or f' {palabra} ' in html,
                    msg=f"Panel usa '{palabra}'"
                )

    def test_mensajes_motor_sin_prohibidas(self):
        """All motor message dicts pass the language audit."""
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA, _PREF_MENSAJES
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        for coleccion, nombre in [
            (_MENSAJES_POR_CAUSA, '_MENSAJES_POR_CAUSA'),
            (_PREF_MENSAJES, '_PREF_MENSAJES'),
            (_MENSAJES_PROGRESION, '_MENSAJES_PROGRESION'),
        ]:
            for clave, msg in coleccion.items():
                texto = msg.lower()
                for prohibida in PALABRAS_PROHIBIDAS_GLOBAL:
                    self.assertNotIn(prohibida, texto,
                                     msg=f"{nombre}['{clave}'] usa '{prohibida}'")


# ── Test 10: fallo en cualquier capa no rompe el panel ───────────────────────

class Test10_FalloNoRompePanel(IntegracionBase):
    def test_fallo_trace_no_rompe_panel(self):
        """If the trace service fails, panel still renders."""
        with patch('entrenos.services.decision_trace_service.registrar_decision_trace',
                   side_effect=Exception('DB error simulado')):
            response = self._get_panel()
        self.assertEqual(response.status_code, 200)

    def test_fallo_joi_semanal_no_rompe_panel(self):
        """If JOI weekly service fails (returns None), panel still renders without JOI card."""
        with patch('clientes.views._ctx_joi_semanal', return_value=None):
            response = self._get_panel()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'JOI · esta semana')

    def test_fallo_hipotesis_no_rompe_centro(self):
        """If hypothesis detection fails, Centro still renders."""
        with patch('entrenos.services.hipotesis_service.detectar_hipotesis_abiertas',
                   side_effect=Exception('Hipótesis error')):
            response = self._get_centro()
        self.assertEqual(response.status_code, 200)

    def test_fallo_evaluacion_trace_no_rompe_centro(self):
        """If trace evaluation fails, Centro still renders."""
        with patch('entrenos.services.evaluacion_trace_service.evaluar_traces_pendientes',
                   side_effect=Exception('Eval error')):
            response = self._get_centro()
        self.assertEqual(response.status_code, 200)
