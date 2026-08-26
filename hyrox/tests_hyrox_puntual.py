import datetime
import uuid

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from entrenos.models import SesionProgramada
from hyrox.models import HyroxObjective, SolicitudHyroxPuntual
from hyrox.hyrox_puntual_service import (
    IdempotencyKeyReutilizada,
    autorizar_solicitud_extra,
)


class SolicitudHyroxPuntualModelTests(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('puntual-modelo').cliente_perfil

    def test_defaults_y_relaciones_nullable(self):
        solicitud = SolicitudHyroxPuntual.objects.create(
            cliente=self.cliente,
            fecha=datetime.date(2026, 8, 26),
            idempotency_key='request-1',
        )

        self.assertIsInstance(solicitud.pk, uuid.UUID)
        self.assertEqual(solicitud.modo, 'extra')
        self.assertEqual(solicitud.resolucion_gym, 'ninguna')
        self.assertEqual(solicitud.estado, 'autorizada')
        self.assertIsNone(solicitud.sesion_gym_programada)
        self.assertIsNone(solicitud.fecha_reubicacion)
        self.assertIsNone(solicitud.hyrox_session)
        self.assertIsNone(solicitud.actor)
        self.assertEqual(solicitud.authority_snapshot, {})
        self.assertEqual(solicitud.safety_snapshot, {})
        self.assertEqual(solicitud.gym_contract_snapshot, {})

    def test_idempotency_key_es_unica_por_cliente(self):
        SolicitudHyroxPuntual.objects.create(
            cliente=self.cliente,
            fecha=datetime.date(2026, 8, 26),
            idempotency_key='same-key',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SolicitudHyroxPuntual.objects.create(
                    cliente=self.cliente,
                    fecha=datetime.date(2026, 8, 27),
                    idempotency_key='same-key',
                )

        otro = User.objects.create_user('puntual-otro').cliente_perfil
        SolicitudHyroxPuntual.objects.create(
            cliente=otro,
            fecha=datetime.date(2026, 8, 26),
            idempotency_key='same-key',
        )


class AutorizarSolicitudExtraTests(TestCase):
    def setUp(self):
        self.hoy = datetime.date(2026, 8, 26)
        self.user = User.objects.create_user('puntual-servicio')
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=60),
        )
        self.safety = {'decision': 'empujar', 'puede_ejecutar': True}
        self.gym_contract = {'semana': '2026-08-24', 'objetivo_sesiones': 4}

    def _autorizar(self, **overrides):
        kwargs = {
            'cliente': self.cliente,
            'objective': self.objetivo,
            'idempotency_key': 'request-abc',
            'fecha': self.hoy,
            'modo': 'extra',
            'safety_snapshot': self.safety,
            'gym_contract_snapshot': self.gym_contract,
            'actor': self.user,
        }
        kwargs.update(overrides)
        return autorizar_solicitud_extra(**kwargs)

    def test_autoriza_extra_hoy_con_snapshots_y_sin_mutar_gym(self):
        gym = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy,
            nombre_sesion='Fuerza A',
        )
        estado_original = (gym.fecha_prevista, gym.estado, gym.pospuesta_hasta)

        solicitud = self._autorizar()

        gym.refresh_from_db()
        self.assertEqual((gym.fecha_prevista, gym.estado, gym.pospuesta_hasta), estado_original)
        self.assertEqual(solicitud.fecha, self.hoy)
        self.assertEqual(solicitud.modo, 'extra')
        self.assertEqual(solicitud.resolucion_gym, 'ninguna')
        self.assertEqual(solicitud.estado, 'autorizada')
        self.assertEqual(solicitud.actor, self.user)
        self.assertTrue(solicitud.authority_snapshot['permisos']['registro_manual'])
        self.assertEqual(solicitud.safety_snapshot, self.safety)
        self.assertEqual(solicitud.gym_contract_snapshot, self.gym_contract)

    def test_misma_key_y_payload_reutiliza_la_solicitud(self):
        primera = self._autorizar()
        segunda = self._autorizar()

        self.assertEqual(segunda.pk, primera.pk)
        self.assertEqual(SolicitudHyroxPuntual.objects.count(), 1)

    def test_misma_key_con_payload_distinto_falla(self):
        self._autorizar()

        with self.assertRaises(IdempotencyKeyReutilizada):
            self._autorizar(safety_snapshot={'decision': 'recuperar'})

        self.assertEqual(SolicitudHyroxPuntual.objects.count(), 1)

    def test_rechaza_objetivo_ajeno(self):
        otro = User.objects.create_user('puntual-ajeno').cliente_perfil
        objetivo_ajeno = HyroxObjective.objects.create(
            cliente=otro,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )

        with self.assertRaises(Exception) as error:
            self._autorizar(objective=objetivo_ajeno)

        self.assertEqual(error.exception.__class__.__name__, 'CampanaHyroxNoAutoriza')
        self.assertFalse(SolicitudHyroxPuntual.objects.exists())

    def test_rechaza_sustitucion_y_fecha_que_no_sea_hoy(self):
        with self.assertRaises(ValueError):
            self._autorizar(modo='sustituye_gym')
        with self.assertRaises(ValueError):
            self._autorizar(fecha=self.hoy + datetime.timedelta(days=1))

        self.assertFalse(SolicitudHyroxPuntual.objects.exists())
