"""Contrato de la vista previa del dashboard silencioso."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

from clientes.models import BitacoraDiaria, Cliente


class DashboardSilenciosoPreviewTests(TestCase):
    def setUp(self):
        self.url = reverse("clientes:dashboard_silencioso_preview")
        self.user = get_user_model().objects.create_user(
            username="dashboard-silencioso", password="secreto"
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={"nombre": "David", "dias_disponibles": 4}
        )

    def test_anonimo_es_redirigido_a_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_usuario_autenticado_ve_decision_y_destinos_profundos(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clientes/dashboard_silencioso_preview.html")
        self.assertContains(response, "Ahora")
        self.assertContains(response, "Esta semana")
        self.assertContains(response, "Lo que el plan aprendió")
        self.assertContains(response, "Rutina")
        self.assertContains(response, "Plan")
        self.assertContains(response, "Memoria")
        self.assertContains(response, "Vida")
        self.assertContains(
            response,
            reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id]),
        )
        self.assertContains(response, reverse("clientes:trayectoria_plan"))
        self.assertNotEqual(
            response.context["quiet_links"]["routine"],
            response.context["quiet_links"]["plan"],
        )
        self.assertEqual(
            response.context["quiet_links"]["plan"],
            reverse("clientes:trayectoria_plan"),
        )
        self.assertContains(response, reverse("clientes:memoria_entrenador", args=[self.cliente.id]))

    def test_alternativas_de_la_decision_se_recogen_sin_ocultar_destinos(self):
        """La decisión muestra una vía principal y deja las alternativas bajo demanda."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, 'class="decision-alternatives"')
        self.assertContains(response, "Otras opciones")
        self.assertContains(response, reverse("estiramientos:panel"))

    def test_cabecera_ofrece_acceso_strava_reconocible_y_accesible(self):
        """Strava vive junto al estado de hoy, no como otra tarjeta del panel."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, reverse("hyrox:strava_reconciliacion"))
        self.assertContains(response, 'class="strava-link"')
        self.assertContains(response, 'aria-label="Abrir Strava"')
        self.assertContains(response, 'class="strava-mark"')
        self.assertContains(response, '#fc4c02')

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_cabecera_resume_carga_fisica_solo_con_un_valor_calculado(
        self, dashboard_contexto, resolver,
    ):
        """La cifra visible es el ACWR real, nunca un estado inventado."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": 0.93,
        }
        resolver.return_value = {
            "estado": "EN_MARGEN",
            "texto": "Hay margen para seguir el plan.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        # 26-oct-2026: en palabras y en porcentaje, no "ACWR 0,93".
        self.assertEqual(response.context["quiet_load"], {
            "valor": "−7 %", "estado": "Estable",
            "frase": "Esta semana vas como en tus semanas normales",
        })
        self.assertContains(response, 'class="load-chip"')
        self.assertContains(response, "Carga física")
        self.assertContains(response, "−7 %")
        self.assertNotContains(response, "ACWR −7 %")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_no_muestra_indicador_numerico_de_carga_sin_historial(
        self, dashboard_contexto, resolver,
    ):
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
        }
        resolver.return_value = {
            "estado": "EN_MARGEN",
            "texto": "Hay margen para seguir el plan.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertIsNone(response.context["quiet_load"])
        self.assertNotContains(response, 'class="load-chip"')

    def test_propuesta_de_zona_se_presenta_con_datos_estructurados_y_no_un_parrafo(self):
        """La iniciativa explica qué cae y qué cambia sin reanalizar su texto."""
        from entrenos.models import PropuestaZonaGym

        PropuestaZonaGym.objects.create(
            cliente=self.cliente,
            zona="isquios",
            series_extra=1,
            semanas=4,
            ejercicios=["Curl femoral tumbado", "Buenos días"],
            deteccion={"pct": -17.1},
            texto="Texto legado que no debe ser la interfaz.",
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, 'class="propuesta-resumen"')
        self.assertContains(response, "Isquios")
        self.assertContains(response, "-17,1 %")
        self.assertContains(response, "series por semana")  # paso 5: ±2 semanales
        self.assertContains(response, "4 semanas")
        self.assertNotContains(response, "Texto legado que no debe ser la interfaz.")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_detalle_de_decision_presenta_acwr_como_senal_separada(
        self, dashboard_contexto, resolver,
    ):
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {"contexto_fisico": {}},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": 0.93,
        }
        resolver.return_value = {
            "estado": "EN_MARGEN",
            "texto": "Hay margen para seguir el plan.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, 'class="decision-signal"')
        self.assertContains(response, "Señal de carga")
        self.assertContains(response, "Esta semana vas como en tus semanas normales")

    @patch('clientes.views._aviso_decision_pendiente')
    def test_muestra_unico_aviso_del_centro_solo_cuando_hay_accion_pendiente(self, aviso):
        """La portada anuncia una revisión, sin duplicar sus controles."""
        aviso.return_value = {'cantidad': 1, 'etiqueta': 'decisión pendiente'}
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, '1 decisión pendiente')
        self.assertContains(response, 'Revisar plan')
        self.assertContains(response, reverse('clientes:plan_decisiones'))
        self.assertNotContains(response, 'Aceptar propuesta')

    @patch('clientes.views._aviso_decision_pendiente', return_value=None)
    def test_no_muestra_aviso_del_centro_sin_accion_real(self, aviso):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertNotContains(response, 'decisión pendiente')

    def test_aprendizaje_no_repite_la_decision_del_dia_sin_evidencia_nueva(self):
        """La tarjeta de aprendizaje debe aportar una conclusión, no eco.

        Si el motor todavía no entrega señales longitudinales, reutilizar el
        mismo mensaje de la decisión principal crea la impresión falsa de que
        se aprendió algo nuevo. La portada debe declarar ese límite con una
        frase distinta y honesta.
        """
        from clientes.views import _resumen_aprendizaje_plan

        self.assertEqual(
            _resumen_aprendizaje_plan(
                [],
                "Esta es la sesión prevista para hoy.",
                "Esta es la sesión prevista para hoy.",
            ),
            "Aún no hay una adaptación nueva que comunicar. El plan seguirá observando tus próximas sesiones.",
        )

    def test_aprendizaje_no_presenta_la_sesion_prevista_como_conclusion(self):
        """Una sesión calendarizada describe el plan, pero no es aprendizaje nuevo."""
        from clientes.views import _resumen_aprendizaje_plan

        self.assertEqual(
            _resumen_aprendizaje_plan(
                [],
                "Hay margen para seguir el plan.",
                "Esta es la sesión prevista para hoy.",
            ),
            "Aún no hay una adaptación nueva que comunicar. El plan seguirá observando tus próximas sesiones.",
        )

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_normaliza_estados_del_organismo_a_decisiones_operativas(
        self, dashboard_contexto, resolver,
    ):
        """Los estados internos nunca se filtran como decisión de la portada."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
        }
        resolver.return_value = {
            "estado": "SILENCIO",
            "motivo": "descanso_planificado",
            "estado_label": "Silencio",
            "texto": "No hay nada que forzar ahora.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["quiet_decision"]["estado"], "DESCANSAR")
        self.assertNotContains(response, "SILENCIO")
        self.assertNotContains(response, "En pausa")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_descansar_no_abre_briefing_si_el_proximo_es_dia_de_descanso(
        self, dashboard_contexto, resolver,
    ):
        """Un descanso no puede fabricar una sesión de fuerza sin ejercicios."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {
                "nombre": "Día de Descanso",
                "rutina_nombre": "Día de Descanso",
                "ejercicios": [],
                "total_ejercicios": 0,
                "es_descanso": True,
            },
            "explicacion_decision": {},
            "acwr_actual": None,
        }
        resolver.return_value = {
            "estado": "SILENCIO",
            "motivo": "descanso_planificado",
            "texto": "No hay nada que forzar ahora.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["quiet_decision"]["estado"], "DESCANSAR")
        self.assertEqual(
            response.context["quiet_decision"]["cta_url"],
            reverse("estiramientos:panel"),
        )
        self.assertEqual(
            response.context["quiet_decision"]["cta_label"],
            "Movilidad y estiramientos",
        )
        self.assertNotIn(
            reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id]),
            response.context["quiet_decision"]["cta_url"],
        )

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_fallback_de_briefing_transporta_sesion_pendiente(
        self, dashboard_contexto, resolver,
    ):
        """Nunca abrir el briefing sin la identidad de la sesión ejecutable."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {
                "nombre": "Torso",
                "ejercicios": [{"nombre": "Press"}],
            },
            "explicacion_decision": {},
            "acwr_actual": None,
            "sesion_programada": SimpleNamespace(pk=75, estado="pendiente"),
        }
        resolver.return_value = {
            "estado": "EN_MARGEN",
            "texto": "Puedes entrenar.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        briefing = reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id])
        self.assertEqual(
            response.context["quiet_decision"]["cta_url"],
            f"{briefing}?sesion_programada_id=75",
        )
        self.assertEqual(
            response.context["quiet_postpone_url"],
            reverse("clientes:posponer_sesion", args=[75]),
        )
        self.assertContains(response, "Hacer esta sesión mañana")
        self.assertEqual(response.content.count(b'data-postpone-session'), 1)

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_plan_hoy_sin_sesion_materializada_conserva_enlace_para_aplazar(
        self, dashboard_contexto, resolver,
    ):
        """La acción no depende de que exista ya una SesionProgramada."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {"nombre": "Pierna", "ejercicios": [{"nombre": "Sentadilla"}]},
            "explicacion_decision": {},
            "acwr_actual": None,
            "sesion_programada": None,
        }
        resolver.return_value = {
            "estado": "EN_MARGEN",
            "texto": "Puedes entrenar.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.context["quiet_postpone_url"],
            reverse("clientes:posponer_sesion_hoy"),
        )
        self.assertContains(response, "Hacer esta sesión mañana")
        self.assertEqual(response.content.count(b'data-postpone-session'), 1)

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_sin_sesion_ejecutable_el_panel_ofrece_rutina_en_vez_de_una_cta_vacia(
        self, dashboard_contexto, resolver,
    ):
        """Una portada degradada sigue teniendo una acción real y no inventa sesión."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
            "sesion_programada": None,
        }
        resolver.return_value = {
            "estado": "OBSERVANDO",
            "texto": "El plan necesita una lectura más antes de elegir.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["quiet_decision"]["estado"], "AJUSTAR")
        self.assertEqual(
            response.context["quiet_decision"]["cta_url"],
            reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id]),
        )
        self.assertEqual(response.context["quiet_decision"]["cta_label"], "Ver rutina")
        self.assertContains(response, "Ver rutina")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_recuperar_sin_url_se_degrada_a_movilidad_y_no_a_una_sesion_inventada(
        self, dashboard_contexto, resolver,
    ):
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
        }
        resolver.return_value = {
            "estado": "PROTEGIENDO",
            "texto": "Conviene bajar el tono hoy.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["quiet_decision"]["estado"], "RECUPERAR")
        self.assertEqual(
            response.context["quiet_decision"]["cta_url"],
            reverse("estiramientos:panel"),
        )
        self.assertEqual(response.context["quiet_decision"]["cta_label"], "Movilidad y estiramientos")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_semana_solo_dice_recuperando_bien_con_energia_y_sueno(
        self, dashboard_contexto, resolver,
    ):
        """No convertir ausencia de check-in en una afirmación de recuperación."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
        }
        resolver.return_value = {
            "estado": "SILENCIO",
            "texto": "No hay nada que forzar ahora.",
            "accion_label": None,
            "accion_url": None,
        }
        self.client.force_login(self.user)

        sin_checkin = self.client.get(self.url)
        self.assertEqual(sin_checkin.context["quiet_week"]["titulo"], "DATOS PENDIENTES")
        self.assertNotContains(sin_checkin, "RECUPERANDO BIEN")

        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.localdate(),
            energia_subjetiva=6,
            horas_sueno=8,
        )
        con_checkin = self.client.get(self.url)
        self.assertEqual(con_checkin.context["quiet_week"]["titulo"], "RECUPERANDO BIEN")
        self.assertContains(con_checkin, "RECUPERANDO BIEN")

    @patch("core.organismo.resolver_estado_sistema_hoy")
    @patch("clientes.views._get_dashboard_context_data")
    def test_carga_alta_no_queda_oculta_por_un_checkin_favorable(
        self, dashboard_contexto, resolver,
    ):
        """La lectura semanal prioriza la carga cuando supera el margen seguro."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": 1.31,
        }
        resolver.return_value = {
            "estado": "SILENCIO",
            "texto": "No hay nada que forzar ahora.",
            "accion_label": None,
            "accion_url": None,
        }
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.localdate(),
            energia_subjetiva=8,
            horas_sueno=8,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["quiet_week"]["titulo"], "VIGILAR CARGA")
        self.assertContains(response, "VIGILAR CARGA")
        self.assertNotContains(response, "RECUPERANDO BIEN")

    def test_datos_pendientes_ofrece_checkin_minimo_en_la_misma_preview(self):
        """La falta de datos debe poder resolverse desde Ahora, sin salir del flujo."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, "Completar check-in")
        self.assertContains(response, reverse("clientes:checkin_matutino"))
        self.assertContains(response, 'name="horas_sueno"')
        self.assertContains(response, 'name="energia_subjetiva"')
        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="14"')
        self.assertContains(response, 'step="0.5"')
        self.assertContains(response, "Escape")

    def test_checkin_modal_declara_y_gestiona_el_foco_de_teclado(self):
        """El check-in rápido no puede sacar al teclado del diálogo ni perder su origen."""
        plantilla = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text()

        self.assertIn('aria-modal="true"', plantilla)
        self.assertIn('aria-describedby="quietCheckinDescription"', plantilla)
        self.assertIn("firstField.focus();", plantilla)
        self.assertIn("dialog.addEventListener('keydown'", plantilla)
        self.assertIn("event.key !== 'Tab'", plantilla)
        self.assertIn("event.shiftKey && document.activeElement === first", plantilla)
        self.assertIn("last.focus();", plantilla)
        self.assertIn("first.focus();", plantilla)
        self.assertIn("lastFocus && lastFocus.isConnected", plantilla)

    def test_checkin_minimo_no_aparece_si_sueno_y_energia_ya_existen(self):
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            fecha=timezone.localdate(),
            energia_subjetiva=6,
            horas_sueno=8,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertNotContains(response, "Completar check-in")
        self.assertNotContains(response, 'id="quietCheckinDialog"')

    def test_deeplink_checkin_reutiliza_el_modal_y_limpia_la_url(self):
        """Plan puede abrir el check-in existente sin cambiar su endpoint."""
        plantilla = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text()

        self.assertIn("new URLSearchParams(window.location.search).get('checkin') === '1'", plantilla)
        self.assertIn('window.history.replaceState', plantilla)
        self.assertIn('openDialog();', plantilla)

    def test_tarjetas_y_enlace_de_aplazamiento_conservan_sus_estilos(self):
        """Un ajuste del enlace no puede desvestir el resto del dashboard."""
        plantilla = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text()

        self.assertIn('.card{', plantilla)
        self.assertIn('.metrics{display:grid', plantilla)
        self.assertIn('.inline-form .secondary-action{font-family:inherit;font-size:9px', plantilla)

    def test_dashboard_y_navegacion_aprovechan_escritorio_sin_alterar_movil(self):
        """La composición sigue siendo compacta en móvil y gana aire a partir de tablet."""
        dashboard = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text()
        navegacion = Path('templates/includes/bottom_nav.html').read_text()

        self.assertIn('@media(min-width:760px)', dashboard)
        self.assertIn('main{width:min(100% - 48px,680px)', dashboard)
        self.assertIn('@media(min-width:760px)', navegacion)
        self.assertIn('.bottom-nav-std ul{width:min(100% - 48px,680px)', navegacion)

    @patch("clientes.views._get_dashboard_context_data")
    def test_accesos_secundarios_preservan_sesion_pendiente_y_movilidad(
        self, dashboard_contexto,
    ):
        """La autonomía conserva la sesión pendiente sin esconder movilidad."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
            "sesion_programada": SimpleNamespace(pk=73, estado="pendiente"),
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        rutina = reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id])
        self.assertEqual(response.context["quiet_links"]["routine"], rutina)
        self.assertEqual(
            response.context["quiet_links"]["mobility"],
            f"{reverse('estiramientos:panel')}?sesion_programada_id=73",
        )
        self.assertContains(response, "Elegir otra rutina")
        self.assertContains(response, "Movilidad y estiramientos")

    @patch("clientes.views._get_dashboard_context_data")
    def test_rutina_nav_lleva_a_la_preview_sin_arrastrar_sesiones_cerradas(
        self, dashboard_contexto,
    ):
        """La pestaña Rutina no duplica el briefing ni arrastra sesiones cerradas."""
        dashboard_contexto.return_value = {
            "_decision_gym_raw": {},
            "proximo_entrenamiento": {},
            "explicacion_decision": {},
            "acwr_actual": None,
            "sesion_programada": SimpleNamespace(pk=74, estado="completada"),
        }
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        rutina = reverse("entrenos:rutina_silenciosa_preview", args=[self.cliente.id])
        self.assertEqual(response.context["quiet_links"]["routine"], rutina)
        self.assertEqual(
            response.context["quiet_links"]["mobility"],
            reverse("estiramientos:panel"),
        )
        self.assertContains(response, "Rutina")
        self.assertNotContains(response, ">Entreno<")
