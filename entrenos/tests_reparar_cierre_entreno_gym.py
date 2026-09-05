import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SerieRealizada, SesionEntrenamiento
from rutinas.models import EjercicioBase, Rutina


class RepararCierreEntrenoGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("reparar-cierre")
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre="Fuerza")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=rutina, fecha=date(2026, 9, 5),
            duracion_minutos=2, volumen_total_kg=5610,
        )
        self.sesion = SesionEntrenamiento.objects.create(
            entreno=self.entreno, duracion_minutos=2, volumen_sesion=5610,
        )
        self.press = EjercicioBase.objects.create(nombre="Press Banca con Mancuernas", grupo_muscular="Pecho")
        self.fondos = EjercicioBase.objects.create(nombre="Fondos Entre Bancos", grupo_muscular="Triceps")
        for ejercicio, total in ((self.press, 6), (self.fondos, 4)):
            for numero in range(1, total + 1):
                SerieRealizada.objects.create(
                    entreno=self.entreno, ejercicio=ejercicio, serie_numero=numero,
                    repeticiones=8, peso_kg=20, completado=True,
                )

    def _run(self, *extra):
        salida = StringIO()
        call_command(
            "reparar_cierre_entreno_gym", self.entreno.pk,
            "--duracion-minutos", "40",
            "--tecnica-buena", "Press Banca con Mancuernas:1-6",
            "--tecnica-buena", "Fondos Entre Bancos:2",
            *extra, stdout=salida,
        )
        return json.loads(salida.getvalue())

    def test_dry_run_no_modifica(self):
        resultado = self._run()
        self.entreno.refresh_from_db()
        self.assertEqual(resultado["modo"], "dry-run")
        self.assertEqual(self.entreno.duracion_minutos, 2)
        self.assertEqual(SerieRealizada.objects.filter(tecnica_calidad="buena").count(), 0)

    def test_apply_es_idempotente_y_backup_es_reversible(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = str(Path(tmp) / "entreno.json")
            resultado = self._run("--apply", "--backup-file", backup)
            self.entreno.refresh_from_db(); self.sesion.refresh_from_db()
            self.assertEqual((self.entreno.duracion_minutos, self.sesion.duracion_minutos), (40, 40))
            self.assertEqual(SerieRealizada.objects.filter(tecnica_calidad="buena").count(), 7)
            self.assertEqual(resultado["series_actualizadas"], 7)
            self.assertEqual(self._run("--apply", "--backup-file", backup)["series_actualizadas"], 0)

            salida = StringIO()
            call_command("reparar_cierre_entreno_gym", self.entreno.pk, "--restore-backup", backup, stdout=salida)
            self.entreno.refresh_from_db(); self.sesion.refresh_from_db()
            self.assertEqual((self.entreno.duracion_minutos, self.sesion.duracion_minutos), (2, 2))
            self.assertEqual(SerieRealizada.objects.filter(tecnica_calidad="buena").count(), 0)

    def test_rechaza_serie_inexistente_sin_cambios(self):
        with self.assertRaises(CommandError):
            call_command(
                "reparar_cierre_entreno_gym", self.entreno.pk,
                "--duracion-minutos", "40", "--tecnica-buena", "Fondos Entre Bancos:9",
                "--apply", stdout=StringIO(),
            )
        self.entreno.refresh_from_db()
        self.assertEqual(self.entreno.duracion_minutos, 2)
