import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from hyrox.models import StravaActivityRaw


class VincularStravaHubLegacyTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="link_strava_legacy", password="x")
        self.cliente = Cliente.objects.get(user=user)
        self.fecha = date(2026, 5, 23)

    def activity(self, *, title, minutes):
        return ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="otro",
            titulo=title,
            fecha=self.fecha,
            duracion_minutos=minutes,
            fuente="strava",
        )

    def raw(self, *, strava_id, title, minutes, estado="created"):
        return StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=strava_id,
            fecha_actividad=self.fecha,
            tipo_strava="Walk",
            nombre_strava=title,
            duracion_segundos=round(minutes * 60),
            raw_json={},
            estado=estado,
        )

    def execute(self, apply=False):
        from entrenos.services.vincular_strava_hub_legacy_service import (
            vincular_strava_hub_legacy,
        )

        return vincular_strava_hub_legacy(
            cliente_id=self.cliente.pk,
            desde=date(2026, 5, 1),
            hasta=date(2026, 5, 31),
            apply=apply,
        )

    def test_dry_run_empareja_por_fecha_titulo_y_duracion_sin_mutar(self):
        short = self.activity(title="Caminata de tarde", minutes=26)
        long = self.activity(title="Caminata de tarde", minutes=41)
        raw_short = self.raw(strava_id=1, title="  CAMINATA   DE TARDE ", minutes=26.5)
        raw_long = self.raw(strava_id=2, title="Caminata de tarde", minutes=41.4)

        result = self.execute()

        pairs = {(row["strava_raw_id"], row["actividad_hub_id"]) for row in result["candidates"]}
        self.assertEqual(pairs, {(raw_short.pk, short.pk), (raw_long.pk, long.pk)})
        self.assertTrue(result["summary"]["solo_lectura"])
        self.assertEqual(result["summary"]["candidatos"], 2)
        self.assertEqual(result["summary"]["aplicados"], 0)
        self.assertFalse(StravaActivityRaw.objects.filter(actividad_hub__isnull=False).exists())

    def test_apply_vincula_y_repetir_es_idempotente(self):
        activity = self.activity(title="Fútbol al anochecer", minutes=60)
        raw = self.raw(strava_id=3, title="Fútbol al anochecer", minutes=60.2)

        first = self.execute(apply=True)
        second = self.execute(apply=True)

        raw.refresh_from_db()
        self.assertEqual(raw.actividad_hub_id, activity.pk)
        self.assertEqual(first["summary"]["aplicados"], 1)
        self.assertEqual(second["summary"]["candidatos"], 0)
        self.assertEqual(second["summary"]["aplicados"], 0)

    def test_no_vincula_fuente_no_strava_ni_merged_ambiguo(self):
        self.activity(title="Fuerza", minutes=38)
        manual = ActividadRealizada.objects.create(
            cliente=self.cliente, tipo="gym", titulo="Fuerza", fecha=self.fecha,
            duracion_minutos=38, fuente="manual",
        )
        raw = self.raw(strava_id=4, title="Fuerza", minutes=38.3, estado="merged")

        result = self.execute(apply=True)

        raw.refresh_from_db()
        self.assertIsNone(raw.actividad_hub_id)
        self.assertEqual(result["summary"]["candidatos"], 0)
        self.assertEqual(result["summary"]["ambiguos"], 1)
        self.assertTrue(ActividadRealizada.objects.filter(pk=manual.pk).exists())

    def test_comando_jsonl_apply_explicito(self):
        activity = self.activity(title="Caminata", minutes=30)
        raw = self.raw(strava_id=5, title="Caminata", minutes=30.4)
        output = StringIO()

        call_command(
            "vincular_strava_hub_legacy",
            cliente=self.cliente.pk,
            desde="2026-05-01",
            hasta="2026-05-31",
            apply=True,
            stdout=output,
        )

        records = [json.loads(line) for line in output.getvalue().splitlines()]
        raw.refresh_from_db()
        self.assertEqual(raw.actividad_hub_id, activity.pk)
        self.assertEqual(records[-1]["modo"], "apply")
        self.assertEqual(records[-1]["aplicados"], 1)

