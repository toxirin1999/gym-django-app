"""
Phase Continuidad 1.2 — narración del freno por pausa en la sesión.

Cuando el motor congela cargas por pausa (motivo_bloqueo='retorno_pausa', 1.1),
la sesión debe explicarlo con marco de retorno, distinto de lesión.

Contrato testeado (templates):
  - entrenamiento_activo.html tiene rama 'retorno_pausa' con copy de retorno.
  - briefing_entrenamiento.html tiene badge '= MANTIENE · VUELTA'.
  - El copy no usa lenguaje de deuda.
"""

from django.test import TestCase

from core.continuidad import auditar_lenguaje_continuidad


def _leer(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


class TestNarracionRetornoPausa(TestCase):
    def test_workout_card_tiene_rama_retorno_pausa(self):
        tpl = _leer('entrenos/templates/entrenos/entrenamiento_activo.html')
        self.assertIn("motivo_bloqueo == 'retorno_pausa'", tpl)
        self.assertIn('Carga mantenida · retorno tras pausa', tpl)

    def test_briefing_tiene_badge_pausa(self):
        tpl = _leer('entrenos/templates/entrenos/briefing_entrenamiento.html')
        self.assertIn("motivo_bloqueo == 'retorno_pausa'", tpl)
        self.assertIn('= MANTIENE · VUELTA', tpl)

    def test_copy_retorno_sin_deuda(self):
        frase = "Vuelves de una pausa: subir vendrá después, sin compensar de golpe."
        self.assertEqual(auditar_lenguaje_continuidad(frase), [])
