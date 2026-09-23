import json
from datetime import date

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, SesionProgramada
from estiramientos.admin import EstiramientoPlanAdmin
from estiramientos.models import (
    EstiramientoEjercicio,
    EstiramientoPaso,
    EstiramientoPlan,
)


class EstiramientoPlanTaxonomiaTests(TestCase):
    def test_plan_tiene_modalidad_codigo_y_permite_repetir_fase(self):
        movilidad = EstiramientoPlan.objects.create(
            nombre="Movilidad global",
            codigo="mobility-recovery-global",
            modalidad="movilidad",
            fase="COMPLETO",
        )
        estiramiento = EstiramientoPlan.objects.create(
            nombre="Estiramiento completo",
            codigo="stretch-full-body",
            modalidad="estiramientos",
            fase="COMPLETO",
        )

        self.assertEqual(movilidad.modalidad, "movilidad")
        self.assertEqual(estiramiento.modalidad, "estiramientos")
        self.assertNotEqual(movilidad.codigo, estiramiento.codigo)
        self.assertEqual(
            EstiramientoPlan.objects.filter(fase="COMPLETO").count(),
            2,
        )


class CatalogoMovilidadSeedTests(TestCase):
    CODIGOS = {
        "mobility-recovery-global",
        "mobility-hip-ankle",
        "mobility-thoracic-shoulder",
        "mobility-lower-prep",
        "mobility-upper-prep",
    }

    def test_seed_crea_los_cinco_planes_con_pasos_ejecutables(self):
        call_command("seed_movilidad", verbosity=0)

        planes = EstiramientoPlan.objects.filter(modalidad="movilidad")
        self.assertSetEqual(set(planes.values_list("codigo", flat=True)), self.CODIGOS)
        for plan in planes:
            with self.subTest(plan=plan.codigo):
                self.assertTrue(plan.pasos.exists())
                self.assertFalse(plan.pasos.filter(duracion_segundos__lte=0).exists())
                self.assertFalse(plan.pasos.filter(ejercicio__activo=False).exists())

    def test_seed_es_idempotente_y_no_duplica_planes_ni_pasos(self):
        call_command("seed_movilidad", verbosity=0)
        foto_inicial = {
            plan.codigo: list(
                plan.pasos.order_by("orden").values_list(
                    "orden", "ejercicio__nombre", "duracion_segundos",
                )
            )
            for plan in EstiramientoPlan.objects.filter(modalidad="movilidad")
        }

        call_command("seed_movilidad", verbosity=0)

        self.assertEqual(
            EstiramientoPlan.objects.filter(modalidad="movilidad").count(), 5,
        )
        foto_final = {
            plan.codigo: list(
                plan.pasos.order_by("orden").values_list(
                    "orden", "ejercicio__nombre", "duracion_segundos",
                )
            )
            for plan in EstiramientoPlan.objects.filter(modalidad="movilidad")
        }
        self.assertEqual(foto_final, foto_inicial)

    def test_catalogos_de_movilidad_y_estiramientos_coexisten_por_codigo(self):
        call_command("seed_estiramientos", verbosity=0)
        call_command("seed_movilidad", verbosity=0)

        self.assertEqual(
            EstiramientoPlan.objects.filter(modalidad="estiramientos").count(), 3,
        )
        self.assertEqual(
            EstiramientoPlan.objects.filter(modalidad="movilidad").count(), 5,
        )
        self.assertEqual(
            EstiramientoPlan.objects.filter(fase="COMPLETO").count(), 2,
        )


