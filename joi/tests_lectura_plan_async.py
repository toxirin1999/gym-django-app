"""
generar_lectura_plan nunca debe bloquear el request con una llamada síncrona
a Haiku — la generación real se dispara en background (Celery) y el request
sirve mientras tanto el último mensaje conocido, aunque esté desactualizado.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from joi.models import MensajeJOI
from joi.services import generar_lectura_plan


class GenerarLecturaPlanNoBloqueanteTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('lectura_plan_user', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_sin_mensaje_previo_no_llama_a_generar_mensaje_joi_sincrono(self):
        with patch('joi.services.generar_mensaje_joi') as mock_sync, \
             patch('joi.services._broker_alcanzable', return_value=True), \
             patch('joi.tasks.generar_lectura_plan_async.apply_async') as mock_apply_async:
            resultado = generar_lectura_plan(self.cliente)
        mock_sync.assert_not_called()
        mock_apply_async.assert_called_once_with(args=[self.cliente.id], retry=False)
        self.assertIsNone(resultado)

    def test_mensaje_reciente_se_sirve_sin_disparar_regeneracion(self):
        MensajeJOI.objects.create(user=self.user, trigger='lectura_plan', mensaje='hola')
        with patch('joi.services._broker_alcanzable') as mock_broker, \
             patch('joi.tasks.generar_lectura_plan_async.apply_async') as mock_apply_async:
            resultado = generar_lectura_plan(self.cliente)
        mock_broker.assert_not_called()
        mock_apply_async.assert_not_called()
        self.assertEqual(resultado.mensaje, 'hola')

    def test_mensaje_desactualizado_se_sirve_igual_y_dispara_regeneracion_en_background(self):
        viejo = MensajeJOI.objects.create(user=self.user, trigger='lectura_plan', mensaje='viejo')
        MensajeJOI.objects.filter(id=viejo.id).update(
            creado_en=timezone.now() - timedelta(hours=9)
        )
        with patch('joi.services._broker_alcanzable', return_value=True), \
             patch('joi.tasks.generar_lectura_plan_async.apply_async') as mock_apply_async:
            resultado = generar_lectura_plan(self.cliente)
        mock_apply_async.assert_called_once_with(args=[self.cliente.id], retry=False)
        self.assertEqual(resultado.mensaje, 'viejo', msg='Debe servir el último conocido, no silencio, mientras regenera en background.')

    def test_broker_no_alcanzable_no_intenta_encolar(self):
        """Sin el circuit-breaker, .apply_async() con Redis caído bloquea varios
        segundos reintentando (verificado manualmente: ~6-19s) — no debe intentarse."""
        with patch('joi.services._broker_alcanzable', return_value=False), \
             patch('joi.tasks.generar_lectura_plan_async.apply_async') as mock_apply_async:
            resultado = generar_lectura_plan(self.cliente)
        mock_apply_async.assert_not_called()
        self.assertIsNone(resultado)

    def test_fallo_al_encolar_no_rompe_el_request(self):
        with patch('joi.services._broker_alcanzable', return_value=True), \
             patch('joi.tasks.generar_lectura_plan_async.apply_async', side_effect=ConnectionError('sin broker')):
            resultado = generar_lectura_plan(self.cliente)
        self.assertIsNone(resultado)
