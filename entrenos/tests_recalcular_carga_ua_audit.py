import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada


class RecalcularCargaUaAuditTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("audit_carga")
        self.cliente = Cliente.objects.get(user=user)

    def _actividad(self, **overrides):
        defaults = {
            "cliente": self.cliente,
            "fecha": date(2026, 8, 9),
            "fuente": "strava",
            "tipo": "futbol",
            "duracion_minutos": 60,
            "rpe_medio": 8.0,
            "carga_ua": 48.0,
        }
        defaults.update(overrides)
        return ActividadRealizada.objects.create(**defaults)

    def _audit(self, *extra_args):
        stdout = StringIO()
        call_command(
            "recalcular_carga_ua",
            "--audit",
            "--cliente",
            str(self.cliente.pk),
            *extra_args,
            stdout=stdout,
        )
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.startswith("{")]

    def test_audit_es_solo_lectura_aunque_no_se_indique_dry_run(self):
        actividad = self._actividad()

        registros = self._audit()

        actividad.refresh_from_db()
        self.assertEqual(actividad.carga_ua, 48.0)
        self.assertEqual(actividad.rpe_medio, 8.0)
        self.assertEqual(registros[-1]["tipo_registro"], "resumen")
        self.assertTrue(registros[-1]["solo_lectura"])

    def test_audit_emite_desglose_estable_y_distingue_rpe_real_de_fallback(self):
        real = self._actividad()
        fallback = self._actividad(
            fecha=date(2026, 8, 8),
            tipo="carrera",
            rpe_medio=None,
            carga_ua=390.0,
        )
        self._actividad(
            fecha=date(2026, 8, 7),
            fuente="manual",
            tipo="gym",
            duracion_minutos=None,
            rpe_medio=None,
            carga_ua=None,
        )

        registros = self._audit()

        resumen = registros[-1]
        self.assertEqual(
            resumen,
            {
                "cambiarian": 1,
                "metodos_calculo": {
                    "fallback_6_5": 1,
                    "hr_estimado": 0,
                    "no_calculable": 1,
                    "rpe_real": 1,
                },
                "sin_valor_posible": 1,
                "solo_lectura": True,
                "tipo_registro": "resumen",
                "total": 3,
            },
        )
        por_fuente = {
            registro["fuente"]: registro
            for registro in registros
            if registro["tipo_registro"] == "grupo_fuente"
        }
        self.assertEqual(
            por_fuente["strava"],
            {
                "cambiarian": 1,
                "con_carga_actual": 2,
                "con_rpe": 1,
                "conteo": 2,
                "fuente": "strava",
                "sin_carga_actual": 0,
                "sin_rpe": 1,
                "tipo_registro": "grupo_fuente",
            },
        )
        por_tipo = {
            registro["tipo_actividad"]: registro
            for registro in registros
            if registro["tipo_registro"] == "grupo_tipo_actividad"
        }
        self.assertEqual(por_tipo["futbol"]["con_rpe"], 1)
        self.assertEqual(por_tipo["carrera"]["sin_rpe"], 1)

        bandas = next(r for r in registros if r["tipo_registro"] == "bandas_ratio")
        self.assertEqual(bandas["bandas"]["9_a_11x"], 1)
        self.assertEqual(bandas["bandas"]["0_8_a_1_25x"], 1)

        top = next(r for r in registros if r["tipo_registro"] == "top_cambio")
        self.assertEqual(top["id"], real.pk)
        self.assertEqual(top["metodo_calculo"], "rpe_real")
        self.assertEqual(top["carga_propuesta"], 480.0)
        self.assertEqual(top["ratio_propuesto_actual"], 10.0)
        self.assertNotIn("cliente", top)
        self.assertNotIn("titulo", top)
        self.assertNotEqual(top["id"], fallback.pk)

    @patch("hyrox.training_engine.HyroxLoadManager.estimar_rpe_desde_fc", return_value=7.0)
    def test_audit_solo_estima_rpe_por_fc_con_flag_explicito(self, estimar):
        actividad = self._actividad(rpe_medio=None, hr_media=150, carga_ua=390.0)

        sin_flag = self._audit()[-1]
        con_flag = self._audit("--with-hr-estimation")[-1]

        self.assertEqual(sin_flag["metodos_calculo"]["fallback_6_5"], 1)
        self.assertEqual(sin_flag["metodos_calculo"]["hr_estimado"], 0)
        self.assertEqual(con_flag["metodos_calculo"]["fallback_6_5"], 0)
        self.assertEqual(con_flag["metodos_calculo"]["hr_estimado"], 1)
        estimar.assert_called_once()
        actividad.refresh_from_db()
        self.assertIsNone(actividad.rpe_medio)
        self.assertEqual(actividad.carga_ua, 390.0)

    def test_sin_audit_conserva_aplicacion_tradicional(self):
        actividad = self._actividad()

        call_command(
            "recalcular_carga_ua",
            "--cliente",
            str(self.cliente.pk),
            stdout=StringIO(),
        )

        actividad.refresh_from_db()
        self.assertEqual(actividad.carga_ua, 480.0)
