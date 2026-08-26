import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import (
    ActividadRealizada, ContratoSemanalGym, EstrategiaSemanalGym,
    SesionProgramada,
)
from hyrox.models import (
    ContratoCampanaHyrox,
    HyroxObjective,
    HyroxSession,
    SolicitudHyroxPuntual,
)


class HyroxPuntualExtraUITests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user('puntual-ui', password='secret')
        self.cliente = self.user.cliente_perfil
        self.objective_old = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy - datetime.timedelta(days=60),
            estado='completado',
        )
        self.objective_latest = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy - datetime.timedelta(days=10),
            estado='cancelado',
        )
        self.campana = ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado='inactiva',
            objetivo=self.objective_latest,
            objetivo_snapshot={},
            bloque_gym_snapshot={},
            limites_snapshot={},
            fingerprint='a' * 64,
        )
        self.gym = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy,
            nombre_sesion='Fuerza intacta',
        )
        self.client.login(username='puntual-ui', password='secret')
        self.url = reverse('hyrox:solicitar_extra')

    def _estado_gym(self):
        self.gym.refresh_from_db()
        return self.gym.fecha_prevista, self.gym.estado, self.gym.pospuesta_hasta

    def test_get_preview_es_factual_y_no_muta_gym_campana_ni_sesiones(self):
        gym_antes = self._estado_gym()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No sustituye ni mueve tu sesión Gym')
        self.assertEqual(response.context['objetivo_historico'], self.objective_latest)
        self.assertEqual(self._estado_gym(), gym_antes)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.estado, 'inactiva')
        self.assertFalse(HyroxSession.objects.exists())
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())

    def test_post_crea_una_sesion_puntual_y_doble_post_es_idempotente(self):
        gym_antes = self._estado_gym()

        first = self.client.post(self.url)
        second = self.client.post(self.url)

        solicitud = SolicitudHyroxPuntual.objects.get()
        self.assertRedirects(
            first, reverse('hyrox:registrar_extra', args=[solicitud.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(second.url, first.url)
        self.assertEqual(solicitud.estado, 'en_registro')
        self.assertEqual(solicitud.modo, 'extra')
        self.assertEqual(solicitud.resolucion_gym, 'ninguna')
        self.assertEqual(solicitud.hyrox_session.titulo, 'Sesión Hyrox puntual')
        self.assertEqual(solicitud.hyrox_session.objective, self.objective_latest)
        self.assertEqual(HyroxSession.objects.count(), 1)
        self.assertEqual(self._estado_gym(), gym_antes)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.estado, 'inactiva')

    def test_registro_es_del_propietario_y_completa_solicitud_y_hub_una_vez(self):
        self.client.post(self.url)
        solicitud = SolicitudHyroxPuntual.objects.get()
        detail = reverse('hyrox:registrar_extra', args=[solicitud.pk])

        response = self.client.post(detail, {
            'titulo': 'Mi trabajo puntual',
            'nivel_energia_pre': 7,
            'tiempo_total_minutos': 35,
            'rpe_global': 6,
            'notas_raw': '',
        })
        repeated = self.client.post(detail, {
            'titulo': 'Mi trabajo puntual',
            'nivel_energia_pre': 7,
            'tiempo_total_minutos': 35,
            'rpe_global': 6,
            'notas_raw': '',
        })

        self.assertRedirects(response, reverse('hyrox:dashboard'), fetch_redirect_response=False)
        self.assertRedirects(repeated, reverse('hyrox:dashboard'), fetch_redirect_response=False)
        solicitud.refresh_from_db()
        solicitud.hyrox_session.refresh_from_db()
        self.assertEqual(solicitud.estado, 'completada')
        self.assertEqual(solicitud.hyrox_session.estado, 'completado')
        self.assertEqual(solicitud.hyrox_session.nivel_energia_pre, 7)
        self.assertEqual(solicitud.hyrox_session.tiempo_total_minutos, 35)
        self.assertEqual(solicitud.hyrox_session.rpe_global, 6)
        self.assertEqual(ActividadRealizada.objects.filter(
            sesion_hyrox=solicitud.hyrox_session
        ).count(), 1)
        self.assertEqual(HyroxSession.objects.count(), 1)

        other = User.objects.create_user('puntual-intruso', password='secret')
        self.client.force_login(other)
        self.assertEqual(self.client.get(detail).status_code, 404)

    def test_sin_objetivo_bloquea_sin_mutacion(self):
        self.campana.delete()
        HyroxObjective.objects.filter(cliente=self.cliente).delete()
        gym_antes = self._estado_gym()

        preview = self.client.get(self.url)
        post = self.client.post(self.url)

        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'No hay un objetivo Hyrox histórico')
        self.assertEqual(post.status_code, 409)
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())
        self.assertFalse(HyroxSession.objects.exists())
        self.assertEqual(self._estado_gym(), gym_antes)

    def test_campana_activa_no_admite_el_flujo_puntual_archivado(self):
        self.campana.estado = 'activa'
        # El modelo es inmutable; simulamos el estado persistido de otra fase.
        ContratoCampanaHyrox.objects.filter(pk=self.campana.pk).update(estado='activa')

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())
        self.assertFalse(HyroxSession.objects.exists())