class PanelMovilidadSeparadoTests(TestCase):
    def setUp(self):
        self.movilidad = self._crear_plan(
            nombre="Movilidad cadera",
            codigo="mobility-hip-ankle",
            modalidad="movilidad",
        )
        self.estiramiento = self._crear_plan(
            nombre="Estiramiento inferior",
            codigo="stretch-lower",
            modalidad="estiramientos",
        )

    def _crear_plan(self, *, nombre, codigo, modalidad):
        plan = EstiramientoPlan.objects.create(
            nombre=nombre,
            codigo=codigo,
            modalidad=modalidad,
            fase="INFERIOR",
        )
        ejercicio = EstiramientoEjercicio.objects.create(
            nombre=f"Paso de {nombre}", fase_recomendada="INFERIOR",
        )
        EstiramientoPaso.objects.create(
            plan=plan, ejercicio=ejercicio, orden=1, duracion_segundos=30,
        )
        return plan

    def test_panel_separa_ambos_catalogos_sin_duplicar_tarjetas(self):
        response = self.client.get(reverse("estiramientos:panel"))

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["planes_movilidad"], [self.movilidad],
        )
        self.assertQuerySetEqual(
            response.context["planes_estiramientos"], [self.estiramiento],
        )
        self.assertContains(response, "Sesiones de movilidad")
        self.assertContains(response, "Sesiones de estiramientos")
        self.assertContains(response, f'data-plan-id="{self.movilidad.pk}"', count=1)
        self.assertContains(response, f'data-plan-id="{self.estiramiento.pk}"', count=1)


class SeguridadModalidadMovilidadTests(TestCase):
    HOY = date(2026, 9, 23)

    def setUp(self):
        self.user = User.objects.create_user("catalogo-movilidad", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Fuerza",
        )
        self.movilidad = self._crear_plan(
            "Movilidad global", "mobility-recovery-global", "movilidad",
        )
        self.estiramiento = self._crear_plan(
            "Estiramiento global", "stretch-recovery-global", "estiramientos",
        )

    def _crear_plan(self, nombre, codigo, modalidad):
        plan = EstiramientoPlan.objects.create(
            nombre=nombre,
            codigo=codigo,
            modalidad=modalidad,
            fase="COMPLETO",
        )
        ejercicio = EstiramientoEjercicio.objects.create(nombre=f"Paso {nombre}")
        EstiramientoPaso.objects.create(
            plan=plan, ejercicio=ejercicio, orden=1, duracion_segundos=45,
        )
        return plan

    def test_resoluciones_gym_solo_acompanan_planes_de_movilidad(self):
        response = self.client.get(
            reverse("estiramientos:panel"),
            {"sesion_programada_id": self.sesion.pk},
        )

        self.assertContains(response, "¿Qué hacemos con tu entrenamiento programado?", count=1)
        contenido = response.content.decode()
        url_movilidad = reverse("estiramientos:iniciar_plan", args=[self.movilidad.pk])
        url_estiramiento = reverse(
            "estiramientos:iniciar_plan", args=[self.estiramiento.pk],
        )
        self.assertIn(
            f'{url_movilidad}?sesion_programada_id=',
            contenido,
        )
        self.assertNotIn(
            f'{url_estiramiento}?sesion_programada_id=',
            contenido,
        )

    def test_endpoint_adaptativo_rechaza_completar_un_plan_de_estiramientos(self):
        response = self.client.post(
            reverse("estiramientos:completar_plan", args=[self.estiramiento.pk]),
            data=json.dumps({
                "fecha": self.HOY.isoformat(),
                "duracion_minutos": 10,
                "rpe": 2,
                "resolucion": "anadir",
                "idempotency_key": "stretch-no-es-mobility",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("movilidad", response.json()["error"].lower())
        self.assertFalse(ActividadRealizada.objects.exists())

    def test_movilidad_completada_crea_actividad_con_tipo_movilidad(self):
        response = self.client.post(
            reverse("estiramientos:completar_plan", args=[self.movilidad.pk]),
            data=json.dumps({
                "fecha": self.HOY.isoformat(),
                "duracion_minutos": 10,
                "rpe": 2,
                "resolucion": "anadir",
                "idempotency_key": "mobility-real-1",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ActividadRealizada.objects.get().tipo, "movilidad")


class EstiramientoPlanAdminTests(TestCase):
    def test_admin_muestra_y_permite_filtrar_modalidad_y_buscar_codigo(self):
        model_admin = EstiramientoPlanAdmin(EstiramientoPlan, admin.site)

        self.assertIn("modalidad", model_admin.list_display)
        self.assertIn("modalidad", model_admin.list_filter)
        self.assertIn("codigo", model_admin.search_fields)
