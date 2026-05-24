"""
Arquitectura 2.1 — Smoke tests del refactoring de context builders.

Objetivo: confirmar que construir_contexto sigue produciendo las mismas claves
y comportamientos clave tras la extracción a joi/context_builders/.

Casos cubiertos:
1. El facade llama a los 5 builders y agrega sus resultados.
2. La dependencia cruzada acwr → fatiga_extragym se propaga correctamente.
3. Cada builder devuelve un dict (no lanza), incluso con BD vacía.
4. El facade tolera que cualquier builder falle silenciosamente.
"""

from datetime import date
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.utils import get_cliente_actual


class ContextBuilderBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cb2', password='x')
        self.cliente = get_cliente_actual(self.user)


class TestFacadeAgregatBuilders(ContextBuilderBase):
    """Case 1: facade devuelve un dict con claves de todos los builders."""

    def test_construir_contexto_devuelve_dict(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        self.assertIsInstance(ctx, dict)

    def test_construir_contexto_incluye_clave_actividad(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        # build_activity_context siempre escribe estas claves
        self.assertIn('actividad_semana', ctx)
        self.assertIn('sesiones_semana_total', ctx)
        self.assertIn('racha_dias', ctx)

    def test_construir_contexto_incluye_clave_gym(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        # build_gym_context siempre escribe decisiones_plan y prs_semana
        self.assertIn('decisiones_plan', ctx)
        self.assertIn('prs_semana', ctx)

    def test_construir_contexto_incluye_historial_joi(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        # build_joi_state_context siempre escribe historial_joi (lista vacía si no hay mensajes)
        self.assertIn('historial_joi', ctx)
        self.assertIsInstance(ctx['historial_joi'], list)


class TestAcwrCrossDependency(ContextBuilderBase):
    """Case 2: acwr de activity_context llega a fatiga_extragym en life_context."""

    def test_fatiga_extragym_cuando_acwr_bajo_y_energia_baja(self):
        from joi.context_builders.life_context import build_life_context
        hoy = date.today()
        semana_reciente = hoy

        mock_bio = {
            'has_data': True,
            'energia': 3,
            'horas_sueno': 7,
            'fc_reposo': 60,
            'hrv_ms': 45,
        }
        with patch('core.bio_context.BioContextProvider.get_bio_signals', return_value=mock_bio):
            ctx = build_life_context(self.cliente, hoy, semana_reciente, acwr=0.7)

        self.assertIn('fatiga_extragym', ctx)
        self.assertEqual(ctx['fatiga_extragym']['acwr'], 0.7)

    def test_fatiga_extragym_ausente_cuando_acwr_normal(self):
        from joi.context_builders.life_context import build_life_context
        hoy = date.today()
        semana_reciente = hoy

        mock_bio = {
            'has_data': True,
            'energia': 3,
            'horas_sueno': 5,
            'fc_reposo': 60,
            'hrv_ms': 45,
        }
        with patch('core.bio_context.BioContextProvider.get_bio_signals', return_value=mock_bio):
            ctx = build_life_context(self.cliente, hoy, semana_reciente, acwr=1.1)

        self.assertNotIn('fatiga_extragym', ctx)

    def test_acwr_del_facade_se_pasa_a_life_context(self):
        """El facade pasa ctx.get('acwr') a build_life_context — test de integración."""
        from joi.services import construir_contexto
        with patch('joi.context_builders.activity_context.build_activity_context') as mock_act:
            mock_act.return_value = {'acwr': 0.65, 'actividad_semana': {}, 'sesiones_semana_total': 0,
                                     'sesiones_gym_semana': 0, 'sesiones_recientes': [], 'racha_dias': 0,
                                     'carga_semanas': None}
            with patch('joi.context_builders.life_context.build_life_context') as mock_life:
                mock_life.return_value = {}
                with patch('joi.context_builders.gym_context.build_gym_context', return_value={}):
                    with patch('joi.context_builders.hyrox_context.build_hyrox_context', return_value={}):
                        with patch('joi.context_builders.joi_state_context.build_joi_state_context',
                                   return_value={'historial_joi': []}):
                            construir_contexto(self.cliente)

        # Verificar que life_context recibió acwr=0.65
        _, kwargs = mock_life.call_args
        self.assertEqual(kwargs.get('acwr'), 0.65)


class TestBuilderResiliencia(ContextBuilderBase):
    """Case 3 & 4: cada builder devuelve dict y el facade sobrevive fallos."""

    def test_activity_builder_devuelve_dict_con_bd_vacia(self):
        from joi.context_builders.activity_context import build_activity_context
        hoy = date.today()
        ctx = build_activity_context(self.cliente, hoy, hoy)
        self.assertIsInstance(ctx, dict)

    def test_gym_builder_devuelve_dict_con_bd_vacia(self):
        from joi.context_builders.gym_context import build_gym_context
        hoy = date.today()
        ctx = build_gym_context(self.cliente, hoy, hoy)
        self.assertIsInstance(ctx, dict)

    def test_hyrox_builder_devuelve_dict_con_bd_vacia(self):
        from joi.context_builders.hyrox_context import build_hyrox_context
        hoy = date.today()
        ctx = build_hyrox_context(self.cliente, hoy, hoy)
        self.assertIsInstance(ctx, dict)

    def test_life_builder_devuelve_dict_con_bd_vacia(self):
        from joi.context_builders.life_context import build_life_context
        hoy = date.today()
        ctx = build_life_context(self.cliente, hoy, hoy)
        self.assertIsInstance(ctx, dict)

    def test_joi_state_builder_devuelve_dict_con_bd_vacia(self):
        from joi.context_builders.joi_state_context import build_joi_state_context
        hoy = date.today()
        ctx = build_joi_state_context(self.cliente, hoy)
        self.assertIsInstance(ctx, dict)
        self.assertIn('historial_joi', ctx)

    def test_facade_sobrevive_si_un_builder_lanza(self):
        """Si un builder explota, el facade no debe propagar la excepción."""
        from joi.services import construir_contexto
        with patch('joi.context_builders.gym_context.build_gym_context',
                   side_effect=RuntimeError('fallo simulado')):
            # No debe lanzar — el facade tiene que ser robusto
            try:
                construir_contexto(self.cliente)
                # Si llega aquí, el facade absorbe el fallo — correcto
            except RuntimeError:
                self.fail('construir_contexto propagó un fallo de builder')
