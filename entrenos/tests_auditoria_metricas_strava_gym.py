import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.models import StravaActivityRaw
from rutinas.models import Rutina


class AuditoriaMetricasStravaGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("audit-metricas")
        self.cliente = Cliente.objects.get(user=user)
        self.fecha = date(2026, 8, 15)
        self.rutina = Rutina.objects.create(nombre="Auditoría métricas")

    def triple(self, *, gym_duration=52, hub_duration=52, strava_seconds=3167,
               rpe=8.0, carga=416.0, estado="merged", cliente=None):
        cliente = cliente or self.cliente
        gym = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=self.rutina, fecha=self.fecha,
            fecha_ejecucion=self.fecha, duracion_minutos=gym_duration,
        )
        hub = ActividadRealizada.objects.get(entreno_gym=gym)
        ActividadRealizada.objects.filter(pk=hub.pk).update(
            fecha_realizado=self.fecha, duracion_minutos=hub_duration,
            rpe_medio=rpe, carga_ua=carga,
        )
        hub.refresh_from_db()
        raw = StravaActivityRaw.objects.create(
            cliente=cliente, strava_id=900000 + gym.pk,
            fecha_actividad=self.fecha, tipo_strava="WeightTraining",
            duracion_segundos=strava_seconds, raw_json={}, estado=estado,
            entreno_gym=gym, actividad_hub=hub,
        )
        return raw, gym, hub

    def audit(self, **changes):
        from entrenos.services.auditoria_metricas_strava_gym_service import (
            auditar_metricas_strava_gym,
        )
        params = dict(
            cliente_id=self.cliente.pk, desde=self.fecha, hasta=self.fecha, limit=500,
        )
        params.update(changes)
        return auditar_metricas_strava_gym(**params)

    def test_match_tolerando_truncado_strava_es_comparable_y_solo_lectura(self):
        raw, gym, hub = self.triple()
        before = (
            raw.duracion_segundos, gym.duracion_minutos, hub.duracion_minutos,
            hub.rpe_medio, hub.carga_ua,
        )

        result = self.audit()

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"]["evaluated"], 1)
        self.assertEqual(result["summary"]["coverage"], {
            "comparable": 1, "classified_without_comparison": 0,
            "duration_truncations_tolerated": 1,
        })
        self.assertEqual(result["summary"]["total_candidates"], 1)
        self.assertEqual(result["summary"]["truncated"], 0)
        self.assertEqual(result["summary"]["duration_truncations_tolerated"], 1)
        self.assertTrue(result["summary"]["solo_lectura"])
        raw.refresh_from_db(); gym.refresh_from_db(); hub.refresh_from_db()
        self.assertEqual(before, (
            raw.duracion_segundos, gym.duracion_minutos, hub.duracion_minutos,
            hub.rpe_medio, hub.carga_ua,
        ))

    def test_divergencias_duracion_y_carga_se_clasifican_sin_volumen(self):
        _, _, hub = self.triple(hub_duration=51, strava_seconds=3300, carga=400.0)
        ActividadRealizada.objects.filter(pk=hub.pk).update(volumen_kg=99999)

        result = self.audit()

        by_code = {row["code"]: row for row in result["findings"]}
        self.assertEqual(set(by_code), {
            "gym_hub_duration_mismatch", "strava_gym_duration_mismatch",
            "hub_load_mismatch",
        })
        self.assertEqual(by_code["strava_gym_duration_mismatch"]["classification"], "provenance_unknown")
        self.assertEqual(by_code["hub_load_mismatch"]["expected"], 408.0)
        self.assertEqual(by_code["hub_load_mismatch"]["actual"], 400.0)
        self.assertNotIn("volumen", json.dumps(result))

    def test_clasifica_links_identidad_unicidad_y_fallbacks_de_carga(self):
        raw_missing, _, _ = self.triple()
        raw_missing.actividad_hub = None
        raw_missing.save(update_fields=["actividad_hub"])

        raw_cross, gym_cross, hub_cross = self.triple()
        other_user = User.objects.create_user("audit-cross")
        other = Cliente.objects.get(user=other_user)
        ActividadRealizada.objects.filter(pk=hub_cross.pk).update(cliente=other)

        raw_multi, gym_multi, hub_multi = self.triple()
        StravaActivityRaw.objects.create(
            cliente=self.cliente, strava_id=990001, fecha_actividad=self.fecha,
            tipo_strava="WeightTraining", duracion_segundos=3120, raw_json={},
            estado="merged", entreno_gym=gym_multi,
        )

        _, _, no_duration = self.triple(hub_duration=None, carga=20.0)
        _, _, no_rpe = self.triple(rpe=None, carga=20.0)

        result = self.audit()
        codes = [row["code"] for row in result["findings"]]

        self.assertIn("missing_actividad_hub_link", codes)
        self.assertIn("cross_client_identity", codes)
        self.assertIn("multiple_strava_raws_for_entreno", codes)
        self.assertIn("load_without_duration", codes)
        self.assertIn("load_without_rpe", codes)
        self.assertEqual(result["summary"]["evaluated"], 6)
        self.assertEqual(result["summary"]["coverage"]["comparable"], 0)
        self.assertEqual(result["summary"]["coverage"]["classified_without_comparison"], 6)

    def test_filtra_merged_cliente_rango_y_limit(self):
        self.triple()
        self.triple(estado="pending")
        self.triple()
        result = self.audit(limit=1)
        self.assertEqual(result["summary"]["evaluated"], 1)
        self.assertEqual(result["summary"]["total_candidates"], 2)
        self.assertEqual(result["summary"]["truncated"], 1)

    def test_ceros_son_valores_y_no_ausencias(self):
        self.triple(gym_duration=0, hub_duration=0, strava_seconds=0, rpe=0.0, carga=0.0)

        result = self.audit()

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"]["comparable"], 1)

    def test_comando_jsonl_y_validaciones_sin_apply(self):
        self.triple()
        out = StringIO()
        call_command(
            "auditar_metricas_strava_gym", cliente=self.cliente.pk,
            desde="2026-08-15", hasta="2026-08-15", limit=10, stdout=out,
        )
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(rows[-1]["tipo_registro"], "resumen")
        self.assertTrue(rows[-1]["solo_lectura"])
        with self.assertRaises(CommandError):
            call_command("auditar_metricas_strava_gym", cliente=self.cliente.pk, desde="bad")
        with self.assertRaises(CommandError):
            call_command(
                "auditar_metricas_strava_gym", cliente=self.cliente.pk,
                desde="2026-08-16", hasta="2026-08-15",
            )
        with self.assertRaises(CommandError):
            call_command("auditar_metricas_strava_gym", cliente=self.cliente.pk, limit=501)
        with self.assertRaises(CommandError):
            call_command("auditar_metricas_strava_gym", cliente=999999)
        with self.assertRaises(CommandError):
            call_command(
                "auditar_metricas_strava_gym", cliente=self.cliente.pk,
                desde="2025-08-14", hasta="2026-08-15",
            )
        with self.assertRaises(TypeError):
            call_command("auditar_metricas_strava_gym", cliente=self.cliente.pk, apply=True)
