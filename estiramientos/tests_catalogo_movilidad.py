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


class PanelMovilidadFidelidadVisualTests(TestCase):
    """Contrato de contenido del catálogo editorial de recuperación."""

    def setUp(self):
        self.recomendada = self._crear_plan(
            "Movilidad global", "mobility-recovery-global", "COMPLETO",
        )
        self.cadera = self._crear_plan(
            "Cadera y tobillo", "mobility-hip-ankle", "INFERIOR",
        )
        self.columna = self._crear_plan(
            "Columna torácica y hombros", "mobility-thoracic-shoulder", "SUPERIOR",
        )

    def _crear_plan(self, nombre, codigo, fase):
        plan = EstiramientoPlan.objects.create(
            nombre=nombre,
            codigo=codigo,
            modalidad="movilidad",
            fase=fase,
        )
        ejercicio = EstiramientoEjercicio.objects.create(nombre=f"Paso de {nombre}")
        EstiramientoPaso.objects.create(
            plan=plan, ejercicio=ejercicio, orden=1, duracion_segundos=240,
        )
        return plan

    def test_panel_presenta_hero_editorial_y_evita_duplicar_la_recomendada(self):
        response = self.client.get(reverse("estiramientos:panel"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("recovery-hero-gym.png", content)
        self.assertIn('class="mv-hero__title"', content)
        self.assertIn("MOVILIDAD GLOBAL · 4 MIN", content)
        self.assertNotIn('data-plan-id="{}"'.format(self.recomendada.pk), content)
        self.assertIn('data-plan-id="{}"'.format(self.cadera.pk), content)
        self.assertIn('data-plan-id="{}"'.format(self.columna.pk), content)
        self.assertNotIn('class="plan-action"', content)

    def test_navegacion_mantiene_iconos_y_ahora_como_estado_activo(self):
        response = self.client.get(reverse("estiramientos:panel"))

        self.assertContains(response, 'class="mv-bottom-nav__icon"')
        self.assertContains(
            response,
            'class="mv-bottom-nav__item is-active" aria-current="page"',
        )

    def test_la_composicion_editorial_usa_serif_regla_e_iconos_svg_propios(self):
        response = self.client.get(reverse("estiramientos:panel"))

        content = response.content.decode()
        self.assertIn('class="mv-hero__rule"', content)
        self.assertIn('<svg class="mv-hero__cta-icon"', content)
        self.assertIn('<svg class="plan-chevron"', content)
        self.assertIn('<svg class="mv-bottom-nav__icon"', content)
        self.assertNotIn('fas fa-chevron-right', content)
        self.assertNotIn('fas fa-house', content)

    def test_las_dos_tarjetas_visibles_se_seleccionan_por_codigo_editorial(self):
        # Un plan alfabéticamente anterior no puede desplazar la pareja
        # editorial Cadera + Columna que sigue a la CTA principal.
        extra = self._crear_plan(
            "Activación aleatoria", "mobility-random-editorial", "COMPLETO",
        )
        response = self.client.get(reverse("estiramientos:panel"))

        content = response.content.decode()
        cadera_at = content.index(f'data-plan-id="{self.cadera.pk}"')
        columna_at = content.index(f'data-plan-id="{self.columna.pk}"')
        extra_at = content.index(f'data-plan-id="{extra.pk}"')
        self.assertLess(cadera_at, columna_at)
        self.assertLess(columna_at, extra_at)

    def test_la_cta_y_las_tarjetas_destacadas_tienen_un_contrato_explicito(self):
        """El orden de la BD no puede decidir la narrativa de recuperación."""
        extra = self._crear_plan(
            "Antes alfabéticamente", "mobility-a-random", "COMPLETO",
        )

        response = self.client.get(reverse("estiramientos:panel"))

        self.assertEqual(response.context["hero_mobility_plan"], self.recomendada)
        self.assertQuerySetEqual(
            response.context["featured_mobility_plans"],
            [self.cadera, self.columna],
            ordered=True,
        )
        self.assertQuerySetEqual(
            response.context["remaining_mobility_plans"], [extra], ordered=True,
        )

    def test_iconos_anatomicos_se_asignan_por_codigo_y_no_por_fase_generica(self):
        response = self.client.get(reverse("estiramientos:panel"))
        content = response.content.decode()

        self.assertIn("plan-card--hip-ankle", content)
        self.assertIn("plan-card--thoracic-shoulder", content)
        self.assertIn("plan-icon--hip-ankle", content)
        self.assertIn("plan-icon--thoracic-shoulder", content)
        self.assertIn('data-plan-icon="hip-ankle"', content)
        self.assertIn('data-plan-icon="thoracic-shoulder"', content)

    def test_tarjetas_destacadas_exponen_copy_e_iconografia_del_pase_final(self):
        """La portada conserva su lectura editorial sin mutar el catálogo."""
        self.cadera.descripcion = "Texto técnico de la base de datos."
        self.cadera.save(update_fields=["descripcion"])
        self.columna.descripcion = "Otro texto técnico de la base de datos."
        self.columna.save(update_fields=["descripcion"])

        response = self.client.get(reverse("estiramientos:panel"))
        content = response.content.decode()

        self.assertIn("Más rango de movimiento, menos rigidez.", content)
        self.assertIn("Libera tensión y mejora tu postura.", content)
        self.assertIn('data-plan-icon-detail="hip-ankle"', content)
        self.assertIn('data-plan-icon-detail="thoracic-shoulder"', content)
        self.assertIn('class="mv-editorial-close" aria-hidden="true"', content)


class PlayerMovilidadInmersivoTests(TestCase):
    """Contrato de composición del reproductor guiado de movilidad."""

    def setUp(self):
        self.plan = EstiramientoPlan.objects.create(
            nombre="Movilidad global",
            codigo="mobility-recovery-global-player",
            modalidad="movilidad",
            fase="COMPLETO",
        )
        primero = EstiramientoEjercicio.objects.create(
            nombre="Respiración 90/90 con alcance",
            musculo_objetivo="Respiración · caja torácica",
            descripcion_corta="Inhala por la nariz. Expande espalda y costillas.",
        )
        segundo = EstiramientoEjercicio.objects.create(nombre="Gato-vaca segmentado")
        EstiramientoPaso.objects.create(
            plan=self.plan, ejercicio=primero, orden=1, duracion_segundos=36,
        )
        EstiramientoPaso.objects.create(
            plan=self.plan, ejercicio=segundo, orden=2, duracion_segundos=40,
        )

    def test_player_expone_la_composicion_inmersiva_y_los_controles_reales(self):
        response = self.client.get(
            reverse("estiramientos:iniciar_plan", args=[self.plan.pk]),
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('class="player-container player-container--immersive"', content)
        self.assertIn('class="player-progress-segments"', content)
        self.assertIn('data-progress-segments', content)
        self.assertIn('class="exercise-stage"', content)
        self.assertIn('id="exerciseImage"', content)
        self.assertIn('id="noImagePlaceholder"', content)
        self.assertIn('class="timer-overlay"', content)
        self.assertIn('id="timerSeconds"', content)
        self.assertIn('class="exercise-name"', content)
        self.assertIn('class="next-exercise"', content)
        self.assertIn('id="nextExerciseName"', content)
        self.assertIn('id="btnRestart"', content)
        self.assertIn('id="btnPause"', content)
        self.assertIn('id="btnSkip"', content)
        self.assertIn('id="btnFinishEarly"', content)
        self.assertNotIn('class="player-header"', content)

    def test_player_asigna_ilustracion_estatica_a_ejercicio_canonico_sin_upload(self):
        """El reproductor no cae al placeholder para los cinco pasos editoriales."""
        primero = self.plan.pasos.get(orden=1)
        primero.ejercicio.nombre = "CARs de cadera en cuadrupedia"
        primero.ejercicio.save(update_fields=["nombre"])

        response = self.client.get(
            reverse("estiramientos:iniciar_plan", args=[self.plan.pk]),
        )

        steps = json.loads(response.context["steps"])
        self.assertEqual(
            steps[0]["image"],
            "/static/estiramientos/images/mobility/hip-cars.png",
        )

    def test_player_prioriza_imagen_subida_sobre_ilustracion_estatica(self):
        """Una imagen curada en el ejercicio siempre prevalece sobre el fallback."""
        primero = self.plan.pasos.get(orden=1)
        primero.ejercicio.nombre = "CARs de cadera en cuadrupedia"
        primero.ejercicio.imagen = "estiramientos/hip-cars-propia.png"
        primero.ejercicio.save(update_fields=["nombre", "imagen"])

        response = self.client.get(
            reverse("estiramientos:iniciar_plan", args=[self.plan.pk]),
        )

        steps = json.loads(response.context["steps"])
        self.assertEqual(steps[0]["image"], "/media/estiramientos/hip-cars-propia.png")


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
