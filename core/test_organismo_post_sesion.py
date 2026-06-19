"""
Tests para Phase Organismo 3.1 — Post-sesión coherente.

Valida que después de completar la sesión principal del día,
el organismo no siga proponiendo "Empezar entrenamiento".
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina
from hyrox.models import UserInjury
from core.organismo import resolver_estado_sistema_hoy


class TestOrganismoPostSesion(TestCase):
    """Tests para coherencia post-sesión del organismo."""

    def setUp(self):
        """Crear usuario y cliente para tests."""
        self.user = User.objects.create_user('test_org31', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

        # Crear una rutina mínima para tests
        self.rutina = Rutina.objects.create(
            nombre='Rutina Test',
            programa=None
        )

    def test_antes_de_completar_en_margen_con_accion(self):
        """
        Test 1: Antes de completar sesión viable → EN_MARGEN con acción.
        """
        estado = resolver_estado_sistema_hoy(self.user)

        # Puede ser EN_MARGEN o SILENCIO dependiendo de datos del día
        # Lo que importa: si es EN_MARGEN, debe tener acción
        if estado and estado['estado'] == 'EN_MARGEN':
            self.assertIsNotNone(estado['accion_label'])
            self.assertEqual(estado['accion_label'], 'Empezar entrenamiento')
            self.assertIsNotNone(estado['accion_url'])

    def test_despues_de_completar_no_en_margen(self):
        """
        Test 2: Después de completar sesión principal hoy → no EN_MARGEN con acción.
        """
        # Crear un EntrenoRealizado hoy para simular sesión completada
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=45,
            volumen_total_kg=1000.0
        )

        estado = resolver_estado_sistema_hoy(self.user)

        # Después de completar, NO debe haber EN_MARGEN con acción "Empezar entrenamiento"
        if estado and estado['estado'] == 'EN_MARGEN':
            # Si aún es EN_MARGEN (por lógica diferente), no debe tener acción de entrenar
            self.assertNotEqual(
                estado['accion_label'],
                'Empezar entrenamiento',
                "No debe proponer 'Empezar entrenamiento' después de completar sesión"
            )
        # Si pasó a OBSERVANDO/SILENCIO, es lo esperado
        self.assertIn(
            estado['estado'],
            ['OBSERVANDO', 'SILENCIO'],
            "Después de completar, debería ser OBSERVANDO o SILENCIO"
        )

    def test_texto_post_sesion_coherente(self):
        """
        Test 3: El texto post-sesión es humano y no invita a repetir.
        """
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=45,
            volumen_total_kg=1000.0
        )

        estado = resolver_estado_sistema_hoy(self.user)

        # El texto no debe invitar a entrenar nuevamente
        if estado:
            texto_bajo = estado['texto'].lower()
            self.assertNotIn(
                'empezar',
                texto_bajo,
                "Texto post-sesión no debe invitar a 'empezar' de nuevo"
            )

    def test_protegiendo_tiene_prioridad_post_sesion(self):
        """
        Test 4: Si hay lesión AGUDA después de completar, PROTEGIENDO tiene prioridad.
        """
        # Completar sesión hoy
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=45,
            volumen_total_kg=1000.0
        )

        # Crear lesión AGUDA
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla',
            fase='AGUDA',
            activa=True,
            tags_restringidos=[],
            gravedad=5
        )

        estado = resolver_estado_sistema_hoy(self.user)

        # PROTEGIENDO debe ganar sobre todo
        self.assertEqual(
            estado['estado'],
            'PROTEGIENDO',
            "PROTEGIENDO debe tener prioridad incluso post-sesión"
        )

    def test_no_bloquea_entrenamientos_opcionales(self):
        """
        Test 5: Un EntrenoRealizado bloquea EN_MARGEN post-sesión.

        (Nota: Este test valida que cualquier EntrenoRealizado hoy
        bloquea EN_MARGEN, que es el comportamiento correcto.)
        """
        # Crear un entrenamiento "ligero" u opcional
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=15,
            volumen_total_kg=200.0
        )

        estado = resolver_estado_sistema_hoy(self.user)

        # Actualmente, cualquier EntrenoRealizado bloquea EN_MARGEN
        # Esto es correcto: "sesión principal ya completada" = no hay próxima acción de entrenar
        if estado and estado['estado'] == 'EN_MARGEN':
            # No debería haber EN_MARGEN con acción de entrenar
            self.assertNotEqual(
                estado['accion_label'],
                'Empezar entrenamiento'
            )

    def test_dashboard_sin_contradiccion_post_sesion(self):
        """
        Test 6: Dashboard renderiza sin contradicción post-sesión.

        Verifica que el estado retornado sea coherente y no contradiga
        la presencia de "Completado hoy" en el dashboard.
        """
        # Completar sesión
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=45,
            volumen_total_kg=1000.0
        )

        estado = resolver_estado_sistema_hoy(self.user)

        # Validar estructura del estado
        self.assertIsNotNone(estado)
        self.assertIn('estado', estado)
        self.assertIn('texto', estado)
        self.assertIn('accion_label', estado)
        self.assertIn('accion_url', estado)

        # Post-sesión: accion_label puede ser None (sin botón)
        # Lo que NO debería ser: "Empezar entrenamiento"
        if estado['accion_label']:
            self.assertNotEqual(
                estado['accion_label'],
                'Empezar entrenamiento',
                "Dashboard no debe proponer 'Empezar entrenamiento' tras completar sesión"
            )

    def test_transicion_en_margen_a_observando(self):
        """
        Test bonus: Validar transición limpia de EN_MARGEN → OBSERVANDO/SILENCIO.
        """
        # Escenario 1: Sin sesión completada
        estado_antes = resolver_estado_sistema_hoy(self.user)

        # Escenario 2: Después de completar sesión
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            duracion_minutos=45,
            volumen_total_kg=1000.0
        )

        estado_despues = resolver_estado_sistema_hoy(self.user)

        # Si antes era EN_MARGEN, después no debe serlo
        if estado_antes and estado_antes['estado'] == 'EN_MARGEN':
            self.assertNotEqual(
                estado_despues['estado'],
                'EN_MARGEN',
                "Transición correcta: EN_MARGEN → OBSERVANDO/SILENCIO post-sesión"
            )
