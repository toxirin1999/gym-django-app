"""Rumbo 12-oct-2026: la voz propia de JOI está congelada por defecto."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from clientes.models import Cliente
from joi.models import MensajeJOI
from joi.services import generar_mensaje_joi, voz_joi_activa


class VozJoiCongeladaTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('voz-congelada', password='x')
        self.cliente = Cliente.objects.get(user=user)

    def test_por_defecto_esta_congelada(self):
        self.assertFalse(voz_joi_activa())

    def test_no_genera_mensajes_propios(self):
        with patch('joi.services.construir_contexto') as contexto:
            for trigger in ('apertura_manana', 'entreno_completado', 'pr_roto', 'lectura_plan'):
                self.assertIsNone(generar_mensaje_joi(self.cliente, trigger, {}))
            contexto.assert_not_called()
        self.assertFalse(MensajeJOI.objects.exists())

    def test_el_resumen_semanal_del_diario_sigue_permitido(self):
        with patch('joi.services.construir_contexto', side_effect=RuntimeError('llegó')) as contexto:
            generar_mensaje_joi(self.cliente, 'resumen_semanal', {})
        contexto.assert_called_once()

    def test_la_sintesis_no_corre(self):
        from joi.tasks import ciclo_sintesis_joi
        self.assertEqual(ciclo_sintesis_joi.run(), {'congelada': True})
        call_command('joi_sintesis')
        self.assertFalse(MensajeJOI.objects.exists())

    @override_settings(JOI_VOZ_ACTIVA=True)
    def test_se_puede_reactivar(self):
        self.assertTrue(voz_joi_activa())
