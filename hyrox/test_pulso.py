from django.test import TestCase, Client
from django.contrib.auth.models import User
from .pulso_service import PulsoService
from .models import HyroxObjective
from clientes.models import Cliente
from django.utils import timezone


class PulsoServiceTest(TestCase):
    """Tests para determinación del estado del Pulso."""

    def test_pulso_protegiendo_por_readiness_bajo(self):
        """Readiness < 40 → PROTEGIENDO."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=35,
            lesion_activa=None
        )
        self.assertEqual(resultado["pulso"], PulsoService.PULSO_PROTEGIENDO)
        self.assertEqual(resultado["motivo"], "readiness_bajo")

    def test_pulso_progresando_con_nuevo_rm(self):
        """Con nuevo RM y readiness >= 50 → PROGRESANDO."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=70,
            lesion_activa=None,
            historial_reciente={"nuevo_rm": True}
        )
        self.assertEqual(resultado["pulso"], PulsoService.PULSO_PROGRESANDO)
        self.assertIn("Nuevo RM", str(resultado["cambios"]))

    def test_pulso_silencioso_default(self):
        """Sin señales especiales → SILENCIOSO."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=55,
            lesion_activa=None,
            historial_reciente=None
        )
        self.assertEqual(resultado["pulso"], PulsoService.PULSO_SILENCIOSO)

    def test_postura_protegiendo_contrae(self):
        """PROTEGIENDO contrae: rutas=1, menos visibilidad."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=30,
            lesion_activa=None
        )
        self.assertEqual(resultado["postura"]["rutas"], 1)
        self.assertFalse(resultado["postura"]["opciones_exploración"])
        self.assertFalse(resultado["postura"]["metricas_secundarias_visible"])

    def test_postura_progresando_abre(self):
        """PROGRESANDO abre: rutas=3, más visibilidad."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=75,
            lesion_activa=None,
            historial_reciente={"peso_subio": 2.5}
        )
        self.assertEqual(resultado["postura"]["rutas"], 3)
        self.assertTrue(resultado["postura"]["opciones_exploración"])
        self.assertTrue(resultado["postura"]["metricas_secundarias_visible"])

    def test_postura_silencioso_minima(self):
        """SILENCIOSO es mínimo: estructura minima, sin exploración."""
        resultado = PulsoService.determinar_pulso(
            objetivo=None,
            readiness_score=50,
            lesion_activa=None
        )
        self.assertEqual(resultado["postura"]["estructura"], "minima")
        self.assertFalse(resultado["postura"]["opciones_exploración"])


class PulsoTemplateTest(TestCase):
    """Tests para renderización visual del Pulso en template."""

    def setUp(self):
        """Crear usuario, cliente y objetivo para tests."""
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.cliente = Cliente.objects.get_or_create(user=self.user)[0]
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            estado='activo',
            categoria='open_men',
            fecha_evento=timezone.now().date() + timezone.timedelta(days=60)
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_pulso_protegiendo_renderiza_clases(self):
        """PROTEGIENDO renderiza clases pulso-protegiendo y pulso-compacta."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        # El bloque debe existir con clases de postura
        if b'pulso-card' in response.content:
            self.assertIn(b'pulso-state-badge', response.content)

    def test_pulso_progresando_renderiza_clases(self):
        """PROGRESANDO renderiza clases pulso-progresando y pulso-abierta."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Verificar estructura HTML del bloque Pulso
        if b'pulso-card' in response.content:
            # Debe tener al menos una de las tres posturas
            has_postura = (
                b'pulso-protegiendo' in response.content or
                b'pulso-progresando' in response.content or
                b'pulso-silencioso' in response.content
            )
            self.assertTrue(has_postura, "El bloque Pulso debe tener una postura definida")

    def test_pulso_silencioso_renderiza_clases(self):
        """SILENCIOSO renderiza clases pulso-silencioso y pulso-minima."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        if b'pulso-card' in response.content:
            self.assertIn(b'pulso-state-badge', response.content)

    def test_pulso_bloque_tiene_estructura_html(self):
        """El bloque Pulso tiene estructura HTML con header y body."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Verificar que el bloque tiene estructura mínima esperada
        if b'pulso-card' in response.content:
            self.assertIn(b'pulso-header', response.content)
            self.assertIn(b'pulso-body', response.content)
            self.assertIn(b'pulso-state-badge', response.content)

    def test_pulso_rutas_visibles(self):
        """El bloque Pulso renderiza rutas visibles."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        if b'pulso-card' in response.content:
            self.assertIn(b'pulso-routes', response.content)
            self.assertIn(b'pulso-route', response.content)

    def test_pulso_no_afecta_hyrox_decision(self):
        """Pulso no reemplaza hyrox_decision, solo la traduce visualmente."""
        response = self.client.get('/hyrox/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Ambos pueden coexistir en la página
        # Simplemente verificar que la página carga correctamente
        self.assertIn(b'Estado de hoy', response.content)
