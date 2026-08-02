from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from diario.models import ReflexionLibre
from joi.models import MensajeJOI
from joi.services import _hay_contexto_para_revision, _leer_diario_reciente, extraer_entidades_simbiosis


class LogosMemoriaTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('logos-memory', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _reflexion(self, contenido, etiquetas=''):
        return ReflexionLibre.objects.create(
            usuario=self.user,
            contenido=contenido,
            etiquetas=etiquetas,
        )

    def test_leer_diario_excluye_cierre_duplicado_y_aplica_limite_despues(self):
        self._reflexion('reflexión normal más antigua')
        self._reflexion('reflexión normal reciente')
        self._reflexion('texto ya presente en Prosoche', 'noche, CIERRE_DIA ')

        texto = _leer_diario_reciente(self.user)

        self.assertNotIn('texto ya presente en Prosoche', texto)
        self.assertIn('reflexión normal reciente', texto)
        self.assertIn('reflexión normal más antigua', texto)

    def test_leer_diario_incluye_reflexion_normal_y_tag_parecido(self):
        self._reflexion('reflexión espontánea')
        self._reflexion('tag parecido no es cierre', 'precierre_dia,cierre_dia_extra')

        texto = _leer_diario_reciente(self.user)

        self.assertIn('reflexión espontánea', texto)
        self.assertIn('tag parecido no es cierre', texto)

    @patch('joi.services._cliente_anthropic')
    def test_extraccion_no_envia_cierre_duplicado_al_modelo(self, cliente_mock):
        self._reflexion('Mencioné a Ana en el cierre', 'cierre_dia')
        self._reflexion('Hablé con Bruno hoy')
        response = SimpleNamespace(content=[SimpleNamespace(text='[]')])
        cliente_mock.return_value.messages.create.return_value = response

        self.assertEqual(extraer_entidades_simbiosis(self.user), [])

        cliente_mock.return_value.messages.create.assert_called_once()
        prompt = cliente_mock.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertNotIn('Mencioné a Ana en el cierre', prompt)
        self.assertIn('Hablé con Bruno hoy', prompt)

    def test_revision_ignora_solo_cierre_dia(self):
        ultima_revision = timezone.now()
        cierre = self._reflexion('duplicado', 'cierre_dia')
        ReflexionLibre.objects.filter(pk=cierre.pk).update(fecha=ultima_revision + timezone.timedelta(seconds=1))
        self.assertFalse(_hay_contexto_para_revision(self.cliente, ultima_revision))

        normal = self._reflexion('evidencia nueva', 'precierre_dia')
        ReflexionLibre.objects.filter(pk=normal.pk).update(fecha=ultima_revision + timezone.timedelta(seconds=2))
        self.assertTrue(_hay_contexto_para_revision(self.cliente, ultima_revision))


class ReflexionLibreSignalTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('signal-owner', password='x')
        self.other = get_user_model().objects.create_user('signal-other', password='x')

    @patch('joi.services.generar_mensaje_joi')
    def test_create_y_edit_invalidan_solo_cache_del_usuario_sin_voz(self, generar_mock):
        own_key = f'joi_ctx_{self.user.pk}'
        other_key = f'joi_ctx_{self.other.pk}'
        cache.set(own_key, 'own')
        cache.set(other_key, 'other')

        with self.captureOnCommitCallbacks(execute=True):
            reflexion = ReflexionLibre.objects.create(usuario=self.user, contenido='Primera versión')
        self.assertIsNone(cache.get(own_key))
        self.assertEqual(cache.get(other_key), 'other')

        cache.set(own_key, 'own-again')
        with self.captureOnCommitCallbacks(execute=True):
            reflexion.contenido = 'Editada'
            reflexion.save()
        self.assertIsNone(cache.get(own_key))
        self.assertEqual(cache.get(other_key), 'other')
        self.assertEqual(MensajeJOI.objects.count(), 0)
        generar_mock.assert_not_called()
