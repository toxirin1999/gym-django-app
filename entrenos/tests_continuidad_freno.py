"""
Phase Continuidad 1.1 — el motor ejecuta la prudencia que 1.0 describe.

Una pausa de entrenamiento (≥6 días sin gym) congela la subida de cargas en
evaluar_permiso_progresion (accion='mantener_carga', motivo='retorno_pausa').
Principio: el copy no promete una prudencia que el motor no ejecuta.

Checklist:
1.  Pausa clara (8d) → mantener_carga / retorno_pausa, bloquea principales.
2.  Pausa larga (14d) → igual (freno por pausa).
3.  Sin pausa (2d) → NO retorno_pausa.
4.  El mensaje retorno_pausa pasa el contrato de lenguaje (sin deuda).
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from entrenos.services.progresion_contextual_service import (
    evaluar_permiso_progresion, _MENSAJES_PROGRESION,
)
from core.continuidad import auditar_lenguaje_continuidad

REF = date(2026, 6, 6)


class FrenoPausaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_freno11', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _gym(self, dias_atras):
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', fecha=REF - timedelta(days=dias_atras),
        )

    def _permiso(self):
        return evaluar_permiso_progresion(self.cliente, fecha_ref=REF)


class TestFrenoPorPausa(FrenoPausaBase):
    def test_pausa_clara_congela_progresion(self):
        self._gym(8)  # 8 días → clara
        p = self._permiso()
        self.assertEqual(p['accion'], 'mantener_carga')
        self.assertEqual(p['motivo'], 'retorno_pausa')
        self.assertTrue(p['aplica_a_principales'])

    def test_pausa_larga_congela_progresion(self):
        self._gym(14)  # 14 días → larga
        p = self._permiso()
        self.assertEqual(p['accion'], 'mantener_carga')
        self.assertEqual(p['motivo'], 'retorno_pausa')

    def test_sin_pausa_no_es_retorno_pausa(self):
        self._gym(2)  # 2 días → normal, sin freno por pausa
        p = self._permiso()
        self.assertNotEqual(p['motivo'], 'retorno_pausa')


class TestLenguajeRetornoPausa(TestCase):
    def test_mensaje_retorno_pausa_sin_deuda(self):
        msg = _MENSAJES_PROGRESION['retorno_pausa']
        self.assertEqual(auditar_lenguaje_continuidad(msg), [],
                         f"el mensaje de retorno_pausa no debe usar lenguaje de deuda: {msg}")
