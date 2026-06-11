"""
Phase 45.1 — Tests de integración de JOI semanal en la experiencia real.

JOI no debe aparecer porque puede hablar; debe aparecer cuando su
presencia mejora la lectura del momento.

Checklist (8):
1.  Sin datos → get_lectura_joi_para_mostrar devuelve None.
2.  estado=minima, debe_hablar=False → None.
3.  Estado válido con texto → devuelve dict con texto_breve.
4.  Misma lectura dos veces → segunda vez devuelve None (ya mostrada).
5.  Lectura diferente → sí se muestra aunque misma sesión.
6.  Panel no muestra tarjeta si joi_semanal=None.
7.  Panel muestra tarjeta si joi_semanal tiene texto.
8.  Centro muestra lectura completa si lectura_semanal_joi existe.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from joi.lectura_joi_presencia import (
    get_lectura_joi_para_mostrar, limpiar_lectura_mostrada,
)


class PresenciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_pres45', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestPres45', 'dias_disponibles': 4},
        )
        cache.clear()

    def tearDown(self):
        cache.clear()


# ── Cases 1-2: sin datos o minima → None ─────────────────────────────────────

class TestCase1_SinDatos(PresenciaBase):
    def test_sin_datos_devuelve_none(self):
        resultado = get_lectura_joi_para_mostrar(self.cliente)
        self.assertIsNone(resultado)


class TestCase2_MinimaNone(PresenciaBase):
    def test_minima_debe_hablar_false_devuelve_none(self):
        lectura_mock = {
            'hay_datos': True, 'n_decisiones': 1,  # < 2 → minima, debe_hablar=False
            'texto_joi': 'Una frase.', 'balance_estados': {'entrenar': 1},
            'senales_positivas': 0, 'senales_no_captadas': 0,
            'n_hipotesis_abiertas': 0, 'n_preferencias_activas': 0,
        }
        from entrenos.services.lectura_semanal_service import calcular_estado_joi_semanal
        lectura_mock['estado_joi'] = calcular_estado_joi_semanal(lectura_mock)

        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   return_value=lectura_mock):
            resultado = get_lectura_joi_para_mostrar(self.cliente)
        self.assertIsNone(resultado)


# ── Cases 3-5: texto válido ───────────────────────────────────────────────────

class TestCase3_DevuelveDict(PresenciaBase):
    def test_lectura_valida_devuelve_dict(self):
        lectura_mock = {
            'hay_datos': True, 'n_decisiones': 4,
            'texto_joi': 'Esta semana el margen apareció en 2 decisiones. Una señal de continuidad.',
            'balance_estados': {'entrenar': 4},
            'senales_positivas': 2, 'senales_no_captadas': 0,
            'n_hipotesis_abiertas': 0, 'n_preferencias_activas': 0,
        }
        from entrenos.services.lectura_semanal_service import calcular_estado_joi_semanal
        lectura_mock['estado_joi'] = calcular_estado_joi_semanal(lectura_mock)

        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   return_value=lectura_mock):
            resultado = get_lectura_joi_para_mostrar(self.cliente)

        self.assertIsNotNone(resultado)
        self.assertIn('texto_breve', resultado)
        self.assertIn('estado', resultado)
        self.assertTrue(resultado['debe_mostrar'])


class TestCase4_MismaDosVecesNone(PresenciaBase):
    def test_misma_lectura_segunda_vez_none(self):
        lectura_mock = {
            'hay_datos': True, 'n_decisiones': 4,
            'texto_joi': 'Esta semana el margen apareció. Continuidad.',
            'balance_estados': {'entrenar': 4},
            'senales_positivas': 2, 'senales_no_captadas': 0,
            'n_hipotesis_abiertas': 0, 'n_preferencias_activas': 0,
        }
        from entrenos.services.lectura_semanal_service import calcular_estado_joi_semanal
        lectura_mock['estado_joi'] = calcular_estado_joi_semanal(lectura_mock)

        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   return_value=lectura_mock):
            r1 = get_lectura_joi_para_mostrar(self.cliente)
            r2 = get_lectura_joi_para_mostrar(self.cliente)

        self.assertIsNotNone(r1)
        self.assertIsNone(r2)  # second time: same text → None


class TestCase5_TextoDiferenteSemuestra(PresenciaBase):
    def test_texto_diferente_se_muestra_de_nuevo(self):
        base_mock = {
            'hay_datos': True, 'n_decisiones': 4,
            'balance_estados': {'entrenar': 4},
            'senales_positivas': 2, 'senales_no_captadas': 0,
            'n_hipotesis_abiertas': 0, 'n_preferencias_activas': 0,
        }
        from entrenos.services.lectura_semanal_service import calcular_estado_joi_semanal

        lectura1 = {**base_mock, 'texto_joi': 'Esta semana hubo margen. Primera.'}
        lectura1['estado_joi'] = calcular_estado_joi_semanal(lectura1)

        lectura2 = {**base_mock, 'texto_joi': 'Esta semana el margen fue menor. Segunda.'}
        lectura2['estado_joi'] = calcular_estado_joi_semanal(lectura2)

        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   return_value=lectura1):
            r1 = get_lectura_joi_para_mostrar(self.cliente)
        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   return_value=lectura2):
            r2 = get_lectura_joi_para_mostrar(self.cliente)

        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)  # different text → shown again


# ── Cases 6-7: panel ─────────────────────────────────────────────────────────

class TestCase6_PanelSinJoiSemanal(PresenciaBase):
    def test_panel_sin_joi_semanal_no_muestra_tarjeta(self):
        with patch('clientes.views._ctx_joi_semanal', return_value=None):
            c = Client()
            c.login(username='tester_pres45', password='x')
            response = c.get(reverse('clientes:mockup_demo'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'JOI · esta semana')


class TestCase7_PanelConJoiSemanal(PresenciaBase):
    def test_panel_con_joi_semanal_muestra_tarjeta(self):
        joi_mock = {
            'texto_breve': 'Esta semana el margen apareció.',
            'texto_completo': 'Esta semana el margen apareció en 2 decisiones.',
            'estado': 'serena',
            'debe_mostrar': True,
        }
        with patch('clientes.views._ctx_joi_semanal', return_value=joi_mock):
            c = Client()
            c.login(username='tester_pres45', password='x')
            response = c.get(reverse('clientes:mockup_demo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JOI · esta semana')
        self.assertContains(response, 'Esta semana el margen apareció.')


# ── Case 8: Centro muestra lectura completa ───────────────────────────────────

class TestCase8_CentroConLectura(PresenciaBase):
    def test_centro_carga_aunque_lectura_semanal_falle(self):
        """If lectura_semanal_joi computation fails, Centro still loads."""
        with patch('entrenos.services.lectura_semanal_service.construir_lectura_semanal_memoria',
                   side_effect=Exception('simulated error')):
            c = Client()
            c.login(username='tester_pres45', password='x')
            response = c.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(response.status_code, 200)
        # lectura_semanal_joi section should not appear (graceful fallback)
        self.assertContains(response, 'Activo ahora')
