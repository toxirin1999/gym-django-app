"""
Phase 63.1 — sincronización de medidas corporales (cintura, peso_corporal,
grasa_corporal) hacia el historial RevisionProgreso.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente, RevisionProgreso
from clientes.revision_sync_service import crear_revision_si_medidas_cambiaron

HOY = date(2026, 6, 14)


class CrearRevisionSiMedidasCambiaronTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_revision_sync', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_cambio_en_cintura_crea_revision(self):
        anteriores = {'cintura': None, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}
        nuevos = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}

        revision = crear_revision_si_medidas_cambiaron(self.cliente, anteriores, nuevos, fecha=HOY)

        self.assertIsNotNone(revision)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 1)
        self.assertEqual(revision.cintura, Decimal('84.00'))

    def test_cambio_en_peso_corporal_crea_revision(self):
        anteriores = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}
        nuevos = {'cintura': 84.0, 'peso_corporal': 81.5, 'grasa_corporal': 18.0}

        revision = crear_revision_si_medidas_cambiaron(self.cliente, anteriores, nuevos, fecha=HOY)

        self.assertIsNotNone(revision)
        self.assertEqual(revision.peso_corporal, Decimal('81.50'))

    def test_cambio_en_grasa_corporal_crea_revision(self):
        anteriores = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}
        nuevos = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 17.0}

        revision = crear_revision_si_medidas_cambiaron(self.cliente, anteriores, nuevos, fecha=HOY)

        self.assertIsNotNone(revision)
        self.assertEqual(revision.grasa_corporal, Decimal('17.00'))

    def test_sin_cambios_no_crea_nada(self):
        valores = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}

        revision = crear_revision_si_medidas_cambiaron(self.cliente, dict(valores), dict(valores), fecha=HOY)

        self.assertIsNone(revision)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 0)

    def test_todos_los_valores_nuevos_vacios_no_crea_nada(self):
        anteriores = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}
        nuevos = {'cintura': None, 'peso_corporal': None, 'grasa_corporal': None}

        revision = crear_revision_si_medidas_cambiaron(self.cliente, anteriores, nuevos, fecha=HOY)

        self.assertIsNone(revision)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 0)

    def test_no_duplica_si_ya_existe_revision_hoy_con_mismos_valores(self):
        nuevos = {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0}

        primera = crear_revision_si_medidas_cambiaron(
            self.cliente, {'cintura': None, 'peso_corporal': None, 'grasa_corporal': None}, nuevos, fecha=HOY,
        )
        self.assertIsNotNone(primera)

        # Otro guardado el mismo día con los mismos valores (p.ej. el usuario
        # vuelve a entrar a "Mi cuerpo" y guarda sin cambiar nada).
        segunda = crear_revision_si_medidas_cambiaron(
            self.cliente, nuevos, nuevos, fecha=HOY,
        )
        self.assertIsNone(segunda)
        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 1)

    def test_phase63_detecta_senal_medidas_tras_dos_cambios_reales(self):
        from entrenos.services.revision_progreso_service import get_revision_progreso

        crear_revision_si_medidas_cambiaron(
            self.cliente,
            {'cintura': None, 'peso_corporal': None, 'grasa_corporal': None},
            {'cintura': 86.0, 'peso_corporal': 82.0, 'grasa_corporal': 19.0},
            fecha=HOY - timedelta(days=14),
        )
        crear_revision_si_medidas_cambiaron(
            self.cliente,
            {'cintura': 86.0, 'peso_corporal': 82.0, 'grasa_corporal': 19.0},
            {'cintura': 84.0, 'peso_corporal': 80.0, 'grasa_corporal': 18.0},
            fecha=HOY,
        )

        self.assertEqual(RevisionProgreso.objects.filter(cliente=self.cliente).count(), 2)

        items = get_revision_progreso(self.cliente, hoy=HOY)
        textos = [item['texto'] for item in items]
        self.assertTrue(any('cintura' in texto.lower() for texto in textos))
