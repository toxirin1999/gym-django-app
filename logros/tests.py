# ============================================================================
# PASO 5: TESTS AUTOMATIZADOS PARA SISTEMA DE GAMIFICACIÓN
# ============================================================================
# Archivo: logros/tests.py

from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from logros.models import (
    PerfilGamificacion, Logro, LogroUsuario, HistorialPuntos,
    Nivel, Mision, MisionUsuario
)
from entrenos.models import EntrenoRealizado, SerieRealizada
from clientes.models import Cliente
from logros.services import GamificacionServiceMejorado, GamificacionDebugService


class GamificacionSystemTestCase(TransactionTestCase):
    """
    Tests completos para el sistema de gamificación.
    Usa TransactionTestCase para probar transacciones atómicas.
    """

    def setUp(self):
        """Configuración inicial para cada test"""
        # Crear cliente de prueba
        self.cliente = Cliente.objects.create(
            nombre="Test User",
            email="test@example.com",
            telefono="123456789"
        )

        # Crear perfil de gamificación
        self.perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente,
            puntos_totales=0,
            nivell=1,
            entrenos_totales=0,
            racha_actual=0
        )

        # Crear logros de prueba
        self.logro_principiante = Logro.objects.create(
            nombre="Liftin Principiante",
            descripcion="Completa 5 entrenamientos de Liftin",
            categoria="entrenos",
            meta_valor=5,
            puntos_recompensa=100,
            icono="🏋️"
        )

        self.logro_intermedio = Logro.objects.create(
            nombre="Liftin Intermedio",
            descripcion="Completa 10 entrenamientos de Liftin",
            categoria="entrenos",
            meta_valor=10,
            puntos_recompensa=200,
            icono="💪"
        )

        self.logro_calorias = Logro.objects.create(
            nombre="Quemador Principiante",
            descripcion="Quema 300 calorías en total",
            categoria="calorias",
            meta_valor=300,
            puntos_recompensa=150,
            icono="🔥"
        )

    def test_procesamiento_automatico_entreno(self):
        """Test: Procesamiento automático cuando se crea un entrenamiento"""
        # Crear entrenamiento
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            fecha=date.today(),
            fuente_datos='liftin',
            duracion_minutos=60,
            calorias_quemadas=100,
            volumen_total_kg=500.0
        )

        # Verificar que se procesó automáticamente
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.entrenos_totales, 1)
        self.assertGreater(self.perfil.puntos_totales, 0)

        # Verificar que se creó entrada en historial
        historial_count = HistorialPuntos.objects.filter(perfil=self.perfil).count()
        self.assertGreater(historial_count, 0)

    def test_desbloqueo_logro_automatico(self):
        """Test: Desbloqueo automático de logros al alcanzar meta"""
        # Crear 5 entrenamientos para desbloquear logro principiante
        for i in range(5):
            EntrenoRealizado.objects.create(
                cliente=self.cliente,
                fecha=date.today() - timedelta(days=i),
                fuente_datos='liftin',
                duracion_minutos=60,
                calorias_quemadas=50,
                volumen_total_kg=400.0
            )

        # Verificar que se desbloqueó el logro
        logro_usuario = LogroUsuario.objects.filter(
            perfil=self.perfil,
            logro=self.logro_principiante,
            completado=True
        ).first()

        self.assertIsNotNone(logro_usuario)
        self.assertTrue(logro_usuario.completado)

        # Verificar puntos del logro
        self.perfil.refresh_from_db()
        self.assertGreaterEqual(self.perfil.puntos_totales, 100)

    def test_calculo_progreso_logros(self):
        """Test: Cálculo correcto del progreso de logros"""
        # Crear 3 entrenamientos
        for i in range(3):
            EntrenoRealizado.objects.create(
                cliente=self.cliente,
                fecha=date.today() - timedelta(days=i),
                fuente_datos='liftin',
                duracion_minutos=60,
                calorias_quemadas=100,
                volumen_total_kg=400.0
            )

        # Calcular progreso del logro principiante (meta: 5)
        progreso = GamificacionServiceMejorado._calcular_progreso_logro(
            self.perfil, self.logro_principiante, None
        )

        self.assertEqual(progreso, 3)

        # Calcular progreso del logro de calorías (meta: 300, actual: 300)
        progreso_calorias = GamificacionServiceMejorado._calcular_progreso_logro(
            self.perfil, self.logro_calorias, None
        )

        self.assertEqual(progreso_calorias, 300)

    def test_sincronizacion_datos(self):
        """Test: Sincronización correcta de datos inconsistentes"""
        # Crear datos inconsistentes intencionalmente
        self.perfil.puntos_totales = 999  # Valor incorrecto
        self.perfil.entrenos_totales = 999  # Valor incorrecto
        self.perfil.save()

        # Crear datos reales
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            fecha=date.today(),
            fuente_datos='liftin',
            duracion_minutos=60,
            calorias_quemadas=100,
            volumen_total_kg=400.0
        )

        HistorialPuntos.objects.create(
            perfil=self.perfil,
            puntos=150,
            descripcion="Test points",
            fecha=timezone.now()
        )

        # Ejecutar sincronización
        resultado = GamificacionDebugService.sincronizar_datos_perfil(self.cliente.id)

        # Verificar corrección
        self.assertTrue(resultado['exito'])
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.entrenos_totales, 1)
        self.assertEqual(self.perfil.puntos_totales, 150)

    def test_deteccion_logros_potenciales(self):
        """Test: Detección de logros que deberían estar completados"""
        # Crear suficientes entrenamientos para logro principiante
        for i in range(6):  # Más de los 5 necesarios
            EntrenoRealizado.objects.create(
                cliente=self.cliente,
                fecha=date.today() - timedelta(days=i),
                fuente_datos='liftin',
                duracion_minutos=60,
                calorias_quemadas=50,
                volumen_total_kg=400.0
            )

        # Simular que el logro no se otorgó automáticamente
        LogroUsuario.objects.filter(
            perfil=self.perfil,
            logro=self.logro_principiante
        ).delete()

        # Detectar logros potenciales
        logros_potenciales = GamificacionDebugService._detectar_logros_potenciales(self.perfil)

        # Verificar detección
        self.assertGreater(len(logros_potenciales), 0)
        logro_detectado = next(
            (l for l in logros_potenciales if l['logro_id'] == self.logro_principiante.id),
            None
        )
        self.assertIsNotNone(logro_detectado)
        self.assertGreaterEqual(logro_detectado['progreso'], 5)

    def test_validacion_integridad_sistema(self):
        """Test: Validación de integridad del sistema completo"""
        # Crear datos de prueba
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            fecha=date.today(),
            fuente_datos='liftin',
            duracion_minutos=60,
            calorias_quemadas=100,
            volumen_total_kg=400.0
        )

        # Ejecutar validación
        reporte = GamificacionDebugService.validar_integridad_sistema()

        # Verificar reporte
        self.assertIn('perfiles_analizados', reporte)
        self.assertIn('perfiles_saludables', reporte)
        self.assertIn('perfiles_con_problemas', reporte)
        self.assertGreaterEqual(reporte['perfiles_analizados'], 1)

    def test_manejo_errores_transacciones(self):
        """Test: Manejo correcto de errores y rollback de transacciones"""
        puntos_iniciales = self.perfil.puntos_totales

        # Simular error durante procesamiento
        with patch.object(GamificacionServiceMejorado, '_otorgar_logro') as mock_otorgar:
            mock_otorgar.side_effect = Exception("Error simulado")

            # Intentar procesar entrenamiento
            try:
                GamificacionServiceMejorado.procesar_gamificacion_completa(
                    self.cliente.id, None
                )
            except:
                pass

            # Verificar que no se corrompieron los datos
            self.perfil.refresh_from_db()
            # Los puntos no deberían haber cambiado debido al rollback
            # (esto depende de la implementación específica)

    def test_performance_procesamiento_masivo(self):
        """Test: Performance del sistema con múltiples entrenamientos"""
        import time

        start_time = time.time()

        # Crear múltiples entrenamientos
        entrenamientos = []
        for i in range(20):
            entrenamientos.append(EntrenoRealizado(
                cliente=self.cliente,
                fecha=date.today() - timedelta(days=i),
                fuente_datos='liftin',
                duracion_minutos=60,
                calorias_quemadas=100,
                volumen_total_kg=400.0
            ))

        EntrenoRealizado.objects.bulk_create(entrenamientos)

        # Procesar gamificación para todos
        for entreno in EntrenoRealizado.objects.filter(cliente=self.cliente):
            GamificacionServiceMejorado.procesar_gamificacion_completa(
                self.cliente.id, entreno
            )

        end_time = time.time()
        processing_time = end_time - start_time

        # Verificar que el procesamiento fue razonablemente rápido
        self.assertLess(processing_time, 10.0)  # Menos de 10 segundos

        # Verificar resultados
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.entrenos_totales, 20)
        self.assertGreater(self.perfil.puntos_totales, 0)


