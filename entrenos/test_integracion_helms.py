# tests/test_integracion_helms.py
import unittest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import math
from clientes.models import Cliente
from analytics.planificador_integrado import PlanificadorIntegrado
from entrenos.utils.convertidor_formatos import ConvertidorFormatos, convertir_plan_para_vista, extraer_datos_educativos


class TestIntegracionHelms(TestCase):
    """Tests para la integración completa del sistema Helms"""

    def setUp(self):
        """Configuración inicial para todos los tests"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

        self.cliente = Cliente.objects.create(
            usuario=self.user,
            nombre='Cliente Test',
            experiencia_años=2.5,
            objetivo_principal='hipertrofia',

            # Campos de Helms
            dias_disponibles=4,
            tiempo_por_sesion=90,
            ejercicios_preferidos=['press_banca', 'sentadilla'],
            ejercicios_evitar=['peso_muerto'],
            flexibilidad_horario=True,
            nivel_estres=5,
            calidad_sueño=7,
            nivel_energia=7,
            one_rm_data={'press_banca': 80, 'sentadilla': 100},
            historial_volumen={'pecho': 16, 'piernas': 20}
        )

        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_creacion_planificador_integrado(self):
        """Test: Crear planificador integrado correctamente"""
        planificador = PlanificadorIntegrado(self.cliente.id)

        # Verificar inicialización
        self.assertIsNotNone(planificador.planificador_helms)
        self.assertIsNotNone(planificador.planificador_actual)
        self.assertEqual(planificador.cliente_id, self.cliente.id)

        # Verificar configuración por defecto
        self.assertTrue(planificador.usar_helms_como_principal)
        self.assertTrue(planificador.incluir_validacion_helms)

    def test_generacion_plan_con_helms(self):
        """Test: Generar plan usando Helms como principal"""
        planificador = PlanificadorIntegrado(self.cliente.id)
        planificador.usar_helms_como_principal = True

        plan = planificador.generar_plan_anual()

        # Verificar estructura básica
        self.assertIn('cliente_id', plan)
        self.assertIn('ejercicios_por_semana', plan)
        self.assertIn('metadata', plan)

        # Verificar que fue generado por Helms
        self.assertEqual(plan['metadata']['generado_por'], 'helms')

        # Verificar datos específicos de Helms
        self.assertIn('datos_helms', plan)
        self.assertIn('rpe_por_ejercicio', plan['datos_helms'])
        self.assertIn('tiempos_descanso', plan['datos_helms'])

    def test_fallback_a_sistema_actual(self):
        """Test: Fallback cuando Helms falla"""
        planificador = PlanificadorIntegrado(self.cliente.id)

        # Simular fallo en Helms (modificando temporalmente)
        planificador.planificador_helms = None

        plan = planificador.generar_plan_anual()

        # Verificar que usó fallback
        self.assertEqual(plan['metadata']['generado_por'], 'fallback')
        self.assertIn('razon_fallback', plan['metadata'])

    def test_conversion_formatos(self):
        """Test: Conversión entre formatos"""
        convertidor = ConvertidorFormatos()

        # Plan de ejemplo en formato Helms
        plan_helms = {
            'cliente_id': self.cliente.id,
            'objetivo': 'hipertrofia',
            'ejercicios_por_semana': {
                '1': [{
                    'nombre': 'Press Banca',
                    'series': 4,
                    'repeticiones': '8-12',
                    'rpe_objetivo': 8,
                    'descanso_minutos': 3,
                    'tempo': '2-0-X-0',
                    'grupo_muscular': 'chest'
                }]
            }
        }

        # Convertir a formato actual
        plan_convertido = convertidor.helms_a_formato_actual(plan_helms)

        # Verificar conversión
        self.assertIn('datos_helms', plan_convertido)
        self.assertEqual(plan_convertido['cliente_id'], self.cliente.id)

        # Verificar ejercicio convertido
        ejercicio = plan_convertido['ejercicios_por_semana']['1'][0]
        self.assertEqual(ejercicio['nombre'], 'Press Banca')
        self.assertEqual(ejercicio['rpe_objetivo'], 8)
        self.assertTrue(ejercicio['es_ejercicio_helms'])

    def test_validacion_conversion(self):
        """Test: Validación de conversión"""
        convertidor = ConvertidorFormatos()

        plan_original = {
            'cliente_id': self.cliente.id,
            'objetivo': 'hipertrofia',
            'ejercicios_por_semana': {'1': [{'nombre': 'Test'}]}
        }

        plan_convertido = convertidor.helms_a_formato_actual(plan_original)
        validacion = convertidor.validar_conversion(plan_original, plan_convertido)

        # Verificar validación exitosa
        self.assertTrue(validacion['exitosa'])
        self.assertEqual(len(validacion['errores']), 0)
        self.assertIn('metricas', validacion)

    def test_vista_plan_calendario(self):
        """Test: Vista principal con integración"""
        url = reverse('vista_plan_calendario', args=[self.cliente.id])
        response = self.client.get(url)

        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, 200)

        # Verificar contexto
        self.assertIn('cliente', response.context)
        self.assertIn('plan', response.context)
        self.assertEqual(response.context['cliente'].id, self.cliente.id)

    def test_api_regenerar_plan(self):
        """Test: API para regenerar plan"""
        url = reverse('api_regenerar_plan', args=[self.cliente.id])

        response = self.client.post(url, {
            'usar_helms': 'true',
            'incluir_validacion': 'true'
        })

        # Verificar respuesta
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('estadisticas', data)

    def test_configuracion_preferencias(self):
        """Test: Configuración de preferencias Helms"""
        url = reverse('configurar_preferencias_helms', args=[self.cliente.id])

        # GET - mostrar formulario
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST - guardar preferencias
        response = self.client.post(url, {
            'dias_disponibles': 5,
            'tiempo_por_sesion': 120,
            'ejercicios_preferidos': ['press_banca', 'sentadilla', 'remo_con_barra'],
            'ejercicios_evitar': ['peso_muerto'],
            'flexibilidad_horario': True,
            'nivel_estres': 4,
            'calidad_sueño': 8,
            'nivel_energia': 8
        })

        # Verificar redirección exitosa
        self.assertEqual(response.status_code, 302)

        # Verificar que se guardaron los cambios
        cliente_actualizado = Cliente.objects.get(id=self.cliente.id)
        self.assertEqual(cliente_actualizado.dias_disponibles, 5)
        self.assertEqual(cliente_actualizado.tiempo_por_sesion, 120)

    def test_estadisticas_integracion(self):
        """Test: Estadísticas de integración"""
        planificador = PlanificadorIntegrado(self.cliente.id)
        estadisticas = planificador.obtener_estadisticas_integracion()

        # Verificar estructura
        self.assertIn('cliente_id', estadisticas)
        self.assertIn('nivel_experiencia', estadisticas)
        self.assertIn('factor_recuperacion', estadisticas)
        self.assertIn('necesita_descarga', estadisticas)

        # Verificar valores
        self.assertEqual(estadisticas['cliente_id'], self.cliente.id)
        self.assertEqual(estadisticas['nivel_experiencia'], 'intermedio')
        self.assertIsInstance(estadisticas['factor_recuperacion'], float)

    def test_manejo_errores(self):
        """Test: Manejo de errores en la integración"""
        # Cliente inexistente
        with self.assertRaises(Exception):
            PlanificadorIntegrado(99999)

        # Plan con datos inválidos
        planificador = PlanificadorIntegrado(self.cliente.id)

        # Simular error modificando cliente
        self.cliente.experiencia_años = -1  # Valor inválido
        self.cliente.save()

        # Debería manejar el error graciosamente
        plan = planificador.generar_plan_anual()
        self.assertIn('metadata', plan)


class TestPerformanceIntegracion(TestCase):
    """Tests de rendimiento para la integración"""

    def setUp(self):
        self.user = User.objects.create_user('perfuser', 'perf@test.com', 'pass')
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            nombre='Cliente Performance',
            experiencia_años=3,
            objetivo_principal='fuerza',
            dias_disponibles=5,
            tiempo_por_sesion=120
        )

    def test_tiempo_generacion_plan(self):
        """Test: Tiempo de generación de plan"""
        import time

        planificador = PlanificadorIntegrado(self.cliente.id)

        inicio = time.time()
        plan = planificador.generar_plan_anual()
        fin = time.time()

        tiempo_generacion = fin - inicio

        # Verificar que toma menos de 5 segundos
        self.assertLess(tiempo_generacion, 5.0)
        self.assertIsNotNone(plan)

    def generar_plan_anual(self) -> Dict[str, Any]:
        """
        Genera el plan anual completo basado en la metodología Helms
        """
        try:
            # 1. Calcular volumen base
            volumen_base = self._calcular_volumen_base()
            print(f"✅ Volumen base calculado: {volumen_base}")

            # 2. Obtener periodización
            periodizacion = self._obtener_periodizacion()
            print(f"✅ Periodización obtenida: {len(periodizacion)} fases")

            # 3. Crear plan semanal base
            plan_semanal = self._crear_plan_semanal_base(volumen_base)
            print(f"✅ Plan semanal creado")

            # 4. Generar fases del año
            fases_anuales = []
            for i, fase_config in enumerate(periodizacion):
                fase = {
                    'numero': i + 1,
                    'semanas': fase_config['semanas'],
                    'fase': fase_config['fase'],
                    'volumen_multiplicador': fase_config['volumen_multiplicador'],
                    'intensidad_rpe': fase_config['intensidad_rpe'],
                    'rep_range': fase_config['rep_range'],
                    'distribucion': self._aplicar_fase_a_plan(plan_semanal, fase_config)
                }
                fases_anuales.append(fase)

            # 5. Crear estructura final del plan
            plan_final = {
                'cliente_id': self.perfil.cliente_id,
                'objetivo': self.perfil.objetivo_principal.value if hasattr(self.perfil.objetivo_principal,
                                                                            'value') else str(
                    self.perfil.objetivo_principal),
                'duracion_semanas': 52,
                'fases': fases_anuales,
                'volumen_base': volumen_base,
                'plan_semanal_base': plan_semanal,
                'metadata': {
                    'generado_por': 'PlanificadorHelms',
                    'version': '1.0',
                    'fecha_generacion': datetime.now().isoformat(),
                    'nivel_experiencia': self.perfil.nivel_experiencia.value if hasattr(self.perfil.nivel_experiencia,
                                                                                        'value') else str(
                        self.perfil.nivel_experiencia),
                    'dias_disponibles': self.dias_disponibles,
                    'tiempo_por_sesion': self.tiempo_por_sesion
                }
            }

            print(f"✅ Plan anual generado: {len(plan_final['fases'])} fases")
            return plan_final

        except Exception as e:
            print(f"❌ Error en generar_plan_anual: {str(e)}")
            import traceback
            traceback.print_exc()

            # Retornar plan básico de emergencia
            return {
                'cliente_id': self.perfil.cliente_id,
                'error': str(e),
                'plan_emergencia': True,
                'fases': [{
                    'numero': 1,
                    'semanas': list(range(1, 53)),
                    'fase': 'plan_basico',
                    'distribucion': {
                        'dia_1': [{'nombre': 'press_banca', 'series': 3, 'repeticiones': '8-10', 'rpe': 7}],
                        'dia_2': [{'nombre': 'sentadilla', 'series': 3, 'repeticiones': '8-10', 'rpe': 7}],
                        'dia_3': [{'nombre': 'remo_con_barra', 'series': 3, 'repeticiones': '8-10', 'rpe': 7}]
                    }
                }],
                'metadata': {
                    'generado_por': 'PlanificadorHelms_Emergencia',
                    'error_original': str(e)
                }
            }

    def _aplicar_fase_a_plan(self, plan_base: Dict, fase_config: Dict) -> Dict:
        """
        Aplica configuración de fase al plan base
        """
        distribucion_fase = {}

        for dia, ejercicios in plan_base.get('distribucion', {}).items():
            ejercicios_fase = []

            for ejercicio in ejercicios:
                if isinstance(ejercicio, dict):
                    ejercicio_fase = ejercicio.copy()

                    # Aplicar multiplicador de volumen
                    series_base = ejercicio_fase.get('series', 3)
                    series_ajustadas = max(1, int(series_base * fase_config['volumen_multiplicador']))
                    ejercicio_fase['series'] = series_ajustadas

                    # Aplicar RPE de la fase
                    rpe_min, rpe_max = fase_config['intensidad_rpe']
                    ejercicio_fase['rpe'] = rpe_max  # Usar el RPE máximo de la fase

                    # Aplicar rango de repeticiones
                    ejercicio_fase['repeticiones'] = fase_config['rep_range']

                    ejercicios_fase.append(ejercicio_fase)
                else:
                    ejercicios_fase.append(ejercicio)

            distribucion_fase[dia] = ejercicios_fase

        return distribucion_fase

    def test_memoria_conversion(self):
        """Test: Uso de memoria en conversión"""
        import sys

        convertidor = ConvertidorFormatos()

        # Plan grande para test de memoria
        plan_grande = {
            'cliente_id': self.cliente.id,
            'ejercicios_por_semana': {
                str(i): [
                    {'nombre': f'Ejercicio {j}', 'series': 4}
                    for j in range(10)
                ] for i in range(1, 53)  # 52 semanas
            }
        }

        memoria_inicial = sys.getsizeof(plan_grande)
        plan_convertido = convertidor.helms_a_formato_actual(plan_grande)
        memoria_final = sys.getsizeof(plan_convertido)

        # Verificar que no hay explosión de memoria
        ratio_memoria = memoria_final / memoria_inicial
        self.assertLess(ratio_memoria, 3.0)  # No más de 3x el tamaño original

# Ejecutar tests con:
# python manage.py test tests.test_integracion_helms
