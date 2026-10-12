from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import PreferenciaPlanAprendida


class TrayectoriaPlanDecisionesTests(TestCase):
    """La trayectoria ofrece un extracto, no una segunda pantalla de decisiones."""

    def setUp(self):
        self.user = User.objects.create_user('trayectoria_decisiones', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def _get(self):
        return self.client.get(reverse('clientes:trayectoria_plan'))

    def test_muestra_un_resumen_vacio_honesto_y_enlaza_al_centro_canonico(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        resumen = response.context['resumen_decisiones_plan']
        self.assertFalse(resumen['hay_senales_activas'])
        self.assertEqual(resumen['total_senales_activas'], 0)
        self.assertContains(response, 'Decisiones del plan')
        self.assertContains(response, 'No hay ajustes activos que cambien el plan hoy.')
        self.assertContains(response, reverse('clientes:plan_decisiones'))

    def test_resume_las_senales_activas_con_la_narrativa_del_centro(self):
        with patch('joi.services.generar_mensaje_joi'):
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=date.today(),
                ultima_confirmacion=date.today(),
            )

        response = self._get()

        resumen = response.context['resumen_decisiones_plan']
        self.assertTrue(resumen['hay_senales_activas'])
        self.assertEqual(resumen['total_senales_activas'], 1)
        self.assertIn('El plan está usando 1 señal activa', resumen['narrativa'])
        self.assertContains(response, resumen['narrativa'])
