import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ActividadRealizada,
    EjercicioRealizado,
    EntrenoRealizado,
    GymDecisionLog,
    RecordPersonal,
    SerieRealizada,
    SesionProgramada,
)
from hyrox.models import StravaActivityRaw
from logros.models import HistorialPuntos, PerfilGamificacion
from rutinas.models import EjercicioBase, Rutina


class RepararEntrenoDuplicadoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("duplicado")
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre="Día 2")
        self.base = EjercicioBase.objects.create(nombre="Remo")
        self.duplicado = self._entreno()
        self.canonico = self._entreno()
        self.perfil, _ = PerfilGamificacion.objects.get_or_create(cliente=self.cliente)
        HistorialPuntos.objects.filter(entreno__in=(self.duplicado, self.canonico)).delete()
        self.perfil.puntos_totales = 200
        self.perfil.entrenos_totales = 10
        self.perfil.save()
        HistorialPuntos.objects.create(
            perfil=self.perfil, entreno=self.duplicado, puntos=54,
            descripcion="Entrenamiento completado",
        )
        HistorialPuntos.objects.create(
            perfil=self.perfil, entreno=self.canonico, puntos=54,
            descripcion="Entrenamiento completado",
        )
        self.record = RecordPersonal.objects.create(
            cliente=self.cliente, ejercicio_nombre="Remo", tipo_record="peso_maximo",
            valor=100, entreno=self.duplicado,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _entreno(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina,
            fecha=date(2026, 8, 10), fecha_ejecucion=date(2026, 8, 10),
            volumen_total_kg=1200,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio="Remo", peso_kg=100,
            series=3, repeticiones=4, orden=1,
        )
        SerieRealizada.objects.create(
            entreno=entreno, ejercicio=self.base, serie_numero=1,
            repeticiones=4, peso_kg=100, completado=True,
        )
        return entreno

    def _run(self, *args):
        stdout = StringIO()
        call_command("reparar_entreno_duplicado", *args, stdout=stdout)
        return json.loads(stdout.getvalue().strip())

    def test_dry_run_por_defecto_no_modifica_y_devuelve_json(self):
        resultado = self._run(str(self.duplicado.pk), str(self.canonico.pk))
        self.assertTrue(resultado["dry_run"])
        self.assertEqual(resultado["duplicado_id"], self.duplicado.pk)
        self.assertEqual(resultado["canonico_id"], self.canonico.pk)
        self.assertTrue(EntrenoRealizado.objects.filter(pk=self.duplicado.pk).exists())
        self.perfil.refresh_from_db()
        self.assertEqual((self.perfil.puntos_totales, self.perfil.entrenos_totales), (200, 10))

    def test_apply_crea_backup_reasigna_records_y_elimina_derivados(self):
        actividad = ActividadRealizada.objects.get(entreno_gym=self.duplicado)
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, entreno_origen=self.duplicado, ejercicio="Remo",
            accion="mantener", motivo="test",
        )
        backup = Path(self.tmp.name) / "backup.json"

        resultado = self._run(
            str(self.duplicado.pk), str(self.canonico.pk), "--apply", "--backup", str(backup),
        )

        self.assertFalse(resultado["dry_run"])
        self.assertFalse(EntrenoRealizado.objects.filter(pk=self.duplicado.pk).exists())
        self.assertFalse(ActividadRealizada.objects.filter(pk=actividad.pk).exists())
        self.assertFalse(GymDecisionLog.objects.filter(pk=decision.pk).exists())
        self.assertFalse(HistorialPuntos.objects.filter(entreno_id=self.duplicado.pk).exists())
        self.record.refresh_from_db()
        self.assertEqual(self.record.entreno_id, self.canonico.pk)
        self.assertTrue(backup.exists())
        evidencia = json.loads(backup.read_text())
        self.assertEqual(evidencia["entreno_duplicado"]["id"], self.duplicado.pk)
        self.assertEqual(evidencia["records"][0]["id"], self.record.pk)
        self.perfil.refresh_from_db()
        self.assertEqual((self.perfil.puntos_totales, self.perfil.entrenos_totales), (146, 9))
        self.assertTrue(HistorialPuntos.objects.filter(entreno=self.canonico, puntos=54).exists())

    def test_bloquea_si_los_entrenos_no_son_identicos(self):
        EjercicioRealizado.objects.filter(entreno=self.canonico).update(repeticiones=5)
        backup = Path(self.tmp.name) / "backup.json"
        with self.assertRaisesMessage(CommandError, "ejercicios"):
            self._run(
                str(self.duplicado.pk), str(self.canonico.pk), "--apply", "--backup", str(backup),
            )
        self.assertFalse(backup.exists())
        self.assertTrue(EntrenoRealizado.objects.filter(pk=self.duplicado.pk).exists())

    def test_bloquea_sesion_programada_o_strava_vinculados(self):
        SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 8, 10),
            entreno_realizado=self.duplicado,
        )
        with self.assertRaisesMessage(CommandError, "SesionProgramada"):
            self._run(str(self.duplicado.pk), str(self.canonico.pk))
        SesionProgramada.objects.all().delete()
        StravaActivityRaw.objects.create(
            cliente=self.cliente, strava_id=999, fecha_actividad=date(2026, 8, 10),
            raw_json={}, entreno_gym=self.duplicado,
        )
        with self.assertRaisesMessage(CommandError, "Strava"):
            self._run(str(self.duplicado.pk), str(self.canonico.pk))

    def test_bloquea_record_equivalente_en_canonico(self):
        RecordPersonal.objects.create(
            cliente=self.cliente, ejercicio_nombre="Remo", tipo_record="peso_maximo",
            valor=100, entreno=self.canonico,
        )
        with self.assertRaisesMessage(CommandError, "records"):
            self._run(str(self.duplicado.pk), str(self.canonico.pk))
