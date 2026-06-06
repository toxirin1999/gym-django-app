"""
Phase Continuidad 1.3b — captura del motivo (pregunta única en el briefing).

Contrato del endpoint guardar_motivo_pausa:
  - motivo válido → se guarda, motivo_respondido=True.
  - motivo inválido o 'desconocido' → se ignora (queda desconocido, no respondido).
  - 'prefiero_no_decirlo' es una RESPUESTA (respondido=True), distinta de
    'desconocido' (no contestó).
  - tras guardar, el motivo viaja a la lectura de continuidad.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, PausaEntrenamiento
from core.continuidad import evaluar_continuidad_entrenamiento

REF = date(2026, 6, 6)


class MotivoUIBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_motivo13b', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym',
                                           fecha=REF - timedelta(days=8))
        self.pausa = PausaEntrenamiento.objects.create(
            cliente=self.cliente, fecha_inicio=REF - timedelta(days=7),
            dias_sin_gym=8, nivel='clara', motivo_preguntado=True,
        )
        self.client = Client()

    def _post(self, motivo):
        return self.client.post(
            reverse('entrenos:guardar_motivo_pausa', args=[self.pausa.id]),
            {'motivo': motivo},
        )


class TestGuardarMotivo(MotivoUIBase):
    def test_motivo_valido_se_guarda(self):
        resp = self._post('enfermedad')
        self.assertEqual(resp.status_code, 302)
        self.pausa.refresh_from_db()
        self.assertEqual(self.pausa.motivo, 'enfermedad')
        self.assertTrue(self.pausa.motivo_respondido)

    def test_motivo_invalido_se_ignora(self):
        self._post('basura_no_valida')
        self.pausa.refresh_from_db()
        self.assertEqual(self.pausa.motivo, 'desconocido')
        self.assertFalse(self.pausa.motivo_respondido)

    def test_desconocido_no_cuenta_como_respuesta(self):
        self._post('desconocido')
        self.pausa.refresh_from_db()
        self.assertEqual(self.pausa.motivo, 'desconocido')
        self.assertFalse(self.pausa.motivo_respondido)

    def test_prefiero_no_decirlo_es_respuesta(self):
        self._post('prefiero_no_decirlo')
        self.pausa.refresh_from_db()
        self.assertEqual(self.pausa.motivo, 'prefiero_no_decirlo')
        self.assertTrue(self.pausa.motivo_respondido)  # distinto de desconocido

    def test_motivo_viaja_a_la_lectura(self):
        self._post('vacaciones_viaje')
        lectura = evaluar_continuidad_entrenamiento(self.cliente, fecha_ref=REF)
        self.assertEqual(lectura['motivo'], 'vacaciones_viaje')
        self.assertEqual(lectura['tipo'], 'pausa_declarada')


class TestTemplatePregunta(TestCase):
    def test_briefing_tiene_tarjeta_motivo(self):
        with open('entrenos/templates/entrenos/briefing_entrenamiento.html', encoding='utf-8') as f:
            tpl = f.read()
        self.assertIn('pausa_pregunta', tpl)
        self.assertIn("guardar_motivo_pausa", tpl)
        self.assertIn('No es obligatorio', tpl)
