"""
Phase 56.15 — Tests for contexto_continuidad_joi.

Capa A (8 tests): contract of build_continuidad_context() — deterministic, DB-backed.
Capa B (5 tests): contract of _bloque_continuidad()        — pure, no DB.

Rule under test:
  JOI does not use memory to build more narrative;
  it uses it to avoid repeating what did not resonate.
"""

from datetime import date, timedelta, datetime, timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from joi.models import MensajeJOI
from joi.context_builders.continuidad_context import (
    build_continuidad_context,
    _bloque_continuidad,
)


# ── Base setup ────────────────────────────────────────────────────────────────

class ContinuidadBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cont56', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestCont', 'dias_disponibles': 3},
        )
        self.hoy = date(2026, 5, 27)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_mensaje(self, dias_atras=1, trigger='apertura_manana',
                       feedback=None, texto='Mensaje de prueba para tests.'):
        msg = MensajeJOI.objects.create(
            user=self.user, trigger=trigger,
            mensaje=texto, contexto={},
            feedback=feedback,
        )
        # Override auto_now_add to control recency
        ts = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc) - timedelta(days=dias_atras)
        MensajeJOI.objects.filter(pk=msg.pk).update(creado_en=ts)
        return MensajeJOI.objects.get(pk=msg.pk)

    def _ctx(self, **kwargs):
        return build_continuidad_context(self.cliente, hoy=self.hoy, **kwargs)


# ── Capa A: context object ────────────────────────────────────────────────────

class ContinuidadContextoCapaA(ContinuidadBase):

    def test_sin_mensajes_previos_hay_continuidad_false_modo_normal(self):
        """Case A: no messages → hay_continuidad=False, modo=normal."""
        ctx = self._ctx()
        self.assertFalse(ctx['hay_continuidad'])
        self.assertEqual(ctx['modo'], 'normal')
        self.assertFalse(ctx['feedback_negativo_reciente'])
        self.assertEqual(ctx['instrucciones'], [])

    def test_feedback_none_no_se_trata_como_positivo(self):
        """
        Case B: feedback=None must not lower narrative intensity.
        None means 'we don't know', not 'it worked'.
        """
        self._crear_mensaje(dias_atras=1, feedback=None)
        ctx = self._ctx()
        self.assertTrue(ctx['hay_continuidad'])
        self.assertEqual(ctx['modo'], 'normal')
        self.assertFalse(ctx['feedback_negativo_reciente'])
        self.assertIsNone(ctx['ultimo_mensaje']['feedback'])

    def test_feedback_clavado_modo_normal_sin_restricciones(self):
        """Case B (positive): clavado → modo normal, no negative flag."""
        self._crear_mensaje(dias_atras=1, feedback='clavado')
        ctx = self._ctx()
        self.assertEqual(ctx['modo'], 'normal')
        self.assertFalse(ctx['feedback_negativo_reciente'])
        self.assertEqual(ctx['ultimo_mensaje']['feedback'], 'lo_has_leido_bien')

    def test_no_encajo_en_ultimos_7_dias_modo_reducida(self):
        """Case C: one equivocado within 7 days → modo=reducida."""
        self._crear_mensaje(dias_atras=3, feedback='equivocado')
        ctx = self._ctx()
        self.assertEqual(ctx['modo'], 'reducida')
        self.assertTrue(ctx['feedback_negativo_reciente'])
        self.assertEqual(ctx['ultimo_mensaje']['feedback'], 'no_encajo')

    def test_dos_no_encajo_en_ultimos_3_dias_modo_silencio(self):
        """Case C (extreme): two equivocado within 3 days → modo=silencio."""
        self._crear_mensaje(dias_atras=1, feedback='equivocado', texto='Mensaje uno.')
        self._crear_mensaje(dias_atras=2, feedback='equivocado', texto='Mensaje dos.')
        ctx = self._ctx()
        self.assertEqual(ctx['modo'], 'silencio')
        self.assertTrue(ctx['feedback_negativo_reciente'])

    def test_extracto_se_conserva_sin_interpretar(self):
        """
        The extracto in ultimo_mensaje must be the raw message text (truncated),
        not a theme or interpretation derived from it.
        """
        texto = 'Tu mente intentó encontrar orden anoche — esas frases épicas que se agolpaban.'
        self._crear_mensaje(dias_atras=1, feedback='equivocado', texto=texto)
        ctx = self._ctx()
        extracto = ctx['ultimo_mensaje']['extracto']
        self.assertIsNotNone(extracto)
        # Must be a prefix of the original, not a keyword or label
        self.assertTrue(texto.startswith(extracto) or extracto in texto)
        self.assertNotEqual(extracto, 'exceso_narrativo')
        self.assertNotEqual(extracto, 'no_demostrar')

    @patch('joi.context_builders.continuidad_context._calcular_referencias_bloqueadas')
    def test_estacion_no_reciente_genera_referencia_bloqueada(self, mock_refs):
        """Case D: station in JOI context but not in recent training → blocked."""
        mock_refs.side_effect = lambda cliente, hoy, ctx, dias: {
            **ctx,
            'referencias_bloqueadas': [
                {'tipo': 'ejercicio', 'valor': 'Sled Push',
                 'motivo': 'no_aparece_en_los_ultimos_14_dias'},
            ],
        }
        ctx = self._ctx()
        valores = [r['valor'] for r in ctx['referencias_bloqueadas']]
        self.assertIn('Sled Push', valores)

    @patch('joi.context_builders.continuidad_context._calcular_referencias_bloqueadas')
    def test_estacion_entrenada_recientemente_no_se_bloquea(self, mock_refs):
        """Case D (inverse): station trained recently → NOT in referencias_bloqueadas."""
        mock_refs.side_effect = lambda cliente, hoy, ctx, dias: {
            **ctx,
            'referencias_bloqueadas': [],  # Sled Push was trained recently
        }
        ctx = self._ctx()
        valores = [r['valor'] for r in ctx['referencias_bloqueadas']]
        self.assertNotIn('Sled Push', valores)


