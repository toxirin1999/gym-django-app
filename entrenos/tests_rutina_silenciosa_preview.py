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
            "hoy": {
                "tipo": "descanso", "titulo": "Día de descanso",
                "detalle": "El plan no programa entreno hoy.",
                "url": reverse("estiramientos:panel"), "cta": "Movilidad y estiramientos",
            },
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

    @patch("entrenos.views._obtener_contexto_rutina_silenciosa")
    def test_semana_previa_se_normaliza_a_lunes_y_se_expone_en_url(self, contexto):
        """La navegación semanal acepta cualquier día, pero comparte su lunes."""
        contexto.return_value = {
            "fase": {"nombre": "DESCARGA", "objetivo": "Recuperar"},
            "semana": [], "hoy": {"tipo": "descanso", "titulo": "Descanso", "detalle": ""},
            "rms": [], "insight": "Margen.",
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"semana": "2026-09-23"})

        self.assertEqual(response.status_code, 200)
        contexto.assert_called_once()
        self.assertEqual(contexto.call_args.kwargs["semana_inicio"], date(2026, 9, 21))
        self.assertEqual(response.context["semana_inicio"], date(2026, 9, 21))
        self.assertEqual(response.context["semana_anterior_url"], f"{self.url}?semana=2026-09-14")
        self.assertEqual(response.context["semana_siguiente_url"], f"{self.url}?semana=2026-09-28")

    @patch("entrenos.views._obtener_contexto_rutina_silenciosa")
    def test_semana_siguiente_cruza_mes_y_conserva_parametro_compartible(self, contexto):
        """La siguiente semana no depende del mes visible del calendario legado."""
        contexto.return_value = {
            "fase": {"nombre": "DESCARGA", "objetivo": "Recuperar"},
            "semana": [], "hoy": {"tipo": "descanso", "titulo": "Descanso", "detalle": ""},
            "rms": [], "insight": "Margen.",
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"semana": "2026-09-28"})

        self.assertEqual(response.context["semana_inicio"], date(2026, 9, 28))
        self.assertEqual(response.context["semana_siguiente_url"], f"{self.url}?semana=2026-10-05")
        self.assertContains(response, "28 Sep – 4 Oct")

    @patch("entrenos.views._obtener_contexto_rutina_silenciosa")
    def test_semana_siguiente_cruza_ano_sin_perder_el_lunes_en_url(self, contexto):
        """La semana del cambio de año continúa en la misma pantalla."""
        contexto.return_value = {
            "fase": {"nombre": "BASE", "objetivo": "Continuidad"},
            "semana": [], "hoy": {"tipo": "descanso", "titulo": "Descanso", "detalle": ""},
            "rms": [], "insight": "Margen.",
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"semana": "2026-12-30"})

        self.assertEqual(response.context["semana_inicio"], date(2026, 12, 28))
        self.assertEqual(response.context["semana_siguiente_url"], f"{self.url}?semana=2027-01-04")
        self.assertContains(response, "28 Dic – 3 Ene")

    def test_controles_semanales_son_accesibles_y_no_abren_el_calendario_legado(self):
        """Cambiar de semana ocurre en Rutina; el calendario sigue siendo opcional."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.assertIn('class="week-nav"', plantilla)
        self.assertIn('aria-label="Semana anterior"', plantilla)
        self.assertIn('aria-label="Semana siguiente"', plantilla)
        self.assertIn('href="{{ semana_anterior_url }}"', plantilla)
        self.assertIn('href="{{ semana_siguiente_url }}"', plantilla)

    def test_selector_de_dias_usa_semantica_de_pestanas_en_lugar_de_botones_toggle(self):
        """Solo hay una previsualización activa: aria-selected describe ese estado."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.assertIn('role="tablist"', plantilla)
        self.assertIn('role="tab"', plantilla)
        self.assertIn('aria-selected=', plantilla)
        self.assertNotIn('aria-pressed=', plantilla)

    def test_preview_del_dia_abre_primero_con_datos_locales_y_se_hidrata_despues(self):
        """La red legacy no puede retrasar ni reabrir el modal de Rutina."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        apertura_local = "renderPreview(preview, { openModal: true });"
        hidratacion_remota = "resolverPreviewLegacy(preview).then(previewCanonica =>"
        self.assertIn('id="routine-day-sync-status"', plantilla)
        self.assertIn('role="status"', plantilla)
        self.assertIn(apertura_local, plantilla)
        self.assertIn(hidratacion_remota, plantilla)
        self.assertLess(plantilla.index(apertura_local), plantilla.index(hidratacion_remota))
        self.assertIn("if (openModal && !modal.open)", plantilla)

    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_fase_traduce_el_identificador_interno_antes_de_mostrarlo(
        self, planificador, educacion,
    ):
        hoy = date(2026, 1, 5)
        cache.delete(f"plan_anual_{self.cliente.id}_{hoy.year}")
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [
                {"nombre": "Metabólica", "objetivo": "hipertrofia_metabolica", "duracion": 8},
            ],
        }
        educacion.side_effect = lambda plan: plan

        from entrenos.views import _obtener_contexto_rutina_silenciosa

        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)

        self.assertEqual(contexto["fase"]["objetivo"], "Hipertrofia metabólica")

    @patch("entrenos.views.agregar_educacion_a_plan")
    @patch("entrenos.views.PlanificadorHelms")
    def test_fase_usa_los_rangos_precisos_del_mismo_plan_anual(
        self, planificador, educacion,
    ):
        hoy = date(2026, 1, 5)
        cache.delete(f"plan_anual_{self.cliente.id}_{hoy.year}")
        planificador.return_value.generar_plan_anual.return_value = {
            "plan_por_bloques": [
                {"nombre": "Metabólica", "objetivo": "hipertrofia_metabolica", "duracion": 8},
            ],
            "metadata": {"periodizacion_completa": [
                {"nombre": "Metabólica", "rpe_inicio": 7, "rpe_fin": 8, "rep_range": "12-15"},
            ]},
        }
        educacion.side_effect = lambda plan: plan

        from entrenos.views import _obtener_contexto_rutina_silenciosa

        contexto = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=hoy)

        self.assertEqual(contexto["fase"]["rpe"], "7–8")
        self.assertEqual(contexto["fase"]["reps"], "12-15")

    def test_preview_de_sesion_sin_ejercicios_explica_el_siguiente_paso(self):
        """Una sesión materializada sin detalle no puede abrir un modal vacío.

        Puede ocurrir antes de que el calendario legado hidrate los ejercicios
        o cuando la sesión se creó sin prescripción local. El CTA sigue siendo
        válido, pero la pantalla debe explicar por qué aún no hay lista.
        """
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.assertIn("const hasExercises = (preview.ejercicios || []).length > 0;", plantilla)
        self.assertIn("empty.hidden = hasExercises;", plantilla)
        self.assertIn(
            "La sesión está preparada. Ábrela para revisar el detalle antes de empezar.",
            plantilla,
        )

    def test_dialogo_de_preview_cierra_con_escape_y_devuelve_el_foco_al_dia(self):
        """Cerrar no deja el teclado perdido detrás del diálogo nativo.

        El mismo cierre centralizado cubre el botón, el fondo y Escape; tras
        cerrar, el selector que abrió la preview recupera el foco para seguir
        recorriendo la semana sin empezar desde el principio de la página.
        """
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.assertIn("let opener = null;", plantilla)
        self.assertIn("opener = button;", plantilla)
        self.assertIn("modal.addEventListener('cancel'", plantilla)
        self.assertIn("event.preventDefault();", plantilla)
        self.assertIn("modal.addEventListener('close'", plantilla)
        self.assertIn("if (trigger && trigger.isConnected) trigger.focus();", plantilla)
        self.assertIn(".modal-close:focus-visible", plantilla)

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

    def test_selector_hace_visible_el_dia_elegido_y_anuncia_la_preview(self):
        """Pulsar un día no puede parecer un control inerte antes del modal."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.assertIn('aria-selected="{% if dia.es_hoy %}true{% else %}false{% endif %}"', plantilla)
        self.assertIn('class="selector-status" data-day-selection aria-live="polite"', plantilla)
        self.assertIn("function seleccionarDia(button, preview)", plantilla)
        self.assertIn("day.classList.toggle('is-selected', selected)", plantilla)
        self.assertIn("day.setAttribute('aria-selected', String(selected));", plantilla)
        self.assertIn("seleccionarDia(button, preview);", plantilla)

    def test_selector_consulta_el_contrato_ajax_del_calendario_para_el_dia_elegido(self):
        """La preview móvil no duplica el plan: lee el mismo JSON del calendario.

        El plan anual legado ya resuelve sesiones materializadas, aplazamientos y
        la prescripción Helms. Cada pulsación debe sustituir el preview inicial
        por ``entrenamientos[YYYY-MM-DD]`` de ese contrato y conservar los
        parámetros que consume el briefing.
        """
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text(encoding="utf-8")

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertContains(
            response,
            reverse("entrenos:ajax_entrenamientos_mes", args=[self.cliente.id]),
        )
        self.assertIn('const entrenamientosMesUrl = "{{ entrenamientos_mes_url }}"', plantilla)
        self.assertIn("const entrenamiento = entrenamientos[preview.fecha_efectiva];", plantilla)
        self.assertIn("function buildLegacyBriefingUrl(entrenamiento, fecha, fallbackUrl)", plantilla)
        self.assertIn("params.set('rutina_nombre', entrenamiento.nombre_rutina || '');", plantilla)
        self.assertIn("params.set('sesion_programada_id', String(sesionProgramadaId));", plantilla)

    def test_navegacion_global_de_rutina_vuelve_a_la_preview_no_al_calendario(self):
        """Rutina es una sección global; el calendario queda como acceso interno."""
        from pathlib import Path

        plantilla = Path(
            "entrenos/templates/entrenos/rutina_silenciosa_preview.html"
        ).read_text()

        self.assertIn("{% include 'includes/bottom_nav.html' with activo='rutina' %}", plantilla)
