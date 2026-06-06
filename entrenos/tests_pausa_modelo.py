"""
Phase Continuidad 1.3a — modelo PausaEntrenamiento (fuente única del motivo).

Contrato:
  - Se crea pausa SOLO desde nivel clara (≥6d); no por huecos pequeños.
  - No duplica: actualiza la pausa abierta.
  - Al retomar (sin pausa) se cierra la pausa abierta (fecha_fin).
  - El motivo persistido viaja a la lectura de continuidad (→ JOI/semáforo/Centro).
  - desconocido (no contestó) ≠ pausa_declarada (motivo_respondido).
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, PausaEntrenamiento
from core.continuidad import (
    evaluar_continuidad_entrenamiento,
    registrar_o_actualizar_pausa,
    get_pausa_abierta,
)

REF = date(2026, 6, 6)


class PausaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_pausa13', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _gym(self, dias_atras):
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', fecha=REF - timedelta(days=dias_atras),
        )

    def _reg(self):
        return registrar_o_actualizar_pausa(self.cliente, fecha_ref=REF)


class TestCicloVidaPausa(PausaBase):
    def test_crea_pausa_en_clara(self):
        self._gym(8)
        p = self._reg()
        self.assertIsNotNone(p)
        self.assertEqual(p.nivel, 'clara')
        self.assertIsNone(p.fecha_fin)
        self.assertEqual(p.motivo, 'desconocido')
        self.assertEqual(PausaEntrenamiento.objects.count(), 1)

    def test_no_crea_pausa_en_normal(self):
        self._gym(2)
        p = self._reg()
        self.assertIsNone(p)
        self.assertEqual(PausaEntrenamiento.objects.count(), 0)

    def test_no_duplica_actualiza(self):
        self._gym(8)
        self._reg()
        self._reg()
        self.assertEqual(PausaEntrenamiento.objects.count(), 1)

    def test_cierra_al_retomar(self):
        self._gym(8)
        self._reg()
        self.assertIsNotNone(get_pausa_abierta(self.cliente))
        # el usuario retoma: gym hoy
        self._gym(0)
        p = self._reg()
        self.assertIsNone(p)  # ya no hay pausa abierta
        cerrada = PausaEntrenamiento.objects.first()
        self.assertEqual(cerrada.fecha_fin, REF)


class TestMotivoEnLectura(PausaBase):
    def test_motivo_declarado_viaja_a_la_lectura(self):
        self._gym(8)
        p = self._reg()
        p.motivo = 'vacaciones_viaje'
        p.motivo_respondido = True
        p.save()
        lectura = evaluar_continuidad_entrenamiento(self.cliente, fecha_ref=REF)
        self.assertEqual(lectura['motivo'], 'vacaciones_viaje')
        self.assertTrue(lectura['motivo_respondido'])
        self.assertEqual(lectura['tipo'], 'pausa_declarada')

    def test_sin_declarar_es_desconocido(self):
        self._gym(8)
        self._reg()
        lectura = evaluar_continuidad_entrenamiento(self.cliente, fecha_ref=REF)
        self.assertEqual(lectura['motivo'], 'desconocido')
        self.assertFalse(lectura['motivo_respondido'])
        self.assertEqual(lectura['tipo'], 'pausa_no_declarada')
