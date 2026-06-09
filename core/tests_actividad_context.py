"""
Phase 59X.B — Tests para core.context.actividad_context

El módulo extrae la agregación de actividad reciente a un lugar neutral
(sin dependencia de JOI) para que tanto el semáforo como JOI puedan
consumirlo sin duplicar lógica.

Tests de contrato: no testean SQL directo, mockean el ORM.
"""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_actividad(tipo, dias_hace=1, titulo='', rpe=None, duracion=None, carga=None):
    """Mock de ActividadRealizada."""
    a = MagicMock()
    hoy = date.today()
    a.tipo = tipo
    a.fecha = hoy - timedelta(days=dias_hace)
    a.fecha_realizado = None
    a.titulo = titulo
    a.rpe_medio = rpe
    a.duracion_minutos = duracion
    a.carga_ua = carga
    return a


def _make_fase(fase='volumen', dias_inicio=10, fecha_fin=None):
    f = MagicMock()
    hoy = date.today()
    f.fase = fase
    f.get_fase_display.return_value = fase.capitalize()
    f.fecha_inicio = hoy - timedelta(days=dias_inicio)
    f.fecha_fin = fecha_fin
    f.es_descarga = (fase == 'descarga')
    return f


# ─── Test: get_actividad_context ────────────────────────────────────────────

