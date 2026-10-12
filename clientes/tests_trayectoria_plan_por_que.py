from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class TrayectoriaPlanPorQueTests(TestCase):
    """La explicación vive junto al bloque y solo afirma datos disponibles."""

    def setUp(self):
        self.user = User.objects.create_user('trayectoria_por_que', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def _trayectoria(self, *, bloque=True, periodizacion=True):
        hoy = date.today()
        return {
            'fecha_corte': hoy,
            'estado': 'available',
            'bloque': ({
                'objetivo': 'Construir fuerza útil',
                'objetivos_secundarios': ['Mejorar la técnica'],
            } if bloque else None),
            'periodizacion': ({
                'nombre': 'Fuerza', 'semana_actual': 2, 'semanas': 4,
                'inicio': hoy, 'fin': hoy + timedelta(days=27),
                'rpe_inicio': 7, 'rpe_fin': 8, 'reps': '4-6',
                'descanso_seg': 120,
            } if periodizacion else None),
            'macrociclo': None,
            'proximo_hito': None,
            'semana': None,
        }

    def _get(self, trayectoria):
        with patch(
            'entrenos.services.trayectoria_plan_service.proyectar_trayectoria_plan',
            return_value=trayectoria,
        ):
            return self.client.get(reverse('clientes:trayectoria_plan'))

    def test_explicacion_del_bloque_usa_solo_objetivo_y_parametros_reales(self):
        response = self._get(self._trayectoria())

        self.assertEqual(response.status_code, 200)
        explicacion = response.context['explicacion_bloque_plan']
        self.assertTrue(explicacion['disponible'])
        self.assertIn('Construir fuerza útil', explicacion['resumen'])
        self.assertIn('4-6', explicacion['detalles'])
        self.assertIn('RPE 7–8', explicacion['detalles'])
        self.assertContains(response, 'Por qué este bloque')
        self.assertContains(response, explicacion['resumen'])
        self.assertContains(response, explicacion['detalles'])

    def test_sin_datos_del_bloque_muestra_un_limite_honesto_sin_enlace_duplicado(self):
        response = self._get(self._trayectoria(bloque=False, periodizacion=False))

        explicacion = response.context['explicacion_bloque_plan']
        self.assertFalse(explicacion['disponible'])
        self.assertContains(response, 'Todavía no hay datos suficientes para explicar este bloque.')
        self.assertNotContains(response, reverse('analytics:explicacion_plan_helms'))
