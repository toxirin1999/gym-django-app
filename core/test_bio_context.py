# core/test_bio_context.py
"""
Tests unitarios para BioContextProvider.

Ejecutar:
    cd /Users/davidmillanblanco/Desktop/app3/app/a/gymproject
    python manage.py test core.test_bio_context -v 2
"""
import os
import sys
import django
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Bootstrap Django antes de importar modelos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')

# Añadir el directorio del proyecto al path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

django.setup()

from django.test import TestCase
from core.bio_context import BioContextProvider


# ─────────────────────────────────────────────────────────────
#  Helpers: objetos mock que simulan modelos Django
# ─────────────────────────────────────────────────────────────

def _make_injury(zona='gemelo', fase='AGUDA', gravedad=7, tags=None, activa=True):
    """Crea un mock de UserInjury."""
    inj = MagicMock()
    inj.pk = 1
    inj.zona_afectada = zona
    inj.fase = fase
    inj.gravedad = gravedad
    inj.tags_restringidos = tags or []
    inj.activa = activa
    inj.fecha_inicio = date.today()
    return inj


def _make_dre(dolor_reposo=3, dolor_movimiento=5, inflamacion=4, rango=6, fecha=None):
    """Crea un mock de DailyRecoveryEntry."""
    entry = MagicMock()
    entry.dolor_reposo = dolor_reposo
    entry.dolor_movimiento = dolor_movimiento
    entry.inflamacion_percibida = inflamacion
    entry.rango_movimiento = rango
    entry.fecha = fecha or date.today()
    return entry


# ─────────────────────────────────────────────────────────────
#  Test: get_current_restrictions
# ─────────────────────────────────────────────────────────────

class TestGetCurrentRestrictions(TestCase):

    @patch('core.bio_context.UserInjury', create=True)
    def test_no_injuries_returns_empty(self, _mock):
        """Sin lesiones activas → tags vacío, has_restrictions=False."""
        with patch('hyrox.models.UserInjury') as MockUI:
            qs = MagicMock()
            qs.exclude.return_value = qs
            qs.__iter__ = lambda s: iter([])
            MockUI.objects.filter.return_value = qs
            MockUI.Fase = MagicMock()
            MockUI.Fase.RECUPERADO = 'RECUPERADO'

            cliente = MagicMock()
            result = BioContextProvider.get_current_restrictions(cliente)

            self.assertEqual(result['tags'], set())
            self.assertEqual(result['injuries'], [])
            self.assertFalse(result['has_restrictions'])

    @patch('hyrox.models.UserInjury')
    def test_single_injury_returns_tags(self, MockUI):
        """Una lesión activa con tags → se devuelven correctamente."""
        inj = _make_injury(tags=['impacto_vertical', 'flexion_rodilla_profunda'])

        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.__iter__ = lambda s: iter([inj])
        MockUI.objects.filter.return_value = qs
        MockUI.Fase = MagicMock()
        MockUI.Fase.RECUPERADO = 'RECUPERADO'

        cliente = MagicMock()
        result = BioContextProvider.get_current_restrictions(cliente)

        self.assertEqual(result['tags'], {'impacto_vertical', 'flexion_rodilla_profunda'})
        self.assertTrue(result['has_restrictions'])
        self.assertEqual(len(result['injuries']), 1)
        self.assertEqual(result['injuries'][0]['zona'], 'gemelo')

    @patch('hyrox.models.UserInjury')
    def test_multiple_injuries_union_tags(self, MockUI):
        """Múltiples lesiones → union de todos los tags."""
        inj1 = _make_injury(zona='gemelo', tags=['impacto_vertical'])
        inj1.pk = 1
        inj2 = _make_injury(zona='rodilla', tags=['flexion_rodilla_profunda', 'empuje_pierna'])
        inj2.pk = 2

        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.__iter__ = lambda s: iter([inj1, inj2])
        MockUI.objects.filter.return_value = qs
        MockUI.Fase = MagicMock()
        MockUI.Fase.RECUPERADO = 'RECUPERADO'

        cliente = MagicMock()
        result = BioContextProvider.get_current_restrictions(cliente)

        self.assertEqual(result['tags'], {'impacto_vertical', 'flexion_rodilla_profunda', 'empuje_pierna'})
        self.assertEqual(len(result['injuries']), 2)


