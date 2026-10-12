"""Regla 3: el por qué de la decisión, en una frase y con el dato (o nada)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from entrenos.services.porque_decision_service import construir_porque


def _decision(causa='sesion_hoy', estado='entrenar', **contexto):
    return {'causa_principal': causa, 'estado': estado, 'contexto_fisico': contexto}


class ConstruirPorqueTests(SimpleTestCase):
    def test_carga_alta_cita_acwr_y_porcentaje(self):
        texto = construir_porque(_decision('carga_alta', 'version_reducida', acwr_valor=1.62))
        self.assertEqual(texto, 'ACWR 1,62: esta semana llevas un 62 % más de carga que tu media. Hoy, versión reducida.')

    def test_dia_normal_explica_el_margen_con_el_dato(self):
        texto = construir_porque(_decision(acwr_valor=0.84))
        self.assertEqual(texto, 'ACWR 0,84: esta semana llevas un 16 % menos de carga que tu media. Carga estable: hay margen.')

    def test_energia_y_readiness_citan_su_valor(self):
        self.assertIn('Energía 3/10', construir_porque(_decision('energia_baja', 'version_reducida', energia_valor=3)))
        self.assertIn('Readiness 40/100', construir_porque(_decision('fatiga_alta', 'recuperar', readiness_valor=40)))

    def test_pico_dudoso_lo_dice_sin_frenar(self):
        texto = construir_porque(_decision(acwr_valor=2.32, acwr_dudoso=True))
        self.assertIn('2,32', texto)
        self.assertIn('parece un error', texto)

    def test_sin_dato_no_inventa(self):
        self.assertIsNone(construir_porque(_decision()))
        self.assertIsNone(construir_porque(_decision('energia_baja', 'version_reducida')))
        self.assertIsNone(construir_porque({}))
        self.assertIsNone(construir_porque(None))


class PorqueEnAhoraTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('porque-ahora', password='x')
        self.client.force_login(self.user)
        self.url = reverse('clientes:dashboard_silencioso_preview')

    def _get(self, estado, decision_gym):
        ctx = {'_decision_gym_raw': decision_gym, 'proximo_entrenamiento': {},
               'explicacion_decision': {}, 'acwr_actual': 0.84}
        with patch('clientes.views._get_dashboard_context_data', return_value=ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', return_value={
                    'estado': estado, 'motivo': 'descanso_planificado' if estado == 'SILENCIO' else '',
                    'texto': 'Hay margen para seguir el plan.', 'accion_label': None, 'accion_url': None,
                }):
            return self.client.get(self.url)

    def test_ahora_muestra_el_porque(self):
        response = self._get('EN_MARGEN', _decision(acwr_valor=0.84))
        self.assertIn('ACWR 0,84', response.context['quiet_decision']['porque'])
        self.assertContains(response, 'class="decision-why"')

    def test_en_descanso_no_hay_porque_de_carga(self):
        response = self._get('SILENCIO', _decision('descanso_planificado', 'descanso', acwr_valor=0.84))
        self.assertIsNone(response.context['quiet_decision']['porque'])
        self.assertNotContains(response, 'class="decision-why"')


class PorqueEnBriefingTests(SimpleTestCase):
    def test_briefing_usa_la_autoridad_vigente(self):
        from entrenos.views import _porque_briefing
        self.assertIsNone(_porque_briefing(None))
        self.assertIn('ACWR 1,62', _porque_briefing(_decision('carga_alta', 'version_reducida', acwr_valor=1.62)))

    def test_plantilla_del_briefing_lo_muestra(self):
        from pathlib import Path
        plantilla = Path('entrenos/templates/entrenos/briefing_entrenamiento.html').read_text(encoding='utf-8')
        self.assertIn('{% if porque_decision %}', plantilla)
