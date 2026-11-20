"""Paquete visual del 20-nov-2026 (Ahora, Plan, navegación compartida): solo presentación,
más la frase de vigencia de los isquios (hasta el 6/12 inclusive; el 7/12 deja de aplicarse)."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

NAV = 'templates/includes/bottom_nav.html'


class NavegacionCompartidaTests(TestCase):
    def test_etiquetas_a_12_px_e_iconos_de_22(self):
        css = Path(NAV).read_text(encoding='utf-8')
        self.assertIn('.bottom-nav-std strong{font:600 12px/1', css)
        self.assertIn('.bottom-nav-std__icon{width:22px;height:22px', css)
        self.assertNotIn('700 7px', css)

    def test_las_cuatro_pestanas_usan_el_mismo_componente(self):
        for plantilla in (
            'clientes/templates/clientes/dashboard_silencioso_preview.html',
            'entrenos/templates/entrenos/rutina_silenciosa_preview.html',
            'clientes/templates/clientes/trayectoria_plan.html',
            'clientes/templates/clientes/memoria_entrenador.html',
        ):
            self.assertIn("includes/bottom_nav.html", Path(plantilla).read_text(encoding='utf-8'), plantilla)


class AhoraVisualTests(TestCase):
    def test_boton_principal_de_56_px_y_sin_lema_de_7_px(self):
        t = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text(encoding='utf-8')
        self.assertIn('.primary{width:100%;min-height:56px', t)
        self.assertIn('.motto{display:none}', t)
        self.assertIn('.strava-link{width:44px;height:44px', t)

    def test_la_pagina_sigue_sirviendo_la_decision_y_las_acciones_de_siempre(self):
        u = get_user_model().objects.create_user(username='ahora-visual', password='x')
        self.client.force_login(u)
        r = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Decisión de hoy')
        self.assertContains(r, 'Cómo responde tu cuerpo')


class PlanVisualTests(TestCase):
    def test_plan_minimo_12_px_en_etiquetas(self):
        t = Path('clientes/templates/clientes/trayectoria_plan.html').read_text(encoding='utf-8')
        self.assertIn('.tp-label{font-size:12px', t)
        self.assertIn('summary.tp-mono{display:flex;align-items:center;min-height:48px', t)

    def test_isquios_dice_hasta_el_6_12_inclusive_y_el_7_12_deja_de_aplicarse(self):
        u = get_user_model().objects.create_user(username='plan-visual', password='x')
        self.client.force_login(u)
        motivo = ('+2 series de Isquios: evolución observada favorable; se aplica hasta el 06/12 inclusive '
                  'y el 07/12 deja de aplicarse si no decides')
        with patch('entrenos.services.volumen_grupo_service.ajustes_volumen',
                   return_value={'isquios': {'series': 2, 'motivos': [motivo]}}), \
             patch('entrenos.services.volumen_grupo_service.revisiones_pendientes', return_value=[]), \
             patch('entrenos.services.propuesta_zona_service.pausa_subir_volumen', return_value=None):
            r = self.client.get(reverse('clientes:trayectoria_plan'))
        self.assertContains(r, 'hasta el 06/12 inclusive')
        self.assertContains(r, 'el 07/12 deja de aplicarse si no decides')
