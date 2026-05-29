"""
Phase 56.17 — Tests: deduplicación del signal joi_mensaje_pr.

Rule: un PR concreto (cliente + ejercicio + fecha + valor) solo puede
generar un MensajeJOI con trigger='pr_roto' en un periodo de 24h.
"""

from unittest.mock import patch, call
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import RecordPersonal, EntrenoRealizado
from rutinas.models import Rutina


class PRSignalBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_pr56', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestPR', 'dias_disponibles': 4},
        )
        rutina, _ = Rutina.objects.get_or_create(nombre='_test_pr56')
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=date.today(),
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_pr(self, ejercicio='Elevación De Gemelos En Prensa', valor=100.0,
                  tipo='peso_maximo', superado=False):
        return RecordPersonal.objects.create(
            cliente=self.cliente,
            ejercicio_nombre=ejercicio,
            valor=valor,
            tipo_record=tipo,
            superado=superado,
            entreno=self.entreno,
        )


class TestPRSignalDeduplicacion(PRSignalBase):

    def test_pr_genera_un_solo_mensaje(self):
        """Crear el mismo PR dos veces en el mismo día → solo 1 llamada a generar_mensaje_joi."""
        with patch('joi.services.generar_mensaje_joi') as mock_gen:
            self._crear_pr(valor=100.0)
            self._crear_pr(valor=100.0)  # mismo ejercicio + valor + fecha
        self.assertEqual(mock_gen.call_count, 1,
                         "El mismo PR no debe generar más de un mensaje JOI al día")

    def test_pr_diferente_puede_generar_otro_mensaje(self):
        """Un PR distinto (otro ejercicio) sí puede generar su propio mensaje."""
        with patch('joi.services.generar_mensaje_joi') as mock_gen:
            self._crear_pr(ejercicio='Press Banca', valor=80.0)
            self._crear_pr(ejercicio='Sentadilla', valor=120.0)
        self.assertEqual(mock_gen.call_count, 2,
                         "PRs de ejercicios distintos deben generar mensajes distintos")

    def test_pr_superado_no_genera_mensaje(self):
        """PR con superado=True (fue batido) no debe generar mensaje JOI."""
        with patch('joi.services.generar_mensaje_joi') as mock_gen:
            self._crear_pr(superado=True)
        mock_gen.assert_not_called()
