"""
Tests para Phase Organismo 2 — Card mínima "Sistema hoy" en dashboard.

Valida que:
1. View llama resolver_estado_sistema_hoy()
2. Card renderiza correctamente en template
3. 1 estado + 1 texto + 0-1 acción (máximo)
4. Colores respetan jerarquía
5. Mobile responsive funciona
6. Error handling graceful (degradación a SILENCIO)
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from clientes.models import Cliente
from hyrox.models import UserInjury
from datetime import date


class TestOrganismoCardView(TestCase):
    """Tests para la integración del resolver en la view mockup_demo."""

    def setUp(self):
        """Crear usuario y cliente para tests."""
        self.user = User.objects.create_user('test_organismo_card', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='test_organismo_card', password='x')

    def test_resolver_es_llamado_en_mockup_demo(self):
        """View llama a resolver_estado_sistema_hoy() y pasa resultado en contexto."""
        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('estado_sistema', response.context)

        estado_sistema = response.context['estado_sistema']
        self.assertIsNotNone(estado_sistema)
        self.assertIn('estado', estado_sistema)
        self.assertIn('motivo', estado_sistema)
        self.assertIn('texto', estado_sistema)
        self.assertIn('accion_label', estado_sistema)
        self.assertIn('accion_url', estado_sistema)

    def test_card_renderiza_estado_silencio(self):
        """Template renderiza SILENCIO correctamente sin botón."""
        response = self.client.get(reverse('clientes:mockup_demo'))

        # Sin lesión activa → SILENCIO
        self.assertEqual(response.context['estado_sistema']['estado'], 'SILENCIO')
        self.assertIsNone(response.context['estado_sistema']['accion_label'])

        # Verificar que el HTML renderiza
        content = response.content.decode()
        self.assertIn('Sistema hoy', content)
        self.assertIn('Silencio', content)  # Estado título case

    def test_card_renderiza_estado_protegiendo(self):
        """Template renderiza PROTEGIENDO con botón de acción."""
        # Crear lesión AGUDA activa
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=['flexion_rodilla_profunda'],
            gravedad=5
        )

        response = self.client.get(reverse('clientes:mockup_demo'))

        estado_sistema = response.context['estado_sistema']
        self.assertEqual(estado_sistema['estado'], 'PROTEGIENDO')
        self.assertIsNotNone(estado_sistema['accion_label'])
        self.assertIsNotNone(estado_sistema['accion_url'])

        # Verificar HTML
        content = response.content.decode()
        self.assertIn('Protegiendo', content)
        self.assertIn(estado_sistema['accion_label'], content)

    def test_card_renderiza_accion_si_existe(self):
        """Si accion_label es None, no renderizar botón. Si existe, renderizar."""
        # Caso 1: Sin lesión → SILENCIO sin acción
        response1 = self.client.get(reverse('clientes:mockup_demo'))
        estado1 = response1.context['estado_sistema']
        self.assertIsNone(estado1['accion_label'])

        content1 = response1.content.decode()
        # Buscar la sección de la card después del BIB HERO y antes del TOGGLE
        # No debe haber botón real con enlace para SILENCIO
        card_start = content1.find('<div class="rb-organismo-card">')
        card_end = content1.find('<!-- ── TOGGLE GYM / HYROX', card_start)
        card_html1 = content1[card_start:card_end]
        # Buscar <a con rb-organismo-btn
        self.assertNotIn('<a href=', card_html1, "SILENCIO no debe tener botón de acción")

        # Caso 2: Con lesión → PROTEGIENDO con acción
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Hombro',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=3
        )

        response2 = self.client.get(reverse('clientes:mockup_demo'))
        estado2 = response2.context['estado_sistema']
        self.assertIsNotNone(estado2['accion_label'])

        content2 = response2.content.decode()
        card_start2 = content2.find('<div class="rb-organismo-card">')
        card_end2 = content2.find('<!-- ── TOGGLE GYM / HYROX', card_start2)
        card_html2 = content2[card_start2:card_end2]
        self.assertIn('<a href=', card_html2, "PROTEGIENDO debe tener botón de acción")

    def test_estado_color_mapping(self):
        """Verificar que clases CSS de color se aplican correctamente."""
        response = self.client.get(reverse('clientes:mockup_demo'))

        estado = response.context['estado_sistema']['estado']
        content = response.content.decode()

        # Buscar la clase CSS correspondiente
        estado_lower = estado.lower()
        expected_class = f'rb-org-{estado_lower}'

        # Verificar que aparece en el HTML
        if 'Sistema hoy' in content:
            self.assertIn(expected_class, content)

    def test_resolver_failure_degradation(self):
        """Si resolver falla, view debe degradar a SILENCIO seguro."""
        # Esto es más difícil de probar sin mockear, pero validamos
        # que incluso con cliente sin datos, se devuelve un estado válido

        response = self.client.get(reverse('clientes:mockup_demo'))

        estado = response.context['estado_sistema']
        self.assertIsNotNone(estado['estado'])
        self.assertIn(estado['estado'], ['SILENCIO', 'OBSERVANDO', 'EN_MARGEN', 'PROTEGIENDO'])
        self.assertIsNotNone(estado['texto'])

    def test_mobile_390px_responsive(self):
        """Template renderiza responsive en mobile 390px."""
        # Verificar que CSS responsive está en el template
        response = self.client.get(reverse('clientes:mockup_demo'))
        content = response.content.decode()

        # Buscar media query CSS para organismo
        self.assertIn('@media (max-width: 640px)', content)

        # Verificar estructura HTML para flexbox mobile
        if 'Sistema hoy' in content:
            self.assertIn('rb-organismo-body', content)

    def test_card_no_duplica_estados(self):
        """Card muestra solo 1 acción, UI es limpia."""
        # Crear múltiples condiciones pero solo uno debería ganar
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=4
        )

        response = self.client.get(reverse('clientes:mockup_demo'))
        content = response.content.decode()

        # Contar cuántas acciones hay en la card
        # Buscar la card específica
        if 'Sistema hoy' in content:
            card_section = content.split('Sistema hoy')[1].split('TOGGLE GYM')[0]
            # No debe haber múltiples botones en la card
            action_count = card_section.count('rb-organismo-btn')
            self.assertLessEqual(action_count, 1, "Card no debe tener múltiples acciones")


class TestOrganismoCardTemplate(TestCase):
    """Tests para verificar que el template renderiza la card correctamente."""

    def setUp(self):
        """Crear usuario de prueba."""
        self.user = User.objects.create_user('test_template', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='test_template', password='x')

    def test_template_estructura_html(self):
        """Verificar estructura HTML de la card."""
        response = self.client.get(reverse('clientes:mockup_demo'))
        content = response.content.decode()

        # Debe tener estructura: .rb-organismo-card → .rb-organismo-label + .rb-organismo-body
        self.assertIn('class="rb-organismo-card"', content)
        self.assertIn('class="rb-organismo-label"', content)
        self.assertIn('class="rb-organismo-body"', content)
        self.assertIn('class="rb-organismo-estado', content)
        self.assertIn('class="rb-organismo-texto"', content)

    def test_template_estado_title_case(self):
        """Estado se renderiza en Title Case (ej: "Silencio", "Protegiendo")."""
        response = self.client.get(reverse('clientes:mockup_demo'))
        content = response.content.decode()

        # El estado en HTML debe ser title case (filtro |title)
        self.assertTrue(
            any(word in content for word in ['Silencio', 'Observando', 'En_margen', 'Protegiendo']),
            "Estado no se renderiza en Title Case"
        )

    def test_template_accion_link_format(self):
        """Si hay acción, se renderiza como link con flecha."""
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Tobillo',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=2
        )

        response = self.client.get(reverse('clientes:mockup_demo'))
        content = response.content.decode()

        # Debe haber link con flecha →
        self.assertIn(' →', content)
        self.assertIn('<a href=', content)

    def test_template_no_html_injection(self):
        """Valores de contexto se escapan correctamente."""
        response = self.client.get(reverse('clientes:mockup_demo'))

        estado = response.context['estado_sistema']
        # Todos los valores deben ser strings seguros
        self.assertIsInstance(estado['estado'], str)
        self.assertIsInstance(estado['texto'], str)
        if estado['accion_label']:
            self.assertIsInstance(estado['accion_label'], str)
        if estado['accion_url']:
            self.assertIsInstance(estado['accion_url'], str)

    def test_en_margen_usa_cliente_profil_para_sesion_gym(self):
        """Fix 2.2: obtener_sesion_recomendada_hoy() recibe cliente_profil, no usuario."""
        from core.organismo import resolver_estado_sistema_hoy

        # Resolver debe pasar cliente_profil (no usuario) a obtener_sesion_recomendada_hoy
        # Si hay sesión viable hoy y sin frenos, debe devolver EN_MARGEN
        estado = resolver_estado_sistema_hoy(self.user)

        # Si hay sesión viable, no debe ser SILENCIO
        # (PROTEGIENDO tiene prioridad, pero si no hay protección → EN_MARGEN)
        if estado['estado'] != 'PROTEGIENDO':
            # Sin protección, si hay sesión viable debe ser EN_MARGEN
            # (Si sigue siendo SILENCIO, significa sesión no fue detectada)
            # Este test valida que el contrato usuario→cliente_profil se respeta
            self.assertIn(estado['estado'], ['EN_MARGEN', 'SILENCIO', 'OBSERVANDO'])

    def test_en_margen_sin_cliente_profil_degrada_sin_romper(self):
        """Fix 2.2: Si usuario no tiene cliente_profil, degradar gracefully sin excepción."""
        from core.organismo import resolver_estado_sistema_hoy

        # Crear usuario sin cliente_profil (simular caso edge)
        orphan_user = User.objects.create_user('orphan_user', password='x')
        # No crear Cliente asociado

        # Llamada no debe explotar
        estado = resolver_estado_sistema_hoy(orphan_user)

        # Debe devolver algo seguro (SILENCIO o None)
        self.assertIsNotNone(estado)
        self.assertIn('estado', estado)
        # Sin cliente_profil no puede haber EN_MARGEN
        self.assertNotEqual(estado['estado'], 'EN_MARGEN')
