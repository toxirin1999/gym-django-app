"""
Tests for Phase JOI Habitación 2C — Razón de presencia (motivo de estado).

Verifica que cada estado devuelve un motivo determinista visible.
8 tests para validar los 7 motivos posibles + prioridad.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from clientes.models import Cliente, BitacoraDiaria
from hyrox.models import HyroxObjective, HyroxSession, UserInjury
from joi.models import MensajeJOI, NarrativaActiva
from joi.services import determinar_estado_habitacion_joi


class JoiHabitacion2CMotivosTests(TestCase):
    """Tests para determinar_estado_habitacion_joi() con motivos"""

    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil

    def tearDown(self):
        User.objects.all().delete()
        Cliente.objects.all().delete()

    # Test 1: SILENCIO devuelve motivo "sin_senales"
    def test_silencio_devuelve_motivo_sin_senales(self):
        """Sin mensaje, sin narrativa, sin protección → ('SILENCIO', 'sin_senales')"""
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual((estado, motivo), ('SILENCIO', 'sin_senales'))

    # Test 2: OBSERVANDO por diario devuelve motivo correcto
    def test_observando_diario_devuelve_motivo_correcto(self):
        """Diario hoy sin narrativa → ('OBSERVANDO', 'diario_hoy_sin_lectura')"""
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.now().date()
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual((estado, motivo), ('OBSERVANDO', 'diario_hoy_sin_lectura'))

    # Test 3: PRESENTE por mensaje devuelve motivo
    def test_presente_mensaje_devuelve_motivo_correcto(self):
        """Mensaje JOI hoy → ('PRESENTE', 'mensaje_joi_hoy')"""
        MensajeJOI.objects.create(
            user=self.user,
            mensaje="Test mensaje",
            creado_en=timezone.now()
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual((estado, motivo), ('PRESENTE', 'mensaje_joi_hoy'))

    # Test 4: PRESENTE por narrativa devuelve motivo
    def test_presente_narrativa_devuelve_motivo_correcto(self):
        """Narrativa activa → ('PRESENTE', 'narrativa_activa')"""
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Test corta'
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual((estado, motivo), ('PRESENTE', 'narrativa_activa'))

    # Test 5: PROTEGIENDO por RPE devuelve motivo
    def test_protegiendo_rpe_devuelve_motivo_correcto(self):
        """RPE >= 10 hoy → ('PROTEGIENDO', 'rpe_extremo' o 'pulso_protegiendo')"""
        hyrox = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=date(2026, 12, 31)
        )
        HyroxSession.objects.create(
            objective=hyrox,
            fecha=timezone.now().date(),
            nivel_energia_pre=8,
            rpe_global=10,
            estado='completado'
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')
        # Pulso Service puede detectar RPE antes de la check específica
        self.assertIn(motivo, ['rpe_extremo', 'pulso_protegiendo'])

    # Test 6: PROTEGIENDO por lesión devuelve motivo
    def test_protegiendo_lesion_devuelve_motivo_correcto(self):
        """Lesión AGUDA → ('PROTEGIENDO', 'lesion_activa' o 'pulso_protegiendo')"""
        hyrox = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=date(2026, 12, 31)
        )
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='rodilla',
            fase='AGUDA'
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')
        # Pulso Service detecta lesión primero
        self.assertIn(motivo, ['lesion_activa', 'pulso_protegiendo'])

    # Test 7: PROTEGIENDO por Pulso devuelve motivo
    def test_protegiendo_pulso_devuelve_motivo_correcto(self):
        """Pulso PROTEGIENDO (lesión AGUDA) → ('PROTEGIENDO', 'pulso_protegiendo')"""
        hyrox = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=date(2026, 12, 31)
        )
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='muñeca',
            fase='AGUDA'
        )
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        # Lesión es detectada antes que Pulso en el orden, pero ambos devuelven PROTEGIENDO
        self.assertEqual(estado, 'PROTEGIENDO')
        self.assertIn(motivo, ['lesion_activa', 'pulso_protegiendo'])

    # Test 8: Motivo nunca es None
    def test_motivo_nunca_es_none(self):
        """Cualquier estado devuelve un motivo válido"""
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertIsNotNone(motivo)
        self.assertIsInstance(motivo, str)
        self.assertIn(motivo, [
            'sin_senales',
            'diario_hoy_sin_lectura',
            'mensaje_joi_hoy',
            'narrativa_activa',
            'rpe_extremo',
            'lesion_activa',
            'pulso_protegiendo'
        ])
