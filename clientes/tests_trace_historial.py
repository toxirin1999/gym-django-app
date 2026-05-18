"""
Phase 33.1 — Tests del historial de decisiones humanizado en el Centro de decisiones.

Checklist (12 items):
1.  Centro muestra trazas recientes si existen.
2.  No muestra bloque de historial si no hay traces.
3.  Muestra causa/decisión en lenguaje humano (no técnico).
4.  Capas visibles en lenguaje legible (no nombres de campo).
5.  Capas suprimidas muestran razón, no nombre técnico.
6.  No muestra JSON crudo.
7.  No muestra None, [], {} ni claves internas.
8.  No duplica preferencia y distribución si hay supresión.
9.  La lectura del trace pasa auditoría narrativa.
10. Lesión muestra zona/fase sin diagnóstico médico.
11. Historial limitado a N elementos (7).
12. Fallo leyendo traces no rompe el Centro de decisiones.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import GymDecisionTrace
from entrenos.services.decision_trace_service import humanizar_trace, get_traces_recientes


PALABRAS_TECNICAS = [
    'decision_estado', 'causa_principal', 'capas_visibles', 'capas_suprimidas',
    'senales_motor', 'explicacion_senales', 'lesion_contexto',
    'redistrib_pierna_futbol', 'evitar_pierna_tras_futbol',
    'futbol_reciente', 'lesion_activa', 'readiness_bajo',
]
PALABRAS_PROHIBIDAS_UI = ['None', '[]', '{}', 'null', 'True', 'False']
ABSOLUTOS = ['siempre', 'nunca', 'debes', 'tienes que']
CULPA = ['no cumpliste', 'fallaste', 'incumplimiento']


class TraceHistorialBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_hist33', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestHist33', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 24)

    def _crear_trace(self, fecha=None, **kwargs):
        defaults = {
            'decision_estado': 'entrenar',
            'causa_principal': 'sesion_hoy',
            'senales_motor': {},
            'capas_visibles': [],
            'capas_suprimidas': [],
            'explicacion_senales': ['Sesión del plan de hoy.'],
            'preferencias_activas': [],
            'intervenciones_activas': [],
            'lesion_contexto': {},
        }
        defaults.update(kwargs)
        return GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=fecha or self.hoy,
            **defaults,
        )

    def _get_centro(self):
        c = Client()
        c.login(username='tester_hist33', password='x')
        return c.get(reverse('clientes:plan_decisiones'))


# ── Cases 1-2: presencia del bloque ─────────────────────────────────────────

class TestCase1_BloqueMostrado(TraceHistorialBase):
    def test_muestra_historial_si_hay_traces(self):
        self._crear_trace()
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Por qué decidió así recientemente')

    def test_no_muestra_historial_sin_traces(self):
        GymDecisionTrace.objects.filter(cliente=self.cliente).delete()
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Por qué decidió así recientemente')


# ── Cases 3-5: lenguaje humano en la salida ──────────────────────────────────

class TestCase3_LenguajeHumano(TraceHistorialBase):
    def test_humanizar_trace_no_devuelve_campos_tecnicos(self):
        trace = self._crear_trace(causa_principal='futbol_reciente', decision_estado='posponer')
        h = humanizar_trace(trace)
        texto_total = str(h)
        for tecnico in PALABRAS_TECNICAS:
            self.assertNotIn(tecnico, texto_total,
                             msg=f"humanizar_trace expone campo técnico: '{tecnico}'")

    def test_decision_label_es_legible(self):
        trace = self._crear_trace(decision_estado='posponer')
        h = humanizar_trace(trace)
        self.assertNotEqual(h['decision_label'], 'posponer')
        self.assertGreater(len(h['decision_label']), 5)


class TestCase4_CapasLegibles(TraceHistorialBase):
    def test_capas_usadas_sin_nombres_de_campo(self):
        trace = self._crear_trace(capas_visibles=['lesion_aviso', 'preferencia_aplicada'])
        h = humanizar_trace(trace)
        capas_str = ' '.join(h['capas_usadas'])
        self.assertNotIn('lesion_aviso', capas_str)
        self.assertNotIn('preferencia_aplicada', capas_str)
        # Should use human names
        self.assertIn('lesión', capas_str.lower())
        self.assertIn('preferencia', capas_str.lower())


class TestCase5_CapasSuprimidasRazon(TraceHistorialBase):
    def test_supresion_muestra_razon_humana(self):
        trace = self._crear_trace(capas_suprimidas=['distribucion_aviso'])
        h = humanizar_trace(trace)
        self.assertIsNotNone(h['supresion_razon'])
        # Should NOT contain technical names
        self.assertNotIn('distribucion_aviso', h['supresion_razon'])
        self.assertNotIn('capas_suprimidas', h['supresion_razon'])


# ── Cases 6-7: sin JSON crudo ni valores nulos ────────────────────────────────

class TestCase6_SinJSONcrudo(TraceHistorialBase):
    def test_html_sin_nombres_tecnicos(self):
        self._crear_trace(
            capas_visibles=['lesion_aviso'],
            capas_suprimidas=['distribucion_aviso'],
            lesion_contexto={'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False, 'ejercicios_riesgo': []},
        )
        response = self._get_centro()
        html = response.content.decode()
        for tecnico in PALABRAS_TECNICAS:
            self.assertNotIn(tecnico, html,
                             msg=f"HTML del Centro expone campo técnico: '{tecnico}'")


class TestCase7_SinValoresVacios(TraceHistorialBase):
    def test_html_sin_none_ni_listas_vacias(self):
        self._crear_trace()
        response = self._get_centro()
        html = response.content.decode()
        for prohibido in PALABRAS_PROHIBIDAS_UI:
            # Only check in the historial section context, not in JS
            # (JS True/False are normal)
            if prohibido in ('True', 'False'):
                continue
            self.assertNotIn(f'>{prohibido}<', html,
                             msg=f"HTML muestra valor vacío: '{prohibido}'")


# ── Case 8: sin duplicación ───────────────────────────────────────────────────

class TestCase8_SinDuplicacion(TraceHistorialBase):
    def test_supresion_evita_doble_mensaje(self):
        trace = self._crear_trace(
            capas_visibles=['preferencia_aplicada'],
            capas_suprimidas=['distribucion_aviso'],
            explicacion_senales=['El plan recuerda que separar pierna del fútbol te dio más margen.'],
        )
        h = humanizar_trace(trace)
        # preferencia is in capas_usadas, distribucion should not be
        capas_str = ' '.join(h['capas_usadas'])
        self.assertNotIn('distribución', capas_str)
        self.assertIn('preferencia', capas_str.lower())


# ── Case 9: auditoría narrativa ───────────────────────────────────────────────

class TestCase9_AuditoriaNarrativa(TraceHistorialBase):
    def test_traces_humanizados_sin_absolutos_ni_culpa(self):
        trace = self._crear_trace(
            capas_visibles=['lesion_aviso', 'preferencia_aplicada'],
            explicacion_senales=[
                'Zona Rodilla en retorno. Ejercicios a revisar: Sentadilla.',
                'El plan recuerda que separar pierna del fútbol te dio más margen.',
            ],
        )
        h = humanizar_trace(trace)
        texto_total = (
            h.get('explicacion', '') + ' ' +
            ' '.join(h.get('capas_usadas', [])) + ' ' +
            (h.get('supresion_razon') or '') + ' ' +
            (h.get('lesion_label') or '')
        ).lower()
        for palabra in ABSOLUTOS + CULPA:
            self.assertNotIn(palabra, texto_total,
                             msg=f"Trace humanizado usa '{palabra}'")


# ── Case 10: lesión sin diagnóstico ──────────────────────────────────────────

class TestCase10_LesionSinDiagnostico(TraceHistorialBase):
    def test_lesion_label_sin_diagnostico(self):
        trace = self._crear_trace(lesion_contexto={
            'zona': 'Rodilla', 'fase': 'RETORNO',
            'es_bloqueante': False, 'ejercicios_riesgo': ['Sentadilla'],
        })
        h = humanizar_trace(trace)
        label = h['lesion_label'].lower()
        self.assertIn('rodilla', label)
        self.assertNotIn('prohibido', label)
        self.assertNotIn('garantizado', label)
        self.assertNotIn('peligroso', label)


# ── Case 11: límite de N elementos ────────────────────────────────────────────

class TestCase11_LimiteN(TraceHistorialBase):
    def test_get_traces_recientes_limitado(self):
        for i in range(10):
            GymDecisionTrace.objects.get_or_create(
                cliente=self.cliente,
                fecha=self.hoy - timedelta(days=i),
                defaults={
                    'decision_estado': 'entrenar',
                    'causa_principal': 'sesion_hoy',
                    'senales_motor': {}, 'capas_visibles': [], 'capas_suprimidas': [],
                    'explicacion_senales': ['Sesión normal.'],
                    'preferencias_activas': [], 'intervenciones_activas': [], 'lesion_contexto': {},
                },
            )
        traces = get_traces_recientes(self.cliente, n=5)
        self.assertLessEqual(len(traces), 5)


# ── Case 12: fallo de trace no rompe el Centro ───────────────────────────────

class TestCase12_FalloSilencioso(TraceHistorialBase):
    def test_centro_carga_sin_traces(self):
        """Sin traces, el Centro carga igual de bien sin la sección de historial."""
        GymDecisionTrace.objects.filter(cliente=self.cliente).delete()
        response = self._get_centro()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activo ahora mismo')
        self.assertNotContains(response, 'Por qué decidió así recientemente')

    def test_contexto_traces_recientes_es_lista_cuando_falla(self):
        """get_traces_recientes degrada silenciosamente devolviendo []."""
        resultado = get_traces_recientes(None, n=5)  # None cliente → falla internamente
        self.assertIsInstance(resultado, list)