class HyroxPuntualExtraCSRFFTests(TestCase):
    def test_post_requiere_csrf(self):
        user = User.objects.create_user('puntual-csrf', password='secret')
        HyroxObjective.objects.create(
            cliente=user.cliente_perfil,
            fecha_evento=timezone.localdate() - datetime.timedelta(days=1),
            estado='completado',
        )
        client = Client(enforce_csrf_checks=True)
        client.login(username='puntual-csrf', password='secret')
        self.assertEqual(client.post(reverse('hyrox:solicitar_extra')).status_code, 403)


class HyroxPuntualSustituirGymUITests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.lunes = self.hoy - datetime.timedelta(days=self.hoy.weekday())
        self.user = User.objects.create_user('puntual-sustituir', password='secret')
        self.cliente = self.user.cliente_perfil
        self.objective = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy - datetime.timedelta(days=20),
            estado='completado',
        )
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=4,
            minimo_valido=3, vigente_desde=self.lunes,
        )
        self.contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia,
            semana=self.lunes, objetivo_sesiones=4, minimo_valido=3,
        )
        self.gym = SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=self.contrato,
            semana_prescrita=self.lunes, fecha_prevista=self.hoy,
            nombre_sesion='Pierna de hoy',
        )
        self.client.login(username='puntual-sustituir', password='secret')
        self.url = reverse('hyrox:solicitar_sustitucion_gym')

    def test_get_preview_muestra_gym_y_consecuencia_sin_mutar(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pierna de hoy')
        self.assertContains(response, 'Saltarla por decisión tuya')
        self.assertContains(response, 'Reubicarla dentro de esta semana')
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.gym.pospuesta_hasta)
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())
        self.assertFalse(HyroxSession.objects.exists())

    def test_omitir_usa_saltada_usuario_y_doble_post_es_idempotente(self):
        first = self.client.post(self.url, {'resolucion_gym': 'omitida'})
        second = self.client.post(self.url, {'resolucion_gym': 'omitida'})

        solicitud = SolicitudHyroxPuntual.objects.get()
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.url, first.url)
        self.assertEqual(solicitud.modo, 'sustituye_gym')
        self.assertEqual(solicitud.resolucion_gym, 'omitida')
        self.assertEqual(solicitud.estado, 'en_registro')
        self.assertEqual(solicitud.sesion_gym_programada, self.gym)
        self.assertEqual(SolicitudHyroxPuntual.objects.count(), 1)
        self.assertEqual(HyroxSession.objects.count(), 1)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.estado, SesionProgramada.ESTADO_SALTADA_USUARIO)
        self.assertNotEqual(self.gym.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertIsNone(self.gym.fecha_realizada)

    def test_reubicar_mismo_contrato_actualiza_fecha_efectiva(self):
        destino = self.hoy + datetime.timedelta(days=1)

        response = self.client.post(self.url, {
            'resolucion_gym': 'reubicada',
            'fecha_reubicacion': destino.isoformat(),
        })

        self.assertEqual(response.status_code, 302)
        solicitud = SolicitudHyroxPuntual.objects.get()
        self.assertEqual(solicitud.resolucion_gym, 'reubicada')
        self.assertEqual(solicitud.fecha_reubicacion, destino)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(self.gym.pospuesta_hasta, destino)
        self.assertEqual(self.gym.contrato_semanal, self.contrato)

    def test_reubicar_fuera_de_semana_o_con_colision_bloquea_sin_mutar(self):
        fuera = self.lunes + datetime.timedelta(days=7)
        response = self.client.post(self.url, {
            'resolucion_gym': 'reubicada', 'fecha_reubicacion': fuera.isoformat(),
        })
        self.assertEqual(response.status_code, 400)

        destino = self.hoy + datetime.timedelta(days=1)
        SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=self.contrato,
            semana_prescrita=self.lunes, fecha_prevista=destino,
            nombre_sesion='Otra sesión',
        )
        response = self.client.post(self.url, {
            'resolucion_gym': 'reubicada', 'fecha_reubicacion': destino.isoformat(),
        })
        self.assertEqual(response.status_code, 409)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.gym.pospuesta_hasta)
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())
        self.assertFalse(HyroxSession.objects.exists())

    def test_sin_gym_hoy_bloquea_y_ownership_csrf_se_conservan(self):
        self.gym.delete()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, {'resolucion_gym': 'omitida'}).status_code, 409)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='puntual-sustituir', password='secret')
        self.assertEqual(csrf_client.post(self.url, {'resolucion_gym': 'omitida'}).status_code, 403)

    def test_decisiones_extra_y_sustitucion_comparten_clave_diaria(self):
        extra = self.client.post(reverse('hyrox:solicitar_extra'))
        self.assertEqual(extra.status_code, 302)

        sustitucion = self.client.post(self.url, {'resolucion_gym': 'omitida'})

        self.assertEqual(sustitucion.status_code, 409)
        self.assertEqual(SolicitudHyroxPuntual.objects.count(), 1)
        self.assertEqual(HyroxSession.objects.count(), 1)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_sustitucion_impide_un_segundo_extra_el_mismo_dia(self):
        sustitucion = self.client.post(self.url, {'resolucion_gym': 'omitida'})
        self.assertEqual(sustitucion.status_code, 302)

        extra = self.client.post(reverse('hyrox:solicitar_extra'))

        self.assertEqual(extra.status_code, 409)
        self.assertEqual(SolicitudHyroxPuntual.objects.count(), 1)
        self.assertEqual(HyroxSession.objects.count(), 1)
