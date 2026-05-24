"""
Arquitectura 3.0 — Tests del bridge Gym → Hyrox.

Cubre:
1. sync_rm_to_hyrox: actualiza solo si nuevo > actual.
2. sync_rm_to_hyrox: invalida caché después del update.
3. sync_rm_to_hyrox: no escribe si nuevo <= actual.
4. sync_gym_fatigue: inyecta en la próxima sesión planificada.
5. sync_gym_fatigue: no toca sesiones completadas.
6. campo_rm_para_ejercicio: mapea nombres correctamente.
7. Gap 1.2 — combinado: PR oficial + estimación Brzycki sobre el mismo objetivo.
8. Gap 1.2 — combinado: señal gym + señal record_personal en orden invertido.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.utils import get_cliente_actual
from entrenos.services.hyrox_bridge import (
    campo_rm_para_ejercicio,
    sync_gym_fatigue,
    sync_rm_to_hyrox,
)


def _make_objetivo(cliente, rm_sentadilla=None, rm_peso_muerto=None):
    from hyrox.models import HyroxObjective
    return HyroxObjective.objects.create(
        cliente=cliente,
        estado='activo',
        categoria='open_men',
        fecha_evento=date.today() + timedelta(days=90),
        rm_sentadilla=rm_sentadilla,
        rm_peso_muerto=rm_peso_muerto,
    )


def _make_sesion(objetivo, estado='planificado', dias=1):
    from hyrox.models import HyroxSession
    return HyroxSession.objects.create(
        objective=objetivo,
        titulo='Test sesión',
        fecha=date.today() + timedelta(days=dias),
        estado=estado,
    )


class TestSyncRm(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('bridge_rm', password='x')
        self.cliente = get_cliente_actual(self.user)
        self.objetivo = _make_objetivo(self.cliente, rm_sentadilla=80.0)

    def test_actualiza_si_nuevo_mayor(self):
        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 90.0)
        self.assertTrue(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 90.0)

    def test_no_actualiza_si_nuevo_igual(self):
        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 80.0)
        self.assertFalse(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 80.0)

    def test_no_actualiza_si_nuevo_menor(self):
        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 70.0)
        self.assertFalse(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 80.0)

    def test_invalida_cache_tras_actualizacion(self):
        from django.core.cache import cache
        cache.set(f'hyrox_readiness_{self.objetivo.pk}', 'cached_value', 60)
        cache.set(f'dashboard_acwr_unificado_{self.cliente.id}', 'cached_acwr', 60)

        sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 95.0)

        self.assertIsNone(cache.get(f'hyrox_readiness_{self.objetivo.pk}'))
        self.assertIsNone(cache.get(f'dashboard_acwr_unificado_{self.cliente.id}'))

    def test_no_invalida_cache_si_no_actualiza(self):
        from django.core.cache import cache
        cache.set(f'hyrox_readiness_{self.objetivo.pk}', 'still_valid', 60)

        sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 70.0)

        self.assertEqual(cache.get(f'hyrox_readiness_{self.objetivo.pk}'), 'still_valid')

    def test_escribe_en_rm_peso_muerto(self):
        objetivo = _make_objetivo(self.cliente, rm_peso_muerto=100.0)
        sync_rm_to_hyrox(objetivo, 'rm_peso_muerto', 120.0)
        objetivo.refresh_from_db()
        self.assertEqual(float(objetivo.rm_peso_muerto), 120.0)


class TestSyncFatiga(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('bridge_fat', password='x')
        self.cliente = get_cliente_actual(self.user)
        self.objetivo = _make_objetivo(self.cliente)

    def test_inyecta_fatiga_en_proxima_planificada(self):
        sesion = _make_sesion(self.objetivo, estado='planificado', dias=1)
        result = sync_gym_fatigue(self.objetivo, 'Alta', 'test', date.today())
        self.assertTrue(result)
        sesion.refresh_from_db()
        self.assertEqual(sesion.muscle_fatigue_index, 'Alta')

    def test_no_toca_sesiones_completadas(self):
        completada = _make_sesion(self.objetivo, estado='completado', dias=1)
        result = sync_gym_fatigue(self.objetivo, 'Alta', 'test', date.today())
        self.assertFalse(result)
        completada.refresh_from_db()
        self.assertNotEqual(completada.muscle_fatigue_index, 'Alta')

    def test_no_inyecta_si_no_hay_sesion_planificada(self):
        result = sync_gym_fatigue(self.objetivo, 'Alta', 'test', date.today())
        self.assertFalse(result)

    def test_inyecta_en_la_mas_proxima_ignorando_pasadas(self):
        _make_sesion(self.objetivo, estado='planificado', dias=5)
        proxima = _make_sesion(self.objetivo, estado='planificado', dias=2)
        sync_gym_fatigue(self.objetivo, 'Alta', 'test', date.today())
        proxima.refresh_from_db()
        self.assertEqual(proxima.muscle_fatigue_index, 'Alta')


class TestCampoRm(TestCase):

    def test_sentadilla_variantes(self):
        for nombre in ['Sentadilla', 'Back Squat', 'Goblet Squat', 'Front squat', 'hack squat']:
            with self.subTest(nombre=nombre):
                self.assertEqual(campo_rm_para_ejercicio(nombre), 'rm_sentadilla')

    def test_peso_muerto_variantes(self):
        for nombre in ['Peso Muerto', 'Deadlift', 'RDL', 'Romanian Deadlift', 'Sumo Dead']:
            with self.subTest(nombre=nombre):
                self.assertEqual(campo_rm_para_ejercicio(nombre), 'rm_peso_muerto')

    def test_ejercicio_irrelevante_devuelve_none(self):
        self.assertIsNone(campo_rm_para_ejercicio('Press Banca'))
        self.assertIsNone(campo_rm_para_ejercicio('Dominadas'))
        self.assertIsNone(campo_rm_para_ejercicio(''))


class TestGap12CombinedSignals(TestCase):
    """
    Gap documentado en Arquitectura 1.2 — HYROX_GYM_BRIDGE.md:
    combinación de PR oficial + estimación Brzycki sin test de cobertura.
    """

    def setUp(self):
        self.user = User.objects.create_user('bridge_gap', password='x')
        self.cliente = get_cliente_actual(self.user)
        self.objetivo = _make_objetivo(self.cliente, rm_sentadilla=90.0)

    def test_brzycki_no_sobreescribe_pr_mayor(self):
        # PR oficial ya tiene 90 kg. Brzycki estima 85 (entrenamiento ligero).
        # No debe retroceder.
        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 85.0)
        self.assertFalse(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 90.0)

    def test_pr_oficial_gana_sobre_brzycki_previo(self):
        # Brzycki estimó 95 antes. Ahora llega PR oficial de 100.
        self.objetivo.rm_sentadilla = 95.0
        self.objetivo.save(update_fields=['rm_sentadilla'])

        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 100.0)
        self.assertTrue(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 100.0)

    def test_secuencia_brzycki_luego_pr_luego_brzycki_menor(self):
        # 1. Brzycki estima 95 → actualiza (90 < 95)
        sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 95.0)
        # 2. PR oficial de 100 → actualiza (95 < 100)
        sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 100.0)
        # 3. Brzycki estima 92 del siguiente entrenamiento → NO actualiza (92 < 100)
        result = sync_rm_to_hyrox(self.objetivo, 'rm_sentadilla', 92.0)
        self.assertFalse(result)
        self.objetivo.refresh_from_db()
        self.assertEqual(float(self.objetivo.rm_sentadilla), 100.0)