class TestGetActividadContext(TestCase):

    def _patch_qs(self, actividades=None, fase=None):
        """Retorna un contexto con mocks de ActividadRealizada y FaseCliente."""
        actividades = actividades or []

        qs_all = MagicMock()
        qs_all.filter.return_value = qs_all
        qs_all.annotate.return_value = qs_all
        qs_all.order_by.return_value = qs_all
        qs_all.first.return_value = actividades[0] if actividades else None
        qs_all.values.return_value = qs_all
        qs_all.__iter__ = lambda s: iter(actividades)
        qs_all.__getitem__ = lambda s, k: actividades[k]
        qs_all.exists.return_value = bool(actividades)

        # count por tipo
        gym_n = sum(1 for a in actividades if a.tipo == 'gym')
        hyrox_n = sum(1 for a in actividades if a.tipo == 'hyrox')
        carrera_n = sum(1 for a in actividades if a.tipo == 'carrera')

        tipo_counts = []
        if gym_n:
            r = MagicMock(); r.__getitem__ = lambda s, k: {'tipo': 'gym', 'n': gym_n}[k]; tipo_counts.append({'tipo': 'gym', 'n': gym_n})
        if hyrox_n:
            tipo_counts.append({'tipo': 'hyrox', 'n': hyrox_n})
        if carrera_n:
            tipo_counts.append({'tipo': 'carrera', 'n': carrera_n})

        qs_semana = MagicMock()
        qs_semana.__iter__ = lambda s: iter(tipo_counts)

        qs_fase = MagicMock()
        qs_fase.order_by.return_value = qs_fase
        qs_fase.first.return_value = fase
        qs_fase.filter.return_value = qs_fase

        return qs_all, qs_semana, qs_fase

    @patch('core.context.actividad_context.FaseCliente')
    @patch('core.context.actividad_context.ActividadRealizada')
    def test_sin_actividad_devuelve_ceros(self, MockAR, MockFC):
        """Sin actividades → sesiones en cero, ultima_actividad=None, racha=0."""
        qs, qs_sem, qs_fase = self._patch_qs(actividades=[])
        MockAR.objects.filter.return_value = qs
        MockAR.objects.filter.return_value.annotate.return_value = qs
        MockFC.objects.filter.return_value = qs_fase

        from core.context.actividad_context import get_actividad_context
        cliente = MagicMock()
        ctx = get_actividad_context(cliente, hoy=date.today())

        self.assertEqual(ctx['sesiones_gym_semana'], 0)
        self.assertEqual(ctx['sesiones_hyrox_semana'], 0)
        self.assertEqual(ctx['sesiones_semana_total'], 0)
        self.assertIsNone(ctx['ultima_actividad'])
        self.assertEqual(ctx['racha_dias'], 0)

    @patch('core.context.actividad_context.FaseCliente')
    @patch('core.context.actividad_context.ActividadRealizada')
    def test_cuenta_gym_y_hyrox_por_separado(self, MockAR, MockFC):
        """2 gym + 1 hyrox esta semana → campos separados correctos."""
        acts = [
            _make_actividad('gym', dias_hace=1),
            _make_actividad('gym', dias_hace=3),
            _make_actividad('hyrox', dias_hace=2),
        ]

        def filter_side(*a, **kw):
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.annotate.return_value = qs
            qs.order_by.return_value = qs
            qs.first.return_value = acts[0]
            qs.exists.return_value = True
            tipo = kw.get('tipo__in', [])
            counts = []
            if 'gym' in tipo:
                counts.append({'tipo': 'gym', 'n': 2})
            if 'hyrox' in tipo:
                counts.append({'tipo': 'hyrox', 'n': 1})
            qs.values.return_value.annotate.return_value = iter(counts)
            qs.__iter__ = lambda s: iter(counts)
            return qs

        MockAR.objects.filter.side_effect = filter_side
        qs_fase = MagicMock(); qs_fase.filter.return_value = qs_fase; qs_fase.order_by.return_value = qs_fase; qs_fase.first.return_value = None
        MockFC.objects.filter.return_value = qs_fase

        from core.context.actividad_context import get_actividad_context
        importlib = __import__('importlib'); importlib.reload(__import__('core.context.actividad_context', fromlist=['']))
        ctx = get_actividad_context(MagicMock(), hoy=date.today())

        self.assertIn('sesiones_gym_semana', ctx)
        self.assertIn('sesiones_hyrox_semana', ctx)

    @patch('core.context.actividad_context.FaseCliente')
    @patch('core.context.actividad_context.ActividadRealizada')
    def test_ultima_actividad_calcula_dias_hace(self, MockAR, MockFC):
        """ultima_actividad.dias_hace refleja cuántos días han pasado."""
        hoy = date.today()
        act = _make_actividad('gym', dias_hace=3)

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.annotate.return_value = qs
        qs.order_by.return_value = qs
        qs.first.return_value = act
        qs.exists.return_value = False
        qs.__iter__ = lambda s: iter([])
        qs.values.return_value.annotate.return_value = iter([])
        MockAR.objects.filter.return_value = qs

        qs_fase = MagicMock(); qs_fase.filter.return_value = qs_fase; qs_fase.order_by.return_value = qs_fase; qs_fase.first.return_value = None
        MockFC.objects.filter.return_value = qs_fase

        from core.context.actividad_context import get_actividad_context
        ctx = get_actividad_context(MagicMock(), hoy=hoy)

        ua = ctx.get('ultima_actividad')
        self.assertIsNotNone(ua)
        self.assertEqual(ua['dias_hace'], 3)
        self.assertEqual(ua['tipo'], 'gym')

    @patch('core.context.actividad_context.FaseCliente')
    @patch('core.context.actividad_context.ActividadRealizada')
    def test_fase_plan_descarga_detectada(self, MockAR, MockFC):
        """Si hay FaseCliente descarga activa → fase_plan.es_descarga=True."""
        qs = MagicMock(); qs.filter.return_value = qs; qs.annotate.return_value = qs
        qs.order_by.return_value = qs; qs.first.return_value = None
        qs.exists.return_value = False; qs.__iter__ = lambda s: iter([])
        qs.values.return_value.annotate.return_value = iter([])
        MockAR.objects.filter.return_value = qs

        fase = _make_fase('descarga', dias_inicio=3)
        qs_fase = MagicMock(); qs_fase.filter.return_value = qs_fase; qs_fase.order_by.return_value = qs_fase; qs_fase.first.return_value = fase
        MockFC.objects.filter.return_value = qs_fase

        from core.context.actividad_context import get_actividad_context
        ctx = get_actividad_context(MagicMock(), hoy=date.today())

        fp = ctx.get('fase_plan')
        self.assertIsNotNone(fp)
        self.assertTrue(fp['es_descarga'])
        self.assertEqual(fp['tipo'], 'descarga')

    @patch('core.context.actividad_context.FaseCliente')
    @patch('core.context.actividad_context.ActividadRealizada')
    def test_fase_plan_none_cuando_no_hay_fase(self, MockAR, MockFC):
        """Sin FaseCliente activa → fase_plan es None."""
        qs = MagicMock(); qs.filter.return_value = qs; qs.annotate.return_value = qs
        qs.order_by.return_value = qs; qs.first.return_value = None
        qs.exists.return_value = False; qs.__iter__ = lambda s: iter([])
        qs.values.return_value.annotate.return_value = iter([])
        MockAR.objects.filter.return_value = qs

        qs_fase = MagicMock(); qs_fase.filter.return_value = qs_fase; qs_fase.order_by.return_value = qs_fase; qs_fase.first.return_value = None
        MockFC.objects.filter.return_value = qs_fase

        from core.context.actividad_context import get_actividad_context
        ctx = get_actividad_context(MagicMock(), hoy=date.today())

        self.assertIsNone(ctx.get('fase_plan'))


