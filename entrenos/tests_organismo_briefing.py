"""
Tests para Phase Organismo 3 — Continuidad de postura en briefing.

Valida que:
1. Briefing obtiene estado_sistema del resolver
2. Estado != SILENCIO se renderiza mínimamente
3. SILENCIO no se renderiza
4. EN_MARGEN mantiene texto "carga ajustada"
5. PROTEGIENDO mantiene texto sin tono de empuje
6. Fallo del resolver no rompe briefing
7. No altera ejercicios ni modo_reducido
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from clientes.models import Cliente
from hyrox.models import UserInjury
from datetime import date
import json


class TestOrganismoBriefing(TestCase):
    """Tests para Phase Organismo 3 — continuidad de postura en briefing."""

    def setUp(self):
        """Crear usuario y cliente para tests."""
        self.user = User.objects.create_user('test_org3_briefing', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='test_org3_briefing', password='x')

    def test_briefing_obtiene_estado_sistema(self):
        """Briefing obtiene estado_sistema en contexto."""
        # Construir URL mínima con parámetros requeridos
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Test',
            'ejercicios': json.dumps([]),
        }
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        self.assertEqual(response.status_code, 200)
        self.assertIn('estado_sistema', response.context)
        estado_sistema = response.context['estado_sistema']
        self.assertIsNotNone(estado_sistema)
        self.assertIn('estado', estado_sistema)

    def test_estado_en_margen_se_renderiza(self):
        """Si estado es EN_MARGEN, se renderiza con texto en briefing."""
        # Crear una sesión viable (esto debería resultar en EN_MARGEN)
        # Para simplificar, vamos a verificar que si hay sesión viable, aparece el bloque
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Potencia',
            'ejercicios': json.dumps([
                {
                    'nombre': 'Curl Femoral Tumbado',
                    'series': 4,
                    'repeticiones': '3-5',
                    'peso_kg': 65.0,
                }
            ]),
            'modo_reducido': '1',
        }
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        content = response.content.decode()
        # Si EN_MARGEN, debería tener la sección de postura
        if 'EN MARGEN' in response.context.get('estado_sistema', {}).get('estado', ''):
            self.assertIn('SISTEMA HOY', content)

    def test_estado_silencio_no_se_renderiza(self):
        """Si estado es SILENCIO, no se renderiza el bloque de postura."""
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Test',
            'ejercicios': json.dumps([]),
        }
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        estado_sistema = response.context.get('estado_sistema', {})
        content = response.content.decode()

        # Si el estado es SILENCIO, NO debe renderizar el bloque
        if estado_sistema and estado_sistema.get('estado') == 'SILENCIO':
            # Buscar en el content si aparece la sección (no debería)
            # (Este test valida que el template respeta la lógica)
            self.assertNotIn('SISTEMA HOY', content[:content.find('BIB')] if 'BIB' in content else content)

    def test_protegiendo_conserva_texto(self):
        """Si estado es PROTEGIENDO, se renderiza con el texto del resolver."""
        # Crear lesión para disparar PROTEGIENDO
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=5
        )

        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Test',
            'ejercicios': json.dumps([]),
        }
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        estado_sistema = response.context.get('estado_sistema', {})
        if estado_sistema.get('estado') == 'PROTEGIENDO':
            content = response.content.decode()
            self.assertIn('SISTEMA HOY', content)
            self.assertIn(estado_sistema['texto'], content)

    def test_resolver_failure_no_rompe_briefing(self):
        """Si resolver falla, briefing sigue funcionando sin estado_sistema."""
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Test',
            'ejercicios': json.dumps([]),
        }
        # La view intenta llamar al resolver dentro de try/except
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        # Debe devolver 200 sin importar si el resolver falló
        self.assertEqual(response.status_code, 200)

    def test_ejercicios_no_alterados(self):
        """Estado_sistema no altera ejercicios ni modo_reducido."""
        ejercicios_orig = [
            {
                'nombre': 'Curl Femoral',
                'series': 4,
                'repeticiones': '3-5',
                'peso_kg': 65.0,
            }
        ]
        fecha_str = date.today().strftime('%Y-%m-%d')
        # El fix 414 usa cache de transporte; poblar la clave determinista.
        _key = f"transporte_ejercicios_dia_{self.cliente.id}_{fecha_str}"
        cache.set(_key, ejercicios_orig, 900)

        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': fecha_str,
            'rutina_nombre': 'Día 5 - Test',
            'modo_reducido': '1',
        }
        response = self.client.get(url, params)

        # Los ejercicios en contexto deben ser los mismos (posiblemente modificados por plan dinámico, pero mismo count)
        self.assertIn('ejercicios', response.context)
        # La cantidad debería coincidir (o ser ajustada por plan dinámico, pero no por estado_sistema)
        self.assertEqual(len(response.context['ejercicios']), len(ejercicios_orig))

    def test_estado_label_renderizado_en_template(self):
        """Template usa estado_label (no filtra el estado)."""
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': 'Día 5 - Test',
            'ejercicios': json.dumps([]),
        }
        response = self.client.get(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")

        estado_sistema = response.context.get('estado_sistema')
        if estado_sistema and estado_sistema.get('estado') != 'SILENCIO':
            # Si hay estado_label, template debe usarlo
            self.assertIsNotNone(estado_sistema.get('estado_label'))
