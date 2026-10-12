"""El ACWR entra en la decisión diaria de Gym, protegido contra datos imposibles."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ActividadRealizada
from entrenos.services.acwr_decision_service import contexto_acwr
from entrenos.services.sesion_recomendada import _aplicar_contexto


def _contexto(**extra):
    base = {
        'lesion_activa': False, 'lesion_fase': None, 'futbol_reciente': False,
        'hyrox_reciente': False, 'energia_baja': False, 'energia_valor': None,
        'readiness_bajo': False, 'readiness_valor': None, 'preferencias_activas': [],
        'acwr_valor': None, 'acwr_alto': False, 'acwr_dudoso': False,
    }
    base.update(extra)
    return base


DECISION_BASE = {'tipo': 'hoy', 'entrenamiento': {'nombre_rutina': 'Día 1'}, 'mensaje': ''}


class ReglaAcwrTests(TestCase):
    def test_carga_alta_pide_version_reducida(self):
        d = _aplicar_contexto(DECISION_BASE, _contexto(acwr_valor=1.62, acwr_alto=True), timezone.localdate())
        self.assertEqual(d['estado'], 'version_reducida')
        self.assertEqual(d['causa_principal'], 'carga_alta')
        self.assertTrue(d['modo_reducido'])
        self.assertIn('carga', d['mensaje'].lower())

    def test_readiness_bajo_sigue_por_delante(self):
        d = _aplicar_contexto(DECISION_BASE, _contexto(readiness_bajo=True, acwr_alto=True), timezone.localdate())
        self.assertEqual(d['causa_principal'], 'fatiga_alta')
        self.assertEqual(d['estado'], 'recuperar')

    def test_carga_alta_gana_a_energia_baja(self):
        d = _aplicar_contexto(DECISION_BASE, _contexto(energia_baja=True, acwr_alto=True), timezone.localdate())
        self.assertEqual(d['causa_principal'], 'carga_alta')

    def test_pico_dudoso_no_frena(self):
        d = _aplicar_contexto(DECISION_BASE, _contexto(acwr_valor=2.32, acwr_dudoso=True), timezone.localdate())
        self.assertEqual(d['estado'], 'entrenar')

    def test_descanso_planificado_no_cambia(self):
        d = _aplicar_contexto({'tipo': 'descanso', 'mensaje': ''}, _contexto(acwr_alto=True), timezone.localdate())
        self.assertEqual(d['estado'], 'descanso')

    def test_explicacion_y_causa_secundaria(self):
        from entrenos.services.autoridad_diaria_gym_service import _causas_secundarias
        from entrenos.services.explicacion_decision_service import construir_explicacion_decision
        d = _aplicar_contexto(DECISION_BASE, _contexto(acwr_valor=1.62, acwr_alto=True), timezone.localdate())
        self.assertIn('ACWR', construir_explicacion_decision(d)['causa_label'])
        d2 = _aplicar_contexto(DECISION_BASE, _contexto(readiness_bajo=True, acwr_alto=True), timezone.localdate())
        self.assertIn('carga_alta', _causas_secundarias(d2))


class _BaseCarga(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='acwr_dec', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'AcwrDec', 'dias_disponibles': 4},
        )
        self.hoy = timezone.now().date()
        # Base estable: 300 UA cada 2 días durante 60 días.
        for dias in range(60, 7, -2):
            self._act(dias, 300, 50)

    def _act(self, dias_atras, carga, duracion):
        d = self.hoy - timedelta(days=dias_atras)
        return ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', fecha=d, fecha_realizado=d,
            carga_ua=carga, duracion_minutos=duracion,
        )


class ContextoAcwrTests(_BaseCarga):
    def test_semana_estable_no_marca_nada(self):
        for dias in (6, 4, 2):
            self._act(dias, 300, 50)
        ctx = contexto_acwr(self.cliente, self.hoy)
        self.assertIsNotNone(ctx['acwr_valor'])
        self.assertFalse(ctx['acwr_alto'])
        self.assertFalse(ctx['acwr_dudoso'])

    def test_semana_cargada_de_verdad_marca_carga_alta(self):
        for dias in range(6, -1, -1):
            self._act(dias, 700, 90)
        ctx = contexto_acwr(self.cliente, self.hoy)
        self.assertGreaterEqual(ctx['acwr_valor'], 1.5)
        self.assertTrue(ctx['acwr_alto'])
        self.assertFalse(ctx['acwr_dudoso'])

    def test_una_sola_sesion_imposible_se_marca_dudosa(self):
        self._act(1, 18432.5, 2525)
        ctx = contexto_acwr(self.cliente, self.hoy)
        self.assertGreaterEqual(ctx['acwr_valor'], 1.5)
        self.assertFalse(ctx['acwr_alto'])
        self.assertTrue(ctx['acwr_dudoso'])

    def test_carga_desproporcionada_sin_duracion_tambien_es_dudosa(self):
        self._act(1, 9000, None)
        ctx = contexto_acwr(self.cliente, self.hoy)
        self.assertTrue(ctx['acwr_dudoso'])
        self.assertFalse(ctx['acwr_alto'])

    def test_historial_insuficiente_no_opina(self):
        ActividadRealizada.objects.filter(cliente=self.cliente).delete()
        cache.clear()
        self._act(3, 900, 90)
        ctx = contexto_acwr(self.cliente, self.hoy)
        self.assertEqual(ctx, {'acwr_valor': None, 'acwr_alto': False, 'acwr_dudoso': False})


class IntegracionContextoFisicoTests(_BaseCarga):
    def test_contexto_fisico_incluye_acwr(self):
        from entrenos.services.sesion_recomendada import _obtener_contexto_fisico
        for dias in range(6, -1, -1):
            self._act(dias, 700, 90)
        ctx = _obtener_contexto_fisico(self.cliente, timezone.localdate())
        self.assertTrue(ctx['acwr_alto'])


class PortadaCargaAltaSinCheckinTests(TestCase):
    """«DATOS PENDIENTES» no puede tapar una carga alta en Ahora."""

    def setUp(self):
        from django.urls import reverse
        self.user = User.objects.create_user(username='portada_acwr', password='x')
        self.url = reverse('clientes:dashboard_silencioso_preview')

    def test_carga_alta_sin_checkin_muestra_vigilar_carga_y_ofrece_checkin(self):
        from unittest.mock import patch
        with patch('clientes.views._get_dashboard_context_data') as ctx, \
                patch('core.organismo.resolver_estado_sistema_hoy') as resolver:
            ctx.return_value = {
                '_decision_gym_raw': {}, 'proximo_entrenamiento': {},
                'explicacion_decision': {}, 'acwr_actual': 1.62,
            }
            resolver.return_value = {
                'estado': 'EN_MARGEN', 'texto': 'Hay margen, con carga ajustada.',
                'accion_label': None, 'accion_url': None,
            }
            self.client.force_login(self.user)
            response = self.client.get(self.url)
        semana = response.context['quiet_week']
        self.assertEqual(semana['titulo'], 'VIGILAR CARGA')
        self.assertTrue(semana['checkin_pendiente'])
        self.assertContains(response, 'Completar check-in')

    def test_pico_dudoso_pide_revisar_la_carga(self):
        from unittest.mock import patch
        with patch('clientes.views._get_dashboard_context_data') as ctx, \
                patch('core.organismo.resolver_estado_sistema_hoy') as resolver:
            ctx.return_value = {
                '_decision_gym_raw': {'contexto_fisico': {'acwr_dudoso': True}},
                'proximo_entrenamiento': {}, 'explicacion_decision': {}, 'acwr_actual': 2.32,
            }
            resolver.return_value = {
                'estado': 'EN_MARGEN', 'texto': 'Hay margen para seguir el plan.',
                'accion_label': None, 'accion_url': None,
            }
            self.client.force_login(self.user)
            response = self.client.get(self.url)
        semana = response.context['quiet_week']
        self.assertEqual(semana['titulo'], 'REVISAR CARGA')
        self.assertIn('parece un error', semana['carga_detalle'])
