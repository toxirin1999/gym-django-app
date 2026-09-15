import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SerieRealizada
from rutinas.models import EjercicioBase, Rutina


class RepararSemanticaCargaEntrenoTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("reparacion-generica")
        self.cliente = Cliente.objects.get(user=user)
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre="Incidente"),
            fecha=date(2026, 9, 15), volumen_total_kg=360,
        )
        base = EjercicioBase.objects.create(nombre="Farmer", grupo_muscular="Full body")
        self.serie = SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=base, serie_numero=1,
            peso_kg=75, repeticiones=1, completado=True,
        )

    def run_command(self, *extra, expected="75.00"):
        stdout = StringIO()
        spec = json.dumps([{
            "id": self.serie.pk,
            "expected": {"peso_kg": expected},
            "set": {"peso_kg": "36", "tipo_carga": "por_mano",
                    "repeticiones": 0, "distancia_metros": "47"},
        }])
        call_command(
            "reparar_semantica_carga_entreno", "--entreno", str(self.entreno.pk),
            "--cliente", str(self.cliente.pk), "--fecha", "2026-09-15",
            "--series-json", spec, *extra, stdout=stdout,
        )
        return json.loads(stdout.getvalue())

    def test_dry_run_no_escribe_y_devuelve_plan_reversible(self):
        result = self.run_command()
        self.assertEqual(result["modo"], "dry-run")
        self.assertEqual(result["reversible"]["series"][0]["id"], self.serie.pk)
        self.serie.refresh_from_db()
        self.assertIsNone(self.serie.tipo_carga)

    def test_apply_actualiza_snapshots_y_es_idempotente(self):
        self.assertFalse(self.run_command("--apply")["noop"])
        self.serie.refresh_from_db()
        self.assertEqual((self.serie.peso_kg, self.serie.peso_total_kg), (36, 72))
        self.assertEqual((self.serie.repeticiones, self.serie.distancia_metros), (0, 47))
        self.assertTrue(self.run_command("--apply")["noop"])

    def test_conflicto_aborta(self):
        self.serie.peso_kg = 99
        self.serie.save(update_fields=["peso_kg"])
        with self.assertRaises(CommandError):
            self.run_command("--apply")