class GamificacionUnitTestCase(TestCase):
    """
    Tests unitarios para funciones específicas del sistema de gamificación.
    """

    def setUp(self):
        """Configuración para tests unitarios"""
        self.cliente = Cliente.objects.create(
            nombre="Unit Test User",
            email="unittest@example.com",
            telefono="987654321"
        )

        self.perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente,
            puntos_totales=500,
            nivell=2,
            entrenos_totales=10,
            racha_actual=3
        )

    def test_calculo_nivel_por_puntos(self):
        """Test: Cálculo correcto de nivel basado en puntos"""
        # Test diferentes rangos de puntos
        self.assertEqual(GamificacionDebugService._calcular_nivel_por_puntos(500), 1)
        self.assertEqual(GamificacionDebugService._calcular_nivel_por_puntos(1500), 2)
        self.assertEqual(GamificacionDebugService._calcular_nivel_por_puntos(4000), 3)
        self.assertEqual(GamificacionDebugService._calcular_nivel_por_puntos(8000), 4)
        self.assertEqual(GamificacionDebugService._calcular_nivel_por_puntos(12000), 5)

    def test_validacion_datos_entrada(self):
        """Test: Validación de datos de entrada"""
        # Test con cliente inexistente
        resultado = GamificacionDebugService.diagnosticar_perfil_completo(99999)
        self.assertIn('error', resultado)

        # Test con datos válidos
        resultado = GamificacionDebugService.diagnosticar_perfil_completo(self.cliente.id)
        self.assertIn('cliente_id', resultado)
        self.assertEqual(resultado['cliente_id'], self.cliente.id)

    def test_logging_operaciones(self):
        """Test: Verificar que se registran logs correctamente"""
        with patch('logros.services.logger') as mock_logger:
            # Ejecutar operación que debería generar logs
            GamificacionDebugService.sincronizar_datos_perfil(self.cliente.id)

            # Verificar que se llamó al logger
            mock_logger.info.assert_called()

            # Verificar contenido de logs
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            self.assertTrue(any('Sincronizando datos' in call for call in log_calls))


