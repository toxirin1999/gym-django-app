import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from diario.models import (
    Interaccion,
    InteraccionSombra,
    PersonaImportante,
    PersonaInterina,
)


class PromocionPersonaInterinaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('simbiosis-promocion', password='x')
        self.client.force_login(self.user)
        self.interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='Ana', estado='radar', veces_mencionada=2,
        )
        self.sombra = InteraccionSombra.objects.create(
            persona_interina=self.interina,
            descripcion='Hablamos de un asunto importante.',
            tipo_interaccion='apoyo',
        )
        InteraccionSombra.objects.filter(pk=self.sombra.pk).update(fecha=date(2026, 6, 15))
        self.sombra.refresh_from_db()
        self.url = reverse('diario:promover_persona_interina')

    def _post(self, accion='promover', interina=None):
        return self.client.post(
            self.url,
            data=json.dumps({'id': (interina or self.interina).pk, 'accion': accion}),
            content_type='application/json',
        )

    def test_promocion_repetida_es_idempotente_y_preserva_origen(self):
        primero = self._post()
        segundo = self._post()

        self.assertEqual(primero.status_code, 200)
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(Interaccion.objects.count(), 1)
        migrada = Interaccion.objects.get()
        self.assertEqual(migrada.origen_sombra, self.sombra)
        self.assertEqual(migrada.fecha, date(2026, 6, 15))
        self.assertEqual(list(migrada.personas.values_list('nombre', flat=True)), ['Ana'])

    def test_reutiliza_persona_confirmada_sin_distinguir_mayusculas(self):
        existente = PersonaImportante.objects.create(usuario=self.user, nombre='ana')

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PersonaImportante.objects.count(), 1)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.persona_importante, existente)

    def test_accion_desconocida_no_modifica_el_estado(self):
        respuesta = self._post('inventada')

        self.assertEqual(respuesta.status_code, 400)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'radar')
        self.assertFalse(Interaccion.objects.exists())

    def test_no_puede_promover_una_persona_de_otro_usuario(self):
        otro = User.objects.create_user('otro')
        ajena = PersonaInterina.objects.create(usuario=otro, nombre='Bea', estado='radar')

        respuesta = self._post(interina=ajena)

        self.assertEqual(respuesta.status_code, 400)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, 'radar')
        self.assertFalse(Interaccion.objects.exists())

    def test_fallo_intermedio_revierte_toda_la_promocion(self):
        InteraccionSombra.objects.create(
            persona_interina=self.interina, descripcion='Segunda interacción',
        )
        original = Interaccion.objects.get_or_create
        llamadas = 0

        def fallar_en_segunda(*args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError('fallo simulado')
            return original(*args, **kwargs)

        with patch.object(Interaccion.objects, 'get_or_create', side_effect=fallar_en_segunda):
            respuesta = self._post()

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Interaccion.objects.exists())
        self.assertFalse(PersonaImportante.objects.exists())
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'radar')

    def test_borrar_sombra_retrae_migrada_pero_conserva_interaccion_manual(self):
        manual = Interaccion.objects.create(
            usuario=self.user, titulo='Manual', descripcion='Creada conscientemente.',
        )
        self._post()
        migrada = Interaccion.objects.get(origen_sombra=self.sombra)

        self.sombra.delete()

        self.assertFalse(Interaccion.objects.filter(pk=migrada.pk).exists())
        self.assertTrue(Interaccion.objects.filter(pk=manual.pk).exists())