# ── Capa B: prompt block ──────────────────────────────────────────────────────

class ContinuidadBloqueCapaB(ContinuidadBase):
    """Pure tests — no DB, just dict → string."""

    def _ctx_reducida(self, extracto=None, feedback='no_encajo'):
        return {
            'hay_continuidad': True,
            'modo': 'reducida',
            'feedback_negativo_reciente': True,
            'ultimo_mensaje': {
                'id': 1, 'tipo': 'apertura_manana', 'fecha': self.hoy,
                'feedback': feedback, 'extracto': extracto,
            },
            'referencias_bloqueadas': [],
            'dias_ventana_referencias': 14,
            'instrucciones': [
                "El mensaje anterior no encajó con el usuario. No sigas en la misma dirección.",
                "Baja la intensidad narrativa. Usa una lectura corporal simple y verificable.",
                "No conectes diario con cuerpo salvo señal corporal explícita en los datos.",
            ],
        }

    def test_modo_reducida_bloque_incluye_bajar_intensidad(self):
        """modo=reducida → block contains instruction to lower narrative intensity."""
        bloque = _bloque_continuidad(self._ctx_reducida())
        self.assertIn('intensidad narrativa', bloque.lower())

    def test_modo_reducida_bloque_incluye_no_sigas_misma_direccion(self):
        """modo=reducida → block instructs not to follow the same direction."""
        bloque = _bloque_continuidad(self._ctx_reducida())
        self.assertIn('misma dirección', bloque.lower())

    def test_modo_silencio_bloque_permite_frase_minima(self):
        """modo=silencio → block allows minimal phrase or silence, not full narrative."""
        ctx = {
            'hay_continuidad': True,
            'modo': 'silencio',
            'feedback_negativo_reciente': True,
            'ultimo_mensaje': {'id': 1, 'tipo': 'apertura_manana', 'fecha': self.hoy,
                               'feedback': 'no_encajo', 'extracto': None},
            'referencias_bloqueadas': [],
            'dias_ventana_referencias': 14,
            'instrucciones': [
                "Varios mensajes recientes no encajaron. No intentes construir relato.",
                "Si no hay señal corporal clara, devuelve silencio.",
                "Si hay señal corporal clara, una sola frase práctica, nada más.",
            ],
        }
        bloque = _bloque_continuidad(ctx)
        self.assertTrue(
            'silencio' in bloque.lower() or 'frase' in bloque.lower(),
            f"Expected silencio/frase in block, got: {bloque[:200]}",
        )

    def test_referencia_bloqueada_aparece_en_bloque(self):
        """referencias_bloqueadas → block forbids mentioning the station."""
        ctx = {
            'hay_continuidad': True,
            'modo': 'normal',
            'feedback_negativo_reciente': False,
            'ultimo_mensaje': {'id': None, 'tipo': None, 'fecha': None,
                               'feedback': None, 'extracto': None},
            'referencias_bloqueadas': [
                {'tipo': 'ejercicio', 'valor': 'Sled Push',
                 'motivo': 'no_aparece_en_los_ultimos_14_dias'},
            ],
            'dias_ventana_referencias': 14,
            'instrucciones': [
                "No menciones Sled Push — no aparece en los últimos 14 días de entrenamiento.",
            ],
        }
        bloque = _bloque_continuidad(ctx)
        self.assertIn('Sled Push', bloque)
        self.assertIn('No menciones', bloque)

    def test_feedback_none_bloque_no_dice_que_encajo(self):
        """
        feedback=None → the prompt block must NOT say the previous message worked.
        None is not signal — it is absence of signal.
        """
        ctx = {
            'hay_continuidad': True,
            'modo': 'normal',
            'feedback_negativo_reciente': False,
            'ultimo_mensaje': {'id': 1, 'tipo': 'apertura_manana', 'fecha': self.hoy,
                               'feedback': None, 'extracto': 'Texto de prueba.'},
            'referencias_bloqueadas': [],
            'dias_ventana_referencias': 14,
            'instrucciones': [],
        }
        bloque = _bloque_continuidad(ctx)
        self.assertNotIn('encajó', bloque.lower())
        self.assertNotIn('lo has leído', bloque.lower())
        self.assertNotIn('clavado', bloque.lower())

    def test_no_encajo_con_extracto_incluye_extracto_en_bloque(self):
        """
        When feedback=no_encajo and extracto exists,
        the block must include the raw extracto so the model
        knows what NOT to continue — without interpreting themes.
        """
        extracto = 'Tu mente intentó encontrar orden anoche — esas frases épicas.'
        ctx = self._ctx_reducida(extracto=extracto)
        bloque = _bloque_continuidad(ctx)
        self.assertIn(extracto[:40], bloque)
