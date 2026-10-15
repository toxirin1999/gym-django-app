"""Ahora: sin aplazar en descanso, sin CTA repetida y con un aprendizaje real."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from clientes.views import _resumen_aprendizaje_plan


class AhoraDescansoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ahora-desc', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('clientes:dashboard_silencioso_preview')
        self.client.force_login(self.user)
        self.ctx = {
            '_decision_gym_raw': {}, 'proximo_entrenamiento': {},
            'explicacion_decision': {}, 'acwr_actual': None,
        }

    def _get(self, motivo):
        with patch('clientes.views._get_dashboard_context_data', return_value=self.ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', return_value={
                    'estado': 'SILENCIO', 'motivo': motivo, 'texto': 'Hoy el plan marca descanso.',
                    'accion_label': None, 'accion_url': None,
                }):
            return self.client.get(self.url)

    def test_descanso_sin_aplazar_ni_movilidad_repetida(self):
        response = self._get('descanso_planificado')
        self.assertIsNone(response.context['quiet_postpone_url'])
        self.assertNotContains(response, 'Hacer esta sesión mañana')
        self.assertEqual(response.content.decode().count('Movilidad y estiramientos'), 1)

    def test_sesion_hecha_tampoco_ofrece_aplazar(self):
        self.assertIsNone(self._get('sesion_completada').context['quiet_postpone_url'])

    def test_dia_de_entreno_conserva_aplazar(self):
        with patch('clientes.views._get_dashboard_context_data', return_value=self.ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', return_value={
                    'estado': 'EN_MARGEN', 'texto': 'Hay margen para seguir el plan.',
                    'accion_label': None, 'accion_url': None,
                }):
            response = self.client.get(self.url)
        self.assertIsNotNone(response.context['quiet_postpone_url'])

    def test_el_aprendizaje_usa_la_ultima_decision_del_plan(self):
        from entrenos.models import GymDecisionLog
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='press banca', accion='subir_peso',
            valor_cambio=2.5, peso_anterior=60, motivo='x', motivo_codigo='progresion_peso',
        )
        response = self._get('descanso_planificado')
        # valor_cambio es un % interno: se cita el peso objetivo, nunca "+2,5 kg".
        self.assertRegex(
            response.context['quiet_insight'],
            r'^Press banca: subí el peso a [\d,]+ kg · progresión de peso\.$',
        )


class ResumenAprendizajeTests(TestCase):
    def test_descanso_no_se_vende_como_aprendizaje(self):
        texto = _resumen_aprendizaje_plan([], 'Nada que forzar.', 'Hoy el plan marca descanso.')
        self.assertIn('Aún no hay una adaptación nueva', texto)

    def test_senal_activa_va_antes_que_el_aprendizaje(self):
        self.assertEqual(
            _resumen_aprendizaje_plan(['⚽ Fútbol reciente'], 'x', None, aprendizaje='Press: mantener.'),
            '⚽ Fútbol reciente',
        )


class AprendizajeComprobadoTests(TestCase):
    """14-oct-2026: lo que el plan volvió a mirar y funcionó va primero (regla 4)."""

    def test_decision_comprobada_va_antes_que_la_senal(self):
        frase = 'Curl femoral: subí el peso a 45 kg. Después: 45 kg × 6 con RPE 8. Funcionó.'
        self.assertEqual(
            _resumen_aprendizaje_plan(['⚽ Fútbol reciente'], 'x', None, aprendizaje=frase), frase,
        )

    def test_ultimo_aprendizaje_cita_la_comprobacion(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from clientes.models import Cliente
        from clientes.views import _ultimo_aprendizaje_plan
        from entrenos.models import GymDecisionLog
        user = User.objects.create_user(username='aprendizaje-comprobado', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'A'})
        GymDecisionLog.objects.create(
            cliente=cliente, ejercicio='curl femoral tumbado', accion='subir_peso',
            valor_cambio=5, peso_anterior=42.5, motivo='x', resultado='validada',
            fecha_evaluacion=timezone.now(),
        )
        GymDecisionLog.objects.create(  # más reciente, pero sin comprobar
            cliente=cliente, ejercicio='press banca', accion='mantener', motivo='x',
        )
        texto = _ultimo_aprendizaje_plan(cliente, timezone.localdate())
        self.assertTrue(texto.startswith('Curl femoral tumbado: subí el peso a '), texto)
        self.assertTrue(texto.endswith('Funcionó.'), texto)
