"""
Phase 32.1 — Tests for GymDecisionTrace (memoria de decisiones).

El sistema no solo debe decidir bien; debe poder recordar por qué decidió así.

Checklist:
1.  Crea traza cuando el motor genera decisión del día.
2.  Guarda causa_principal y decision_estado correctamente.
3.  Guarda capas_visibles del panel.
4.  Guarda capas_suprimidas por no-duplicación.
5.  Guarda preferencias_activas si influyeron.
6.  Guarda intervenciones_activas si influyeron.
7.  Guarda lesion_contexto si frenó o modificó carga.
8.  No guarda lenguaje culpabilizador en explicacion_senales.
9.  No duplica trazas para mismo (cliente, fecha).
10. Permite reconstruir explicación humana posterior.
11. Si no hay señales relevantes y es descanso, no crea traza.
12. Si una capa se oculta por Preferencia > Distribución, queda en capas_suprimidas.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionTrace, IntervencionPlan, PreferenciaPlanAprendida
from entrenos.services.decision_trace_service import registrar_decision_trace


ABSOLUTOS = ['siempre', 'nunca', 'debes', 'tienes que']
CULPA     = ['no cumpliste', 'fallaste', 'incumplimiento']


class TraceBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_trace32', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestTrace32', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 24)

    def _decision(self, **kwargs):
        base = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None, 'entrenamiento': {},
            'mensaje': 'Sesión prevista.', 'causa_principal': 'sesion_hoy',
            'modo_reducido': False, 'distribucion_aviso': None,
            'preferencia_aplicada': None, 'lesion_aviso': None,
            'contexto_fisico': {
                'lesion_activa': False, 'lesion_fase': None,
                'futbol_reciente': False, 'energia_baja': False,
                'energia_valor': None, 'readiness_bajo': False,
                'readiness_valor': None, 'preferencias_activas': [],
            },
        }
        base.update(kwargs)
        return base


# ── Case 1-2: creación básica ─────────────────────────────────────────────────

class TestCase1_CreacionBasica(TraceBase):
    def test_crea_traza(self):
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        self.assertTrue(GymDecisionTrace.objects.filter(
            cliente=self.cliente, fecha=self.hoy,
        ).exists())

    def test_guarda_estado_y_causa(self):
        decision = self._decision(estado='recuperar', causa_principal='lesion')
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertEqual(t.decision_estado, 'recuperar')
        self.assertEqual(t.causa_principal, 'lesion')


# ── Case 3: capas_visibles ────────────────────────────────────────────────────

class TestCase3_CapasVisibles(TraceBase):
    def test_guarda_lesion_aviso_en_capas_visibles(self):
        decision = self._decision(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Sentadilla'],
            'mensaje': 'Revisar Rodilla.',
        })
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn('lesion_aviso', t.capas_visibles)

    def test_guarda_preferencia_en_capas_visibles(self):
        decision = self._decision(preferencia_aplicada={
            'tipo': 'evitar_pierna_tras_futbol',
            'mensaje': 'El plan recuerda separar pierna del fútbol.',
            'accion_sugerida': 'posponer_recomendado',
        })
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn('preferencia_aplicada', t.capas_visibles)


# ── Case 4: capas_suprimidas ──────────────────────────────────────────────────

class TestCase4_CapasSuprimidas(TraceBase):
    def test_distribucion_suprimida_queda_en_capas_suprimidas(self):
        decision = self._decision(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda separar pierna.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba activa: separar pierna.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn('distribucion_aviso', t.capas_suprimidas)
        self.assertNotIn('distribucion_aviso', t.capas_visibles)


# ── Case 5: preferencias_activas ──────────────────────────────────────────────

class TestCase5_PreferenciasActivas(TraceBase):
    def test_guarda_preferencias_activas(self):
        decision = self._decision()
        decision['contexto_fisico']['preferencias_activas'] = ['evitar_pierna_tras_futbol']
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn('evitar_pierna_tras_futbol', t.preferencias_activas)


# ── Case 6: intervenciones_activas ───────────────────────────────────────────

class TestCase6_IntervencionesActivas(TraceBase):
    def test_guarda_intervenciones_activas(self):
        from datetime import timedelta
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=3),
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn(IntervencionPlan.TIPO_NO_SUBIR, t.intervenciones_activas)


# ── Case 7: lesion_contexto ───────────────────────────────────────────────────

class TestCase7_LesionContexto(TraceBase):
    def test_guarda_lesion_contexto(self):
        decision = self._decision(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Sentadilla', 'Prensa'],
            'mensaje': 'Revisar.',
        })
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertEqual(t.lesion_contexto['zona'], 'Rodilla')
        self.assertEqual(t.lesion_contexto['fase'], 'RETORNO')
        self.assertIn('Sentadilla', t.lesion_contexto['ejercicios_riesgo'])

    def test_sin_lesion_contexto_vacio(self):
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertEqual(t.lesion_contexto, {})


# ── Case 8: sin lenguaje culpabilizador ──────────────────────────────────────

class TestCase8_SinCulpa(TraceBase):
    def test_explicacion_senales_sin_culpa_ni_absolutos(self):
        decision = self._decision(
            lesion_aviso={
                'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
                'ejercicios_en_riesgo': ['Sentadilla'],
                'mensaje': 'En fase de retorno la articulación puede tolerar carga gradual.',
            },
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
        )
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        for senal in t.explicacion_senales:
            texto = senal.lower()
            for palabra in ABSOLUTOS + CULPA:
                self.assertNotIn(palabra, texto,
                                 msg=f"Senal usa '{palabra}': {senal}")


# ── Case 9: no duplica ────────────────────────────────────────────────────────

class TestCase9_NoDuplicados(TraceBase):
    def test_no_crea_duplicados_misma_fecha(self):
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        registrar_decision_trace(
            self.cliente,
            self._decision(estado='recuperar', causa_principal='lesion'),
            self.hoy,
        )
        count = GymDecisionTrace.objects.filter(
            cliente=self.cliente, fecha=self.hoy,
        ).count()
        self.assertEqual(count, 1)

    def test_update_in_place_con_nuevo_estado(self):
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        registrar_decision_trace(
            self.cliente,
            self._decision(estado='posponer', causa_principal='fatiga_alta'),
            self.hoy,
        )
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertEqual(t.decision_estado, 'posponer')


# ── Case 10: explicación humana ───────────────────────────────────────────────

class TestCase10_ExplicacionHumana(TraceBase):
    def test_get_explicacion_humana_con_senales(self):
        decision = self._decision(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Sentadilla'],
            'mensaje': 'Zona Rodilla en retorno. Ejercicios a revisar.',
        })
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        explicacion = t.get_explicacion_humana()
        self.assertIsInstance(explicacion, str)
        self.assertGreater(len(explicacion), 5)

    def test_get_explicacion_humana_sin_senales(self):
        registrar_decision_trace(self.cliente, self._decision(), self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        explicacion = t.get_explicacion_humana()
        self.assertIn(str(self.hoy), explicacion)


# ── Case 11: descanso limpio no crea traza ────────────────────────────────────

class TestCase11_DescansoSinTraza(TraceBase):
    def test_descanso_sin_senales_no_crea_traza(self):
        decision = self._decision(
            estado='descanso', causa_principal='descanso_planificado',
        )
        registrar_decision_trace(self.cliente, decision, self.hoy)
        existe = GymDecisionTrace.objects.filter(
            cliente=self.cliente, fecha=self.hoy,
        ).exists()
        self.assertFalse(existe)


# ── Case 12: capa suprimida registrada ───────────────────────────────────────

class TestCase12_CapaSuprimidaRegistrada(TraceBase):
    def test_supresion_registrada_con_detalle(self):
        decision = self._decision(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda separar pierna.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba activa.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        registrar_decision_trace(self.cliente, decision, self.hoy)
        t = GymDecisionTrace.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertIn('distribucion_aviso', t.capas_suprimidas)
        # Should NOT be in visible layers
        self.assertNotIn('distribucion_aviso', t.capas_visibles)
