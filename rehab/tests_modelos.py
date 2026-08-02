from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from clientes.models import Cliente
from rehab.models import EpisodioRehab, ProtocoloRehab, RegistroDiarioRehab


class ProtocoloRehabUniqueTests(TestCase):
    def test_slug_version_unico(self):
        ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='Protocolo Cook & Purdam',
            fuente_referencia='Cook & Purdam, 2009',
            advertencias='Detener si dolor > 5/10',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProtocoloRehab.objects.create(
                    slug='tendinopatia-rotuliana',
                    version=1,
                    nombre='Tendinopatía rotuliana (duplicado)',
                    zona='rodilla',
                    descripcion='x',
                    fuente_referencia='x',
                    advertencias='x',
                )

    def test_misma_slug_distinta_version_permitida(self):
        ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=2,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        self.assertEqual(ProtocoloRehab.objects.filter(slug='tendinopatia-rotuliana').count(), 2)


class EpisodioRehabConstraintTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paciente_rehab', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        self.otro_protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-aquilea',
            version=1,
            nombre='Tendinopatía aquílea',
            zona='tobillo',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )

    def test_no_permite_dos_episodios_activos_mismo_protocolo(self):
        EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.protocolo,
            protocolo_version=1,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            fase_actual_desde=date(2026, 1, 1),
            estado='ACTIVO',
            dolor_basal_inicial=4,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EpisodioRehab.objects.create(
                    cliente=self.cliente,
                    protocolo=self.protocolo,
                    protocolo_version=1,
                    lateralidad='izquierda',
                    fecha_inicio=date(2026, 2, 1),
                    fase_actual_desde=date(2026, 2, 1),
                    estado='ACTIVO',
                    dolor_basal_inicial=5,
                )

    def test_permite_episodio_activo_de_protocolo_distinto(self):
        EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.protocolo,
            protocolo_version=1,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            fase_actual_desde=date(2026, 1, 1),
            estado='ACTIVO',
            dolor_basal_inicial=4,
        )
        EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.otro_protocolo,
            protocolo_version=1,
            lateralidad='izquierda',
            fecha_inicio=date(2026, 1, 5),
            fase_actual_desde=date(2026, 1, 5),
            estado='ACTIVO',
            dolor_basal_inicial=3,
        )
        self.assertEqual(
            EpisodioRehab.objects.filter(cliente=self.cliente, estado='ACTIVO').count(), 2
        )

    def test_permite_episodio_no_activo_repetido_mismo_protocolo(self):
        EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.protocolo,
            protocolo_version=1,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            fase_actual_desde=date(2026, 1, 1),
            estado='ALTA',
            dolor_basal_inicial=4,
        )
        EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.protocolo,
            protocolo_version=1,
            lateralidad='derecha',
            fecha_inicio=date(2026, 3, 1),
            fase_actual_desde=date(2026, 3, 1),
            estado='ACTIVO',
            dolor_basal_inicial=6,
        )
        self.assertEqual(EpisodioRehab.objects.filter(cliente=self.cliente).count(), 2)


class RegistroDiarioRehabUniqueTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paciente_registro', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        self.episodio = EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=self.protocolo,
            protocolo_version=1,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            fase_actual_desde=date(2026, 1, 1),
            estado='ACTIVO',
            dolor_basal_inicial=4,
        )

    def test_no_permite_dos_registros_mismo_dia(self):
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 2),
            dolor_manana=3,
            rigidez_manana=2,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroDiarioRehab.objects.create(
                    episodio=self.episodio,
                    fecha=date(2026, 1, 2),
                    dolor_manana=5,
                    rigidez_manana=4,
                )

    def test_permite_registros_dias_distintos(self):
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 2),
            dolor_manana=3,
            rigidez_manana=2,
        )
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 3),
            dolor_manana=2,
            rigidez_manana=1,
        )
        self.assertEqual(RegistroDiarioRehab.objects.filter(episodio=self.episodio).count(), 2)
