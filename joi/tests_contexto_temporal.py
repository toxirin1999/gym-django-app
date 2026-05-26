"""
Phase 56.13 — Conciencia temporal JOI.

JOI no solo debe saber qué ocurrió — debe saber desde qué parte del día
está mirando. Sin esto puede dar consejos para un día que ya terminó.

Checklist (10):
1.  Cierre nocturno no contiene "descansa hoy".
2.  Cierre nocturno no contiene "entrena hoy".
3.  Cierre nocturno no contiene "esta tarde".
4.  Cierre nocturno usa pasado o transición hacia mañana.
5.  Apertura de mañana puede mencionar ayer y orientar hoy.
6.  Apertura de mañana no habla como si el día ya hubiera terminado.
7.  Post-entreno no recomienda cómo hacer la sesión ya completada.
8.  Post-entreno indica respuesta corporal / recuperación posterior.
9.  Post-Hyrox no se mezcla con apertura diaria.
10. Si momento_del_dia falta, fallback conservador (noche → sin prescripción).
"""

import unittest.mock as mock

from django.test import TestCase

from joi.services import resolver_contexto_temporal, _bloque_temporal, _TEMPORAL_PROMPTS


class TestResolverContextoTemporal(TestCase):
    """El resolver asigna el momento correcto."""

    def test_trigger_entreno_completado_es_post_entreno(self):
        ctx = resolver_contexto_temporal('entreno_completado')
        self.assertEqual(ctx['momento'], 'post_entreno')
        self.assertFalse(ctx['puede_prescribir_hoy'])

    def test_trigger_hyrox_sesion_es_post_hyrox(self):
        ctx = resolver_contexto_temporal('hyrox_sesion_completada')
        self.assertEqual(ctx['momento'], 'post_sesion_hyrox')
        self.assertFalse(ctx['puede_prescribir_hoy'])

    def _hora(self, h):
        """Helper: mock de django.utils.timezone.localtime que devuelve una hora fija."""
        dt = mock.MagicMock()
        dt.hour = h
        return mock.patch('django.utils.timezone.localtime', return_value=dt)

    def test_hora_manana_es_manana(self):
        with self._hora(8):
            ctx = resolver_contexto_temporal('apertura_manana')
        self.assertEqual(ctx['momento'], 'manana')
        self.assertTrue(ctx['puede_prescribir_hoy'])

    def test_hora_tarde_es_tarde(self):
        with self._hora(15):
            ctx = resolver_contexto_temporal('apertura_manana')
        self.assertEqual(ctx['momento'], 'tarde')
        self.assertTrue(ctx['puede_prescribir_hoy'])

    def test_hora_noche_es_noche(self):
        with self._hora(22):
            ctx = resolver_contexto_temporal('apertura_manana')
        self.assertEqual(ctx['momento'], 'noche')
        self.assertFalse(ctx['puede_prescribir_hoy'])

    def test_apertura_generada_tarde_marca_fuera_de_hora(self):
        """Si 'apertura_manana' se genera a las 14h, 'generado_en_hora_prevista' es False."""
        with self._hora(14):
            ctx = resolver_contexto_temporal('apertura_manana')
        self.assertFalse(ctx['generado_en_hora_prevista'])

    def test_sintesis_joi_sin_trigger_definido_es_noche(self):
        """La síntesis se genera post-reflexión nocturna — debe caer en noche."""
        with self._hora(22):
            ctx = resolver_contexto_temporal('sintesis_joi')
        self.assertEqual(ctx['momento'], 'noche')


class TestBloqueTemporal(TestCase):
    """El bloque de texto temporal contiene las restricciones correctas."""

    # ── 1-3. Restricciones de cierre nocturno ──────────────────────────────

    def test_noche_contiene_prohibicion_descansa_hoy(self):
        ctx = {'momento': 'noche', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx)
        self.assertIn('descansa hoy', bloque)

    def test_noche_contiene_prohibicion_entrena_hoy(self):
        ctx = {'momento': 'noche', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx)
        self.assertIn('entrena hoy', bloque)

    def test_noche_contiene_prohibicion_esta_tarde(self):
        ctx = {'momento': 'noche', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx)
        self.assertIn('esta tarde', bloque)

    # ── 4. Cierre nocturno orienta hacia pasado o mañana ──────────────────

    def test_noche_menciona_pasado_o_manana(self):
        ctx = {'momento': 'noche', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx).lower()
        tiene_pasado = 'pasado' in bloque
        tiene_manana = 'mañana' in bloque
        self.assertTrue(tiene_pasado or tiene_manana,
                        msg=f"Bloque noche no menciona pasado ni mañana: {bloque}")

    # ── 5. Apertura mañana puede orientar el día ──────────────────────────

    def test_manana_puede_prescribir(self):
        ctx = {'momento': 'manana', 'puede_prescribir_hoy': True, 'generado_en_hora_prevista': True}
        bloque = _bloque_temporal(ctx)
        # No debe tener las prohibiciones de noche
        self.assertNotIn('PROHIBIDO', bloque)

    # ── 6. Apertura mañana no habla como si el día terminó ────────────────

    def test_manana_no_contiene_dia_termino(self):
        ctx = {'momento': 'manana', 'puede_prescribir_hoy': True, 'generado_en_hora_prevista': True}
        bloque = _bloque_temporal(ctx).lower()
        self.assertNotIn('ya terminó', bloque)
        self.assertNotIn('ya termino', bloque)

    # ── 7. Post-entreno no recomienda hacer la sesión completada ──────────

    def test_post_entreno_dice_no_recomendar_sesion(self):
        ctx = {'momento': 'post_entreno', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx)
        self.assertIn('ya terminó', bloque)

    # ── 8. Post-entreno orienta hacia recuperación ────────────────────────

    def test_post_entreno_menciona_cuerpo_o_recuperacion(self):
        ctx = {'momento': 'post_entreno', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx).lower()
        self.assertTrue(
            'cuerpo' in bloque or 'recuper' in bloque,
            msg=f"Bloque post_entreno no menciona cuerpo/recuperación: {bloque}"
        )

    # ── 9. Post-Hyrox no se mezcla con apertura ──────────────────────────

    def test_post_hyrox_no_menciona_apertura(self):
        ctx = {'momento': 'post_sesion_hyrox', 'puede_prescribir_hoy': False}
        bloque = _bloque_temporal(ctx).lower()
        self.assertNotIn('por la mañana', bloque)
        self.assertNotIn('empieza el día', bloque)

    # ── 10. Fallback conservador si falta momento ─────────────────────────

    def test_fallback_sin_momento_no_prescribe(self):
        """Si el dict viene vacío, el bloque puede ser vacío pero nunca contradictor."""
        ctx = {}
        bloque = _bloque_temporal(ctx)
        # No debe contener "entrena hoy" en el fallback
        self.assertNotIn('entrena hoy', bloque)

    def test_todos_los_momentos_tienen_bloque(self):
        """Cada momento definido produce un bloque no vacío."""
        for momento in ('manana', 'tarde', 'noche', 'post_entreno', 'post_sesion_hyrox'):
            ctx = {'momento': momento}
            bloque = _bloque_temporal(ctx)
            self.assertTrue(len(bloque) > 10, msg=f"Bloque vacío para momento={momento}")
