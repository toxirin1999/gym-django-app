"""
Tests para Phase Organismo 1 — Resolver estado global del sistema.

Tests simplificados: validan la lógica del resolver sin depender de modelos complejos.

Tests:
1. Sin señales → SILENCIO
2. Resolver devuelve estructura válida
3. Estados válidos
4. Lesión AGUDA activa → PROTEGIENDO
5. No modifica BD
"""

from datetime import date
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User

from clientes.models import Cliente
from hyrox.models import UserInjury
from core.organismo import resolver_estado_sistema_hoy


class TestOrganismoResolver(TestCase):
    """Tests del resolver de estado global."""

    def setUp(self):
        """Crear usuario y cliente mínimo."""
        self.user = User.objects.create_user('test_organismo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.experiencia_años = 3
        self.cliente.objetivo_principal = 'hipertrofia'
        self.cliente.dias_disponibles = 4
        self.cliente.save()

    def test_sin_senales_retorna_silencio(self):
        """Sin señales de ningún módulo (sesión simulada como descanso) → SILENCIO."""
        _descanso = {'tipo': 'descanso', 'estado': 'descanso', 'entrenamiento': None, 'sesion_programada': None, 'mensaje': 'Descanso.', 'causa_principal': None, 'modo_reducido': False, 'distribucion_aviso': None}
        with patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy', return_value=_descanso):
            resultado = resolver_estado_sistema_hoy(self.user)

        self.assertEqual(resultado['estado'], 'SILENCIO')
        self.assertEqual(resultado['motivo'], 'sin_senales')
        self.assertIn('nada que forzar', resultado['texto'].lower())
        self.assertIsNone(resultado['accion_label'])

    def test_resolver_retorna_estructura_valida(self):
        """Resolver siempre devuelve dict con estructura correcta."""
        resultado = resolver_estado_sistema_hoy(self.user)

        # Validar estructura
        self.assertIsInstance(resultado, dict)
        self.assertIn('estado', resultado)
        self.assertIn('motivo', resultado)
        self.assertIn('texto', resultado)
        self.assertIn('accion_label', resultado)
        self.assertIn('accion_url', resultado)
        self.assertIn('modulo_principal', resultado)

        # Validar tipos
        self.assertIsInstance(resultado['estado'], str)
        self.assertIsInstance(resultado['motivo'], str)
        self.assertIsInstance(resultado['texto'], str)

    def test_estados_validos(self):
        """El resolver solo devuelve 4 estados válidos."""
        resultado = resolver_estado_sistema_hoy(self.user)

        self.assertIn(
            resultado['estado'],
            ['SILENCIO', 'OBSERVANDO', 'EN_MARGEN', 'PROTEGIENDO']
        )

    def test_lesion_aguda_retorna_protegiendo(self):
        """Lesión AGUDA activa → PROTEGIENDO."""
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=['flexion_rodilla_profunda'],
            gravedad=5
        )

        resultado = resolver_estado_sistema_hoy(self.user)

        self.assertEqual(resultado['estado'], 'PROTEGIENDO')
        self.assertEqual(resultado['motivo'], 'lesion_activa')
        self.assertEqual(resultado['modulo_principal'], 'hyrox')
        self.assertIsNotNone(resultado['accion_url'])

    def test_lesion_retorno_no_es_protegiendo(self):
        """Lesión RETORNO no activa PROTEGIENDO."""
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Tobillo',
            fase='RETORNO',  # ← RETORNO, no AGUDA
            activa=True,
            tags_restringidos=['flexion_tobillo'],
            gravedad=2
        )

        resultado = resolver_estado_sistema_hoy(self.user)

        # RETORNO no debería activar PROTEGIENDO (solo AGUDA/SUB_AGUDA)
        self.assertNotEqual(resultado['estado'], 'PROTEGIENDO')

    def test_resolver_no_modifica_modelos(self):
        """El resolver no modifica nada en BD."""
        # Registrar cambios iniciales
        lesion_count_before = UserInjury.objects.count()

        # Llamar resolver
        resultado = resolver_estado_sistema_hoy(self.user)

        # Verificar que nada cambió
        self.assertEqual(UserInjury.objects.count(), lesion_count_before)

    def test_motivo_siempre_tiene_valor(self):
        """El motivo nunca debe ser None o vacío."""
        resultado = resolver_estado_sistema_hoy(self.user)

        self.assertIsNotNone(resultado['motivo'])
        self.assertTrue(resultado['motivo'].strip())

    def test_texto_siempre_tiene_valor(self):
        """El texto nunca debe ser None o vacío."""
        resultado = resolver_estado_sistema_hoy(self.user)

        self.assertIsNotNone(resultado['texto'])
        self.assertTrue(resultado['texto'].strip())

    def test_prioridad_protegiendo_sobre_silencio(self):
        """PROTEGIENDO > SILENCIO: si lesión activa, gana PROTEGIENDO."""
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Tobillo',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=3
        )

        resultado = resolver_estado_sistema_hoy(self.user)

        # Debe ganar PROTEGIENDO
        self.assertEqual(resultado['estado'], 'PROTEGIENDO')

    def test_multiple_lesiones_una_activa(self):
        """Si hay múltiples lesiones pero una está AGUDA, devuelve PROTEGIENDO."""
        # Crear una RETORNO (no activa)
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Hombro',
            fase='RETORNO',
            activa=True,
            tags_restringidos=[],
            gravedad=2
        )
        # Crear una AGUDA
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=4
        )

        resultado = resolver_estado_sistema_hoy(self.user)

        # Debe ganar PROTEGIENDO por la lesión AGUDA
        self.assertEqual(resultado['estado'], 'PROTEGIENDO')

    def test_resolver_con_usuario_sin_lesion(self):
        """Resolver funciona para usuario sin lesiones."""
        resultado = resolver_estado_sistema_hoy(self.user)

        self.assertIsNotNone(resultado)
        # Sin lesiones activas, PROTEGIENDO no puede activarse
        self.assertNotEqual(resultado['estado'], 'PROTEGIENDO')

    def test_accion_correspond_to_module(self):
        """La acción viene del módulo principal (lesión AGUDA → Hyrox)."""
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=5
        )

        resultado = resolver_estado_sistema_hoy(self.user)

        # Si módulo es hyrox, acción debe estar en hyrox
        if resultado['modulo_principal'] == 'hyrox':
            self.assertIsNotNone(resultado['accion_url'])
            if resultado['accion_url']:
                self.assertIn('hyrox', resultado['accion_url'])
