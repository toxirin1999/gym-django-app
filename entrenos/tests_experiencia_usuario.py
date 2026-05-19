"""
Phase 41 — Validación de experiencia de usuario.

El sistema ya sabe decidir, recordar y aprender.
Ahora tiene que demostrar que se entiende.

Tres escenarios:
41.1 — Día vacío: ¿se siente tranquilo o parece roto?
41.2 — Día complejo: ¿explica o se justifica demasiado?
41.3 — Lectura semanal JOI: ¿suena humano o como informe?

No tocar el motor. No añadir modelos. Solo validar experiencia.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    GymDecisionTrace, GymDecisionTraceEvaluation, PreferenciaPlanAprendida,
)
from entrenos.services.lectura_semanal_service import construir_lectura_semanal_memoria, _construir_texto
from entrenos.services.explicacion_decision_service import construir_explicacion_decision


class ExperienciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_ux41', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestUX41', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)

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


# ── Phase 41.1 — Día vacío ─────────────────────────────────────────────────

class TestDiaVacio(ExperienciaBase):
    """¿La app se siente tranquila o parece vacía?"""

    def test_explicacion_todo_limpio_cuando_no_hay_senales(self):
        decision = self._decision()
        resultado = construir_explicacion_decision(decision)
        self.assertTrue(resultado['todo_limpio'])
        self.assertEqual(resultado['senales_activas'], [])

    def test_por_que_hoy_no_aparece_sin_senales(self):
        """El colapsable no debe renderizarse cuando no hay nada que explicar."""
        decision = self._decision()
        # When todo_limpio=True, template should NOT show '¿Por qué hoy?'
        # This is enforced by {% if explicacion_decision and not explicacion_decision.todo_limpio %}
        resultado = construir_explicacion_decision(decision)
        self.assertTrue(resultado['todo_limpio'])
        # No false noise
        self.assertEqual(len(resultado['senales_activas']), 0)

    def test_lectura_semanal_vacia_sin_datos(self):
        lectura = construir_lectura_semanal_memoria(self.cliente, self.hoy)
        self.assertFalse(lectura['hay_datos'])
        self.assertEqual(lectura['texto_joi'], '')

    def test_centro_estado_limpio_hero(self):
        """When no active signals, Centro Hero shows 'Sin señales activas'."""
        c = Client()
        c.login(username='tester_ux41', password='x')
        response = c.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sin señales activas')


# ── Phase 41.2 — Día complejo ─────────────────────────────────────────────

class TestDiaComplejo(ExperienciaBase):
    """¿La app explica o se justifica demasiado?"""

    def _dia_complejo(self):
        return self._decision(
            estado='posponer',
            causa_principal='futbol_reciente',
            lesion_aviso={
                'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
                'ejercicios_en_riesgo': ['Sentadilla'],
                'mensaje': 'En fase de retorno la Rodilla puede tolerar carga progresiva.',
            },
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba activa: separar pierna del fútbol.',
                'accion_sugerida': 'posponer_opcional',
            },
        )

    def test_dia_complejo_tiene_senales_pero_no_mas_de_3(self):
        """Día complejo no debe generar más de 3 señales activas simultáneas."""
        decision = self._dia_complejo()
        resultado = construir_explicacion_decision(decision)
        self.assertLessEqual(len(resultado['senales_activas']), 3,
                             msg=f"Demasiadas señales: {resultado['senales_activas']}")

    def test_distribucion_suprimida_cuando_preferencia_activa(self):
        """Cuando PRF y distribución dicen lo mismo, distribución se suprime."""
        decision = self._dia_complejo()
        resultado = construir_explicacion_decision(decision)
        self.assertTrue(resultado['distribucion_aviso_suprimido'])
        # No distribución text in senales
        self.assertFalse(
            any('Prueba activa' in s for s in resultado['senales_activas'])
        )

    def test_causa_principal_siempre_legible(self):
        """La causa principal se traduce a lenguaje humano."""
        from entrenos.services.explicacion_decision_service import _CAUSAS
        self.assertIn('futbol_reciente', _CAUSAS)
        label = _CAUSAS['futbol_reciente']
        self.assertNotEqual(label, 'futbol_reciente')  # not technical
        self.assertGreater(len(label), 5)

    def test_lesion_primera_en_senales(self):
        """La lesión aparece primero — tiene prioridad semántica."""
        decision = self._dia_complejo()
        resultado = construir_explicacion_decision(decision)
        if resultado['senales_activas']:
            primera = resultado['senales_activas'][0].lower()
            self.assertIn('rodilla', primera,
                          msg=f"Lesión no aparece primera: {resultado['senales_activas']}")


# ── Phase 41.3 — Lectura semanal JOI ─────────────────────────────────────

class TestLecturaSemanalVoz(ExperienciaBase):
    """¿Suena humano o como informe?"""

    def test_texto_no_empieza_con_el_sistema(self):
        """La lectura debe sonar como JOI, no como un log técnico."""
        texto = _construir_texto(4, {'entrenar': 3, 'posponer': 1}, 2, 0, 0, 1)
        texto_lower = texto.lower()
        frases_administrativas = [
            'el sistema registró', 'el sistema generó',
            'se han procesado', 'registró 4 decisiones',
        ]
        for frase in frases_administrativas:
            self.assertNotIn(frase, texto_lower,
                             msg=f"Texto suena a informe: '{frase}' en '{texto[:120]}'")

    def test_semana_positiva_usa_tono_de_continuidad(self):
        """2 libero_margen + 0 no_captadas → tono de continuidad."""
        texto = _construir_texto(3, {'entrenar': 3}, 2, 0, 0, 0).lower()
        tono_continuidad = ['margen', 'continuidad', 'señal de']
        usa_continuidad = any(k in texto for k in tono_continuidad)
        self.assertTrue(usa_continuidad, msg=f"Texto no usa tono de continuidad: {texto}")

    def test_semana_mixta_conectores_naturales(self):
        """2 positivas + 1 no_captada → conectores como 'pero también'."""
        texto = _construir_texto(4, {'entrenar': 4}, 2, 1, 0, 0).lower()
        conectores = ['pero', 'también', 'además', 'sin embargo']
        usa_conector = any(k in texto for k in conectores)
        self.assertTrue(usa_conector, msg=f"Texto mixto no usa conectores: {texto}")

    def test_hipotesis_abierta_suena_como_hilo(self):
        """Hipótesis no debe sonar como alerta, sino como hilo pendiente."""
        texto = _construir_texto(3, {'entrenar': 3}, 1, 0, 1, 0).lower()
        frases_hilo = ['sigue abierta', 'pendiente', 'anotada', 'observando']
        usa_hilo = any(k in texto for k in frases_hilo)
        self.assertTrue(usa_hilo, msg=f"Hipótesis suena a alerta: {texto}")

    def test_semana_sin_senales_es_corta(self):
        """Sin señales especiales → texto breve, no relleno."""
        texto = _construir_texto(2, {'entrenar': 2}, 0, 0, 0, 0)
        self.assertLess(len(texto), 150,
                        msg=f"Texto vacío demasiado largo: {texto}")

    def test_lectura_con_datos_reales_produce_texto(self):
        """Con traces reales, la lectura produce texto no vacío."""
        for i in range(2):
            tr = GymDecisionTrace.objects.create(
                cliente=self.cliente,
                fecha=self.hoy - timedelta(days=i),
                decision_estado='entrenar',
                causa_principal='sesion_hoy',
                senales_motor={}, capas_visibles=[], capas_suprimidas=[],
                explicacion_senales=[], preferencias_activas=[],
                intervenciones_activas=[], lesion_contexto={},
            )
            GymDecisionTraceEvaluation.objects.create(
                trace=tr, resultado='libero_margen',
                resumen='Test.', senales_posteriores={},
            )
        lectura = construir_lectura_semanal_memoria(self.cliente, self.hoy)
        self.assertTrue(lectura['hay_datos'])
        self.assertGreater(len(lectura['texto_joi']), 10)
        # Should NOT sound administrative
        self.assertNotIn('registró 2 decisiones', lectura['texto_joi'])
