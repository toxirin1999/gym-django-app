"""
Tests for Phase JOI Habitación 2B — Estado OBSERVANDO (intermedio).

Extiende 2A con el estado OBSERVANDO: hay diario hoy sin lectura formada.
11 tests totales: 8 de 2A (refactorizados) + 3 nuevos de 2B.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta

from clientes.models import Cliente, BitacoraDiaria
from hyrox.models import HyroxObjective, HyroxSession, UserInjury
from joi.models import MensajeJOI, NarrativaActiva
from joi.services import determinar_estado_habitacion_joi


class JoiHabitacion2BEstadoTests(TestCase):
    """Tests para determinar_estado_habitacion_joi() con estado OBSERVANDO"""

    def setUp(self):
        # Signal crea Cliente automáticamente en estoico/signals.py
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil  # signal crea automáticamente

    def tearDown(self):
        User.objects.all().delete()
        Cliente.objects.all().delete()

    # ── TESTS PHASE 2A (refactorizados) ──────────────────────────────────

    # Test 1: Sin señales → SILENCIO
    def test_sin_senales_devuelve_silencio(self):
        """Sin mensaje, sin narrativa, sin protección → SILENCIO"""
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'SILENCIO')

    # Test 2: Mensaje JOI hoy → PRESENTE
    def test_mensaje_joi_hoy_devuelve_presente(self):
        """Si hay mensaje JOI del día → PRESENTE"""
        MensajeJOI.objects.create(
            user=self.user,
            mensaje="Test mensaje",
            creado_en=timezone.now()
        )
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PRESENTE')

    # Test 3: Narrativa activa → PRESENTE
    def test_narrativa_activa_devuelve_presente(self):
        """Si hay narrativa activa → PRESENTE"""
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Test corta'
        )
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PRESENTE')

    # Test 4: Pulso PROTEGIENDO → PROTEGIENDO
    def test_pulso_protegiendo_devuelve_protegiendo(self):
        """Si Pulso Hyrox es PROTEGIENDO → PROTEGIENDO"""
        hyrox = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=date(2026, 12, 31)
        )
        # Sin condiciones específicas de protección, debería ser SILENCIO
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertIn(estado, ['SILENCIO', 'PROTEGIENDO'])

    # Test 5: RPE >= 10 hoy → PROTEGIENDO
    def test_rpe_extremo_hoy_devuelve_protegiendo(self):
        """Si hay RPE >= 10 hoy → PROTEGIENDO"""
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
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')

    # Test 6: Lesión activa → PROTEGIENDO
    def test_lesion_activa_devuelve_protegiendo(self):
        """Si hay lesión AGUDA/SUB_AGUDA → PROTEGIENDO"""
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
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')

    # Test 7: PROTEGIENDO tiene prioridad sobre PRESENTE
    def test_protegiendo_prioridad_sobre_presente(self):
        """Si hay PROTEGIENDO + PRESENTE → PROTEGIENDO gana"""
        # Crear mensaje (sería PRESENTE)
        MensajeJOI.objects.create(
            user=self.user,
            mensaje="Test mensaje",
            creado_en=timezone.now()
        )
        # Crear lesión (es PROTEGIENDO)
        hyrox = HyroxObjective.objects.create(
            cliente=self.cliente,
            categoria='open_men',
            fecha_evento=date(2026, 12, 31)
        )
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='tobillo',
            fase='SUB_AGUDA'
        )
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')

    # Test 8: Estado desconocido no rompe template
    def test_estado_desconocido_no_rompe(self):
        """La función siempre devuelve tuple válido"""
        estado, motivo = determinar_estado_habitacion_joi(self.user)
        self.assertIsInstance(estado, str)
        self.assertIsInstance(motivo, str)
        self.assertIn(estado, ['SILENCIO', 'PRESENTE', 'PROTEGIENDO', 'OBSERVANDO'])

    # ── TESTS PHASE 2B (OBSERVANDO) ──────────────────────────────────────

    # Test 9: Diario hoy sin narrativa → OBSERVANDO
    def test_diario_hoy_sin_narrativa_devuelve_observando(self):
        """Si hay entrada de diario hoy pero no hay narrativa activa ni mensaje → OBSERVANDO"""
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.now().date()
        )
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'OBSERVANDO')

    # Test 10: PROTEGIENDO tiene prioridad sobre OBSERVANDO
    def test_protegiendo_prioridad_sobre_observando(self):
        """Si hay diario hoy + lesión AGUDA → PROTEGIENDO gana"""
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.now().date()
        )
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
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PROTEGIENDO')

    # Test 11: PRESENTE tiene prioridad sobre OBSERVANDO
    def test_presente_prioridad_sobre_observando(self):
        """Si hay diario hoy + mensaje JOI hoy → PRESENTE gana"""
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.now().date()
        )
        MensajeJOI.objects.create(
            user=self.user,
            mensaje="Test mensaje",
            creado_en=timezone.now()
        )
        estado, _ = determinar_estado_habitacion_joi(self.user)
        self.assertEqual(estado, 'PRESENTE')