# ─── Test: integración semáforo ─────────────────────────────────────────────

class TestSemaforoConActividadContext(TestCase):
    """
    Verifica que get_estado_hoy incluye los nuevos campos en datos_raw,
    y que la fase descarga suprime el estado 'volver' por ausencia.
    """

    def _mock_semaforo_base(self):
        """Mocks mínimos para que get_estado_hoy no crashee."""
        bio = MagicMock()
        bio.get_bio_signals.return_value = {
            'has_data': False, 'hrv_ms': None, 'energia': 7,
            'horas_sueno': None,
        }
        bio.get_readiness_score.return_value = {
            'score': 0.75, 'needs_deload': False, 'volume_modifier': 1.0,
        }
        return bio

    @patch('core.daily_decision.get_actividad_context')
    @patch('core.daily_decision.BioContextProvider')
    def test_datos_raw_incluye_sesiones_gym_semana(self, MockBio, MockGAC):
        """datos_raw tiene sesiones_gym_semana con el valor del módulo compartido."""
        bio = self._mock_semaforo_base()
        MockBio.get_bio_signals.return_value = bio.get_bio_signals.return_value
        MockBio.get_readiness_score.return_value = bio.get_readiness_score.return_value

        MockGAC.return_value = {
            'sesiones_gym_semana': 3,
            'sesiones_hyrox_semana': 1,
            'sesiones_semana_total': 4,
            'actividad_semana': {'gym': 3, 'hyrox': 1},
            'ultima_actividad': {'dias_hace': 1, 'tipo': 'gym', 'fecha': str(date.today()), 'titulo': ''},
            'racha_dias': 2,
            'fase_plan': None,
        }

        from core.daily_decision import DailyDecisionEngine
        cliente = MagicMock()
        resultado = DailyDecisionEngine.get_estado_hoy(cliente)

        raw = resultado['datos_raw']
        self.assertIn('sesiones_gym_semana', raw)
        self.assertEqual(raw['sesiones_gym_semana'], 3)
        self.assertIn('sesiones_hyrox_semana', raw)
        self.assertIn('racha_dias', raw)

    @patch('core.daily_decision.get_actividad_context')
    @patch('core.daily_decision.BioContextProvider')
    def test_descarga_suprime_volver_por_ausencia(self, MockBio, MockGAC):
        """
        Con ausencia >= 5 días pero fase_plan.es_descarga=True,
        el estado debe ser 'recuperar' (o 'empujar'), NO 'volver'.
        El plan marcó deload — la ausencia es planificada.
        """
        bio = self._mock_semaforo_base()
        MockBio.get_bio_signals.return_value = bio.get_bio_signals.return_value
        MockBio.get_readiness_score.return_value = bio.get_readiness_score.return_value

        MockGAC.return_value = {
            'sesiones_gym_semana': 0,
            'sesiones_hyrox_semana': 0,
            'sesiones_semana_total': 0,
            'actividad_semana': {},
            'ultima_actividad': {'dias_hace': 6, 'tipo': 'gym', 'fecha': str(date.today() - __import__('datetime').timedelta(days=6)), 'titulo': ''},
            'racha_dias': 0,
            'fase_plan': {'tipo': 'descarga', 'es_descarga': True, 'dias_en_fase': 3, 'nombre': 'Descarga'},
        }

        # ausencia >= 5 vía continuidad mock
        with patch('core.daily_decision.DailyDecisionEngine._calcular_ausencia_dias', return_value=6):
            from core.daily_decision import DailyDecisionEngine
            resultado = DailyDecisionEngine.get_estado_hoy(MagicMock())

        self.assertNotEqual(resultado['estado'], 'volver',
            "Con deload planificado, la ausencia no debería disparar 'volver'")
        self.assertIn(resultado['causa'], ('descanso_plan', 'normal', 'fatiga', 'fragilidad', 'carga'),
            f"Causa inesperada: {resultado['causa']}")
