from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import SesionProgramada
from estiramientos.models import EstiramientoEjercicio, EstiramientoPaso, EstiramientoPlan


class SeedCardioZ2Tests(TestCase):
    CODIGOS = {"cardio-z2-bici-remo", "cardio-z2-caminata-inclinada"}

    def test_seed_crea_los_planes_de_cardio_con_pasos_ejecutables(self):
        call_command("seed_cardio_z2", verbosity=0)

        planes = EstiramientoPlan.objects.filter(fase="CARDIO")
        self.assertSetEqual(set(planes.values_list("codigo", flat=True)), self.CODIGOS)
        for plan in planes:
            with self.subTest(plan=plan.codigo):
                self.assertEqual(plan.modalidad, EstiramientoPlan.MODALIDAD_MOVILIDAD)
                self.assertTrue(plan.pasos.exists())
                self.assertFalse(plan.pasos.filter(duracion_segundos__lte=0).exists())

    def test_seed_es_idempotente(self):
        call_command("seed_cardio_z2", verbosity=0)
        call_command("seed_cardio_z2", verbosity=0)

        self.assertEqual(EstiramientoPlan.objects.filter(fase="CARDIO").count(), 2)

    def test_duracion_estimada_suma_los_pasos_reales_no_solo_los_cuenta(self):
        call_command("seed_cardio_z2", verbosity=0)

        bici_remo = EstiramientoPlan.objects.get(codigo="cardio-z2-bici-remo")
        self.assertEqual(bici_remo.nombre, "Bici / Remo Zona 2")
        self.assertEqual(bici_remo.descripcion, "Enfoque regenerativo FC < 130 bpm")
        self.assertEqual(bici_remo.pasos.count(), 1)
        self.assertEqual(bici_remo.duracion_estimada_min, 30)

        caminata = EstiramientoPlan.objects.get(codigo="cardio-z2-caminata-inclinada")
        self.assertEqual(caminata.nombre, "Caminata Inclinada Activa")
        self.assertEqual(caminata.descripcion, "Ritmo constante Z2")
        self.assertEqual(caminata.pasos.count(), 1)
        self.assertEqual(caminata.duracion_estimada_min, 20)


class PanelCardioZ2Tests(TestCase):
    def setUp(self):
        call_command("seed_cardio_z2", verbosity=0)
        self.movilidad = EstiramientoPlan.objects.create(
            nombre="Movilidad cadera", codigo="mobility-hip-ankle-cardio-test",
            modalidad="movilidad", fase="INFERIOR",
        )

    def test_panel_separa_cardio_de_movilidad_regular(self):
        response = self.client.get(reverse("estiramientos:panel"))

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["planes_cardio"],
            EstiramientoPlan.objects.filter(fase="CARDIO").order_by("nombre"),
        )
        self.assertNotIn(self.movilidad, response.context["planes_cardio"])
        self.assertIn(self.movilidad, response.context["planes_movilidad"])
        self.assertContains(response, "03 CARDIO")
        self.assertContains(response, "Sesiones de cardio")
        self.assertContains(response, "Cardio Z2")
        self.assertContains(response, "Bici / Remo Zona 2")
        self.assertContains(response, "Caminata Inclinada Activa")
        self.assertNotContains(response, "No hay sesiones de cardio disponibles.")


class SustitucionAutomaticaHoyTests(TestCase):
    HOY = date.today()

    def setUp(self):
        self.user = User.objects.create_user("cardio-swap-hoy", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.sesion_hoy = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Fuerza de hoy",
        )
        self.plan = EstiramientoPlan.objects.create(
            nombre="Movilidad completa", codigo="mobility-swap-today-test",
            modalidad="movilidad", fase="COMPLETO",
        )
        ejercicio = EstiramientoEjercicio.objects.create(nombre="Paso swap hoy")
        EstiramientoPaso.objects.create(
            plan=self.plan, ejercicio=ejercicio, orden=1, duracion_segundos=60,
        )

    def test_checkbox_de_sustitucion_aparece_sin_parametro_de_url(self):
        response = self.client.get(reverse("estiramientos:panel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sesion_hoy"], self.sesion_hoy)
        self.assertContains(response, 'id="mobilitySwapToday"')
        self.assertContains(
            response, "Contabilizar como sustituto de la sesión de fuerza de hoy",
        )
        self.assertContains(
            response, f'data-sesion-hoy-id="{self.sesion_hoy.id}"',
        )
        self.assertContains(response, 'id="mobilitySwapHint"')
        self.assertContains(
            response,
            "Reemplazará la sesión de fuerza programada para hoy en tu planning semanal",
        )
        # No debe pisar el flujo ya existente de "3 resoluciones" por URL.
        self.assertNotContains(response, "¿Qué hacemos con tu entrenamiento programado?")

    def test_checkbox_no_aparece_cuando_ya_hay_sesion_programada_por_url(self):
        response = self.client.get(
            reverse("estiramientos:panel"),
            {"sesion_programada_id": self.sesion_hoy.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["sesion_hoy"])
        self.assertNotContains(response, 'id="mobilitySwapToday"')

    def test_checkbox_no_aparece_sin_sesion_pendiente_hoy(self):
        self.sesion_hoy.estado = SesionProgramada.ESTADO_COMPLETADA
        self.sesion_hoy.save(update_fields=["estado"])

        response = self.client.get(reverse("estiramientos:panel"))

        self.assertIsNone(response.context["sesion_hoy"])
        self.assertNotContains(response, 'id="mobilitySwapToday"')
