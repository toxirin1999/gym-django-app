"""
Fase 1 del CONTRATO_ANALIZADOR_GESTOS.md — corrección de zona horaria.

Antes de esta fase, `TIME_ZONE='UTC'` y varias vistas usaban
`timezone.now().date()` / `date.today()` para calcular "hoy". Como el
usuario real vive en Europe/Madrid (UTC+1/+2), un cierre nocturno tardío
podía calcularse con la fecha equivocada: p. ej. las 23:30 UTC del 17 de
julio ya son la 01:30 del 18 de julio en Madrid.

Estos tests fijan un instante concreto donde UTC y Europe/Madrid discrepan
de día civil, y verifican que la app usa el día de Madrid, no el de UTC.
"""
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Gesto, RegistroGesto

# 23:30 UTC del 17 de julio de 2026 = 01:30 del 18 de julio en Europe/Madrid
# (CEST, UTC+2 en julio). Es el caso canónico de discrepancia de día civil.
INSTANTE_MEDIANOCHE_UTC = datetime(2026, 7, 17, 23, 30, tzinfo=dt_timezone.utc)
DIA_UTC = date(2026, 7, 17)
DIA_MADRID = date(2026, 7, 18)


class ZonaHorariaLocaldateTestCase(TestCase):
    """timezone.localdate() debe devolver el día de Madrid, no el de UTC."""

    @patch('django.utils.timezone.now', return_value=INSTANTE_MEDIANOCHE_UTC)
    def test_localdate_usa_dia_madrid_no_dia_utc(self, mock_now):
        self.assertEqual(timezone.localdate(), DIA_MADRID)
        self.assertNotEqual(timezone.localdate(), DIA_UTC)


class PresenciaCierreMedianocheTestCase(TestCase):
    """El cierre nocturno tardío debe registrarse en el día civil de Madrid."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )

    @patch('django.utils.timezone.now', return_value=INSTANTE_MEDIANOCHE_UTC)
    def test_cierre_tardio_registra_fecha_de_madrid(self, mock_now):
        self.client.post(
            '/diario/presencia/cierre/',
            {
                'reflexion_libre': '',
                'habitos_completados': f'[{self.gesto.id}]',
            },
            SERVER_NAME='127.0.0.1',
        )
        self.assertTrue(
            RegistroGesto.objects.filter(
                gesto=self.gesto, fecha=DIA_MADRID, estado='cumplido'
            ).exists(),
            "El cierre a las 23:30 UTC (01:30 en Madrid) debe registrarse "
            "el 18 de julio (día de Madrid), no el 17 (día UTC).",
        )
        self.assertFalse(
            RegistroGesto.objects.filter(gesto=self.gesto, fecha=DIA_UTC).exists(),
            "No debe quedar ningún registro colgado en el día UTC.",
        )


class RachaCercaDeMedianocheTestCase(TestCase):
    """Gesto.get_racha_actual() ya usaba timezone.localdate() — debe seguir
    contando la racha en días de Madrid una vez corregido TIME_ZONE, sin
    necesidad de tocar su código."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        RegistroGesto.objects.create(gesto=self.gesto, fecha=DIA_MADRID, estado='cumplido')

    @patch('django.utils.timezone.now', return_value=INSTANTE_MEDIANOCHE_UTC)
    def test_racha_cuenta_el_dia_de_madrid_como_hoy(self, mock_now):
        # A las 23:30 UTC del 17, ya es 18 en Madrid: el registro de "hoy"
        # (DIA_MADRID) debe contar como racha vigente, no como "de ayer".
        self.assertEqual(self.gesto.get_racha_actual(), 1)
