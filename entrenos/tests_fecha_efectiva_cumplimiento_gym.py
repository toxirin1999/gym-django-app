from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado, SesionProgramada
from entrenos.services.sesion_recomendada import _fecha_completada, _marcar_completadas
from rutinas.models import Programa, Rutina


class FechaEfectivaCumplimientoGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="fecha_efectiva_gym")
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user,
            defaults={"nombre": "Fecha efectiva", "dias_disponibles": 5},
        )
        programa = Programa.objects.create(nombre="Programa fecha efectiva")
        self.rutina = Rutina.objects.create(
            programa=programa,
            nombre="Día efectivo",
        )
        self.fecha_plan = date(2026, 8, 10)
        self.fecha_real = date(2026, 8, 11)
        self.hoy = self.fecha_real + timedelta(days=1)

    def _entreno(self, *, fecha_ejecucion):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.fecha_plan,
            fecha_ejecucion=fecha_ejecucion,
        )

    def _actividad(self, *, fecha_realizado):
        return ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo="gym",
            titulo="Día efectivo",
            fecha=self.fecha_plan,
            fecha_realizado=fecha_realizado,
        )

    def _pendiente(self, fecha):
        return SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=fecha,
            nombre_sesion="",
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )

    def test_fecha_completada_actividad_usa_fecha_realizado_como_fallback_exclusivo(self):
        self._actividad(fecha_realizado=self.fecha_real)

        self.assertFalse(_fecha_completada(self.cliente, self.fecha_plan))
        self.assertTrue(_fecha_completada(self.cliente, self.fecha_real))

    def test_fecha_completada_actividad_sin_fecha_realizado_usa_fecha(self):
        self._actividad(fecha_realizado=None)

        self.assertTrue(_fecha_completada(self.cliente, self.fecha_plan))

    def test_fecha_completada_entreno_usa_fecha_ejecucion_como_fallback_exclusivo(self):
        self._entreno(fecha_ejecucion=self.fecha_real)

        self.assertFalse(_fecha_completada(self.cliente, self.fecha_plan))
        self.assertTrue(_fecha_completada(self.cliente, self.fecha_real))

    def test_fecha_completada_excluye_actividad_no_gym(self):
        actividad = self._actividad(fecha_realizado=self.fecha_real)
        actividad.tipo = "futbol"
        actividad.save(update_fields=["tipo"])

        self.assertFalse(_fecha_completada(self.cliente, self.fecha_real))

    def test_fecha_completada_no_anticipa_una_actividad_futura(self):
        self._actividad(fecha_realizado=self.fecha_real + timedelta(days=1))

        self.assertFalse(_fecha_completada(self.cliente, self.fecha_real))

    def test_batch_entreno_usa_fecha_ejecucion_y_no_fecha_planificada(self):
        planificada = self._pendiente(self.fecha_plan)
        efectiva = self._pendiente(self.fecha_real)
        self._entreno(fecha_ejecucion=self.fecha_real)

        _marcar_completadas(self.cliente, self.hoy)

        planificada.refresh_from_db()
        efectiva.refresh_from_db()
        self.assertEqual(planificada.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(efectiva.estado, SesionProgramada.ESTADO_COMPLETADA)

    def test_batch_actividad_usa_fecha_realizado_y_no_fecha_planificada(self):
        planificada = self._pendiente(self.fecha_plan)
        efectiva = self._pendiente(self.fecha_real)
        self._actividad(fecha_realizado=self.fecha_real)

        _marcar_completadas(self.cliente, self.hoy)

        planificada.refresh_from_db()
        efectiva.refresh_from_db()
        self.assertEqual(planificada.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(efectiva.estado, SesionProgramada.ESTADO_COMPLETADA)

    def test_batch_sin_fecha_efectiva_conserva_fallback_legacy(self):
        pendiente = self._pendiente(self.fecha_plan)
        self._entreno(fecha_ejecucion=None)

        _marcar_completadas(self.cliente, self.hoy)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, SesionProgramada.ESTADO_COMPLETADA)

    def test_batch_entreno_y_hub_mismo_esfuerzo_tienen_un_unico_efecto(self):
        pendiente = self._pendiente(self.fecha_real)
        entreno = self._entreno(fecha_ejecucion=self.fecha_real)
        hub = entreno.hub_actividad
        hub.fecha = self.fecha_plan
        hub.fecha_realizado = self.fecha_real
        hub.save(
            update_fields=["fecha", "fecha_realizado"],
        )

        _marcar_completadas(self.cliente, self.hoy)
        _marcar_completadas(self.cliente, self.hoy)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(pendiente.fecha_realizada, self.fecha_real)
        self.assertEqual(
            SesionProgramada.objects.filter(cliente=self.cliente).count(),
            1,
        )
