"""
Phase 59X.0 — El semáforo no debe tratar la fragilidad (subutilización) como
fatiga.

Bug original (intermitente, ventana días 1-4 de un parón): ACWR bajo + readiness
alto + energía alta → causa='fragilidad', pero:
  (1) se disparaba la Paradoja A → "los datos piden calma" (al revés: estás
      fresco, los datos NO piden calma), y
  (2) reutilizaba el copy de fatiga 'recuperar_movimiento' ("el cuerpo pide
      bajar intensidad").

Fix: fragilidad tiene tipo_recuperar/copy propios (marco de retorno) y queda
excluida de la Paradoja A.

Checklist:
1.  Fragilidad + energía alta NO produce Paradoja A.
2.  Fragilidad usa su mensaje propio, no el copy de fatiga ni el de Paradoja A.
3.  Las recomendaciones de fragilidad no son las de descanso/fatiga.
4.  El bug 'activo' no vuelve a continuidad_context (usa estado='activo').
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from core.daily_decision import DailyDecisionEngine as DDE


def _forzar_fragilidad(energia):
    """Mockea las dependencias del semáforo para caer en causa='fragilidad'.

    ACWR 0.5 (<0.7) + readiness 88% (>60) → cond_recuperar_movimiento → fragilidad.
    Sin lesión, sin objetivo Hyrox (tsb=None), sin actividades (ausencia=0).
    """
    bio = {'has_data': True, 'hrv_ms': None, 'energia': energia}
    return (
        patch('core.bio_context.BioContextProvider.get_bio_signals', return_value=bio),
        patch('core.bio_context.BioContextProvider.get_readiness_score', return_value={'score': 0.88}),
        patch('entrenos.services.services.EstadisticasService.analizar_acwr_unificado',
              return_value={'acwr_actual': 0.5}),
    )


class TestSemaforoFragilidad(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_59x0', password='x')
        # El signal auto-crea el Cliente; lo recuperamos (no crear de nuevo).
        self.cliente = Cliente.objects.get(user=self.user)

    def _estado(self, energia):
        p1, p2, p3 = _forzar_fragilidad(energia)
        with p1, p2, p3:
            return DDE.get_estado_hoy(self.cliente)

    def test_fragilidad_no_dispara_paradoja_a(self):
        e = self._estado(energia=8)
        self.assertEqual(e['causa'], 'fragilidad',
                         f"setup debía forzar fragilidad, salió {e['causa']}")
        self.assertIsNone(e['paradoja'],
                          "fragilidad con energía alta NO debe disparar Paradoja A")

    def test_fragilidad_no_usa_copy_de_fatiga_ni_paradoja(self):
        e = self._estado(energia=8)
        msg = e['mensaje']
        self.assertNotIn('piden calma', msg,
                         "no debe usar el copy de Paradoja A")
        self.assertNotIn('bajar intensidad', msg,
                         "no debe reutilizar el copy de fatiga recuperar_movimiento")
        # Debe ser el mensaje propio de fragilidad (marco de retorno).
        self.assertIn('menos carga', msg)

    def test_fragilidad_recomendaciones_de_retorno(self):
        e = self._estado(energia=8)
        self.assertNotEqual(e['recomendacion_gym'], "Movilidad o descanso activo.")
        self.assertIn('poco a poco', e['recomendacion_gym'])

    def test_fragilidad_estable_aunque_energia_baja(self):
        # Sin energía alta tampoco debe colarse Paradoja A en fragilidad.
        e = self._estado(energia=3)
        self.assertEqual(e['causa'], 'fragilidad')
        self.assertIsNone(e['paradoja'])


class TestBugActivoContinuidad(TestCase):
    def test_continuidad_usa_estado_activo_no_activo(self):
        import inspect
        from joi.context_builders import continuidad_context
        src = inspect.getsource(continuidad_context)
        self.assertNotIn('activo=True', src,
                         "continuidad_context no debe filtrar por campo inexistente 'activo'")
        self.assertIn("estado='activo'", src)

    def test_build_continuidad_no_revienta(self):
        from joi.context_builders.continuidad_context import build_continuidad_context
        user = User.objects.create_user('tester_cont59x', password='x')
        cliente = Cliente.objects.get(user=user)
        ctx = build_continuidad_context(cliente)
        self.assertIsInstance(ctx, dict)
        self.assertIn('referencias_bloqueadas', ctx)
