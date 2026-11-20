from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

VOL = 'entrenos.services.volumen_grupo_service.'
PAUSA = 'entrenos.services.propuesta_zona_service.pausa_subir_volumen'
AJUSTE_ISQUIOS = {'isquios': {'series': 2, 'motivos': [
    '+2 series de Isquios: el cambio funcionó; se mantiene hasta el 06/12 y después queda pendiente de tu decisión',
]}}
PAUSA_TRI_TRAP = {'zonas': ('triceps', 'trapecios'), 'fin_previsto': date(2026, 12, 6),
                  'bloque': 'Fuerza — Hipertrofia'}


class PlanLeeLosAjustesEfectivosTests(TestCase):
    """20-nov-2026: Plan dice lo que el planificador aplica de verdad, no «No hay ajustes activos»."""

    def setUp(self):
        self.user = User.objects.create_user('plan_ajustes_efectivos', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def _get(self, ajustes=None, revisiones=None, pausa=None):
        with patch(VOL + 'ajustes_volumen', return_value=ajustes or {}), \
                patch(VOL + 'revisiones_pendientes', return_value=revisiones or []), \
                patch(PAUSA, return_value=pausa):
            return self.client.get(reverse('clientes:trayectoria_plan'))

    def test_un_ajuste_de_series_vigente_se_muestra_con_su_porque(self):
        response = self._get(ajustes=AJUSTE_ISQUIOS)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '+2 series por semana de isquios')
        self.assertContains(response, 'se mantiene hasta el 06/12')
        self.assertNotContains(response, 'No hay ajustes activos')
        self.assertEqual(response.context['ajustes_efectivos_plan'][0]['tipo'], 'series')

    def test_la_pausa_de_subir_series_de_triceps_y_trapecio_se_muestra_con_su_fecha(self):
        response = self._get(pausa=PAUSA_TRI_TRAP)

        self.assertContains(response, 'Sin subir series de tríceps y trapecio')
        self.assertContains(response, 'en pausa hasta el 06/12')
        self.assertContains(response, 'El peso y las repeticiones siguen su progresión.')
        self.assertNotContains(response, 'No hay ajustes activos')

    def test_ajuste_y_pausa_conviven(self):
        response = self._get(ajustes=AJUSTE_ISQUIOS, pausa=PAUSA_TRI_TRAP)

        tipos = [a['tipo'] for a in response.context['ajustes_efectivos_plan']]
        self.assertEqual(tipos, ['series', 'pausa'])

    def test_una_revision_vencida_pide_decision_y_no_cuenta_como_ajuste_aplicado(self):
        revision = {'series': 2, 'nombre_zona': 'Isquios', 'limite': date(2026, 12, 6)}
        response = self._get(revisiones=[revision])

        self.assertContains(response, 'Decidir si siguen las 2 series por semana de isquios')
        self.assertContains(response, 'No se prolonga sin una decisión tuya.')
        self.assertEqual([a['tipo'] for a in response.context['ajustes_efectivos_plan']], ['revision'])

    def test_sin_ajustes_ni_pausa_se_mantiene_el_texto_honesto(self):
        response = self._get()

        self.assertEqual(response.context['ajustes_efectivos_plan'], [])
        self.assertContains(response, 'No hay ajustes activos que cambien el plan hoy.')

    def test_si_falla_la_lectura_no_rompe_la_pagina(self):
        with patch(VOL + 'ajustes_volumen', side_effect=RuntimeError('boom')), \
                patch(PAUSA, side_effect=RuntimeError('boom')):
            response = self.client.get(reverse('clientes:trayectoria_plan'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ajustes_efectivos_plan'], [])
