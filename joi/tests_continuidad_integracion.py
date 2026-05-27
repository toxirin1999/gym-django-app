"""
Phase 56.15A — Integration tests: _bloque_continuidad injected in generar_mensaje_joi.

Tests verify that the continuity block actually reaches the prompt string
sent to the LLM — not that the LLM respects it (that's non-deterministic).

Strategy: patch _llamar_haiku to capture the prompt, patch
build_continuidad_context to return controlled contexts.
"""

from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from rutinas.models import Rutina


def _ctx_base(**overrides):
    """Minimal continuidad context for tests."""
    return {
        'hay_continuidad': True,
        'modo': 'normal',
        'feedback_negativo_reciente': False,
        'ultimo_mensaje': {
            'id': None, 'tipo': None, 'fecha': None,
            'feedback': None, 'extracto': None,
        },
        'referencias_bloqueadas': [],
        'dias_ventana_referencias': 14,
        'instrucciones': [],
        **overrides,
    }


class IntegracionBloquePromptBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_int56', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestInt', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_int56')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _generar(self, continuidad_ctx, trigger='entreno_completado'):
        """
        Calls generar_mensaje_joi with:
        - build_continuidad_context mocked to return continuidad_ctx
        - _llamar_haiku mocked to return a fixed string and capture the prompt
        - construir_contexto mocked to avoid DB/LLM calls
        Returns the captured prompt string.
        """
        captured = {}

        def fake_haiku(prompt, **kwargs):
            captured['prompt'] = prompt
            return 'Mensaje de prueba generado.'

        with patch('joi.services.build_continuidad_context', return_value=continuidad_ctx), \
             patch('joi.services._llamar_haiku', side_effect=fake_haiku), \
             patch('joi.services.construir_contexto', return_value={}), \
             patch('joi.services._bloque_memoria', return_value=''), \
             patch('joi.services._bloque_manual', return_value=''), \
             patch('joi.services._bloque_temporal', return_value=''), \
             patch('joi.services.validar_semantica_joi'):
            from joi.services import generar_mensaje_joi
            generar_mensaje_joi(
                self.cliente,
                trigger=trigger,
                datos_extra={'volumen_kg': 0, 'prs': [], 'rpe': 6.0},
            )

        return captured.get('prompt', '')


class IntegracionBloqueModoReducida(IntegracionBloquePromptBase):

    def test_modo_reducida_prompt_contiene_bajar_intensidad(self):
        """
        modo=reducida → prompt must instruct to lower narrative intensity.
        56.15A requirement 1.
        """
        ctx = _ctx_base(
            modo='reducida',
            feedback_negativo_reciente=True,
            instrucciones=[
                "El mensaje anterior no encajó con el usuario. No sigas en la misma dirección.",
                "Baja la intensidad narrativa. Usa una lectura corporal simple y verificable.",
                "No conectes diario con cuerpo salvo señal corporal explícita en los datos.",
            ],
        )
        prompt = self._generar(ctx)
        self.assertIn('intensidad narrativa', prompt.lower(),
                      "Expected 'intensidad narrativa' in prompt for modo=reducida")

    def test_modo_reducida_prompt_contiene_no_sigas_misma_direccion(self):
        """
        modo=reducida → prompt must include 'no sigas en la misma dirección'.
        56.15A requirement 5.
        """
        ctx = _ctx_base(
            modo='reducida',
            feedback_negativo_reciente=True,
            instrucciones=[
                "El mensaje anterior no encajó con el usuario. No sigas en la misma dirección.",
                "Baja la intensidad narrativa. Usa una lectura corporal simple y verificable.",
            ],
        )
        prompt = self._generar(ctx)
        self.assertIn('misma dirección', prompt.lower(),
                      "Expected 'misma dirección' in prompt for modo=reducida")


class IntegracionBloqueModSilencio(IntegracionBloquePromptBase):

    def test_modo_silencio_prompt_permite_frase_minima_o_silencio(self):
        """
        modo=silencio → prompt must allow minimal phrase or silence.
        56.15A requirement 2.
        """
        ctx = _ctx_base(
            modo='silencio',
            feedback_negativo_reciente=True,
            instrucciones=[
                "Varios mensajes recientes no encajaron. No intentes construir relato.",
                "Si no hay señal corporal clara, devuelve silencio.",
                "Si hay señal corporal clara, una sola frase práctica, nada más.",
            ],
        )
        prompt = self._generar(ctx)
        self.assertTrue(
            'silencio' in prompt.lower() or 'frase' in prompt.lower(),
            f"Expected 'silencio' or 'frase' in prompt for modo=silencio. Got:\n{prompt[:300]}",
        )


class IntegracionBloqueReferencias(IntegracionBloquePromptBase):

    def test_referencia_bloqueada_prompt_prohibe_mencionarla(self):
        """
        referencias_bloqueadas → prompt must forbid mentioning the station.
        56.15A requirement 3.
        """
        ctx = _ctx_base(
            referencias_bloqueadas=[
                {'tipo': 'ejercicio', 'valor': 'Sled Push',
                 'motivo': 'no_aparece_en_los_ultimos_14_dias'},
            ],
            instrucciones=[
                "No menciones Sled Push — no aparece en los últimos 14 días de entrenamiento.",
            ],
        )
        prompt = self._generar(ctx)
        self.assertIn('Sled Push', prompt,
                      "Expected 'Sled Push' prohibition in prompt")
        self.assertIn('No menciones', prompt)


class IntegracionBloqueVacio(IntegracionBloquePromptBase):

    def test_sin_continuidad_prompt_no_tiene_bloque_vacio(self):
        """
        hay_continuidad=False + no instrucciones → prompt must not contain
        an empty continuity block or placeholder text.
        56.15A requirement 4.
        """
        ctx = _ctx_base(
            hay_continuidad=False,
            instrucciones=[],
        )
        prompt = self._generar(ctx)
        self.assertNotIn('RESTRICCIONES DE CONTINUIDAD', prompt,
                         "Prompt should not contain empty continuity block")
