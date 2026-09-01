import json
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ActividadRealizada,
    EjercicioRealizado,
    EntrenoRealizado,
    GymDecisionLog,
    RecordPersonal,
    SerieRealizada,
    SesionEntrenamiento,
)
from rutinas.models import EjercicioBase, Rutina


class RepararPesoSeriesEjercicioTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("reparar-peso")
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre="Fuerza")
        self.base = EjercicioBase.objects.create(
            nombre="Press inclinado", grupo_muscular="Pecho",
        )
        self.otro_base = EjercicioBase.objects.create(
            nombre="Remo", grupo_muscular="Espalda",
        )
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 31),
            volumen_total_kg=Decimal("1035.00"),
        )
        self.ejercicio = EjercicioRealizado.objects.create(
            entreno=self.entreno,
            nombre_ejercicio=self.base.nombre,
            peso_kg=47.5,
            series=6,
            repeticiones=3,
            orden=1,
        )
        self.otro_ejercicio = EjercicioRealizado.objects.create(
            entreno=self.entreno,
            nombre_ejercicio=self.otro_base.nombre,
            peso_kg=30,
            series=1,
            repeticiones=6,
            orden=2,
        )
        for numero in range(1, 7):
            SerieRealizada.objects.create(
                entreno=self.entreno,
                ejercicio=self.base,
                serie_numero=numero,
                repeticiones=3,
                peso_kg=Decimal("47.50"),
                completado=True,
            )
        SerieRealizada.objects.create(
            entreno=self.entreno,
            ejercicio=self.otro_base,
            serie_numero=1,
            repeticiones=6,
            peso_kg=Decimal("30.00"),
            completado=True,
        )
        self.sesion, _ = SesionEntrenamiento.objects.update_or_create(
            entreno=self.entreno,
            defaults={"duracion_minutos": 45, "volumen_sesion": Decimal("1035.00")},
        )
        self.actividad, _ = ActividadRealizada.objects.update_or_create(
            entreno_gym=self.entreno,
            defaults={
                "cliente": self.cliente,
                "tipo": "gym",
                "fecha": self.entreno.fecha,
                "volumen_kg": Decimal("1035.00"),
            },
        )
        self.record = RecordPersonal.objects.create(
            cliente=self.cliente,
            ejercicio_nombre=self.base.nombre,
            tipo_record="peso_maximo",
            valor=Decimal("47.50"),
            entreno=self.entreno,
        )
        self.record_ajeno = RecordPersonal.objects.create(
            cliente=self.cliente,
            ejercicio_nombre=self.base.nombre,
            tipo_record="peso_maximo",
            valor=Decimal("47.50"),
            entreno=EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 8, 30),
            ),
        )
        self.decision = GymDecisionLog.objects.create(
            cliente=self.cliente,
            entreno_origen=self.entreno,
            ejercicio=self.base.nombre.lower(),
            ejercicio_normalizado="press inclinado",
            peso_anterior=47.5,
            accion="subir_peso",
            motivo="Progresión",
        )

    def _run(self, apply=False, **overrides):
        valores = {
            "entreno_id": self.entreno.pk,
            "ejercicio_realizado_id": self.ejercicio.pk,
            "expected_nombre": self.base.nombre,
            "expected_series": 6,
            "expected_reps": 3,
            "expected_peso_anterior": "47.5",
            "nuevo_peso": "50",
        }
        valores.update(overrides)
        args = [str(valores.pop("entreno_id")), str(valores.pop("ejercicio_realizado_id"))]
        for nombre, valor in valores.items():
            args.extend(("--" + nombre.replace("_", "-"), str(valor)))
        if apply:
            args.append("--apply")
        stdout = StringIO()
        call_command("reparar_peso_series_ejercicio", *args, stdout=stdout)
        return json.loads(stdout.getvalue())

    def test_dry_run_por_defecto_no_modifica(self):
        resultado = self._run()

        self.assertTrue(resultado["dry_run"])
        self.assertEqual(resultado["volumen_total_nuevo"], "1080.00")
        self.ejercicio.refresh_from_db()
        self.assertEqual(self.ejercicio.peso_kg, 47.5)
        self.assertFalse(
            SerieRealizada.objects.filter(entreno=self.entreno, peso_kg=50).exists()
        )
        self.record.refresh_from_db()
        self.decision.refresh_from_db()
        self.assertEqual(self.record.valor, Decimal("47.50"))
        self.assertEqual(self.decision.peso_anterior, 47.5)

    def test_apply_actualiza_solo_objetos_ligados_y_preserva_series_reps(self):
        resultado = self._run(apply=True)

        self.assertFalse(resultado["dry_run"])
        self.assertEqual(resultado["series_actualizadas"], 6)
        self.assertEqual(resultado["decisiones_actualizadas"], 1)
        self.ejercicio.refresh_from_db()
        self.entreno.refresh_from_db()
        self.sesion.refresh_from_db()
        self.actividad.refresh_from_db()
        self.record.refresh_from_db()
        self.record_ajeno.refresh_from_db()
        self.decision.refresh_from_db()
        self.assertEqual(self.ejercicio.peso_kg, 50)
        self.assertEqual((self.ejercicio.series, self.ejercicio.repeticiones), (6, 3))
        series = list(
            SerieRealizada.objects.filter(entreno=self.entreno, ejercicio=self.base)
            .order_by("serie_numero")
            .values_list("peso_kg", "repeticiones")
        )
        self.assertEqual(series, [(Decimal("50.00"), 3)] * 6)
        self.assertEqual(self.entreno.volumen_total_kg, Decimal("1080.00"))
        self.assertEqual(self.sesion.volumen_sesion, Decimal("1080.00"))
        self.assertEqual(self.actividad.volumen_kg, Decimal("1080.00"))
        self.assertEqual(self.record.valor, Decimal("50.00"))
        self.assertEqual(self.record_ajeno.valor, Decimal("47.50"))
        self.assertEqual(self.decision.peso_anterior, 50)

    def test_apply_es_idempotente(self):
        self._run(apply=True)
        resultado = self._run(apply=True)

        self.assertTrue(resultado["ya_aplicado"])
        self.assertEqual(resultado["series_actualizadas"], 0)
        self.assertEqual(resultado["records_actualizados"], 0)
        self.assertEqual(resultado["decisiones_actualizadas"], 0)
        self.assertEqual(RecordPersonal.objects.filter(pk=self.record.pk).count(), 1)

    def test_rechaza_expected_incorrecto_sin_cambios(self):
        with self.assertRaisesMessage(CommandError, "series esperadas"):
            self._run(apply=True, expected_series=5)

        self.ejercicio.refresh_from_db()
        self.assertEqual(self.ejercicio.peso_kg, 47.5)

    def test_rechaza_si_una_serie_guardada_no_coincide(self):
        SerieRealizada.objects.filter(
            entreno=self.entreno, ejercicio=self.base, serie_numero=6,
        ).update(repeticiones=4)

        with self.assertRaisesMessage(CommandError, "repeticiones"):
            self._run(apply=True)

        self.ejercicio.refresh_from_db()
        self.assertEqual(self.ejercicio.peso_kg, 47.5)
