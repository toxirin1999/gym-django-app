"""17-nov-2026 · Lentitud: Ahora no genera el plan anual que no muestra."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

_GENERADORES = (
    'obtener_estadisticas_plan_anual',
    'obtener_historial_adherencia_semanal',
    'predecir_riesgo_abandono',
    'calcular_reporte_adherencia_cliente',
)


class AhoraSinEstadisticasDelPlan(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = get_user_model().objects.create_user(username='ahora-sin-stats', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'David', 'dias_disponibles': 4},
        )
        self.client.force_login(self.user)

    def _parchear(self):
        return [patch(f'clientes.views.{n}', wraps=None, return_value=None) for n in _GENERADORES]

    def test_ahora_no_llama_a_ningun_generador_de_estadisticas(self):
        ps = self._parchear()
        mocks = [p.start() for p in ps]
        try:
            r = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(r.status_code, 200)
        for nombre, m in zip(_GENERADORES, mocks):
            self.assertFalse(m.called, f'Ahora no debe llamar a {nombre}')

    def test_el_panel_principal_sigue_pidiendo_las_estadisticas(self):
        from clientes.views import _get_dashboard_context_data
        from django.test import RequestFactory
        req = RequestFactory().get('/x/')
        req.user = self.user
        ps = self._parchear()
        mocks = [p.start() for p in ps]
        try:
            try:
                _get_dashboard_context_data(req, self.cliente)  # por defecto: con estadísticas
            except Exception:
                pass  # el contexto completo puede necesitar sesión; basta con que haya llegado al bloque
        finally:
            for p in ps:
                p.stop()
        self.assertTrue(mocks[0].called, 'el panel completo debe seguir calculando el plan anual')

    def test_sesion_y_decision_de_ahora_no_cambian(self):
        from clientes.views import _get_dashboard_context_data
        from django.core.cache import cache
        from django.test import RequestFactory
        req = RequestFactory().get('/x/')
        req.user = self.user
        cache.clear()
        con = _get_dashboard_context_data(req, self.cliente)
        cache.clear()
        sin = _get_dashboard_context_data(req, self.cliente, con_estadisticas_plan=False)
        for clave in ('proximo_entrenamiento', 'explicacion_decision', '_decision_gym_raw',
                      'sesion_programada', 'acwr_actual'):
            self.assertEqual(con.get(clave), sin.get(clave), clave)
        self.assertIsNone(sin.get('estadisticas_plan'))
        self.assertIsNone(sin.get('reporte'))

    def test_la_plantilla_de_ahora_no_usa_esos_valores(self):
        from pathlib import Path
        base = Path(__file__).resolve().parent.parent
        for ruta in ('clientes/templates/clientes/dashboard_silencioso_preview.html',
                     'templates/includes/bottom_nav.html'):
            src = (base / ruta).read_text(encoding='utf-8')
            for clave in ('estadisticas_plan', 'historial_adherencia', 'prediccion', 'reporte'):
                self.assertNotIn(clave, src, f'{ruta} usa {clave}')

    def test_la_semana_dinamica_en_curso_queda_creada_cargando_ahora(self):
        """El cálculo que quitamos creaba, de paso, la fila de la semana en curso."""
        from entrenos.models import SemanaPlanGym
        self.assertFalse(SemanaPlanGym.objects.filter(cliente=self.cliente).exists())
        self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertTrue(SemanaPlanGym.objects.filter(cliente=self.cliente).exists())
