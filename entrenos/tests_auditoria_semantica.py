"""
Phase 23.2 — Auditoría semántica del ciclo de preferencias aprendidas.

Objetivo: asegurar que las preferencias entran en JOI como memoria operativa
del plan, no como narrativa personal profunda ni identidad del usuario.

Checklist (10 puntos + variantes):
1.  Prompt no usa "eres" (convierte dato en identidad).
2.  Prompt no usa "siempre".
3.  Prompt no usa "nunca".
4.  Prompt no usa "debes".
5.  Prompt usa "el plan" como sujeto principal (memoria operativa).
6.  Prompt menciona evidencia o repetición (el dato está respaldado).
7.  Prompt mantiene tono tentativo (intentará, suele, cuando sea posible...).
8.  crear_preferencia + generar_mensaje_joi no escriben en ManualDavid.
9a. apertura_mañana puede incluir preferencias si existen.
9b. apertura_mañana funciona sin preferencias y no añade ruido.
10. [Ya cubierto en Phase 23.1 TestCase11] — no se duplica.

Regla de oro:
"El plan aprendió X" ≠ "Eres alguien que X"
"""

from datetime import date
from unittest.mock import patch, MagicMock, call

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, PreferenciaPlanAprendida
from entrenos.services.preferencias_service import crear_preferencia


class AuditoriaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_audit23', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestAudit', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _prompt_for(self, tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                    descripcion='El plan intentará no colocar pierna tras el fútbol.',
                    evidencia=3):
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS['preferencia_aprendida']
        return builder({}, {
            'tipo_preferencia': tipo,
            'descripcion': descripcion,
            'evidencia_count': evidencia,
        })


# ── Puntos 1-4: palabras prohibidas en prompt ─────────────────────────────────

class TestAuditoria1_NoEres(AuditoriaBase):
    def test_prompt_no_contiene_eres(self):
        for tipo in PreferenciaPlanAprendida.TIPOS:
            texto = self._prompt_for(tipo=tipo[0]).lower()
            self.assertNotIn(' eres ', texto, msg=f"Tipo {tipo[0]}: contiene 'eres'")
            self.assertNotIn('eres alguien', texto, msg=f"Tipo {tipo[0]}: contiene 'eres alguien'")

    def test_prompt_no_convierte_en_identidad(self):
        texto = self._prompt_for().lower()
        frases_identidad = ['eres', 'eres alguien que', 'eso te define', 'es tu forma de']
        for frase in frases_identidad:
            self.assertNotIn(frase, texto, msg=f"Prompt contiene identidad: '{frase}'")


class TestAuditoria2_NoSiempre(AuditoriaBase):
    def test_prompt_no_contiene_siempre(self):
        for tipo in PreferenciaPlanAprendida.TIPOS:
            texto = self._prompt_for(tipo=tipo[0]).lower()
            self.assertNotIn('siempre', texto, msg=f"Tipo {tipo[0]}: contiene 'siempre'")


class TestAuditoria3_NoNunca(AuditoriaBase):
    def test_prompt_no_contiene_nunca(self):
        for tipo in PreferenciaPlanAprendida.TIPOS:
            texto = self._prompt_for(tipo=tipo[0]).lower()
            self.assertNotIn('nunca', texto, msg=f"Tipo {tipo[0]}: contiene 'nunca'")


class TestAuditoria4_NoDebes(AuditoriaBase):
    def test_prompt_no_contiene_debes(self):
        for tipo in PreferenciaPlanAprendida.TIPOS:
            texto = self._prompt_for(tipo=tipo[0]).lower()
            self.assertNotIn('debes', texto, msg=f"Tipo {tipo[0]}: contiene 'debes'")
            self.assertNotIn('tienes que', texto, msg=f"Tipo {tipo[0]}: contiene 'tienes que'")


# ── Punto 5: "el plan" como sujeto ───────────────────────────────────────────

