import json
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.db.models.signals import post_save
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado,
    EntrenoRealizado,
    SerieRealizada,
    SesionProgramada,
)
from rutinas.models import EjercicioBase, Rutina


class RepararSeriesFaltantesEntrenoCommandTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user(username="repair-series")
        self.cliente = Cliente.objects.get(user=usuario)
        self.rutina = Rutina.objects.create(nombre="Fuerza")
        self.base = EjercicioBase.objects.create(nombre="Press banca", grupo_muscular="Pecho")
        self.otra_base = EjercicioBase.objects.create(nombre="Remo", grupo_muscular="Espalda")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 9, 7),
            numero_ejercicios=6,
            volumen_total_kg=Decimal("9582.50"),
        )
        self.agregado = EjercicioRealizado.objects.create(
            entreno=self.entreno,
            nombre_ejercicio=self.base.nombre,
            peso_kg=60,
            series=1,
            repeticiones=6,
            rpe=7,
            completado=False,
            es_tope_maquina=True,
            orden=2,
        )
        self.otro_agregado = EjercicioRealizado.objects.create(
            entreno=self.entreno,
            nombre_ejercicio=self.otra_base.nombre,
            peso_kg=1,
            series=1,
            repeticiones=1,
            orden=1,
        )
        SerieRealizada.objects.create(
            entreno=self.entreno,
            ejercicio=self.base,
            serie_numero=1,
            repeticiones=6,
            peso_kg=Decimal("60"),
            rpe_real=7.5,
            tecnica_calidad=None,
            completado=True,
        )
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 9, 7),
            nombre_sesion="Fuerza",
        )

    def _argumentos(self, *extra):
        return (
            "--entreno", str(self.entreno.pk),
            "--ejercicio", str(self.base.pk),
            "--agregado", str(self.agregado.pk),
            "--sesion-programada", str(self.sp.pk),
            "--fecha", "2026-09-07",
            "--expected-numero-ejercicios", "6",
            "--expected-volumen", "9582.50",
            "--expected-volumen-final", "10392.50",
            "--expected-series-final", "3",
            "--expected-peso-promedio-final", "65",
            "--expected-reps-promedio-final", "6",
            "--expected-rpe-promedio-final", "8",
            "--serie", "2:65:6:8:buena",
            "--serie", "3:70:6:8.5:aceptable",
            "--tecnica-existente", "1:buena",
            *extra,
        )

    def _run(self, *extra):
        salida = StringIO()
        call_command(
            "reparar_series_faltantes_entreno",
            *self._argumentos(*extra),
            stdout=salida,
        )
        return json.loads(salida.getvalue())

    def test_dry_run_por_defecto_emite_json_y_no_modifica(self):
        resultado = self._run()

        self.entreno.refresh_from_db()
        self.agregado.refresh_from_db()
        self.sp.refresh_from_db()
        self.assertEqual(resultado["modo"], "dry-run")
        self.assertEqual(resultado["plan"]["series_a_crear"], [2, 3])
        self.assertEqual(resultado["plan"]["tecnicas_a_actualizar"], [1])
        self.assertEqual(resultado["before"]["volumen_total_kg"], "9582.50")
        self.assertEqual(resultado["after"]["volumen_total_kg"], "10392.50")
        self.assertEqual(resultado["ids_creados"], [])
        self.assertIn("reversible", resultado)
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)
        self.assertIsNone(SerieRealizada.objects.get(entreno=self.entreno, serie_numero=1).tecnica_calidad)
        self.assertEqual(self.entreno.volumen_total_kg, Decimal("9582.50"))
        self.assertEqual(self.agregado.series, 1)
        self.assertEqual(self.sp.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.sp.entreno_realizado_id)

    def test_apply_crea_series_y_actualiza_solo_agregado_entreno_y_sp_sin_signals(self):
        eventos = []

        def registrar(sender, instance, **kwargs):
            eventos.append((sender, instance.pk))

        uid = "test-reparar-series-faltantes-sin-signals"
        post_save.connect(registrar, dispatch_uid=uid, weak=False)
        try:
            resultado = self._run("--apply")
        finally:
            post_save.disconnect(dispatch_uid=uid)

        self.entreno.refresh_from_db()
        self.agregado.refresh_from_db()
        self.otro_agregado.refresh_from_db()
        self.sp.refresh_from_db()
        nuevas = list(
            SerieRealizada.objects.filter(entreno=self.entreno, serie_numero__in=[2, 3])
            .order_by("serie_numero")
        )
        self.assertEqual(resultado["modo"], "apply")
        self.assertEqual(
            [(s.serie_numero, s.peso_kg, s.repeticiones, s.rpe_real, s.tecnica_calidad, s.completado) for s in nuevas],
            [
                (2, Decimal("65.00"), 6, 8.0, "buena", True),
                (3, Decimal("70.00"), 6, 8.5, "aceptable", True),
            ],
        )
        self.assertEqual(
            SerieRealizada.objects.get(entreno=self.entreno, ejercicio=self.base, serie_numero=1).tecnica_calidad,
            "buena",
        )
        self.assertEqual(self.entreno.volumen_total_kg, Decimal("10392.50"))
        self.assertEqual(self.entreno.numero_ejercicios, 6)
        self.assertEqual(self.agregado.series, 3)
        self.assertEqual((self.agregado.peso_kg, self.agregado.repeticiones, self.agregado.rpe), (65, 6, 8))
        self.assertTrue(self.agregado.completado)
        self.assertTrue(self.agregado.es_tope_maquina)
        self.assertEqual(self.otro_agregado.series, 1)
        self.assertEqual(self.sp.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(self.sp.fecha_realizada, self.entreno.fecha)
        self.assertEqual(self.sp.entreno_realizado_id, self.entreno.pk)
        self.assertEqual(eventos, [])
        self.assertEqual(len(resultado["ids_creados"]), 2)
        self.assertEqual(resultado["after"]["agregado"]["series"], 3)

    def test_rerun_apply_es_noop_idempotente_con_series_identicas(self):
        primera = self._run("--apply")
        segunda = self._run("--apply")

        self.assertEqual(len(primera["ids_creados"]), 2)
        self.assertEqual(segunda["ids_creados"], [])
        self.assertEqual(segunda["plan"]["series_a_crear"], [])
        self.assertEqual(segunda["plan"]["tecnicas_a_actualizar"], [])
        self.assertTrue(segunda["noop"])
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno, ejercicio=self.base).count(), 3)

    def test_conflicto_de_serie_existente_aborta_toda_la_operacion(self):
        SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=self.base, serie_numero=2,
            repeticiones=5, peso_kg=60, completado=True,
        )
        with self.assertRaisesMessage(CommandError, "serie 2 ya existe con datos distintos"):
            self._run("--apply")

        self.entreno.refresh_from_db()
        self.sp.refresh_from_db()
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 2)
        self.assertIsNone(SerieRealizada.objects.get(entreno=self.entreno, serie_numero=1).tecnica_calidad)
        self.assertEqual(self.entreno.volumen_total_kg, Decimal("9582.50"))
        self.assertEqual(self.sp.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_guardrails_rechazan_fecha_numero_volumen_agregado_y_sp_ajenos(self):
        casos = [
            (("--fecha", "2026-09-08"), "fecha"),
            (("--expected-numero-ejercicios", "5"), "numero_ejercicios"),
            (("--expected-volumen", "1"), "volumen"),
            (("--agregado", str(self.otro_agregado.pk)), "agregado"),
        ]
        otro_entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 9, 6)
        )
        sp_ajena = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 9, 6),
            entreno_realizado=otro_entreno,
            estado=SesionProgramada.ESTADO_COMPLETADA,
        )
        casos.append((("--sesion-programada", str(sp_ajena.pk)), "sesión programada"))

        for reemplazo, mensaje in casos:
            with self.subTest(reemplazo=reemplazo):
                argumentos = list(self._argumentos("--apply"))
                indice = argumentos.index(reemplazo[0])
                argumentos[indice + 1] = reemplazo[1]
                with self.assertRaisesMessage(CommandError, mensaje):
                    call_command("reparar_series_faltantes_entreno", *argumentos, stdout=StringIO())

        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)

    def test_expected_final_incorrecto_aborta_sin_cambios(self):
        argumentos = list(self._argumentos("--apply"))
        indice = argumentos.index("--expected-series-final")
        argumentos[indice + 1] = "4"
        with self.assertRaisesMessage(CommandError, "series final"):
            call_command("reparar_series_faltantes_entreno", *argumentos, stdout=StringIO())
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)

    def test_agregado_ambiguo_para_mismo_nombre_aborta(self):
        EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio=self.base.nombre,
            peso_kg=60, series=1, repeticiones=6,
        )
        with self.assertRaisesMessage(CommandError, "agregado ambiguo"):
            self._run("--apply")
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)

    def test_sp_conflictiva_aborta_sin_cambios(self):
        otro = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 9, 6)
        )
        SesionProgramada.objects.filter(pk=self.sp.pk).update(
            estado=SesionProgramada.ESTADO_COMPLETADA,
            fecha_realizada=otro.fecha,
            entreno_realizado=otro,
        )
        with self.assertRaisesMessage(CommandError, "sesión programada"):
            self._run("--apply")
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)

    def test_rechaza_payloads_invalidos_y_tecnica_existente_conflictiva(self):
        casos = [
            (("--serie", "2:65:6:8:perfecta"), "técnica"),
            (("--serie", "2:65:6"), "--serie"),
            (("--serie", "1:65:6:8:buena"), "no puede ser nueva y existente"),
            (("--tecnica-existente", "9:buena"), "serie existente 9"),
        ]
        for reemplazo, mensaje in casos:
            with self.subTest(reemplazo=reemplazo):
                argumentos = list(self._argumentos("--apply"))
                indice = argumentos.index(reemplazo[0])
                argumentos[indice + 1] = reemplazo[1]
                with self.assertRaisesMessage(CommandError, mensaje):
                    call_command("reparar_series_faltantes_entreno", *argumentos, stdout=StringIO())

        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)

    def test_tecnica_existente_distinta_aborta(self):
        SerieRealizada.objects.filter(
            entreno=self.entreno, ejercicio=self.base, serie_numero=1
        ).update(tecnica_calidad="buena")
        argumentos = list(self._argumentos("--apply"))
        indice = argumentos.index("--tecnica-existente")
        argumentos[indice + 1] = "1:aceptable"
        with self.assertRaisesMessage(CommandError, "conflicto de técnica"):
            call_command("reparar_series_faltantes_entreno", *argumentos, stdout=StringIO())
        self.assertEqual(SerieRealizada.objects.filter(entreno=self.entreno).count(), 1)
