import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.models import HyroxObjective, HyroxSession, StravaActivityRaw
from rutinas.models import Rutina


class ClasificarIdentidadStravaGymTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(user=User.objects.create_user("identity-owner"))
        self.otro = Cliente.objects.get(user=User.objects.create_user("identity-other"))
        self.fecha = date(2026, 8, 15)
        self.rutina = Rutina.objects.create(nombre="Identidad Strava Gym")
        self.sequence = 810000

    def gym(self, cliente=None):
        return EntrenoRealizado.objects.create(
            cliente=cliente or self.cliente, rutina=self.rutina,
            fecha=self.fecha, fecha_ejecucion=self.fecha,
        )

    def raw(self, *, gym=None, hub=None, cliente=None, estado="merged",
            tipo="WeightTraining", hyrox_session=None):
        self.sequence += 1
        return StravaActivityRaw.objects.create(
            cliente=cliente or self.cliente, strava_id=self.sequence,
            fecha_actividad=self.fecha, tipo_strava=tipo,
            duracion_segundos=3600, raw_json={}, estado=estado,
            entreno_gym=gym, actividad_hub=hub, hyrox_session=hyrox_session,
        )

    def classify(self, **changes):
        from entrenos.services.clasificar_identidad_strava_gym_service import (
            clasificar_identidad_strava_gym,
        )
        params = dict(cliente_id=self.cliente.pk, desde=self.fecha, hasta=self.fecha, limit=500)
        params.update(changes)
        return clasificar_identidad_strava_gym(**params)

    def test_particion_exhaustiva_disjunta_y_datos_de_identidad(self):
        complete_gym = self.gym()
        complete_hub = complete_gym.hub_actividad
        complete = self.raw(gym=complete_gym, hub=complete_hub)

        recoverable_gym = self.gym()
        ActividadRealizada.objects.filter(pk=recoverable_gym.hub_actividad.pk).update(
            fecha_realizado=self.fecha,
        )
        recoverable = self.raw(gym=recoverable_gym)

        no_hub_gym = self.gym()
        no_hub_gym.hub_actividad.delete()
        no_hub = self.raw(gym=no_hub_gym)

        multi_gym = self.gym()
        multi_a = self.raw(gym=multi_gym)
        multi_b = self.raw(gym=multi_gym)

        non_gym = self.raw(tipo="Run")

        conflict_gym = self.gym()
        conflict_hub = conflict_gym.hub_actividad
        ActividadRealizada.objects.filter(pk=conflict_hub.pk).update(cliente=self.otro)
        conflict = self.raw(gym=conflict_gym, hub=conflict_hub)

        result = self.classify()
        rows = result["classifications"]
        by_id = {row["strava_raw_id"]: row for row in rows}
        self.assertEqual(len(rows), 7)
        self.assertEqual(by_id[complete.pk]["category"], "gym_complete")
        self.assertEqual(by_id[recoverable.pk]["category"], "gym_missing_hub_recoverable")
        self.assertEqual(by_id[no_hub.pk]["category"], "gym_missing_hub_no_canonical_hub")
        self.assertEqual(by_id[multi_a.pk]["category"], "gym_missing_hub_multiple_raw")
        self.assertEqual(by_id[multi_b.pk]["category"], "gym_missing_hub_multiple_raw")
        self.assertEqual(by_id[non_gym.pk]["category"], "non_gym_out_of_scope")
        self.assertEqual(by_id[non_gym.pk]["non_gym_classification"], "merged:carrera")
        self.assertEqual(by_id[conflict.pk]["category"], "identity_conflict")
        self.assertEqual(by_id[recoverable.pk]["reverse_actividad_hub_id"], recoverable_gym.hub_actividad.pk)
        self.assertEqual(by_id[multi_a.pk]["gym_raw_count"], 2)
        self.assertEqual(by_id[complete.pk]["actividad_hub_id"], complete_hub.pk)
        self.assertEqual(by_id[complete.pk]["entreno_gym_id"], complete_gym.pk)
        self.assertEqual(by_id[complete.pk]["tipo_strava"], "WeightTraining")
        summary = result["summary"]
        self.assertEqual(sum(summary["counts_by_category"].values()), summary["evaluated"])
        self.assertEqual(summary["partition_count"], summary["evaluated"])
        self.assertTrue(summary["partition_complete"])
        self.assertTrue(summary["solo_lectura"])

    def test_conflicto_tiene_prioridad_sobre_no_gym_y_missing(self):
        foreign_gym = self.gym(cliente=self.otro)
        raw = self.raw(gym=foreign_gym, tipo="Run")
        result = self.classify()
        self.assertEqual(result["classifications"][0]["category"], "identity_conflict")
        self.assertIn("raw_gym_cross_client", result["classifications"][0]["conflicts"])

    def test_hyrox_fuera_de_alcance_se_subclasifica(self):
        objective = HyroxObjective.objects.create(cliente=self.cliente, fecha_evento=self.fecha)
        session = HyroxSession.objects.create(objective=objective, fecha=self.fecha)
        raw = self.raw(hyrox_session=session, estado="merged", tipo="Run")
        row = self.classify()["classifications"][0]
        self.assertEqual(row["category"], "non_gym_out_of_scope")
        self.assertEqual(row["non_gym_classification"], "hyrox_session:merged:carrera")
        self.assertEqual(row["hyrox_session_id"], session.pk)

    def test_limit_no_altera_total_ni_multiplicidad_global(self):
        gym = self.gym()
        first = self.raw(gym=gym)
        self.raw(gym=gym)
        self.raw()
        result = self.classify(limit=1)
        self.assertEqual(result["summary"]["total"], 3)
        self.assertEqual(result["summary"]["evaluated"], 1)
        self.assertEqual(result["summary"]["truncated"], 2)
        self.assertEqual(result["classifications"][0]["strava_raw_id"], first.pk)
        self.assertEqual(result["classifications"][0]["gym_raw_count"], 2)
        self.assertEqual(result["classifications"][0]["category"], "gym_missing_hub_multiple_raw")

    def test_missing_hub_con_fechas_gym_hub_divergentes_no_es_recuperable(self):
        gym = self.gym()
        hub = gym.hub_actividad
        ActividadRealizada.objects.filter(pk=hub.pk).update(
            fecha_realizado=self.fecha + timedelta(days=1),
        )
        raw = self.raw(gym=gym)

        row = self.classify()["classifications"][0]

        self.assertEqual(row["strava_raw_id"], raw.pk)
        self.assertEqual(row["category"], "gym_missing_hub_date_conflict")
        self.assertEqual(row["fecha_gym_planificada"], self.fecha.isoformat())
        self.assertEqual(row["fecha_gym_efectiva"], self.fecha.isoformat())
        self.assertEqual(row["fecha_hub_planificada"], self.fecha.isoformat())
        self.assertEqual(row["fecha_hub_efectiva"], (self.fecha + timedelta(days=1)).isoformat())
        self.assertEqual(row["delta_dias_strava_gym"], 0)

    def test_missing_hub_con_strava_a_mas_de_un_dia_no_es_recuperable(self):
        gym = self.gym()
        raw = self.raw(gym=gym)
        StravaActivityRaw.objects.filter(pk=raw.pk).update(
            fecha_actividad=self.fecha + timedelta(days=2),
        )

        row = self.classify(
            desde=self.fecha, hasta=self.fecha + timedelta(days=2),
        )["classifications"][0]

        self.assertEqual(row["category"], "gym_missing_hub_date_conflict")
        self.assertEqual(row["delta_dias_strava_gym"], 2)

    def test_multiplicidad_precede_conflicto_de_fecha(self):
        gym = self.gym()
        ActividadRealizada.objects.filter(pk=gym.hub_actividad.pk).update(
            fecha_realizado=self.fecha + timedelta(days=3),
        )
        self.raw(gym=gym)
        self.raw(gym=gym)

        rows = self.classify()["classifications"]

        self.assertEqual(
            {row["category"] for row in rows},
            {"gym_missing_hub_multiple_raw"},
        )

    def test_solo_lectura_y_por_defecto_solo_clasifica_merged(self):
        gym = self.gym()
        pending = self.raw(gym=gym, estado="pending")
        raw = self.raw(gym=gym)
        before = (raw.entreno_gym_id, raw.actividad_hub_id, raw.estado)
        result = self.classify()
        raw.refresh_from_db()
        self.assertEqual((raw.entreno_gym_id, raw.actividad_hub_id, raw.estado), before)
        self.assertEqual(result["summary"]["state"], "merged")
        self.assertEqual(result["summary"]["total"], 1)
        self.assertNotIn(pending.pk, [row["strava_raw_id"] for row in result["classifications"]])

    def test_comando_jsonl_validaciones_y_sin_apply(self):
        self.raw()
        out = StringIO()
        call_command("clasificar_identidad_strava_gym", cliente=self.cliente.pk,
                     desde="2026-08-15", hasta="2026-08-15", limit=10, stdout=out)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(rows[-1]["tipo_registro"], "resumen")
        self.assertTrue(rows[-1]["solo_lectura"])
        with self.assertRaises(CommandError):
            call_command("clasificar_identidad_strava_gym", cliente=999999)
        with self.assertRaises(CommandError):
            call_command("clasificar_identidad_strava_gym", cliente=self.cliente.pk, desde="bad")
        with self.assertRaises(CommandError):
            call_command("clasificar_identidad_strava_gym", cliente=self.cliente.pk,
                         desde="2026-08-16", hasta="2026-08-15")
        with self.assertRaises(CommandError):
            call_command("clasificar_identidad_strava_gym", cliente=self.cliente.pk, limit=501)
        with self.assertRaises(TypeError):
            call_command("clasificar_identidad_strava_gym", cliente=self.cliente.pk, apply=True)