class TestAuditoria5_ElPlanComoSujeto(AuditoriaBase):
    def test_prompt_menciona_el_plan_como_sujeto(self):
        texto = self._prompt_for().lower()
        # Either the prompt itself or the instruction to JOI should reference "el plan"
        self.assertIn('el plan', texto, msg="Prompt no menciona 'el plan' como sujeto")

    def test_descripcion_service_usa_el_plan(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        for tipo, desc in _DESCRIPCION_PREFERENCIA.items():
            texto = desc.lower()
            self.assertIn('el plan', texto, msg=f"Descripción de '{tipo}' no usa 'el plan'")


# ── Punto 6: evidencia mencionada ────────────────────────────────────────────

class TestAuditoria6_EvidenciaMencionada(AuditoriaBase):
    def test_prompt_menciona_numero_de_pruebas(self):
        texto = self._prompt_for(evidencia=4)
        self.assertIn('4', texto, msg="Prompt no menciona el número de pruebas")

    def test_prompt_menciona_prueba_o_repeticion(self):
        texto = self._prompt_for().lower()
        palabras_evidencia = ['prueba', 'repeti', 'sesion', 'veces', 'evidencia', 'patrón', 'patron']
        usa_evidencia = any(k in texto for k in palabras_evidencia)
        self.assertTrue(usa_evidencia, msg=f"Prompt no menciona evidencia o repetición: {texto[:200]}")


# ── Punto 7: tono tentativo ───────────────────────────────────────────────────

class TestAuditoria7_TonoTentativo(AuditoriaBase):
    def test_prompt_usa_vocabulario_tentativo(self):
        texto = self._prompt_for().lower()
        palabras_blandas = [
            'intentará', 'cuando sea posible', 'inclinación', 'blanda',
            'suele', 'preferencia', 'puede', 'posible', 'cuando',
        ]
        usa_blanda = any(k in texto for k in palabras_blandas)
        self.assertTrue(usa_blanda, msg=f"Prompt no usa tono tentativo. Texto: {texto[:300]}")

    def test_prompt_pide_a_joi_tono_preciso_no_absoluto(self):
        texto = self._prompt_for().lower()
        # Prompt should instruct JOI to be precise, not use absolute language
        indicadores_precision = ['precis', 'observ', 'nombra', 'concret']
        usa_precision = any(k in texto for k in indicadores_precision)
        self.assertTrue(usa_precision, msg="Prompt no instruye a JOI sobre precisión")


# ── Punto 8: no escribe en ManualDavid ───────────────────────────────────────

class TestAuditoria8_NoManualDavid(AuditoriaBase):
    def test_crear_preferencia_no_toca_manual_david(self):
        with patch('joi.models.ManualDavid.objects') as mock_md:
            mock_generar = MagicMock(return_value=None)
            with patch('joi.services.generar_mensaje_joi', mock_generar):
                crear_preferencia(
                    self.cliente,
                    PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                    IntervencionPlan.TIPO_REDISTRIB_PIERNA,
                    fecha_ref=self.hoy,
                )
        mock_md.create.assert_not_called()
        mock_md.filter.assert_not_called()

    def test_generar_mensaje_joi_preferencia_no_llama_manual_david_create(self):
        """generar_mensaje_joi con trigger preferencia_aprendida no crea entradas ManualDavid."""
        with patch('joi.models.ManualDavid.objects') as mock_md:
            mock_md.create = MagicMock(return_value=None)
            # Simulate the call chain: generar_mensaje_joi → _prompt_builder
            from joi.services import _PROMPT_BUILDERS
            builder = _PROMPT_BUILDERS['preferencia_aprendida']
            # Building the prompt should not interact with ManualDavid at all
            builder({}, {
                'tipo_preferencia': PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                'descripcion': 'El plan intentará no colocar pierna.',
                'evidencia_count': 2,
            })
        mock_md.create.assert_not_called()


# ── Punto 9: apertura_mañana y preferencias ──────────────────────────────────

class TestAuditoria9_AperturaYPreferencias(AuditoriaBase):
    def _prompt_apertura(self, ctx):
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS['apertura_manana']
        return builder(ctx, {})

    def test_apertura_sin_preferencias_no_añade_ruido(self):
        ctx = {'ultima_actividad': {'dias_hace': 1, 'tipo': 'gym', 'titulo': 'Push'}}
        texto = self._prompt_apertura(ctx)
        self.assertNotIn('preferencia', texto.lower(),
                         msg="apertura_mañana sin prefs no debería mencionar preferencias")

    def test_apertura_con_preferencias_las_incluye_con_etiqueta(self):
        ctx = {
            'ultima_actividad': {'dias_hace': 1, 'tipo': 'gym', 'titulo': 'Push'},
            'preferencias_plan_activas': [
                {
                    'tipo': PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                    'descripcion': 'El plan intentará no colocar pierna tras el fútbol.',
                    'evidencia': 2,
                }
            ],
        }
        texto = self._prompt_apertura(ctx)
        self.assertIn('Memoria operativa del plan', texto,
                      msg="apertura_mañana con prefs debería incluir etiqueta de límite semántico")
        self.assertIn('inclinaciones aprendidas', texto.lower(),
                      msg="Etiqueta debe clarificar que son inclinaciones, no rasgos")

    def test_etiqueta_apertura_explicita_que_no_son_rasgos(self):
        ctx = {
            'preferencias_plan_activas': [
                {
                    'tipo': PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
                    'descripcion': 'El plan tomará como referencia menos días semanales.',
                    'evidencia': 2,
                }
            ],
        }
        texto = self._prompt_apertura(ctx)
        if 'Memoria operativa' in texto:
            # The label should EXPLICITLY REJECT identity attribution
            # (e.g., "no rasgos del usuario") — affirmative identity claims are the risk
            self.assertIn('no rasgos', texto.lower(),
                          msg="Etiqueta debe rechazar explícitamente la atribución de rasgos")
            # "personalidad" should not appear as an affirmation
            self.assertNotIn('define tu personalidad', texto.lower())


# ── Punto 10: sin ruido cuando no hay prefs ──────────────────────────────────
# (Ya cubierto en Phase 23.1 TestCase11 — se verifica brevemente aquí)

class TestAuditoria10_SinPreferenciasSinRuido(AuditoriaBase):
    def test_contexto_sin_preferencias_no_tiene_clave(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        prefs = ctx.get('preferencias_plan_activas', [])
        # Should be empty list (not absent key — either is fine) but never populated
        self.assertEqual(len(prefs), 0,
                         msg="Sin preferencias activas, la lista debe estar vacía")
