import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.models import StravaActivityRaw
from rutinas.models import Rutina


class ReconciliarFechasStravaGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="fecha_strava_gym", password="x")
        self.cliente = Cliente.objects.get(user=user)
        self.plan_date = date(2026, 8, 11)
        self.wrong_date = date(2026, 8, 10)
        self.real_date = date(2026, 8, 11)
        routine = Rutina.objects.create(nombre="Torso")
        self.workout = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=routine,
            fecha=self.plan_date,
            fecha_ejecucion=self.wrong_date,
            duracion_minutos=52,
        )
        self.activity = ActividadRealizada.objects.get(entreno_gym=self.workout)
        ActividadRealizada.objects.filter(pk=self.activity.pk).update(
            fecha=self.plan_date,
            fecha_realizado=self.wrong_date,
            duracion_minutos=52,
        )
        self.raw = StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=300001,
            fecha_actividad=self.real_date,
            tipo_strava="WeightTraining",
            nombre_strava="Torso",
            duracion_segundos=52 * 60,
            raw_json={},
            estado="merged",
            entreno_gym=self.workout,
            actividad_hub=self.activity,
        )

    def execute(self, apply=False):
        from entrenos.services.reconciliar_fechas_strava_gym_service import (
            reconciliar_fechas_strava_gym,
        )

        return reconciliar_fechas_strava_gym(
            cliente_id=self.cliente.pk,
            desde=date(2026, 8, 1),
            hasta=date(2026, 8, 31),
            apply=apply,
        )

    def test_dry_run_detecta_diferencia_y_no_muta(self):
        result = self.execute()

        candidate = result["candidates"][0]
        self.assertEqual(candidate["entreno_gym_id"], self.workout.pk)
        self.assertEqual(candidate["actividad_hub_id"], self.activity.pk)
        self.assertEqual(candidate["fecha_actual"], "2026-08-10")
        self.assertEqual(candidate["fecha_strava"], "2026-08-11")
        self.assertEqual(candidate["dias_diferencia"], 1)
        self.workout.refresh_from_db()
        self.activity.refresh_from_db()
        self.assertEqual(self.workout.fecha_ejecucion, self.wrong_date)
        self.assertEqual(self.activity.fecha_realizado, self.wrong_date)
        self.assertTrue(result["summary"]["solo_lectura"])

    def test_apply_corrige_fecha_efectiva_preserva_plan_e_idempotente(self):
        first = self.execute(apply=True)
        second = self.execute(apply=True)

        self.workout.refresh_from_db()
        self.activity.refresh_from_db()
        self.assertEqual(self.workout.fecha, self.plan_date)
        self.assertEqual(self.activity.fecha, self.plan_date)
        self.assertEqual(self.workout.fecha_ejecucion, self.real_date)
        self.assertEqual(self.activity.fecha_realizado, self.real_date)
        self.assertEqual(first["summary"]["aplicados"], 1)
        self.assertEqual(second["summary"]["candidatos"], 0)

    def test_no_corrige_saltos_mayores_de_un_dia(self):
        self.raw.fecha_actividad = self.real_date + timedelta(days=2)
        self.raw.save(update_fields=["fecha_actividad"])

        result = self.execute(apply=True)

        self.assertEqual(result["summary"]["candidatos"], 0)
        self.assertEqual(result["summary"]["ambiguos"], 1)
        self.workout.refresh_from_db()
        self.assertEqual(self.workout.fecha_ejecucion, self.wrong_date)

    def test_legacy_deriva_hub_desde_entreno_y_lo_persiste_al_aplicar(self):
        self.raw.actividad_hub = None
        self.raw.save(update_fields=["actividad_hub"])

        dry_run = self.execute()

        self.assertEqual(dry_run["summary"]["evaluados"], 1)
        self.assertEqual(dry_run["candidates"][0]["actividad_hub_id"], self.activity.pk)
        self.raw.refresh_from_db()
        self.assertIsNone(self.raw.actividad_hub_id)

        applied = self.execute(apply=True)

        self.raw.refresh_from_db()
        self.assertEqual(self.raw.actividad_hub_id, self.activity.pk)
        self.assertEqual(applied["summary"]["aplicados"], 1)

    def test_varios_strava_mismo_entreno_prioriza_el_que_coincide_con_fecha_actual(self):
        self.raw.actividad_hub = None
        self.raw.save(update_fields=["actividad_hub"])
        matching = StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=300002,
            fecha_actividad=self.wrong_date,
            tipo_strava="WeightTraining",
            nombre_strava="Torso duplicado",
            duracion_segundos=52 * 60,
            raw_json={},
            estado="merged",
            entreno_gym=self.workout,
        )

        result = self.execute()

        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["strava_raw_id"], matching.pk)
        discarded = next(
            row for row in result["ambiguous"]
            if row["code"] == "varios_strava_mismo_entreno"
        )
        self.assertEqual(discarded["strava_raw_id"], self.raw.pk)

        applied = self.execute(apply=True)

        self.workout.refresh_from_db()
        matching.refresh_from_db()
        self.raw.refresh_from_db()
        self.assertEqual(self.workout.fecha_ejecucion, self.wrong_date)
        self.assertEqual(matching.actividad_hub_id, self.activity.pk)
        self.assertIsNone(self.raw.actividad_hub_id)
        self.assertEqual(applied["summary"]["aplicados"], 1)

    def test_comando_jsonl(self):
        output = StringIO()
        call_command(
            "reconciliar_fechas_strava_gym",
            cliente=self.cliente.pk,
            desde="2026-08-01",
            hasta="2026-08-31",
            stdout=output,
        )

        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(records[0]["tipo_registro"], "candidato")
        self.assertEqual(records[-1]["modo"], "dry-run")
