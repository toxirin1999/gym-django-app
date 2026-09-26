"""Contrato de la vista previa del dashboard silencioso."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from types import SimpleNamespace

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
        self.assertContains(response, reverse("entrenos:vista_plan_anual", args=[self.cliente.id]))
        self.assertContains(response, reverse("clientes:plan_decisiones"))
        self.assertNotEqual(
            response.context["quiet_links"]["routine"],
            response.context["quiet_links"]["plan"],
        )
        self.assertContains(response, reverse("clientes:memoria_entrenador", args=[self.cliente.id]))

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

        calendario = reverse("entrenos:vista_plan_anual", args=[self.cliente.id])
        self.assertEqual(response.context["quiet_links"]["routine"], calendario)
        self.assertEqual(
            response.context["quiet_links"]["mobility"],
            f"{reverse('estiramientos:panel')}?sesion_programada_id=73",
        )
        self.assertContains(response, "Elegir otra rutina")
        self.assertContains(response, "Movilidad y estiramientos")

    @patch("clientes.views._get_dashboard_context_data")
    def test_rutina_nav_lleva_al_calendario_sin_parametro_si_no_esta_pendiente(
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

        calendario = reverse("entrenos:vista_plan_anual", args=[self.cliente.id])
        self.assertEqual(response.context["quiet_links"]["routine"], calendario)
        self.assertEqual(
            response.context["quiet_links"]["mobility"],
            reverse("estiramientos:panel"),
        )
        self.assertContains(response, "Rutina")
        self.assertNotContains(response, ">Entreno<")
