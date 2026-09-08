from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services.peso_semantica_service import resolver_semantica_carga
from rutinas.models import EjercicioBase, Rutina


class PesoSemanticaServiceTests(TestCase):
    def test_resuelve_enums_canonicos_y_no_confia_en_multiplicador_cliente(self):
        self.assertEqual(
            resolver_semantica_carga("por_mano", Decimal("12.5"), multiplicador_solicitado=99),
            {"tipo_carga": "por_mano", "multiplicador_carga": 2, "peso_total_kg": Decimal("25.0")},
        )
        self.assertEqual(
            resolver_semantica_carga("por_lado", Decimal("20"), multiplicador_solicitado=7),
            {"tipo_carga": "por_lado", "multiplicador_carga": 2, "peso_total_kg": Decimal("40")},
        )
        self.assertEqual(resolver_semantica_carga("total_ambas", 30)["tipo_carga"], "total")

    def test_tipo_invalido_converge_a_total(self):
        self.assertEqual(
            resolver_semantica_carga("inventado", 18),
            {"tipo_carga": "total", "multiplicador_carga": 1, "peso_total_kg": Decimal("18")},
        )


class SnapshotSemanticaCargaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("peso-user", password="secret")
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.nombre = "Peso"
        self.cliente.save(update_fields=["nombre"])
        self.rutina = Rutina.objects.create(nombre="Carga")
        self.base = EjercicioBase.objects.create(
            nombre="Press nuevo", grupo_muscular="Pecho", tipo_carga_default="por_mano"
        )
        self.entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina)

    def test_legacy_null_conserva_peso_como_total(self):
        ejercicio = EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio="Legacy", peso_kg=12, series=3, repeticiones=10
        )
        self.assertIsNone(ejercicio.tipo_carga)
        self.assertEqual(ejercicio.volumen(), 360)

    def test_volumen_prefiere_snapshot_total_sin_multiplicarlo_otra_vez(self):
        ejercicio = EjercicioRealizado.objects.create(
            entreno=self.entreno,
            nombre_ejercicio="Press nuevo",
            peso_kg=12,
            series=3,
            repeticiones=10,
            tipo_carga="por_mano",
            multiplicador_carga=2,
            peso_total_kg=24,
        )
        self.assertEqual(ejercicio.volumen(), 720)

    def test_guardado_post_persiste_semantica_y_descarta_multiplicador_post(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
            {
                "fecha": "2026-09-08",
                "rutina_nombre": "Carga",
                "ej1_nombre": "Press nuevo",
                "ej1_tipo_progresion": "peso_reps",
                "ej1_tipo_carga": "por_mano",
                "ej1_multiplicador_carga": "99",
                "ej1_peso_1": "12.5",
                "ej1_reps_1": "10",
                "ej1_completado_1": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        agregado = EjercicioRealizado.objects.filter(entreno__cliente=self.cliente).latest("pk")
        serie = SerieRealizada.objects.filter(entreno=agregado.entreno).latest("pk")
        for snapshot in (agregado, serie):
            self.assertEqual(snapshot.tipo_carga, "por_mano")
            self.assertEqual(snapshot.multiplicador_carga, 2)
            self.assertEqual(snapshot.peso_total_kg, Decimal("25.00"))
        agregado.entreno.refresh_from_db()
        self.assertEqual(agregado.entreno.volumen_total_kg, Decimal("250.00"))
