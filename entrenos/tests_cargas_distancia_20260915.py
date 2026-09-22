import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services.records_service import RecordsService
from entrenos.views import obtener_ultimo_peso_ejercicio
from rutinas.models import EjercicioBase, Rutina


class MetricasCargaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("metricas-carga")
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre="Cargas")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 9, 15)
        )
        self.farmer = EjercicioBase.objects.create(
            nombre="Farmer Carry", grupo_muscular="Full body",
            tipo_progresion="progresion_distancia", tipo_carga_default="por_mano",
        )

    def test_distancia_no_se_guarda_como_repeticiones_y_calcula_kg_m(self):
        serie = SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=self.farmer, serie_numero=1,
            repeticiones=0, distancia_metros=Decimal("47"), peso_kg=Decimal("36"),
            peso_total_kg=Decimal("72"), tipo_carga="por_mano", multiplicador_carga=2,
            completado=True,
        )
        self.assertEqual(serie.tonelaje_kg, Decimal("0"))
        self.assertEqual(serie.carga_distancia_kg_m, Decimal("3384"))

    def test_progresion_farmer_parte_de_mejor_distancia_real(self):
        for numero, metros in enumerate((42, 47), 1):
            SerieRealizada.objects.create(
                entreno=self.entreno, ejercicio=self.farmer, serie_numero=numero,
                repeticiones=0, distancia_metros=metros, peso_kg=36,
                peso_total_kg=72, completado=True,
            )
        EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio="Farmer Carry", peso_kg=36,
            peso_total_kg=72, series=2, repeticiones=0, es_tope_maquina=True,
        )
        anterior = obtener_ultimo_peso_ejercicio(
            self.cliente.pk, "Farmer Carry", date(2026, 9, 16)
        )
        self.assertEqual(anterior["repeticiones"], 47)
        self.assertEqual(anterior["volumen"], 0)

    def test_volumen_de_fuerza_usa_peso_total_pero_pr_peso_conserva_peso_contractual(self):
        base = EjercicioBase.objects.create(nombre="Curl martillo", grupo_muscular="Bíceps")
        SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=base, serie_numero=1, repeticiones=7,
            peso_kg=Decimal("17.5"), peso_total_kg=Decimal("35"),
            tipo_carga="por_mano", multiplicador_carga=2, completado=True,
        )
        EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio=base.nombre, grupo_muscular="Bíceps",
            peso_kg=17.5, peso_total_kg=35, tipo_carga="por_mano",
            multiplicador_carga=2, series=1, repeticiones=7,
        )
        records = RecordsService.detectar_records_sesion(self.entreno)
        valores = {r.tipo_record: r.valor for r in records}
        self.assertEqual(valores["peso_maximo"], Decimal("17.5"))
        self.assertEqual(valores["volumen_total"], Decimal("245"))


class GuardadoDistanciaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("guardar-distancia")
        self.client.force_login(user)
        self.cliente = Cliente.objects.get(user=user)
        Rutina.objects.create(nombre="Carry")
        EjercicioBase.objects.create(
            nombre="Farmer Carry", grupo_muscular="Full body",
            tipo_progresion="progresion_distancia", tipo_carga_default="por_mano",
        )

    def test_post_farmer_preserva_metros_y_no_contamina_tonelaje(self):
        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            {
                "fecha": "2026-09-15", "rutina_nombre": "Carry",
                "ej1_nombre": "Farmer Carry", "ej1_tipo_progresion": "progresion_distancia",
                "ej1_tipo_carga": "por_mano", "ej1_peso_1": "36", "ej1_reps_1": "47",
                "ej1_rpe_1": "8", "ej1_completado_1": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        serie = SerieRealizada.objects.get(entreno__cliente=self.cliente)
        self.assertEqual(serie.repeticiones, 0)
        self.assertEqual(serie.distancia_metros, Decimal("47"))
        self.assertEqual(serie.carga_distancia_kg_m, Decimal("3384"))
        serie.entreno.refresh_from_db()
        self.assertEqual(serie.entreno.volumen_total_kg, Decimal("0"))


class UiCargaTests(TestCase):
    def test_ui_usa_incremento_del_ejercicio_y_peso_sin_redondeo_forzado(self):
        template = (Path(__file__).parent / "templates/entrenos/entrenamiento_activo.html").read_text()
        self.assertNotIn("ajustarPesoPanel('{{ ejercicio.form_id }}',{{ sn }},-2.5)", template)
        self.assertIn("data-inc-kg", template)
        self.assertIn("step=\"any\"", template)
        self.assertIn("por mano", template)
        self.assertIn("Tope de peso", template)
        self.assertNotIn("pesoRaw / 2.5", template)
        self.assertIn("calcularPesoSiguienteSerie(fid,", template)

    def test_resumen_separa_tonelaje_distancia_y_repeticiones(self):
        template = (Path(__file__).parent / "templates/entrenos/entrenamiento_activo.html").read_text()
        self.assertIn("cargaDistancia", template)
        self.assertIn("distanciaTotal", template)
        self.assertIn("s.usaDistancia", template)
        self.assertIn("s.multiplicador", template)
        self.assertIn("kg·m", template)


class ReparacionDeclarativaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("repair")
        self.cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre="Incidente")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=date(2026, 9, 15), volumen_total_kg=0
        )
        base = EjercicioBase.objects.create(nombre="Curl Z", grupo_muscular="Bíceps")
        self.serie = SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=base, serie_numero=1, peso_kg=35,
            repeticiones=8, completado=True,
        )

    def _run(self, *extra):
        out = StringIO()
        spec = json.dumps([{
            "id": self.serie.pk, "expected": {"peso_kg": "35.00", "repeticiones": 8},
            "set": {"peso_kg": "44", "repeticiones": 5, "tipo_carga": "total"},
        }])
        call_command(
            "reparar_semantica_carga_entreno", "--entreno", str(self.entreno.pk),
            "--cliente", str(self.cliente.pk), "--fecha", "2026-09-15",
            "--series-json", spec, *extra, stdout=out,
        )
        return json.loads(out.getvalue())

    def test_dry_run_apply_idempotencia_y_salida_reversible(self):
        dry = self._run()
        self.serie.refresh_from_db()
        self.assertEqual(self.serie.peso_kg, 35)
        self.assertEqual(dry["reversible"]["series"][0]["set"]["peso_kg"], "35.00")
        self.assertFalse(self._run("--apply")["noop"])
        self.serie.refresh_from_db()
        self.assertEqual((self.serie.peso_kg, self.serie.repeticiones), (44, 5))
        self.assertTrue(self._run("--apply")["noop"])
