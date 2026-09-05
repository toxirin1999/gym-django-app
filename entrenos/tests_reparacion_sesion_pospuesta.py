from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.sesion_recomendada import (
    _marcar_completadas,
    obtener_sesion_recomendada_hoy,
)
from rutinas.models import Rutina


class ReconciliacionSesionPospuestaTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="pospuesta")
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={"nombre": "Pospuesta"})
        self.miercoles = date(2026, 9, 2)
        self.jueves = date(2026, 9, 3)
        self.viernes = date(2026, 9, 4)
        self.dia3 = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.miercoles,
            pospuesta_hasta=self.jueves, estado=SesionProgramada.ESTADO_COMPLETADA,
            fecha_realizada=self.jueves, nombre_sesion="Dia 3 - Fuerza — Avanzada", dia_numero=3,
        )
        self.dia4 = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.jueves,
            nombre_sesion="Dia 4 - Fuerza — Avanzada", dia_numero=4,
        )
        self.dia5 = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.viernes,
            nombre_sesion="Dia 5 - Fuerza — Avanzada", dia_numero=5,
        )
        rutina3 = Rutina.objects.create(nombre=self.dia3.nombre_sesion)
        self.entreno3 = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina3, fecha=self.jueves, fecha_ejecucion=self.jueves,
        )
        self.dia3.entreno_realizado = self.entreno3
        self.dia3.save(update_fields=["entreno_realizado", "actualizada_en"])

    def test_entreno_pospuesto_no_cierra_sesion_original_de_la_fecha(self):
        _marcar_completadas(self.cliente, self.viernes)

        self.dia4.refresh_from_db()
        self.assertEqual(self.dia4.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.dia4.fecha_realizada)
        self.assertIsNone(self.dia4.entreno_realizado_id)

    def test_un_entreno_vinculado_no_puede_cerrar_otra_sesion(self):
        self.dia4.nombre_sesion = self.dia3.nombre_sesion
        self.dia4.save(update_fields=["nombre_sesion", "actualizada_en"])

        _marcar_completadas(self.cliente, self.viernes)

        self.dia4.refresh_from_db()
        self.assertEqual(self.dia4.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.dia4.entreno_realizado_id)


class RepararSesionesProgramadasCommandTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="reparar-pospuesta")
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={"nombre": "Reparar"})
        self.dia4 = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 9, 3),
            estado=SesionProgramada.ESTADO_COMPLETADA, fecha_realizada=date(2026, 9, 3),
            nombre_sesion="Dia 4 - Fuerza — Avanzada", dia_numero=4,
        )
        self.dia5 = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 9, 4),
            nombre_sesion="Dia 5 - Fuerza — Avanzada", dia_numero=5,
        )
        rutina5 = Rutina.objects.create(nombre=self.dia5.nombre_sesion)
        self.entreno5 = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina5,
            fecha=date(2026, 9, 4), fecha_ejecucion=date(2026, 9, 4),
        )

    def _call(self, apply=False):
        return call_command(
            "reparar_sesiones_programadas",
            cliente=self.cliente.pk,
            restaurar_sesion=self.dia4.pk,
            vincular_sesion=self.dia5.pk,
            entreno=self.entreno5.pk,
            apply=apply,
            stdout=StringIO(),
        )

    def test_dry_run_es_el_modo_por_defecto_y_no_escribe(self):
        self._call()
        self.dia4.refresh_from_db()
        self.dia5.refresh_from_db()
        self.assertEqual(self.dia4.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(self.dia5.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.dia5.entreno_realizado_id)

    def test_apply_restaura_y_vincula_de_forma_idempotente(self):
        self._call(apply=True)
        self._call(apply=True)

        self.dia4.refresh_from_db()
        self.dia5.refresh_from_db()
        self.assertEqual(self.dia4.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.dia4.fecha_realizada)
        self.assertIsNone(self.dia4.entreno_realizado_id)
        self.assertEqual(self.dia5.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(self.dia5.fecha_realizada, date(2026, 9, 4))
        self.assertEqual(self.dia5.entreno_realizado_id, self.entreno5.pk)

    def test_sesion_restaurada_sigue_siendo_autoridad_el_sabado(self):
        self._call(apply=True)
        # Las señales de creación del Cliente pueden materializar sesiones de apoyo
        # ajenas a este escenario. La regresión solo compara las dos sesiones del
        # contrato que estamos reparando.
        SesionProgramada.objects.filter(cliente=self.cliente).exclude(
            pk__in=[self.dia4.pk, self.dia5.pk],
        ).update(estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        cache.set(f"sesion_sync_{self.cliente.pk}_2026-09-05", True, 60)

        decision = obtener_sesion_recomendada_hoy(
            self.cliente,
            date(2026, 9, 5),
        )

        self.dia4.refresh_from_db()
        self.assertEqual(decision["tipo"], "pendiente")
        self.assertEqual(decision["estado"], "entrenar")
        self.assertEqual(decision["sesion_programada"].pk, self.dia4.pk)
        self.assertEqual(self.dia4.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.dia4.entreno_realizado_id)

    def test_rechaza_entreno_incompatible_por_nombre(self):
        self.entreno5.rutina.nombre = "Dia 3 - Fuerza — Avanzada"
        self.entreno5.rutina.save(update_fields=["nombre"])
        with self.assertRaises(CommandError):
            self._call(apply=True)
