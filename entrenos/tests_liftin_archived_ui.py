from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina
from entrenos.urls import liftin_ui_required


LIFTIN_ROUTE_CASES = (
    ("dashboard_liftin", {"cliente_id": 1}, "get"),
    ("dashboard_liftin_cliente", {"cliente_id": 1}, "get"),
    ("importar_liftin", {}, "post"),
    ("importar_liftin_completo", {}, "post"),
    ("estadisticas_liftin", {}, "get"),
    ("exportar_datos_liftin", {}, "get"),
    ("detalle_ejercicios_liftin", {"entreno_id": 1}, "get"),
    ("editar_entrenamiento_liftin", {"entrenamiento_id": 1}, "post"),
    ("eliminar_entrenamiento_liftin", {"entrenamiento_id": 1}, "post"),
    ("buscar_entrenamientos_liftin", {}, "get"),
    ("comparar_liftin_manual", {}, "get"),
    ("api_stats_liftin", {}, "get"),
    ("api_ejercicios_liftin", {"entrenamiento_id": 1}, "get"),
)


class LiftinArchivedRoutesTests(TestCase):
    def test_feature_flag_is_disabled_by_default(self):
        self.assertIs(settings.LIFTIN_UI_ENABLED, False)

    def test_all_thirteen_named_routes_remain_reversible_but_return_404(self):
        self.assertEqual(len(LIFTIN_ROUTE_CASES), 13)
        for name, kwargs, method in LIFTIN_ROUTE_CASES:
            with self.subTest(name=name):
                url = reverse(f"entrenos:{name}", kwargs=kwargs)
                response = getattr(self.client, method)(url, data={"sentinel": "no-view"})
                self.assertEqual(response.status_code, 404)

    def test_guard_rejects_before_calling_wrapped_view(self):
        calls = []

        @liftin_ui_required
        def mutating_view(request):
            calls.append("called")

        request = RequestFactory().post("/mutating-liftin/")
        with self.assertRaisesMessage(Http404, "La interfaz Liftin está archivada"):
            mutating_view(request)
        self.assertEqual(calls, [])

    @override_settings(LIFTIN_UI_ENABLED=True)
    def test_flag_can_restore_route_without_changing_its_name(self):
        response = self.client.get(reverse("entrenos:api_stats_liftin"))
        self.assertNotEqual(response.status_code, 404)


class LiftinHistoricalUiTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("liftin-history")
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre="Archivo Liftin")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 20),
            fuente_datos="liftin",
            nombre_rutina_liftin="Histórico visible Liftin",
        )

    def test_archived_liftin_row_remains_visible_in_general_list(self):
        response = self.client.get(reverse("entrenos:lista_entrenamientos"))
        self.assertContains(response, "Histórico visible Liftin")

    def test_general_detail_keeps_history_but_hides_edit_and_delete_actions(self):
        response = self.client.get(
            reverse("entrenos:detalle_entrenamiento", args=[self.entreno.pk])
        )
        self.assertContains(response, "📱 Liftin")
        self.assertNotContains(response, "Editar Entrenamiento")
        self.assertNotContains(response, "Eliminar Entrenamiento")

    @override_settings(LIFTIN_UI_ENABLED=True)
    def test_general_detail_restores_liftin_actions_when_flag_is_enabled(self):
        response = self.client.get(
            reverse("entrenos:detalle_entrenamiento", args=[self.entreno.pk])
        )
        self.assertContains(response, "Editar Entrenamiento")
        self.assertContains(response, "Eliminar Entrenamiento")
