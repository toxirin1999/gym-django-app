import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from hyrox.models import StravaActivityRaw


class AuditarEventosFisicosTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="audit_eventos", password="x")
        self.cliente = Cliente.objects.get(user=user)
        self.desde = date(2026, 8, 1)
        self.hasta = date(2026, 8, 16)

    def actividad(self, **changes):
        attrs = {
            "cliente": self.cliente,
            "tipo": "gym",
            "titulo": "Fuerza",
            "fecha": date(2026, 8, 10),
            "duracion_minutos": 60,
            "rpe_medio": 8,
            "carga_ua": 480,
            "fuente": "manual",
        }
        attrs.update(changes)
        return ActividadRealizada.objects.create(**attrs)

    def auditar(self):
        from entrenos.services.auditoria_eventos_fisicos_service import (
            auditar_eventos_fisicos,
        )

        return auditar_eventos_fisicos(
            cliente_id=self.cliente.pk,
            desde=self.desde,
            hasta=self.hasta,
        )

    def test_actividad_unica_no_genera_hallazgo_y_es_solo_lectura(self):
        self.actividad()
        before = list(ActividadRealizada.objects.values())

        result = self.auditar()

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"]["eventos_evaluados"], 1)
        self.assertEqual(result["summary"]["grupos_candidatos"], 0)
        self.assertTrue(result["summary"]["solo_lectura"])
        self.assertEqual(before, list(ActividadRealizada.objects.values()))

    def test_agrupa_por_fecha_efectiva_y_tipo_sin_afirmar_duplicado(self):
        first = self.actividad(
            titulo="Registro app",
            fecha=date(2026, 8, 9),
            fecha_realizado=date(2026, 8, 10),
        )
        second = self.actividad(
            titulo="Strava Weight Training",
            fuente="strava",
            duracion_minutos=62,
            carga_ua=496,
        )

        finding = self.auditar()["findings"][0]

        self.assertEqual(finding["code"], "duplicado_probable")
        self.assertEqual(finding["confidence"], "alta")
        self.assertEqual(finding["fecha_efectiva"], "2026-08-10")
        self.assertEqual(finding["tipo"], "gym")
        self.assertEqual(finding["event_ids"], [first.pk, second.pk])
        self.assertEqual(finding["fuentes"], ["manual", "strava"])
        self.assertEqual(finding["carga_ua_sumada"], 976.0)
        self.assertFalse(finding["aplicar_automaticamente"])

    def test_dos_modalidades_el_mismo_dia_son_eventos_independientes(self):
        self.actividad(tipo="gym")
        self.actividad(tipo="futbol", titulo="Partido", fuente="strava")

        self.assertEqual(self.auditar()["findings"], [])

    def test_strava_created_legacy_sin_vinculo_no_se_presenta_como_duplicado(self):
        raw = StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=818181,
            fecha_actividad=date(2026, 8, 10),
            tipo_strava="WeightTraining",
            nombre_strava="Gym",
            duracion_segundos=3600,
            raw_json={},
            estado="created",
        )

        finding = self.auditar()["findings"][0]

        self.assertEqual(finding["code"], "strava_legacy_sin_vinculo_hub")
        self.assertEqual(finding["strava_raw_id"], raw.pk)
        self.assertEqual(finding["strava_id"], 818181)
        self.assertEqual(finding["estado"], "created")
        self.assertEqual(finding["confidence"], "media")

    def test_varias_actividades_strava_mismo_tipo_son_eventos_independientes(self):
        self.actividad(titulo="Caminata mañana", tipo="otro", fuente="strava")
        self.actividad(titulo="Caminata noche", tipo="otro", fuente="strava")

        result = self.auditar()

        self.assertFalse(any(
            row["code"] == "duplicado_probable" for row in result["findings"]
        ))

    def test_strava_vinculado_al_hub_conserva_identidad_y_no_genera_gap(self):
        activity = self.actividad(fuente="strava")
        raw = StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=919191,
            fecha_actividad=date(2026, 8, 10),
            tipo_strava="WeightTraining",
            nombre_strava="Fuerza",
            duracion_segundos=3600,
            raw_json={},
            estado="created",
            actividad_hub=activity,
        )

        result = self.auditar()

        self.assertEqual(raw.actividad_hub_id, activity.pk)
        self.assertEqual(activity.strava_source.pk, raw.pk)
        self.assertFalse(any(
            row.get("strava_raw_id") == raw.pk for row in result["findings"]
        ))

    def test_merged_sin_ningun_vinculo_sigue_siendo_incoherencia_alta(self):
        raw = StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=929292,
            fecha_actividad=date(2026, 8, 10),
            tipo_strava="WeightTraining",
            nombre_strava="Fuerza",
            duracion_segundos=3600,
            raw_json={},
            estado="merged",
        )

        finding = self.auditar()["findings"][0]

        self.assertEqual(finding["code"], "strava_procesado_sin_vinculo")
        self.assertEqual(finding["confidence"], "alta")
        self.assertEqual(finding["strava_raw_id"], raw.pk)

    def test_comando_emite_jsonl_estable_y_no_acepta_apply(self):
        self.actividad()
        output = StringIO()

        call_command(
            "auditar_eventos_fisicos_gym",
            cliente=self.cliente.pk,
            desde=self.desde.isoformat(),
            hasta=self.hasta.isoformat(),
            stdout=output,
        )

        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(records[-1]["tipo_registro"], "resumen")
        self.assertEqual(records[-1]["cliente_id"], self.cliente.pk)
        self.assertEqual(records[-1]["desde"], "2026-08-01")
        self.assertEqual(records[-1]["hasta"], "2026-08-16")
        self.assertTrue(records[-1]["solo_lectura"])
