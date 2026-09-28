"""Contrato de las series de aproximación en el registro activo."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, RecordPersonal, SerieRealizada
from entrenos.services.decision_log_service import _rendimiento_representativo_desde_series
from rutinas.models import EjercicioBase, Rutina


class SeriesAproximacionPostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("aproximacion-user", password="secret")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.rutina = Rutina.objects.create(nombre="Aproximaciones")
        self.base = EjercicioBase.objects.create(
            nombre="Press aproximaciones", grupo_muscular="Pecho"
        )
        self.url = reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk])

    def _post(self):
        return self.client.post(self.url, {
            "fecha": date.today().isoformat(),
            "rutina_nombre": self.rutina.nombre,
            "ej1_nombre": self.base.nombre,
            "ej1_tipo_progresion": "peso_reps",
            # La primera se conserva como aproximación; la segunda es trabajo.
            "ej1_peso_1": "100", "ej1_reps_1": "8", "ej1_rpe_1": "6",
            "ej1_completado_1": "1", "ej1_aproximacion_1": "1",
            "ej1_peso_2": "60", "ej1_reps_2": "10", "ej1_rpe_2": "8",
            "ej1_completado_2": "1",
            "motivo_cierre": "tiempo",
        })

    def test_aproximacion_se_guarda_pero_no_alimenta_volumen_rpe_ni_1rm(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)

        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        aproximacion = SerieRealizada.objects.get(entreno=entreno, serie_numero=1)
        trabajo = SerieRealizada.objects.get(entreno=entreno, serie_numero=2)
        self.assertTrue(aproximacion.es_aproximacion)
        self.assertFalse(trabajo.es_aproximacion)
        self.assertEqual(entreno.volumen_total_kg, Decimal("600.00"))

        agregado = EjercicioRealizado.objects.get(entreno=entreno)
        self.assertEqual(agregado.series, 1)
        self.assertEqual(agregado.rpe, 8)
        self.assertEqual(
            RecordPersonal.objects.get(
                cliente=self.cliente, ejercicio_nombre__iexact=self.base.nombre,
                tipo_record="peso_maximo", superado=False,
            ).valor,
            Decimal("60"),
        )
        rendimiento = _rendimiento_representativo_desde_series(
            entreno, self.base.nombre.lower()
        )
        self.assertEqual(rendimiento, (Decimal("60.00"), Decimal("10")))
        self.cliente.refresh_from_db()
        self.assertNotEqual(self.cliente.one_rm_data.get("press aproximaciones"), 0)
