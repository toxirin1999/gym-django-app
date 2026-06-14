"""
Phase Hábitos 2.0C — Tests del data layer persistente de gestos (Gesto/RegistroGesto)
y de la migración de datos legacy ProsocheHabito -> Gesto/RegistroGesto.
"""
import importlib
from datetime import date

from django.apps import apps
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from diario.models import (
    Gesto, RegistroGesto, ProsocheMes, ProsocheHabito, ProsocheHabitoDia,
)

_migracion_0018 = importlib.import_module('diario.migrations.0018_migrar_habitos_a_gestos')
migrar_datos = _migracion_0018.migrar_datos
reverse_migrar_datos = _migracion_0018.reverse_migrar_datos


class GestoMigracionTestCase(TestCase):
    """Tests de la migración de datos 0018_migrar_habitos_a_gestos."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')

    def _crear_mes(self, mes, año):
        return ProsocheMes.objects.create(usuario=self.usuario, mes=mes, año=año)

    def _crear_habito(self, prosoche_mes, nombre='Entrenar', tipo_habito='positivo',
                       color='#ff0000', objetivo_dias=30):
        return ProsocheHabito.objects.create(
            prosoche_mes=prosoche_mes,
            nombre=nombre,
            tipo_habito=tipo_habito,
            color=color,
            objetivo_dias=objetivo_dias,
        )

    def _ejecutar_migracion(self):
        migrar_datos(apps, schema_editor=None)

    # 1. Consolidación de varios ProsocheHabito en un único Gesto
    def test_consolida_varios_meses_en_un_gesto(self):
        meses = [
            ('October', 2025), ('November', 2025), ('December', 2025),
            ('January', 2026), ('March', 2026), ('May', 2026), ('June', 2026),
        ]
        for mes, año in meses:
            pm = self._crear_mes(mes, año)
            self._crear_habito(pm, nombre='Entrenar')

        self._ejecutar_migracion()

        self.assertEqual(
            Gesto.objects.filter(usuario=self.usuario, nombre='Entrenar').count(), 1
        )

    # 2. Config del Gesto viene del ProsocheHabito más reciente
    def test_config_gesto_usa_habito_mas_reciente(self):
        pm_antiguo = self._crear_mes('October', 2025)
        self._crear_habito(
            pm_antiguo, nombre='Leer', tipo_habito='positivo',
            color='#111111', objetivo_dias=21,
        )

        pm_reciente = self._crear_mes('June', 2026)
        self._crear_habito(
            pm_reciente, nombre='Leer', tipo_habito='negativo',
            color='#222222', objetivo_dias=45,
        )

        self._ejecutar_migracion()

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Leer')
        self.assertEqual(gesto.tipo, 'suelto')
        self.assertEqual(gesto.color, '#222222')
        self.assertEqual(gesto.periodo_observacion_dias, 45)

    # 3. ProsocheHabitoDia completado=True produce RegistroGesto cumplido
    def test_dia_completado_produce_registro(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar')
        ProsocheHabitoDia.objects.create(habito=habito, dia=5, completado=True)

        self._ejecutar_migracion()

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Entrenar')
        registro = RegistroGesto.objects.get(gesto=gesto, fecha=date(2025, 10, 5))
        self.assertEqual(registro.estado, 'cumplido')

    # 4. ProsocheHabitoDia completado=False NO produce RegistroGesto
    def test_dia_no_completado_no_produce_registro(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar')
        ProsocheHabitoDia.objects.create(habito=habito, dia=6, completado=False)

        self._ejecutar_migracion()

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Entrenar')
        self.assertFalse(
            RegistroGesto.objects.filter(gesto=gesto, fecha=date(2025, 10, 6)).exists()
        )
        self.assertEqual(gesto.registros.count(), 0)

    # 5. Idempotencia: ejecutar dos veces no duplica
    def test_migracion_es_idempotente(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar')
        ProsocheHabitoDia.objects.create(habito=habito, dia=5, completado=True)
        ProsocheHabitoDia.objects.create(habito=habito, dia=6, completado=True)

        self._ejecutar_migracion()
        self._ejecutar_migracion()

        self.assertEqual(Gesto.objects.filter(usuario=self.usuario, nombre='Entrenar').count(), 1)
        self.assertEqual(
            RegistroGesto.objects.filter(gesto__usuario=self.usuario, gesto__nombre='Entrenar').count(),
            2,
        )

    # 6. ProsocheHabitoDia(dia=31) en mes de 30 días no aborta la migración
    def test_dia_invalido_no_aborta_migracion(self):
        pm = self._crear_mes('April', 2026)  # abril tiene 30 días
        habito = self._crear_habito(pm, nombre='Entrenar')
        ProsocheHabitoDia.objects.create(habito=habito, dia=15, completado=True)
        ProsocheHabitoDia.objects.create(habito=habito, dia=31, completado=True)

        self._ejecutar_migracion()

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Entrenar')
        self.assertTrue(
            RegistroGesto.objects.filter(gesto=gesto, fecha=date(2026, 4, 15)).exists()
        )
        self.assertFalse(gesto.registros.filter(fecha__day=31).exists())
        self.assertEqual(gesto.registros.count(), 1)

    # 9. mejor_racha histórica
    def test_mejor_racha_se_calcula_correctamente(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar')
        # racha de 14 días consecutivos en el pasado (días 1-14 de octubre 2025)
        for dia in range(1, 15):
            ProsocheHabitoDia.objects.create(habito=habito, dia=dia, completado=True)
        # racha actual = 0 (no hay registros recientes, día 20 no es consecutivo con día 14)
        ProsocheHabitoDia.objects.create(habito=habito, dia=20, completado=True)

        self._ejecutar_migracion()

        gesto = Gesto.objects.get(usuario=self.usuario, nombre='Entrenar')
        self.assertEqual(gesto.mejor_racha, 14)
        self.assertEqual(gesto.get_racha_actual(), 0)

    # 10. ProsocheHabito y ProsocheHabitoDia permanecen intactos
    def test_datos_legacy_no_se_modifican(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar', color='#abcdef')
        dia = ProsocheHabitoDia.objects.create(habito=habito, dia=5, completado=True)

        habito_count_antes = ProsocheHabito.objects.count()
        dia_count_antes = ProsocheHabitoDia.objects.count()

        self._ejecutar_migracion()

        self.assertEqual(ProsocheHabito.objects.count(), habito_count_antes)
        self.assertEqual(ProsocheHabitoDia.objects.count(), dia_count_antes)

        habito.refresh_from_db()
        dia.refresh_from_db()
        self.assertEqual(habito.color, '#abcdef')
        self.assertEqual(habito.nombre, 'Entrenar')
        self.assertEqual(dia.dia, 5)
        self.assertTrue(dia.completado)

    # Reverse migration borra lo creado
    def test_reverse_migracion_borra_gestos_y_registros(self):
        pm = self._crear_mes('October', 2025)
        habito = self._crear_habito(pm, nombre='Entrenar')
        ProsocheHabitoDia.objects.create(habito=habito, dia=5, completado=True)

        self._ejecutar_migracion()
        self.assertGreater(Gesto.objects.count(), 0)
        self.assertGreater(RegistroGesto.objects.count(), 0)

        reverse_migrar_datos(apps, schema_editor=None)

        self.assertEqual(Gesto.objects.count(), 0)
        self.assertEqual(RegistroGesto.objects.count(), 0)
        # los datos legacy no se tocan
        self.assertEqual(ProsocheHabito.objects.count(), 1)


class GestoModelTestCase(TestCase):
    """Tests del comportamiento de los modelos Gesto y RegistroGesto."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')

    def _crear_gesto(self, **kwargs):
        defaults = {'usuario': self.usuario, 'nombre': 'Entrenar'}
        defaults.update(kwargs)
        return Gesto.objects.create(**defaults)

    # 7. get_racha_actual cruza el límite de un mes calendario
    def test_racha_actual_cruza_limite_de_mes(self):
        gesto = self._crear_gesto()
        hoy = date(2026, 3, 1)
        ayer = date(2026, 2, 28)

        RegistroGesto.objects.create(gesto=gesto, fecha=ayer, estado='cumplido')
        RegistroGesto.objects.create(gesto=gesto, fecha=hoy, estado='cumplido')

        # ancla = hoy si hoy tiene registro
        import unittest.mock as mock
        with mock.patch('diario.models.timezone.localdate', return_value=hoy):
            self.assertEqual(gesto.get_racha_actual(), 2)

    # 8. RegistroGesto con fechas en meses sin ProsocheMes correspondiente funciona sin error
    def test_registro_gesto_sin_prosoche_mes_correspondiente(self):
        gesto = self._crear_gesto()
        # Fecha en un mes para el que no existe ningún ProsocheMes
        fecha_sin_mes = date(2024, 7, 15)
        registro = RegistroGesto.objects.create(
            gesto=gesto, fecha=fecha_sin_mes, estado='cumplido'
        )
        self.assertEqual(registro.fecha, fecha_sin_mes)
        self.assertEqual(gesto.registros.count(), 1)

    # 11. unique_together('usuario', 'nombre') en Gesto
    def test_unique_together_usuario_nombre(self):
        self._crear_gesto(nombre='Entrenar')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_gesto(nombre='Entrenar')

    # 12. unique_together('gesto', 'fecha') en RegistroGesto
    def test_unique_together_gesto_fecha(self):
        gesto = self._crear_gesto()
        fecha = date(2026, 6, 1)
        RegistroGesto.objects.create(gesto=gesto, fecha=fecha, estado='cumplido')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroGesto.objects.create(gesto=gesto, fecha=fecha, estado='fallado')
