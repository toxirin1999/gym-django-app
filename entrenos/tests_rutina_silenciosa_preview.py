"""Contrato de la preview compacta de Rutina.

La preview no reemplaza al calendario histórico: ofrece una entrada móvil y
debe conservar siempre los destinos profundos de planificación y movilidad.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import SesionProgramada


class RutinaSilenciosaPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rutina-silenciosa", password="secreto"
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id])

    def test_anonimo_es_redirigido_a_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_dueno_puede_renderizar_contexto_real_del_plan(self):
        """El modo móvil usa el contrato real del plan, no solo el mock del test."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fase actual")
        self.assertContains(response, "Elegir día")

    @patch("entrenos.views._obtener_contexto_rutina_silenciosa")
    def test_dueno_ve_fase_hoy_y_destinos_reales(self, contexto):
        contexto.return_value = {
            "fase": {"nombre": "DESCARGA ACTIVA", "objetivo": "Recuperación activa"},
            "semana": [{"numero": 26, "fecha": date(2026, 9, 26), "es_hoy": True}],
            "hoy": {"tipo": "descanso", "titulo": "Día de descanso", "detalle": "El plan no programa entreno hoy."},
            "rms": [{"nombre": "Press banca", "valor": 100}],
            "insight": "La descarga protege tu adaptación.",
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "entrenos/rutina_silenciosa_preview.html")
        self.assertContains(response, "DESCARGA ACTIVA")
        self.assertContains(response, "Día de descanso")
        self.assertContains(response, "La descarga protege tu adaptación.")
        self.assertContains(response, reverse("entrenos:vista_plan_anual", args=[self.cliente.id]))
        self.assertContains(response, reverse("clientes:trayectoria_plan"))
        self.assertContains(response, reverse("estiramientos:panel"))
        self.assertContains(response, 'data-day-preview="0"')
        self.assertContains(response, 'id="routine-day-modal"')

    def test_otro_usuario_no_puede_ver_la_preview(self):
        otro = get_user_model().objects.create_user(
            username="intruso-rutina", password="secreto"
        )
        self.client.force_login(otro)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_sesion_pospuesta_hasta_hoy_es_la_accion_del_dia(
        self, planificador, educacion,
    ):
        """La fecha efectiva, no la prescrita, decide la Rutina de hoy."""
        hoy = date(2026, 9, 26)
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 9, 25),
            pospuesta_hasta=hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Torso pospuesto",
        )
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [{"nombre": "Descarga", "duracion": 52}],
        }
        educacion.side_effect = lambda plan: plan

        from entrenos.views import _obtener_contexto_rutina_silenciosa

        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)

        self.assertEqual(contexto["hoy"]["tipo"], "sesion")
        self.assertEqual(contexto["hoy"]["titulo"], "Torso pospuesto")
        self.assertIn("sesion_programada_id=", contexto["hoy"]["url"])
        sabado = next(dia for dia in contexto["semana"] if dia["fecha"] == hoy)
        self.assertEqual(sabado["tipo"], "sesion")

    @patch("entrenos.views._calcular_ejercicios_dia")
    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_dia_pospuesto_tiene_preview_y_cta_con_identidad_original(
        self, planificador, educacion, calcular_ejercicios,
    ):
        """El selector abre el día efectivo sin perder su sesión prescrita."""
        hoy = date(2026, 9, 26)
        sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 9, 25),
            pospuesta_hasta=hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Torso pospuesto",
        )
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [{"nombre": "Descarga", "duracion": 52}],
        }
        educacion.side_effect = lambda plan: plan
        calcular_ejercicios.return_value = [{
            "nombre": "Press inclinado", "series": 3,
            "reps_objetivo": 10, "peso_recomendado_kg": 40,
        }]

        from entrenos.views import _obtener_contexto_rutina_silenciosa
        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)
        sabado = next(dia for dia in contexto["semana"] if dia["fecha"] == hoy)

        self.assertEqual(sabado["preview"]["sesion_programada_id"], sesion.pk)
        self.assertEqual(sabado["preview"]["fecha_efectiva"], "2026-09-26")
        self.assertIn("sesion_programada_id={}".format(sesion.pk), sabado["preview"]["url"])
        self.assertEqual(sabado["preview"]["ejercicios"][0]["nombre"], "Press inclinado")
        calcular_ejercicios.assert_called_once_with(
            self.cliente.id, date(2026, 9, 25),
        )

    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_plan_helms_sin_sesion_programada_da_preview_del_dia(
        self, planificador, educacion,
    ):
        """Un hueco de SesionProgramada no convierte un entreno Helms en descanso."""
        hoy = date(2026, 9, 25)
        cache.delete(f"plan_anual_{self.cliente.id}_{hoy.year}")
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [{"nombre": "Descarga", "duracion": 52}],
            "entrenos_por_fecha": {
                "2026-09-25": {
                    "nombre_rutina": "Día 5 - Descarga activa",
                    "ejercicios": [{
                        "nombre": "Press inclinado", "series": 3,
                        "repeticiones": "10-15", "peso_kg": 40,
                    }],
                },
            },
        }
        educacion.side_effect = lambda plan: plan

        from entrenos.views import _obtener_contexto_rutina_silenciosa
        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)
        viernes = next(dia for dia in contexto["semana"] if dia["fecha"] == hoy)

        self.assertEqual(viernes["tipo"], "sesion")
        self.assertEqual(viernes["preview"]["titulo"], "Día 5 - Descarga activa")
        self.assertEqual(viernes["preview"]["ejercicios"][0]["nombre"], "Press inclinado")
        self.assertEqual(viernes["preview"]["fecha_efectiva"], "2026-09-25")
        self.assertIn("?fecha=2026-09-25", viernes["preview"]["url"])
        self.assertNotIn("sesion_programada_id", viernes["preview"]["url"])
        self.assertEqual(contexto["hoy"]["tipo"], "sesion")

    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_sesion_cerrada_no_resucita_desde_plan_helms(
        self, planificador, educacion,
    ):
        """El fallback sólo cubre sesiones no materializadas, nunca historial cerrado."""
        hoy = date(2026, 9, 25)
        cache.delete(f"plan_anual_{self.cliente.id}_{hoy.year}")
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=hoy,
            estado=SesionProgramada.ESTADO_COMPLETADA,
            nombre_sesion="Sesión ya cerrada",
        )
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [{"nombre": "Descarga", "duracion": 52}],
            "entrenos_por_fecha": {
                hoy.isoformat(): {
                    "nombre_rutina": "Día 5 - Descarga activa",
                    "ejercicios": [{"nombre": "Press", "series": 3}],
                },
            },
        }
        educacion.side_effect = lambda plan: plan

        from entrenos.views import _obtener_contexto_rutina_silenciosa
        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)
        viernes = next(dia for dia in contexto["semana"] if dia["fecha"] == hoy)

        self.assertEqual(viernes["tipo"], "descanso")

    def test_selector_renderiza_dialogo_local_y_no_enlaza_dias_al_calendario(self):
        """El calendario legado es explícito; los días abren una preview local."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text()

        self.assertIn('data-day-preview', plantilla)
        self.assertIn('role="dialog"', plantilla)
        self.assertIn('id="routine-day-modal"', plantilla)
        self.assertNotIn('href="{{ calendario_url }}?año={{ dia.fecha.year }}', plantilla)

    def test_navegacion_global_de_rutina_vuelve_a_la_preview_no_al_calendario(self):
        """Rutina es una sección global; el calendario queda como acceso interno."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text()

        self.assertIn(
            "href=\"{% url 'entrenos:rutina_silenciosa_preview' cliente.id %}\"",
            plantilla,
        )
