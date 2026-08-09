import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.models import StravaActivityRaw
from rutinas.models import Rutina


class RepararCargaStravaGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reparar_carga")
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre="Rutina reparación")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _actividad(self, *, carga=48.0, fuente="manual", tipo="gym", rpe=8.0,
                   duracion=60, raw_estado="merged", con_raw=True,
                   sesion_hyrox_id=None):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 9),
            fuente_datos="liftin" if fuente == "liftin" else "manual",
        )
        actividad = ActividadRealizada.objects.get(entreno_gym=entreno)
        ActividadRealizada.objects.filter(pk=actividad.pk).update(
            fuente=fuente,
            tipo=tipo,
            rpe_medio=rpe,
            duracion_minutos=duracion,
            carga_ua=carga,
            sesion_hyrox_id=sesion_hyrox_id,
        )
        actividad.refresh_from_db()
        if con_raw:
            StravaActivityRaw.objects.create(
                cliente=self.cliente,
                strava_id=10_000 + entreno.pk,
                fecha_actividad=entreno.fecha,
                tipo_strava="WeightTraining",
                duracion_segundos=(duracion or 0) * 60,
                raw_json={},
                estado=raw_estado,
                entreno_gym=entreno,
            )
        return actividad

    def _run(self, *args):
        stdout = StringIO()
        call_command("reparar_carga_strava_gym", *args, stdout=stdout)
        return [
            json.loads(line)
            for line in stdout.getvalue().splitlines()
            if line.startswith("{")
        ]

    def test_auditoria_selecciona_solo_fusiones_gym_demostrables_fuera_tolerancia(self):
        candidato = self._actividad()
        candidato_none = self._actividad(carga=None, fuente="liftin")
        coherente = self._actividad(carga=470.0)
        sin_raw = self._actividad(con_raw=False)
        raw_pending = self._actividad(raw_estado="pending")
        fuente_strava = self._actividad(fuente="strava")
        fuente_hyrox = self._actividad(fuente="hyrox_engine")
        sin_rpe = self._actividad(rpe=None)
        otro_tipo = self._actividad(tipo="futbol")

        registros = self._run("--cliente", str(self.cliente.pk))

        candidatos = [r for r in registros if r["tipo_registro"] == "candidato"]
        self.assertEqual({r["id"] for r in candidatos}, {candidato.pk, candidato_none.pk})
        self.assertTrue(registros[-1]["solo_lectura"])
        self.assertEqual(registros[-1]["candidatos"], 2)
        for actividad in (candidato, candidato_none, coherente, sin_raw, raw_pending,
                          fuente_strava, fuente_hyrox, sin_rpe, otro_tipo):
            actividad.refresh_from_db()
        self.assertEqual(candidato.carga_ua, 48.0)
        self.assertIsNone(candidato_none.carga_ua)

    def test_apply_exige_cliente_y_backup_nuevo_y_guarda_evidencia(self):
        actividad = self._actividad()
        backup = Path(self.tmp.name) / "carga.json"

        with self.assertRaises(CommandError):
            self._run("--apply", "--cliente", str(self.cliente.pk))
        with self.assertRaises(CommandError):
            self._run("--apply", "--backup-file", str(backup))

        registros = self._run(
            "--apply", "--cliente", str(self.cliente.pk),
            "--backup-file", str(backup),
        )

        actividad.refresh_from_db()
        self.assertEqual(actividad.carga_ua, 480.0)
        documento = json.loads(backup.read_text())
        self.assertEqual(documento["formato"], "reparar_carga_strava_gym")
        self.assertEqual(documento["version"], 1)
        self.assertEqual(documento["cliente_id"], self.cliente.pk)
        self.assertEqual(documento["cambios"][0]["id"], actividad.pk)
        self.assertEqual(documento["cambios"][0]["before"], 48.0)
        self.assertEqual(documento["cambios"][0]["after"], 480.0)
        self.assertEqual(documento["cambios"][0]["evidencia"]["strava_estado"], "merged")
        self.assertEqual(registros[-1]["aplicados"], 1)

        with self.assertRaises(CommandError):
            self._run(
                "--apply", "--cliente", str(self.cliente.pk),
                "--backup-file", str(backup),
            )

    def test_rollback_restaura_solo_si_el_actual_coincide_con_after(self):
        restaurable = self._actividad(carga=48.0)
        conflicto = self._actividad(carga=61.0)
        backup = Path(self.tmp.name) / "carga.json"
        self._run(
            "--apply", "--cliente", str(self.cliente.pk),
            "--backup-file", str(backup),
        )
        ActividadRealizada.objects.filter(pk=conflicto.pk).update(carga_ua=777.0)

        registros = self._run("--rollback-file", str(backup))

        restaurable.refresh_from_db()
        conflicto.refresh_from_db()
        self.assertEqual(restaurable.carga_ua, 48.0)
        self.assertEqual(conflicto.carga_ua, 777.0)
        resumen = registros[-1]
        self.assertEqual(resumen["restaurados"], 1)
        self.assertEqual(resumen["conflictos"], 1)
        conflicto_linea = next(r for r in registros if r["tipo_registro"] == "conflicto")
        self.assertEqual(conflicto_linea["id"], conflicto.pk)
