"""
Phase 9.2 — Tests for contextual progression brake.

Checklist:
1. Semana sólida + margen alto → progresión permitida
2. Carga alta sostenida (patrón) → progresión bloqueada
3. Sesión esencial completada → sesión válida pero sin subida automática
4. Bloque principal parcial (patrón) → no subir
5. Alta continuidad → mantener progresión normal
6. Esenciales frecuentes → bloquear o mantener
7. Margen bajo repetido → no subir accesorios / revisión volumen
8. Lesión activa → (handled by Phase 3A context, brake inherits estado)
9. Sin datos semanales → comportamiento actual (backward compat)
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.services.progresion_contextual_service import (
    evaluar_permiso_progresion,
    aplicar_freno_contextual,
    _es_ejercicio_principal,
    _GRUPOS_GRANDES,
)
from rutinas.models import Rutina


EJ_PRINCIPAL = {
    'nombre': 'Sentadilla con Barra',
    'grupo_muscular': 'cuadriceps',
    'tipo_ejercicio': 'compuesto_principal',
    'peso_kg': 90.0,
}
EJ_ACCESORIO = {
    'nombre': 'Extensión de Cuadriceps',
    'grupo_muscular': 'cuadriceps',
    'tipo_ejercicio': 'aislamiento',
    'peso_kg': 50.0,
}
EJ_GRUPO_PEQUENO = {
    'nombre': 'Curl de Bíceps',
    'grupo_muscular': 'biceps',
    'tipo_ejercicio': 'compuesto_principal',
    'peso_kg': 20.0,
}


def _entrenamiento(ejercicios):
    return {
        'rutina_nombre': 'Test',
        'nombre_rutina': 'Test',
        'ejercicios': [dict(e) for e in ejercicios],
        'objetivo': 'Hipertrofia',
    }


def _permiso_mock(accion, motivo='ok'):
    from entrenos.services.progresion_contextual_service import _permiso
    return _permiso(accion, motivo)


class TestEsEjercicioPrincipal(TestCase):
    def test_compuesto_principal_grupo_grande_es_principal(self):
        self.assertTrue(_es_ejercicio_principal(EJ_PRINCIPAL))

    def test_aislamiento_no_es_principal(self):
        self.assertFalse(_es_ejercicio_principal(EJ_ACCESORIO))

    def test_compuesto_principal_grupo_pequeno_no_es_principal(self):
        self.assertFalse(_es_ejercicio_principal(EJ_GRUPO_PEQUENO))


class TestEvaluarPermisoProgresion(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_p92', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestP92', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 20)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_sin_datos_semana_progresion_permitida(self):
        # Case 9: no weekly data → backward compatible, allow progression
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'progresion_permitida')
        self.assertFalse(permiso['hay_datos_semana'])

    def test_semana_solida_margen_alto_permite(self):
        # Case 1: solid week + high margin → allow
        mock_semana = {
            'hay_datos': True, 'estado_semana': 'margen_extra',
            'margen': 'alto', 'continuidad': 'alta', 'suficiencia': 'completa',
            'sesiones_completadas': 3, 'sesiones_esenciales': 0,
            'bloques_principales_parciales': 0,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'progresion_permitida')

    def test_carga_alta_semanal_bloquea(self):
        # Case 2: weekly carga_alta → block
        mock_semana = {
            'hay_datos': True, 'estado_semana': 'carga_alta',
            'margen': 'bajo', 'continuidad': 'alta', 'suficiencia': 'completa',
            'sesiones_completadas': 2, 'sesiones_esenciales': 2,
            'bloques_principales_parciales': 0,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'mantener_carga')
        self.assertTrue(permiso['aplica_a_principales'])

    def test_sin_error_si_servicio_falla(self):
        # Degradation: service failure → allow (backward compat)
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   side_effect=Exception('servicio caído')):
            permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'progresion_permitida')


class TestAplicarFrenoContextual(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_p92b', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestP92B', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 20)

    def test_progresion_permitida_no_cambia_pesos(self):
        ent = _entrenamiento([EJ_PRINCIPAL])
        permiso = _permiso_mock('progresion_permitida')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        self.assertEqual(resultado['ejercicios'][0]['peso_kg'], EJ_PRINCIPAL['peso_kg'])
        self.assertFalse(resultado['ejercicios'][0]['progresion_bloqueada'])

    def test_mantener_carga_bloquea_principal_y_accesorio(self):
        # Case 2 + 4: mantener_carga blocks all
        ent = _entrenamiento([EJ_PRINCIPAL, EJ_ACCESORIO])
        permiso = _permiso_mock('mantener_carga', 'carga_alta_sostenida')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        for ej in resultado['ejercicios']:
            self.assertTrue(ej['progresion_bloqueada'])
            self.assertIsNotNone(ej['peso_kg_propuesto'])

    def test_reducir_accesorios_solo_bloquea_no_principals(self):
        # Case 7: reducir_accesorios — principal can progress, accessory blocked
        ent = _entrenamiento([EJ_PRINCIPAL, EJ_ACCESORIO])
        permiso = _permiso_mock('reducir_accesorios', 'margen_bajo_repetido')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)

        principal = next(e for e in resultado['ejercicios'] if e['nombre'] == EJ_PRINCIPAL['nombre'])
        accesorio = next(e for e in resultado['ejercicios'] if e['nombre'] == EJ_ACCESORIO['nombre'])

        self.assertFalse(principal['progresion_bloqueada'])   # principal can progress
        self.assertTrue(accesorio['progresion_bloqueada'])    # accessory blocked

    def test_modo_reducido_bloquea_todo(self):
        # Case 3: esencial session completed → no auto-progression
        ent = _entrenamiento([EJ_PRINCIPAL])
        permiso = _permiso_mock('progresion_permitida')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso, modo_reducido=True)
        self.assertTrue(resultado['ejercicios'][0]['progresion_bloqueada'])
        self.assertEqual(resultado['ejercicios'][0]['motivo_bloqueo'], 'modo_reducido')

    def test_bloqueo_preserva_peso_propuesto_para_auditoria(self):
        ent = _entrenamiento([EJ_PRINCIPAL])
        permiso = _permiso_mock('mantener_carga', 'carga_alta_sostenida')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        ej = resultado['ejercicios'][0]
        # peso_kg_propuesto should hold the planificador's proposed weight
        self.assertEqual(ej['peso_kg_propuesto'], EJ_PRINCIPAL['peso_kg'])

    def test_sin_ejercicios_devuelve_intacto(self):
        ent = {'rutina_nombre': 'Test', 'ejercicios': [], 'objetivo': 'Descanso'}
        permiso = _permiso_mock('mantener_carga')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        self.assertEqual(resultado, ent)

    def test_none_devuelve_none(self):
        permiso = _permiso_mock('mantener_carga')
        resultado = aplicar_freno_contextual(self.cliente, None, permiso)
        self.assertIsNone(resultado)

    def test_alta_continuidad_permite_progresion_principal(self):
        # Case 5: alta_continuidad → allow
        ent = _entrenamiento([EJ_PRINCIPAL])
        permiso = _permiso_mock('progresion_permitida', 'ok')
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        self.assertFalse(resultado['ejercicios'][0]['progresion_bloqueada'])


class TestFrenoEsTechoNoSustitucion(TestCase):
    """
    El freno congela la progresión, pero nunca debe SUBIR el peso por
    encima de lo que el plan ya proponía para hoy. Si el plan ya bajó
    (p.ej. por RPE alto o recalibración), esa bajada se respeta —
    "conserva X" debe cumplir siempre X <= peso_kg_propuesto.
    """
    def setUp(self):
        self.user = User.objects.create_user(username='tester_freno_techo', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestFrenoTecho', 'dias_disponibles': 4},
        )

    def test_no_sube_si_propuesto_ya_es_menor_que_ultimo_registrado(self):
        ent = _entrenamiento([{**EJ_PRINCIPAL, 'peso_kg': 52.5}])
        permiso = _permiso_mock('mantener_carga', 'retorno_pausa')
        with patch('entrenos.services.progresion_contextual_service._obtener_peso_actual',
                   return_value=53.8):
            resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        ej = resultado['ejercicios'][0]
        self.assertEqual(ej['peso_kg_propuesto'], 52.5)
        self.assertEqual(ej['peso_kg'], 52.5)

    def test_capa_a_ultimo_registrado_si_propuesto_es_mayor(self):
        ent = _entrenamiento([{**EJ_PRINCIPAL, 'peso_kg': 55.0}])
        permiso = _permiso_mock('mantener_carga', 'retorno_pausa')
        with patch('entrenos.services.progresion_contextual_service._obtener_peso_actual',
                   return_value=52.5):
            resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        ej = resultado['ejercicios'][0]
        self.assertEqual(ej['peso_kg_propuesto'], 55.0)
        self.assertEqual(ej['peso_kg'], 52.5)
