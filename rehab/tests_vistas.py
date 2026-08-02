from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from rehab.models import (
    EjercicioRehab,
    EjercicioSesionRehab,
    EpisodioRehab,
    FaseProtocolo,
    PrescripcionEjercicio,
    ProtocoloRehab,
    RegistroDiarioRehab,
    SesionRehab,
)
from rehab.services import iniciar_episodio


class VistasRehabTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paciente_vistas', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.login(username='paciente_vistas', password='x')

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


class IniciarEpisodioViewTests(VistasRehabTestBase):
    def test_post_crea_episodio(self):
        response = self.client.post(reverse('rehab:iniciar_episodio'), {
            'protocolo': self.protocolo.id,
            'lateralidad': 'derecha',
            'fecha_inicio': '2026-01-01',
            'dolor_basal_inicial': 4,
            'notas': '',
        })

        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(EpisodioRehab.objects.filter(cliente=self.cliente).count(), 1)
        episodio = EpisodioRehab.objects.get(cliente=self.cliente)
        self.assertEqual(episodio.fase_actual, self.fase1)
        self.assertEqual(episodio.estado, 'ACTIVO')

    def test_segundo_episodio_activo_no_devuelve_500(self):
        iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

        response = self.client.post(reverse('rehab:iniciar_episodio'), {
            'protocolo': self.protocolo.id,
            'lateralidad': 'izquierda',
            'fecha_inicio': '2026-02-01',
            'dolor_basal_inicial': 5,
            'notas': '',
        })

        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(EpisodioRehab.objects.filter(cliente=self.cliente).count(), 1)


class RegistrarDolorViewTests(VistasRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

    def test_post_crea_registro_diario(self):
        response = self.client.post(
            reverse('rehab:registrar_dolor', args=[self.episodio.id]),
            {
                'fecha': '2026-01-05',
                'dolor_manana': 3,
                'rigidez_manana': 2,
                'notas': '',
            },
        )

        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(RegistroDiarioRehab.objects.filter(episodio=self.episodio).count(), 1)


class RegistrarSesionViewTests(VistasRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

    def test_post_crea_sesion_y_ejercicios(self):
        response = self.client.post(
            reverse('rehab:registrar_sesion', args=[self.episodio.id]),
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

        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(SesionRehab.objects.filter(episodio=self.episodio).count(), 1)
        sesion = SesionRehab.objects.get(episodio=self.episodio)
        self.assertEqual(EjercicioSesionRehab.objects.filter(sesion=sesion).count(), 1)
