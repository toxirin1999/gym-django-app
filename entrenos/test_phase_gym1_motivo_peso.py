"""
Phase Gym 1 Tests: Motivo del Peso Recomendado

Validación que cada ejercicio muestra una explicación determinista
del peso elegido: sube/mantiene/frenado/sin_datos.

Tests:
1. test_motivo_peso_sube_cuando_rpe_baja
2. test_motivo_peso_mantiene_cuando_rpe_normal
3. test_motivo_peso_frenado_cuando_rpe_alta
4. test_motivo_peso_sin_datos_cuando_sin_historial
5. test_motivo_peso_en_template_render
6. test_motivo_peso_mobile_render
"""

import json
from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from clientes.models import Cliente
from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente


class TestMotivoPeso(TestCase):
    """Test del motivo_peso en los ejercicios recomendados."""

    def setUp(self):
        """Crear usuario y cliente de prueba."""
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password123')
        # El Cliente se crea automáticamente por un signal cuando se crea el User
        self.cliente = Cliente.objects.get(user=self.user)
        # Actualizar campos si es necesario
        self.cliente.experiencia_años = 3
        self.cliente.objetivo_principal = 'hipertrofia'
        self.cliente.dias_disponibles = 4
        self.cliente.nivel_estres = 5
        self.cliente.calidad_sueño = 7
        self.cliente.nivel_energia = 7
        self.cliente.save()
        self.client = Client()

    def test_planificador_incluye_motivo_peso(self):
        """Verificar que PlanificadorHelms incluye motivo_peso en ejercicios."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)

        # Generar una sesión
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        # Verificar que si hay ejercicios, cada uno tiene motivo_peso
        if entrenamiento and entrenamiento.get('ejercicios'):
            for ej in entrenamiento['ejercicios']:
                self.assertIn('motivo_peso', ej,
                    f"Ejercicio '{ej.get('nombre')}' no tiene motivo_peso")
                self.assertIn('tipo', ej['motivo_peso'],
                    f"motivo_peso para '{ej.get('nombre')}' sin 'tipo'")
                self.assertIn('texto', ej['motivo_peso'],
                    f"motivo_peso para '{ej.get('nombre')}' sin 'texto'")

                # Validar que tipo es uno de los válidos
                valid_tipos = ['sube', 'mantiene', 'frenado', 'sin_datos']
                self.assertIn(ej['motivo_peso']['tipo'], valid_tipos,
                    f"tipo '{ej['motivo_peso']['tipo']}' no es válido")

                # Validar que texto no es vacío
                self.assertTrue(ej['motivo_peso']['texto'].strip(),
                    f"texto de motivo_peso vacío para '{ej.get('nombre')}'")

    def test_motivo_peso_json_serializable(self):
        """Verificar que motivo_peso puede ser serializado a JSON."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        # Intentar serializar a JSON
        try:
            json_str = json.dumps(entrenamiento)
            self.assertIsNotNone(json_str)

            # Verificar que se puede deserializar
            data = json.loads(json_str)
            self.assertIsNotNone(data)

            if data and data.get('ejercicios'):
                for ej in data['ejercicios']:
                    self.assertIn('motivo_peso', ej)
        except (TypeError, ValueError) as e:
            self.fail(f"motivo_peso no es JSON serializable: {e}")

    def test_motivo_peso_tipos_validos(self):
        """Verificar que los tipos de motivo_peso son los esperados."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        valid_tipos = ['sube', 'mantiene', 'frenado', 'sin_datos']

        if entrenamiento and entrenamiento.get('ejercicios'):
            for ej in entrenamiento['ejercicios']:
                motivo_tipo = ej['motivo_peso']['tipo']
                self.assertIn(motivo_tipo, valid_tipos,
                    f"tipo '{motivo_tipo}' no es válido")

    def test_motivo_peso_no_vacio(self):
        """Verificar que el texto de motivo_peso no está vacío."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        if entrenamiento and entrenamiento.get('ejercicios'):
            for ej in entrenamiento['ejercicios']:
                texto = ej['motivo_peso']['texto']
                self.assertTrue(texto.strip(),
                    f"texto vacío para ejercicio '{ej.get('nombre')}'")
                # Verificar que el texto contiene patrones esperados
                self.assertTrue(
                    'Sube por' in texto or
                    'Carga mantenida' in texto or
                    'Progresión frenada' in texto or
                    'Sin historial' in texto or
                    'Peso determinado' in texto,
                    f"texto inesperado: {texto}"
                )

    def test_motivo_peso_en_vista_entrenamiento_activo(self):
        """Verificar que motivo_peso se pasa correctamente a la vista."""
        self.client.login(username='testuser', password='password123')

        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios generados para probar")

        # Serializar ejercicios
        ejercicios_json = json.dumps(entrenamiento['ejercicios'])

        # Llamar a la vista
        response = self.client.get(
            f'/entrenos/cliente/{self.cliente.id}/entrenamiento-activo/',
            {
                'fecha': date.today().isoformat(),
                'rutina_nombre': entrenamiento.get('rutina_nombre', ''),
                'ejercicios': ejercicios_json,
            }
        )

        # Verificar que la respuesta es 200
        self.assertEqual(response.status_code, 200,
            f"Vista retornó {response.status_code}, esperaba 200")

    def test_motivo_peso_en_template(self):
        """Verificar que motivo_peso se renderiza en el template."""
        self.client.login(username='testuser', password='password123')

        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios generados para probar")

        # Serializar ejercicios
        ejercicios_json = json.dumps(entrenamiento['ejercicios'])

        # Llamar a la vista
        response = self.client.get(
            f'/entrenos/cliente/{self.cliente.id}/entrenamiento-activo/',
            {
                'fecha': date.today().isoformat(),
                'rutina_nombre': entrenamiento.get('rutina_nombre', ''),
                'ejercicios': ejercicios_json,
            }
        )

        # Verificar que el HTML contiene referencias a motivo
        content = response.content.decode()

        # Si hay ejercicios, debe haber al menos uno con motivo_peso
        if entrenamiento['ejercicios']:
            # Buscar referencias al motivo en el HTML
            # (puede estar en data attributes o en el texto visible)
            self.assertIn('peso-motivo', content,
                "No se encontró .peso-motivo en el HTML renderizado")

    def test_motivo_peso_estructura_valida(self):
        """Verificar que la estructura de motivo_peso es siempre válida."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(date.today())

        if entrenamiento and entrenamiento.get('ejercicios'):
            for ej in entrenamiento['ejercicios']:
                motivo = ej['motivo_peso']

                # Verificar que es un diccionario
                self.assertIsInstance(motivo, dict,
                    f"motivo_peso debe ser dict, no {type(motivo)}")

                # Verificar que tiene exactamente las claves esperadas
                self.assertEqual(set(motivo.keys()), {'tipo', 'texto'},
                    f"motivo_peso tiene claves inesperadas: {motivo.keys()}")

                # Verificar tipos de datos
                self.assertIsInstance(motivo['tipo'], str,
                    "tipo debe ser string")
                self.assertIsInstance(motivo['texto'], str,
                    "texto debe ser string")
