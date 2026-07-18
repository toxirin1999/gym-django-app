"""
Fase 4.1 del CONTRATO_ANALIZADOR_GESTOS.md — saneamiento de
Gesto.fecha_inicio (default=timezone.now → default=timezone.localdate).

Propiedad que se protege: el tipo y significado de fecha_inicio no deben
depender de si la instancia fue recargada desde la base de datos.
"""
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Gesto
from .services.analizador_gestos import _como_fecha


class FechaInicioTipoConsistenteTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_gesto_recien_instanciado_sin_guardar_tiene_date(self):
        gesto = Gesto(usuario=self.user, nombre='Meditar', tipo='cultivo')
        self.assertIs(type(gesto.fecha_inicio), date)

    def test_create_mantiene_el_mismo_tipo_antes_y_despues_de_recargar(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo')
        tipo_antes = type(gesto.fecha_inicio)
        valor_antes = gesto.fecha_inicio

        gesto.refresh_from_db()
        tipo_despues = type(gesto.fecha_inicio)

        self.assertIs(tipo_antes, date)
        self.assertIs(tipo_despues, date)
        self.assertEqual(valor_antes, gesto.fecha_inicio)

    def test_fecha_inicio_por_defecto_es_hoy(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo')
        self.assertEqual(gesto.fecha_inicio, timezone.localdate())


class AnalizadorSigueAceptandoDatetimeManualTestCase(TestCase):
    """La normalización defensiva del analizador se mantiene a propósito
    — protege frente a instancias antiguas, factories o asignaciones
    manuales incorrectas, aunque ya no sea el mecanismo principal."""

    def test_como_fecha_normaliza_datetime_asignado_a_mano(self):
        instante = datetime(2026, 6, 1, 10, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(_como_fecha(instante), date(2026, 6, 1))

    def test_como_fecha_deja_pasar_un_date_normal(self):
        self.assertEqual(_como_fecha(date(2026, 6, 1)), date(2026, 6, 1))

    def test_gesto_con_fecha_inicio_forzada_a_datetime_no_rompe_el_analizador(self):
        from .services import analizador_gestos as az

        user = User.objects.create_user(username='david2', password='x')
        gesto = Gesto.objects.create(usuario=user, nombre='Meditar', tipo='cultivo')
        # Simula una instancia vieja o mal construida a mano.
        gesto.fecha_inicio = datetime(2026, 6, 1, 10, 30, tzinfo=dt_timezone.utc)
        resultado = az.apariciones(gesto, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(resultado['valor'], 0)  # no explota, y sin registros da 0


class MigracionNoAlteraDatosExistentesTestCase(TestCase):
    """La migración 0023 solo cambia el default de Python para inserts
    futuros — los valores ya persistidos no cambian."""

    def test_fecha_inicio_persistida_no_cambia_tras_la_migracion(self):
        user = User.objects.create_user(username='david', password='x')
        fecha_explicita = date(2020, 1, 1)
        gesto = Gesto.objects.create(
            usuario=user, nombre='Hábito antiguo', tipo='cultivo', fecha_inicio=fecha_explicita,
        )
        gesto.refresh_from_db()
        self.assertEqual(gesto.fecha_inicio, fecha_explicita)
