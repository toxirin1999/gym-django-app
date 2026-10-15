from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class TrayectoriaPlanPorQueTests(TestCase):
    """La trayectoria prioriza acciones y no repite la ficha del bloque."""

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

    def test_no_muestra_el_panel_generico_por_que_este_bloque(self):
        response = self._get(self._trayectoria())

        self.assertEqual(response.status_code, 200)
        explicacion = response.context['explicacion_bloque_plan']
        self.assertTrue(explicacion['disponible'])
        self.assertNotContains(response, 'Por qué este bloque')
        self.assertNotContains(response, 'Lectura del bloque')
        self.assertNotContains(response, 'RPE 7–8')

    def test_sin_datos_del_bloque_tampoco_muestra_un_panel_vacio(self):
        response = self._get(self._trayectoria(bloque=False, periodizacion=False))

        explicacion = response.context['explicacion_bloque_plan']
        self.assertFalse(explicacion['disponible'])
        self.assertNotContains(response, 'Todavía no hay datos suficientes para explicar este bloque.')
        self.assertNotContains(response, reverse('analytics:explicacion_plan_helms'))

    def test_situa_el_progreso_temporal_con_fechas_reales_del_plan(self):
        hoy = date(2026, 10, 12)
        trayectoria = self._trayectoria()
        trayectoria['fecha_corte'] = hoy
        trayectoria['periodizacion']['inicio'] = date(2026, 10, 5)
        trayectoria['periodizacion']['fin'] = date(2026, 11, 1)
        trayectoria['periodizacion']['semana_actual'] = 2
        trayectoria['periodizacion']['semanas'] = 4

        response = self._get(trayectoria)

        progreso = response.context['progreso_temporal_plan']
        self.assertTrue(progreso['disponible'])
        self.assertEqual(progreso['porcentaje'], 29)
        self.assertEqual(progreso['semana_iso'], 42)
        self.assertEqual(progreso['semanas_restantes'], 3)
        self.assertContains(response, 'Progreso temporal')
        self.assertContains(response, '29%')
        self.assertContains(response, '2 de 4')  # semana del bloque, no la ISO (14-oct-2026)

    def test_no_finge_un_progreso_anual_sin_rango_fechado(self):
        trayectoria = self._trayectoria(periodizacion=False)

        response = self._get(trayectoria)

        self.assertFalse(response.context['progreso_temporal_plan']['disponible'])
        self.assertNotContains(response, 'Progreso temporal')
