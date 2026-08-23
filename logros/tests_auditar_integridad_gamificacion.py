import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from logros.models import HistorialPuntos, PerfilGamificacion
from rutinas.models import Rutina


class AuditarIntegridadGamificacionTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get_or_create(
            user=User.objects.create_user("audit-gam-owner"),
            defaults={"nombre": "Audit gam owner"},
        )[0]
        self.otro = Cliente.objects.get_or_create(
            user=User.objects.create_user("audit-gam-other"),
            defaults={"nombre": "Audit gam other"},
        )[0]
        self.rutina = Rutina.objects.create(nombre="Audit gam")

    def entreno(self, cliente=None, *, procesado=True):
        return EntrenoRealizado.objects.create(
            cliente=cliente or self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 23),
            procesado_gamificacion=procesado,
        )

    def ejecutar(self, **kwargs):
        salida = StringIO()
        call_command(
            "auditar_integridad_gamificacion",
            cliente=self.cliente.pk,
            stdout=salida,
            **kwargs,
        )
        return salida.getvalue(), [
            json.loads(line) for line in salida.getvalue().splitlines() if line
        ]

    def test_fixture_sana_emite_solo_resumen_estable(self):
        perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente, puntos_totales=25, entrenos_totales=1,
        )
        entreno = self.entreno()
        HistorialPuntos.objects.create(
            perfil=perfil, entreno=entreno, puntos=25, descripcion="Entreno base",
        )

        primera, rows = self.ejecutar()
        segunda, _ = self.ejecutar()

        self.assertEqual(primera, segunda)
        self.assertEqual(len(rows), 1)
        resumen = rows[0]
        self.assertEqual(resumen["tipo_registro"], "resumen")
        self.assertEqual(resumen["schema_version"], 1)
        self.assertTrue(resumen["solo_lectura"])
        self.assertEqual(resumen["counts_by_code"], {})
        self.assertEqual(resumen["totals"]["entrenos_reales"], 1)
        self.assertEqual(resumen["totals"]["historial_count"], 1)
        self.assertEqual(resumen["totals"]["historial_sum"], 25)
        self.assertEqual(len(resumen["fingerprint"]), 64)

    def test_clasifica_anomalias_sin_inferir_reparacion(self):
        perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente, puntos_totales=90, entrenos_totales=9,
        )
        perfil_otro = PerfilGamificacion.objects.create(cliente=self.otro)
        procesado_sin_ledger = self.entreno()
        abierto_con_ledger = self.entreno(procesado=False)
        duplicado = self.entreno()
        ajeno = self.entreno(cliente=self.otro)
        HistorialPuntos.objects.create(perfil=perfil, entreno=abierto_con_ledger, puntos=10)
        HistorialPuntos.objects.create(perfil=perfil, entreno=duplicado, puntos=11)
        HistorialPuntos.objects.create(perfil=perfil, entreno=duplicado, puntos=12)
        HistorialPuntos.objects.create(perfil=perfil, entreno=ajeno, puntos=13)
        HistorialPuntos.objects.create(perfil=perfil, puntos=14, descripcion="Quest o prueba")
        # Un ledger de otro perfil unido a un entreno propio también es cruce.
        HistorialPuntos.objects.create(perfil=perfil_otro, entreno=procesado_sin_ledger, puntos=7)

        _, rows = self.ejecutar()
        findings = rows[:-1]
        summary = rows[-1]
        codes = {row["code"] for row in findings}

        self.assertTrue({
            "training_total_mismatch", "point_total_mismatch",
            "multiple_base_events_for_training", "cross_client_training_history",
            "processed_training_without_own_history", "unprocessed_training_with_history",
            "history_without_training",
        }.issubset(codes))
        points = next(row for row in findings if row["code"] == "point_total_mismatch")
        self.assertEqual(points["classification"], "profile_greater_than_ledger")
        unlinked = next(row for row in findings if row["code"] == "history_without_training")
        self.assertEqual(unlinked["classification"], "non_training_event_unknown_origin")
        self.assertNotIn("duplic", unlinked["classification"])
        self.assertEqual(summary["totals"]["historial_sin_entreno"], 1)
        self.assertEqual(summary["counts_by_code"]["cross_client_training_history"], 2)
        self.assertNotIn("repair", json.dumps(rows).lower())
        self.assertNotIn("aplicar", json.dumps(rows).lower())

    def test_es_solo_lectura_y_limita_filas_sin_perder_conteos_globales(self):
        perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente, puntos_totales=6, entrenos_totales=0,
        )
        for puntos in (1, 2, 3):
            HistorialPuntos.objects.create(perfil=perfil, puntos=puntos)
        antes = {
            "perfil": list(PerfilGamificacion.objects.values().order_by("pk")),
            "historial": list(HistorialPuntos.objects.values().order_by("pk")),
            "entrenos": list(EntrenoRealizado.objects.values().order_by("pk")),
        }

        _, rows = self.ejecutar(limit=2)

        self.assertEqual(len(rows[:-1]), 2)
        self.assertEqual(rows[-1]["counts_by_code"]["history_without_training"], 3)
        self.assertEqual(rows[-1]["truncados"], 1)
        despues = {
            "perfil": list(PerfilGamificacion.objects.values().order_by("pk")),
            "historial": list(HistorialPuntos.objects.values().order_by("pk")),
            "entrenos": list(EntrenoRealizado.objects.values().order_by("pk")),
        }
        self.assertEqual(antes, despues)

    def test_perfil_ausente_y_cliente_obligatorio(self):
        self.entreno(procesado=False)
        _, rows = self.ejecutar()
        self.assertEqual(rows[0]["code"], "missing_gamification_profile")
        self.assertEqual(rows[-1]["totals"]["perfiles"], 0)
        with self.assertRaises(CommandError):
            call_command("auditar_integridad_gamificacion", stdout=StringIO())
