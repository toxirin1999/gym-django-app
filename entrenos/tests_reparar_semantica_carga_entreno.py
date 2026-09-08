import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada, SesionProgramada
from rutinas.models import EjercicioBase, Rutina


class RepararSemanticaCargaEntrenoTests(TestCase):
    def setUp(self):
        User.objects.create_user("dummy")
        user = User.objects.create_user("cliente2")
        self.cliente = Cliente.objects.get(user=user)
        self.assertEqual(self.cliente.pk, 2)
        rutina = Rutina.objects.create(nombre="Incidente carga")
        self.entreno = EntrenoRealizado.objects.create(
            pk=362, cliente=self.cliente, rutina=rutina, fecha=date(2026, 8, 29),
            volumen_total_kg="9102.50",
        )
        farmer = EjercicioBase.objects.create(nombre="Farmer")
        curl = EjercicioBase.objects.create(nombre="Curl martillo")
        jalon = EjercicioBase.objects.create(nombre="Jalón")
        for pk, base, peso in ((1813, farmer, 75), (1814, farmer, 75),
                               (1821, curl, 15), (1822, curl, 15), (1823, curl, 15),
                               (1824, jalon, 45), (1825, jalon, 40), (1826, jalon, 35)):
            SerieRealizada.objects.create(
                pk=pk, entreno=self.entreno, ejercicio=base, serie_numero=pk,
                peso_kg=peso, repeticiones=1, completado=True,
            )
        EjercicioRealizado.objects.create(pk=1059, entreno=self.entreno, nombre_ejercicio="Farmer", peso_kg=75, es_tope_maquina=True)
        EjercicioRealizado.objects.create(pk=1062, entreno=self.entreno, nombre_ejercicio="Curl martillo", peso_kg=15)
        EjercicioRealizado.objects.create(pk=1063, entreno=self.entreno, nombre_ejercicio="Jalón", peso_kg=40)
        SesionProgramada.objects.create(pk=44, cliente=self.cliente, fecha_prevista=date(2026, 8, 29))

    def run_command(self, *extra):
        stdout = StringIO()
        call_command("reparar_semantica_carga_entreno", "--fecha", "2026-08-29", *extra, stdout=stdout)
        return json.loads(stdout.getvalue())

    def test_dry_run_no_escribe_y_devuelve_before_after(self):
        result = self.run_command()
        self.assertEqual(result["modo"], "dry-run")
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertIn("reversible", result)
        self.assertIsNone(SerieRealizada.objects.get(pk=1813).tipo_carga)

    def test_apply_actualiza_snapshots_volumen_y_sesion_y_es_idempotente(self):
        result = self.run_command("--apply")
        self.assertFalse(result["noop"])
        self.assertEqual(SerieRealizada.objects.get(pk=1813).peso_total_kg, 72)
        self.assertEqual(SerieRealizada.objects.get(pk=1813).peso_kg, 36)
        self.assertEqual(SerieRealizada.objects.get(pk=1825).peso_total_kg, 80)
        farmer = EjercicioRealizado.objects.get(pk=1059)
        self.assertTrue(farmer.es_tope_maquina)
        self.assertEqual((farmer.peso_kg, farmer.tipo_carga, farmer.multiplicador_carga, farmer.peso_total_kg), (36, "por_mano", 2, 72))
        self.entreno.refresh_from_db()
        self.assertEqual(self.entreno.volumen_total_kg, 9576.5)
        sp = SesionProgramada.objects.get(pk=44)
        self.assertEqual((sp.estado, sp.entreno_realizado_id, sp.fecha_realizada), ("completada", 362, date(2026, 8, 29)))
        self.assertTrue(self.run_command("--apply")["noop"])

    def test_conflicto_aborta_todo(self):
        SerieRealizada.objects.filter(pk=1813).update(peso_kg=99)
        with self.assertRaises(CommandError):
            self.run_command("--apply")
        self.entreno.refresh_from_db()
        self.assertEqual(self.entreno.volumen_total_kg, 9102.5)
        self.assertIsNone(SerieRealizada.objects.get(pk=1814).tipo_carga)
