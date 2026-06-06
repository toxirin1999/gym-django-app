"""
Phase Continuidad 1.4 (JOI) — JOI recibe señal COCINADA de pausa, no días crudos.

construir_contexto debe incluir un hecho "[Continuidad] Pausa ... motivo ..."
cuando hay pausa de gym significativa, en vez de "PAUSA — última actividad
hace N días". La app no inventa el motivo.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, PausaEntrenamiento
from joi.services import construir_contexto, _prompt_apertura_manana


class TestSenalCocinadaJoi(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_joi14', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        hoy = timezone.now().date()
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym',
                                          fecha=hoy - timedelta(days=8))

    def _prompt(self):
        # El prompt de apertura es lo que JOI recibe realmente.
        ctx = construir_contexto(self.cliente)
        return _prompt_apertura_manana(ctx, {})

    def test_prompt_incluye_senal_cocinada(self):
        prompt = self._prompt()
        self.assertIn('[Continuidad]', prompt,
                      "JOI debe recibir la señal cocinada de pausa")
        self.assertNotIn('PAUSA — última actividad hace 8 días', prompt,
                         "no debe quedar la señal cruda cuando hay señal cocinada")

    def test_motivo_no_declarado_se_marca(self):
        self.assertIn('no asumir causa', self._prompt(),
                      "sin motivo declarado, JOI no debe asumir la causa")

    def test_motivo_declarado_viaja_a_joi(self):
        PausaEntrenamiento.objects.create(
            cliente=self.cliente, fecha_inicio=timezone.now().date() - timedelta(days=7),
            dias_sin_gym=8, nivel='clara', motivo='vacaciones_viaje', motivo_respondido=True,
        )
        self.assertIn('vacaciones', self._prompt())