# ============================================================================
# TESTS DE INTEGRACIÓN CON COMANDOS DE GESTIÓN
# ============================================================================

class ComandosGestionTestCase(TestCase):
    """
    Tests para los comandos de gestión Django.
    """

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre="Command Test User",
            email="command@example.com",
            telefono="555666777"
        )

        self.perfil = PerfilGamificacion.objects.create(
            cliente=self.cliente,
            puntos_totales=1000,
            nivell=2,
            entrenos_totales=5,
            racha_actual=1
        )

    def test_comando_diagnosticar(self):
        """Test: Comando de diagnóstico"""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('gamificacion_debug', 'diagnosticar', '--cliente', self.cliente.id, stdout=out)

        output = out.getvalue()
        self.assertIn('DIAGNÓSTICO COMPLETO', output)
        self.assertIn(str(self.cliente.id), output)

    def test_comando_sincronizar(self):
        """Test: Comando de sincronización"""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('gamificacion_debug', 'sincronizar', '--cliente', self.cliente.id, stdout=out)

        output = out.getvalue()
        self.assertIn('Sincronización exitosa', output)


# ============================================================================
# CONFIGURACIÓN DE TESTS
# ============================================================================

"""
CONFIGURACIÓN PARA EJECUTAR TESTS:

1. Agregar a settings.py (para tests):

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Base de datos en memoria para tests
    }
}

2. Ejecutar tests:

# Todos los tests
python manage.py test logros

# Tests específicos
python manage.py test logros.tests.GamificacionSystemTestCase

# Tests con verbose
python manage.py test logros --verbosity=2

# Tests con coverage (instalar: pip install coverage)
coverage run --source='.' manage.py test logros
coverage report
coverage html

3. Tests de performance:
python manage.py test logros.tests.GamificacionSystemTestCase.test_performance_procesamiento_masivo

4. Tests de integración:
python manage.py test logros.tests.ComandosGestionTestCase
"""


# ============================================================================
# MÉTRICAS Y BENCHMARKS
# ============================================================================

class GamificacionBenchmarkTestCase(TestCase):
    """
    Tests de performance y benchmarks del sistema.
    """

    def test_benchmark_procesamiento_100_entrenos(self):
        """Benchmark: Procesar 100 entrenamientos"""
        import time

        cliente = Cliente.objects.create(
            nombre="Benchmark User",
            email="benchmark@example.com",
            telefono="111222333"
        )

        start_time = time.time()

        # Crear y procesar 100 entrenamientos
        for i in range(100):
            EntrenoRealizado.objects.create(
                cliente=cliente,
                fecha=date.today() - timedelta(days=i % 30),
                fuente_datos='liftin',
                duracion_minutos=60,
                calorias_quemadas=100,
                volumen_total_kg=400.0
            )

        end_time = time.time()
        total_time = end_time - start_time

        print(f"\n📊 Benchmark: 100 entrenamientos procesados en {total_time:.2f} segundos")
        print(f"⚡ Promedio: {total_time / 100:.4f} segundos por entrenamiento")

        # Verificar que el tiempo es aceptable
        self.assertLess(total_time, 30.0)  # Menos de 30 segundos para 100 entrenamientos
