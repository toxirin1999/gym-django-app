from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from rehab.models import (
    EjercicioRehab,
    EpisodioRehab,
    FaseProtocolo,
    PrescripcionEjercicio,
    ProtocoloRehab,
    RegistroDiarioRehab,
    SesionRehab,
)
from rehab.services import iniciar_episodio

HOY = timezone.localdate()


class DashboardRehabTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paciente_dashboard', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
            activo=True,
        )
        self.fase1 = FaseProtocolo.objects.create(
            protocolo=self.protocolo,
            orden=1,
            slug='fase-1-isometrica',
            nombre='Fase 1',
            objetivo='x',
            duracion_minima_dias=7,
            duracion_tipica_dias=14,
            reglas_avance={'min_sesiones': 6, 'umbral_dolor': 4, 'min_adherencia': 0.5},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 3},
            descripcion='x',
        )
        self.fase2 = FaseProtocolo.objects.create(
            protocolo=self.protocolo,
            orden=2,
            slug='fase-2-isotonica',
            nombre='Fase 2',
            objetivo='x',
            duracion_minima_dias=7,
            duracion_tipica_dias=14,
            descripcion='x',
        )
        self.ejercicio = EjercicioRehab.objects.create(
            nombre='Sentadilla isométrica en pared',
            slug='sentadilla-isometrica-pared',
            tipo_contraccion='isometrico',
            descripcion_ejecucion='x',
        )
        self.prescripcion = PrescripcionEjercicio.objects.create(
            fase=self.fase1,
            ejercicio=self.ejercicio,
            orden=1,
            series=5,
            frecuencia_semanal=5,
            parametros={'duracion_segundos': 45},
        )


class HoyViewSinAutenticarTests(TestCase):
    def test_get_sin_login_redirige_a_login(self):
        response = self.client.get(reverse('rehab:hoy'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class HoyViewSinEpisodioTests(DashboardRehabTestBase):
    def test_sin_episodio_activo_muestra_invitacion(self):
        self.client.login(username='paciente_dashboard', password='x')
        response = self.client.get(reverse('rehab:hoy'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('iniciar', contenido.lower())
        self.assertNotIn('Sentadilla isométrica', contenido)
        self.assertNotIn('Traceback', contenido)


class HoyViewSinRegistroDolorTests(DashboardRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=HOY - timedelta(days=10),
            dolor_basal_inicial=4,
        )
        self.client.login(username='paciente_dashboard', password='x')

    def test_sin_registro_dolor_hoy_muestra_sin_datos(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('SIN_DATOS', contenido)


class HoyViewConDolorBajoTests(DashboardRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=HOY - timedelta(days=10),
            dolor_basal_inicial=4,
        )
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=HOY,
            dolor_manana=1,
            rigidez_manana=1,
        )
        self.client.login(username='paciente_dashboard', password='x')

    def test_dolor_bajo_muestra_entrenar_hoy_y_ejercicios(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('ENTRENAR_HOY', contenido)
        self.assertIn('Sentadilla isométrica en pared', contenido)
        self.assertIn(reverse('rehab:registrar_sesion', args=[self.episodio.id]), contenido)
        self.assertIn(reverse('rehab:registrar_dolor', args=[self.episodio.id]), contenido)


class HoyViewElegibleAvanceTests(DashboardRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=HOY - timedelta(days=10),
            dolor_basal_inicial=4,
        )
        for i in range(6):
            SesionRehab.objects.create(
                episodio=self.episodio,
                fase=self.fase1,
                fecha=HOY - timedelta(days=9 - i),
                estado='COMPLETADA',
                dolor_durante=1,
            )
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=HOY,
            dolor_manana=1,
            rigidez_manana=1,
        )
        self.client.login(username='paciente_dashboard', password='x')

    def test_elegible_muestra_cta_proponer_avance(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn(reverse('rehab:proponer_avance'), contenido)


class HoyViewEstancamientoTests(DashboardRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=HOY - timedelta(days=60),
            dolor_basal_inicial=4,
        )
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=HOY,
            dolor_manana=1,
            rigidez_manana=1,
        )
        self.client.login(username='paciente_dashboard', password='x')

    def test_estancamiento_muestra_mensaje(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('no está progresando', contenido)


class RedirectsApuntanAHoyTests(DashboardRehabTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='paciente_dashboard', password='x')

    def test_iniciar_episodio_redirige_a_hoy(self):
        response = self.client.post(reverse('rehab:iniciar_episodio'), {
            'protocolo': self.protocolo.id,
            'lateralidad': 'derecha',
            'fecha_inicio': '2026-01-01',
            'dolor_basal_inicial': 4,
            'notas': '',
        })
        self.assertRedirects(response, reverse('rehab:hoy'))

    def test_registrar_dolor_redirige_a_hoy(self):
        episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )
        response = self.client.post(
            reverse('rehab:registrar_dolor', args=[episodio.id]),
            {
                'fecha': '2026-01-05',
                'dolor_manana': 3,
                'rigidez_manana': 2,
                'notas': '',
            },
        )
        self.assertRedirects(response, reverse('rehab:hoy'))

    def test_registrar_sesion_redirige_a_hoy(self):
        episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )
        response = self.client.post(
            reverse('rehab:registrar_sesion', args=[episodio.id]),
            {
                'fecha': '2026-01-06',
                'estado': 'COMPLETADA',
                'dolor_durante': 2,
                'dolor_post_24h': 1,
                'duracion_min': 20,
                'notas': '',
                f'presc_{self.prescripcion.id}_series_completadas': 5,
                f'presc_{self.prescripcion.id}_carga_kg': '',
                f'presc_{self.prescripcion.id}_dolor_ejercicio': 2,
                f'presc_{self.prescripcion.id}_completado': 'on',
            },
        )
        self.assertRedirects(response, reverse('rehab:hoy'))

    def test_confirmar_avance_redirige_a_proponer_avance_no_a_placeholder(self):
        episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )
        response = self.client.post(
            reverse('rehab:confirmar_avance', args=[episodio.id]),
            {'forzado': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('placeholder', response.url)