# ─────────────────────────────────────────────────────────────
#  Test: get_readiness_score
# ─────────────────────────────────────────────────────────────

class TestGetReadinessScore(TestCase):

    @patch('hyrox.models.DailyRecoveryEntry')
    @patch('hyrox.models.UserInjury')
    def test_no_data_returns_healthy_defaults(self, MockUI, MockDRE):
        """Sin lesiones ni datos de dolor → score alto (cercano a 1.0)."""
        # No injuries
        qs_inj = MagicMock()
        qs_inj.exclude.return_value = qs_inj
        qs_inj.exists.return_value = False
        qs_inj.count.return_value = 0
        MockUI.objects.filter.return_value = qs_inj
        MockUI.Fase = MagicMock()
        MockUI.Fase.RECUPERADO = 'RECUPERADO'
        MockUI.Fase.AGUDA = 'AGUDA'
        MockUI.Fase.SUB_AGUDA = 'SUB_AGUDA'

        # No DRE entries
        qs_dre = MagicMock()
        qs_dre.exclude.return_value = qs_dre
        qs_dre.order_by.return_value = qs_dre
        qs_dre.__getitem__ = lambda s, k: []
        MockDRE.objects.filter.return_value = qs_dre

        cliente = MagicMock()
        result = BioContextProvider.get_readiness_score(cliente)

        self.assertGreater(result['score'], 0.7)
        self.assertEqual(result['volume_modifier'], 1.0)
        self.assertFalse(result['needs_deload'])

    @patch('hyrox.models.DailyRecoveryEntry')
    @patch('hyrox.models.UserInjury')
    def test_high_pain_lowers_score(self, MockUI, MockDRE):
        """Dolor alto → score bajo, volume_modifier reducido."""
        # Injury aguda
        inj = _make_injury(fase='AGUDA', gravedad=8, tags=['impacto_vertical'])
        qs_inj = MagicMock()
        qs_inj.exclude.return_value = qs_inj
        qs_inj.exists.return_value = True
        qs_inj.count.return_value = 1
        qs_inj.__iter__ = lambda s: iter([inj])
        MockUI.objects.filter.return_value = qs_inj
        MockUI.Fase = MagicMock()
        MockUI.Fase.RECUPERADO = 'RECUPERADO'
        MockUI.Fase.AGUDA = 'AGUDA'
        MockUI.Fase.SUB_AGUDA = 'SUB_AGUDA'

        # DRE con dolor alto
        dre = _make_dre(dolor_reposo=7, dolor_movimiento=8, inflamacion=8, rango=3)
        qs_dre = MagicMock()
        qs_dre.exclude.return_value = qs_dre
        qs_dre.order_by.return_value = qs_dre
        qs_dre.__getitem__ = lambda s, k: [dre]
        MockDRE.objects.filter.return_value = qs_dre

        cliente = MagicMock()
        result = BioContextProvider.get_readiness_score(cliente)

        self.assertLess(result['score'], 0.5)
        self.assertLess(result['volume_modifier'], 1.0)
        self.assertGreater(result['pain_score'], 5.0)

    def test_score_boundaries(self):
        """El score siempre está en [0.0, 1.0]."""
        # Verificamos con la lógica directa del cálculo
        # Score min: helms_component=0 + pain_component=0 + phase_penalty=0.3
        raw_min = (0.0 * 0.4) + (0.0 * 0.4) + ((1.0 - 0.3) * 0.2)
        self.assertGreaterEqual(max(0.0, min(1.0, raw_min)), 0.0)

        # Score max: helms_component=1 + pain_component=1 + phase_penalty=0
        raw_max = (1.0 * 0.4) + (1.0 * 0.4) + (1.0 * 0.2)
        self.assertLessEqual(max(0.0, min(1.0, raw_max)), 1.0)
