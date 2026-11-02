"""2-nov-2026 · Pausar la propuesta no recoloca los días de la descarga."""

from unittest.mock import patch

from django.test import TestCase

from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.test_planificador_helms_x4 import PERFIL_DAVID, _build_planner


def _semana(ajustes_fn):
    per = GeneradorPeriodizacion.generar_periodizacion_anual()
    j = next(i for i, b in enumerate(per) if b['fase'] == 'descarga' and i > 2)
    p = _build_planner(PERFIL_DAVID)
    p._cliente_dinamico = object()
    with patch('entrenos.services.volumen_grupo_service.series_por_grupo', side_effect=ajustes_fn):
        s = p._generar_semana_especifica(per[j], j + 1)
    return {d: sorted({e['grupo_muscular'] for e in ejs}) for d, ejs in s.items()}, s


class Reparto(TestCase):
    def test_pausada_reparte_igual_que_activa(self):
        activa, _ = _semana(lambda c, f, incluir_pausadas=False: {'isquios': 2})
        pausada, s = _semana(lambda c, f, incluir_pausadas=False: {'isquios': 2} if incluir_pausadas else {})
        self.assertEqual(activa, pausada)
        # Y en pausa no suma las series de la propuesta.
        _, s_activa = _semana(lambda c, f, incluir_pausadas=False: {'isquios': 2})
        isq = lambda sem: sum(e['series'] for ejs in sem.values() for e in ejs if e['grupo_muscular'] == 'isquios')
        self.assertLessEqual(isq(s), isq(s_activa))
