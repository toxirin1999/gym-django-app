"""Contrato de presentación para la memoria del entrenador."""

from pathlib import Path
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from clientes.views import _progreso_estaciones_comparables
from entrenos.models import GymDecisionLog
from hyrox.models import HyroxActivity, HyroxObjective, HyroxSession


class MemoriaEntrenadorUITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='memoria-ui', password='secreto',
        )
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('clientes:memoria_entrenador', args=[self.cliente.id])

    def test_memoria_prioriza_lectura_de_hoy_y_profundidad_plegable(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'clientes/memoria_entrenador.html')
        self.assertContains(response, 'Lectura de hoy')
        self.assertContains(response, 'Señales esenciales')
        self.assertContains(response, 'Expediente completo')
        self.assertContains(response, 'Memoria')

    def test_plantilla_fija_nav_global_y_secciones_de_profundidad(self):
        plantilla = Path('clientes/templates/clientes/memoria_entrenador.html').read_text()

        self.assertIn("{% include 'includes/bottom_nav.html' with activo='memoria' %}", plantilla)
        self.assertIn('mem-depth', plantilla)
        self.assertIn('<details', plantilla)

    def test_estaciones_solo_compara_evidencia_compatible_y_con_lectura_semantica(self):
        objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=timezone.localdate(),
        )
        primera = HyroxSession.objects.create(
            objective=objetivo, fecha=timezone.localdate() - timedelta(days=7),
            estado='completado',
        )
        ultima = HyroxSession.objects.create(
            objective=objetivo, fecha=timezone.localdate(), estado='completado',
        )
        HyroxActivity.objects.create(
            sesion=primera, tipo_actividad='hyrox_station', nombre_ejercicio='Sled Push',
            data_metricas={'tiempo_s': 100},
        )
        HyroxActivity.objects.create(
            sesion=ultima, tipo_actividad='hyrox_station', nombre_ejercicio='Sled Push',
            data_metricas={'tiempo_s': 90},
        )
        HyroxActivity.objects.create(
            sesion=ultima, tipo_actividad='hiit', nombre_ejercicio='Sled Push intervalos',
            data_metricas={'tiempo_s': 1},
        )

        progreso = _progreso_estaciones_comparables(objetivo)

        self.assertEqual(len(progreso), 1)
        self.assertEqual(progreso[0]['sesiones'], 2)
        self.assertEqual(progreso[0]['lectura_progreso'], '10% más rápido')
        self.assertEqual(progreso[0]['ultimo_seg'], 90)

    def test_decisiones_total_usa_los_noventa_dias_no_el_limite_de_recientes(self):
        for indice in range(25):
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=f'Ejercicio {indice}', accion='mantener',
                motivo='Evidencia suficiente',
            )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context['decisiones_total'], 25)
        self.assertEqual(len(response.context['decisiones_recientes']), 20)
        self.assertEqual(response.context['decisiones_agrupadas']['mantener'], 25)
        self.assertContains(response, '20 de 25')

    def test_perfil_filtra_metadatos_no_numericos_y_muestra_caveat(self):
        self.cliente.one_rm_data = {
            'sentadilla': 120,
            '_rpe_bias': -1.5,
            '_rpe_bias_convention': 'fc_estimated_minus_reported',
            'fuente': {'importacion': 'manual'},
        }
        self.cliente.save(update_fields=['one_rm_data'])
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context['perfil_atletico'], [
            {'ejercicio': 'Sentadilla', 'rm': 120.0},
        ])
        self.assertEqual(response.context['rm_metadatos_descartados'], 3)
        self.assertContains(response, 'datos de metadatos no numéricos')

    def test_actualizacion_refleja_la_fuente_y_no_el_momento_de_renderizado(self):
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press', accion='mantener', motivo='Estable',
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.context['data_updated_source'], 'decisión del plan')
        self.assertIsNotNone(response.context['data_updated_at'])
        self.assertContains(response, 'Datos más recientes')
        self.assertNotContains(response, 'Últ. actualización')
