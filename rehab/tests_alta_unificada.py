from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from hyrox.models import HyroxSession, UserInjury
from rehab.models import (
    EpisodioRehab, EventoAltaRehab, FaseProtocolo, ProtocoloRehab,
    RegistroDiarioRehab, SesionRehab,
)


class AltaRehabUnificadaTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user('alta-rehab', password='secret')
        self.cliente = self.user.cliente_perfil
        self.protocolo = ProtocoloRehab.objects.create(
            slug='rodilla-alta', version=1, nombre='Rodilla', zona='rodilla',
            descripcion='Rehab', fuente_referencia='Fuente', criterios_alta={},
            advertencias='No sustituye valoración clínica.',
        )
        self.fase = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=1, slug='carga', nombre='Carga',
            objetivo='Tolerar carga', duracion_minima_dias=1,
            duracion_tipica_dias=7, reglas_avance={}, reglas_retroceso={},
            descripcion='Carga gradual',
        )
        self.injury = UserInjury.objects.create(
            cliente=self.cliente, zona_afectada='Rodilla derecha',
            fase=UserInjury.Fase.RETORNO, fecha_inicio=self.hoy - timedelta(days=30),
            activa=True, tags_restringidos=['flexion_rodilla_profunda'],
        )
        self.episodio = EpisodioRehab.objects.create(
            cliente=self.cliente, protocolo=self.protocolo, protocolo_version=1,
            fase_actual=self.fase, lateralidad='derecha',
            fecha_inicio=self.hoy - timedelta(days=20),
            fase_actual_desde=self.hoy - timedelta(days=7), estado='ACTIVO',
            dolor_basal_inicial=5, lesion_hyrox=self.injury,
        )
        self.diario = RegistroDiarioRehab.objects.create(
            episodio=self.episodio, fecha=self.hoy, dolor_manana=0,
            rigidez_manana=0, notas='Sin dolor',
        )
        self.sesion = SesionRehab.objects.create(
            episodio=self.episodio, fase=self.fase, fecha=self.hoy,
            estado='COMPLETADA', dolor_durante=0, prescripcion_snapshot={},
        )
        self.client.login(username='alta-rehab', password='secret')
        self.url = reverse('rehab:confirmar_alta', args=[self.episodio.pk])

    def _payload(self, **overrides):
        data = {
            'confirmacion_usuario': 'on',
            'lesion_hyrox_id': str(self.injury.pk),
            'nota_evidencia': 'Tres semanas sin restricción funcional percibida.',
        }
        data.update(overrides)
        return data

    def test_get_es_confirmacion_explicita_sin_mutar_y_no_es_alta_medica(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'confirmas que ahora entrenas sin restricciones por esta molestia')
        self.assertContains(response, 'Esto no es un alta médica')
        self.episodio.refresh_from_db()
        self.injury.refresh_from_db()
        self.assertEqual(self.episodio.estado, 'ACTIVO')
        self.assertTrue(self.injury.activa)
        self.assertFalse(EventoAltaRehab.objects.exists())

    @patch('entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym')
    def test_post_cierra_rehab_e_injury_vinculada_preservando_historial(self, autoridad):
        antes = (RegistroDiarioRehab.objects.count(), SesionRehab.objects.count())
        sesiones_hyrox_antes = HyroxSession.objects.count()

        response = self.client.post(self.url, self._payload())

        self.assertRedirects(response, reverse('rehab:hoy'), fetch_redirect_response=False)
        self.episodio.refresh_from_db()
        self.injury.refresh_from_db()
        evento = EventoAltaRehab.objects.get()
        self.assertEqual(self.episodio.estado, 'ALTA')
        self.assertEqual(self.injury.fase, UserInjury.Fase.RECUPERADO)
        self.assertFalse(self.injury.activa)
        self.assertEqual(self.injury.fecha_resolucion, self.hoy)
        self.assertEqual(evento.episodio, self.episodio)
        self.assertEqual(evento.lesion_hyrox, self.injury)
        self.assertEqual(evento.fecha, self.hoy)
        self.assertEqual(evento.actor, self.user)
        self.assertTrue(evento.confirmacion_usuario)
        self.assertEqual(evento.motivo, 'confirmacion_usuario')
        self.assertIn('Tres semanas', evento.nota_evidencia)
        self.assertEqual((RegistroDiarioRehab.objects.count(), SesionRehab.objects.count()), antes)
        self.assertEqual(HyroxSession.objects.count(), sesiones_hyrox_antes)
        autoridad.assert_not_called()

    def test_doble_post_es_idempotente_y_evento_append_only(self):
        first = self.client.post(self.url, self._payload())
        second = self.client.post(self.url, self._payload())

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(EventoAltaRehab.objects.count(), 1)
        evento = EventoAltaRehab.objects.get()
        evento.motivo = 'reescrito'
        with self.assertRaises(Exception):
            evento.save()

    def test_sin_injury_cierra_rehab_sin_inventar_lesion(self):
        self.episodio.lesion_hyrox = None
        self.episodio.save(update_fields=['lesion_hyrox'])
        UserInjury.objects.all().delete()

        response = self.client.post(self.url, self._payload(lesion_hyrox_id=''))

        self.assertEqual(response.status_code, 302)
        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.estado, 'ALTA')
        self.assertIsNone(EventoAltaRehab.objects.get().lesion_hyrox)
        self.assertFalse(UserInjury.objects.exists())

    def test_no_hace_matching_fuzzy_y_solo_resuelve_vinculo_explicito(self):
        otra = UserInjury.objects.create(
            cliente=self.cliente, zona_afectada='Rodilla derecha',
            fase=UserInjury.Fase.SUB_AGUDA, activa=True,
        )

        self.client.post(self.url, self._payload())

        otra.refresh_from_db()
        self.assertTrue(otra.activa)
        self.assertEqual(otra.fase, UserInjury.Fase.SUB_AGUDA)

    def test_exige_confirmacion_post_csrf_y_ownership(self):
        response = self.client.post(self.url, self._payload(confirmacion_usuario=''))
        self.assertEqual(response.status_code, 400)
        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.estado, 'ACTIVO')

        csrf = Client(enforce_csrf_checks=True)
        csrf.login(username='alta-rehab', password='secret')
        self.assertEqual(csrf.post(self.url, self._payload()).status_code, 403)

        otro = User.objects.create_user('alta-ajeno', password='secret')
        self.client.force_login(otro)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self._payload()).status_code, 404)

    def test_admite_estado_pausado(self):
        self.episodio.estado = 'PAUSADO'
        self.episodio.save(update_fields=['estado'])

        response = self.client.post(self.url, self._payload())

        self.assertEqual(response.status_code, 302)
        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.estado, 'ALTA')
