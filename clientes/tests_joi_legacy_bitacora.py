"""
Phase 59E.1 — Extirpar JOI legacy no canónica de bitácora.

Regla funcional que estos tests blindan:
    Si JOI habla, el sistema JOI canónico debe saberlo.
    Si el sistema JOI no lo sabe, no era JOI.

Por tanto `registrar_bitacora` debe ser registro puro: no genera voz JOI
hardcodeada, no lanza flash messages con voz JOI, y no persiste esa voz en
`RecuerdoEmocional`.

Checklist:
1.  GET no incluye 'respuesta_joi' ni 'saludo_joi' en el contexto.
2.  POST válido NO crea RecuerdoEmocional desde la vista.
3.  POST válido NO añade un flash message con prefijo "✨ Joi".
4.  POST válido sí guarda la BitacoraDiaria (sigue funcionando como bitácora).
5.  Contrato de código: la vista no contiene caminos JOI legacy.
6.  La función muerta obtener_frase_memoria_emocional ya no existe.
"""

import inspect

from datetime import date

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse

from clientes import views
from clientes.models import BitacoraDiaria, Cliente
from joi.models import RecuerdoEmocional


class BitacoraSinJoiLegacyBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester_59e1', password='testpass',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Test59E1', 'dias_disponibles': 4},
        )
        self.client = Client()
        self.client.login(username='tester_59e1', password='testpass')
        self.url = reverse('clientes:registrar_bitacora')

    def _post_valido(self):
        # energia/dolor/autoconciencia son los únicos campos required del form.
        return self.client.post(self.url, {
            'energia_subjetiva': 2,   # <= 3 disparaba la antigua frase_joi "calma"
            'dolor_articular': 8,     # >= 7 disparaba la antigua frase_joi "dolor"
            'autoconciencia': 2,
            'reflexion_diaria': 'hoy me siento triste y agotado',  # disparaba frase JOI
            'quien_quiero_ser': 'quiero ser valiente y mejor',
        })


class TestBitacoraGet(BitacoraSinJoiLegacyBase):
    def test_get_no_incluye_voz_joi_en_contexto(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('respuesta_joi', resp.context)
        self.assertNotIn('saludo_joi', resp.context)
        self.assertNotIn('frase_joi', resp.context)


class TestBitacoraPost(BitacoraSinJoiLegacyBase):
    def test_post_no_crea_recuerdo_emocional(self):
        antes = RecuerdoEmocional.objects.filter(user=self.user).count()
        self._post_valido()
        despues = RecuerdoEmocional.objects.filter(user=self.user).count()
        self.assertEqual(antes, despues,
                         "registrar_bitacora no debe persistir voz JOI en RecuerdoEmocional")

    def test_post_no_emite_flash_voz_joi(self):
        resp = self._post_valido()
        mensajes = [m.message for m in get_messages(resp.wsgi_request)]
        for m in mensajes:
            self.assertNotIn('✨ Joi', m)
            self.assertNotIn('Joi:', m)

    def test_post_sigue_guardando_bitacora(self):
        self._post_valido()
        self.assertTrue(
            BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=date.today()).exists(),
            "La bitácora debe seguir guardándose como registro puro",
        )


class TestContratoCodigoSinJoiLegacy(TestCase):
    """Blinda que nadie reintroduzca voz JOI legacy en la vista."""

    def test_registrar_bitacora_sin_caminos_joi_legacy(self):
        src = inspect.getsource(views.registrar_bitacora)
        for prohibido in ('frase_joi', '✨ Joi', 'RecuerdoEmocional', 'respuesta_joi'):
            self.assertNotIn(
                prohibido, src,
                f"registrar_bitacora no debe contener '{prohibido}' (JOI legacy)",
            )

    def test_obtener_frase_memoria_emocional_eliminada(self):
        self.assertFalse(
            hasattr(views, 'obtener_frase_memoria_emocional'),
            "La función muerta obtener_frase_memoria_emocional debe estar eliminada",
        )
