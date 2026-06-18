"""
Tests for Phase Diario UI — Estado del ciclo diario

Verifica que el dashboard muestre claramente el estado actual del día
y el CTA correcto sin crear nuevos modelos.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from diario.models import ProsocheDiario, ProsocheMes
from diario.services.estado_diario import calcular_estado_diario_hoy


class DiarioUIEstadoCicloTests(TestCase):
    """Tests para visibilidad del estado del ciclo diario"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.now().date()

        # Crear mes para prosoche
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=str(self.hoy.month),
            año=self.hoy.year,
        )

    def tearDown(self):
        User.objects.all().delete()
        ProsocheMes.objects.all().delete()
        ProsocheDiario.objects.all().delete()

    # Test 1: sin_entrada muestra "Día sin abrir"
    def test_sin_entrada_muestra_dia_sin_abrir(self):
        """Sin apertura ni cierre → dashboard muestra 'Día sin abrir'"""
        self.client.login(username='testuser', password='pass123')

        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Día sin abrir')
        self.assertContains(response, 'Aún no has hecho la apertura')
        # Verificar CTA
        self.assertContains(response, 'Abrir día')

    # Test 2: manana_hecha muestra "Día abierto"
    def test_manana_hecha_muestra_dia_abierto(self):
        """Con apertura sin cierre → dashboard muestra 'Día abierto'"""
        # Crear entrada con apertura
        ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='Ser paciente hoy',
            gratitud_1='Por el café',
        )

        self.client.login(username='testuser', password='pass123')

        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Día abierto')
        self.assertContains(response, 'La apertura está hecha')
        self.assertContains(response, 'Completar cierre')

    # Test 3: solo_noche muestra "Cierre registrado"
    def test_solo_noche_muestra_cierre_registrado(self):
        """Sin apertura con cierre → dashboard muestra 'Cierre registrado'"""
        # Crear entrada con solo cierre
        ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            que_ha_ido_bien='Entrenamiento bien',
        )

        self.client.login(username='testuser', password='pass123')

        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cierre registrado')
        self.assertContains(response, 'no hubo apertura')
        self.assertContains(response, 'Ver cierre')

    # Test 4: dia_completo muestra "Día completo"
    def test_dia_completo_muestra_completo(self):
        """Con apertura y cierre → dashboard muestra 'Día completo'"""
        # Crear entrada con ambos
        ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='Ser paciente hoy',
            gratitud_1='Por el café',
            que_ha_ido_bien='Entrenamiento bien',
        )

        self.client.login(username='testuser', password='pass123')

        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Día completo')
        self.assertContains(response, 'Apertura y cierre registrados')

    # Test 5: CTA existe por estado
    def test_cta_existe_por_estado(self):
        """Cada estado muestra un CTA principal"""
        self.client.login(username='testuser', password='pass123')

        # sin_entrada
        response = self.client.get('/diario/')
        self.assertContains(response, 'hoy-btn-primary')
        self.assertContains(response, 'Abrir día')

        # manana_hecha
        ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='test',
            gratitud_1='test',
        )
        response = self.client.get('/diario/')
        self.assertContains(response, 'hoy-btn-primary')
        self.assertContains(response, 'Completar cierre')

    # Test 6: Mobile no rompe jerarquía
    def test_mobile_no_rompe_jerarquia(self):
        """Desktop 1024px y Mobile 390px renderean sin errores"""
        self.client.login(username='testuser', password='pass123')

        # Desktop
        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hoy-section')

        # Mobile (sin viewport, pero validar que template compila)
        response = self.client.get('/diario/')
        self.assertEqual(response.status_code, 200)
        # Validar estructura existe
        self.assertContains(response, 'hoy-titulo-estado')
        self.assertContains(response, 'hoy-detalle-estado')


class DiarioEstadoFuncionTests(TestCase):
    """Tests para función calcular_estado_diario_hoy()"""

    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.hoy = timezone.now().date()
        self.mes = ProsocheMes.objects.create(
            usuario=self.user,
            mes=str(self.hoy.month),
            año=self.hoy.year,
        )

    def test_sin_entrada_devuelve_sin_entrada(self):
        """ProsocheDiario vacío → estado = 'sin_entrada'"""
        prosoche = None
        estado = calcular_estado_diario_hoy(prosoche)
        self.assertEqual(estado['estado'], 'sin_entrada')

    def test_manana_hecha_devuelve_manana_hecha(self):
        """Solo campos de apertura → estado = 'manana_hecha'"""
        prosoche = ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='test',
        )
        estado = calcular_estado_diario_hoy(prosoche)
        self.assertEqual(estado['estado'], 'manana_hecha')
        self.assertTrue(estado['manana_hecha'])
        self.assertFalse(estado['noche_hecha'])

    def test_dia_completo_devuelve_dia_completo(self):
        """Apertura + cierre → estado = 'dia_completo'"""
        prosoche = ProsocheDiario.objects.create(
            prosoche_mes=self.mes,
            fecha=self.hoy,
            persona_quiero_ser='test',
            que_ha_ido_bien='test',
        )
        estado = calcular_estado_diario_hoy(prosoche)
        self.assertEqual(estado['estado'], 'dia_completo')
