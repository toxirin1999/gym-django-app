from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

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
    TransicionFase,
)
from rehab.services import iniciar_episodio, registrar_dolor_diario, registrar_sesion


class ServiciosRehabTestBase(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paciente_servicios', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
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
        self.fase2 = FaseProtocolo.objects.create(
            protocolo=self.protocolo,
            orden=2,
            slug='fase-2-isotonica',
            nombre='Fase 2',
            objetivo='x',
            duracion_minima_dias=14,
            duracion_tipica_dias=42,
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


class IniciarEpisodioTests(ServiciosRehabTestBase):
    def test_crea_episodio_en_primera_fase_y_transicion_inicio(self):
        episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

        self.assertEqual(episodio.fase_actual, self.fase1)
        self.assertEqual(episodio.protocolo_version, self.protocolo.version)
        self.assertEqual(episodio.estado, 'ACTIVO')
        self.assertEqual(episodio.fase_actual_desde, date(2026, 1, 1))

        transicion = TransicionFase.objects.get(episodio=episodio)
        self.assertEqual(transicion.direccion, 'INICIO')
        self.assertIsNone(transicion.fase_desde)
        self.assertEqual(transicion.fase_hasta, self.fase1)
        self.assertTrue(transicion.confirmada_por_usuario)
        self.assertFalse(transicion.automatica)

    def test_lanza_validation_error_si_ya_hay_episodio_activo(self):
        episodio_original = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

        with self.assertRaises(ValidationError):
            iniciar_episodio(
                cliente=self.cliente,
                protocolo=self.protocolo,
                lateralidad='izquierda',
                fecha_inicio=date(2026, 2, 1),
                dolor_basal_inicial=5,
            )

        self.assertEqual(EpisodioRehab.objects.filter(cliente=self.cliente).count(), 1)
        episodio_original.refresh_from_db()
        self.assertEqual(episodio_original.lateralidad, 'derecha')
        self.assertEqual(episodio_original.dolor_basal_inicial, 4)


class RegistrarDolorDiarioTests(ServiciosRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

    def test_llamar_dos_veces_mismo_dia_actualiza_no_duplica(self):
        registrar_dolor_diario(
            episodio=self.episodio,
            fecha=date(2026, 1, 5),
            dolor_manana=3,
            rigidez_manana=2,
        )
        registrar_dolor_diario(
            episodio=self.episodio,
            fecha=date(2026, 1, 5),
            dolor_manana=6,
            rigidez_manana=5,
            notas='empeoró',
        )

        self.assertEqual(
            RegistroDiarioRehab.objects.filter(episodio=self.episodio, fecha=date(2026, 1, 5)).count(),
            1,
        )
        registro = RegistroDiarioRehab.objects.get(episodio=self.episodio, fecha=date(2026, 1, 5))
        self.assertEqual(registro.dolor_manana, 6)
        self.assertEqual(registro.rigidez_manana, 5)
        self.assertEqual(registro.notas, 'empeoró')


class RegistrarSesionTests(ServiciosRehabTestBase):
    def setUp(self):
        super().setUp()
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

    def test_crea_sesion_con_fase_actual_y_ejercicios(self):
        sesion = registrar_sesion(
            episodio=self.episodio,
            fecha=date(2026, 1, 6),
            estado='COMPLETADA',
            dolor_durante=2,
            ejercicios_data=[
                {
                    'prescripcion_id': self.prescripcion.id,
                    'series_completadas': 5,
                    'carga_kg': None,
                    'dolor_ejercicio': 2,
                    'completado': True,
                },
            ],
            dolor_post_24h=1,
            duracion_min=20,
        )

        self.assertEqual(sesion.fase, self.episodio.fase_actual)
        self.assertEqual(sesion.fase, self.fase1)
        self.assertEqual(EjercicioSesionRehab.objects.filter(sesion=sesion).count(), 1)

        ejercicio_sesion = EjercicioSesionRehab.objects.get(sesion=sesion)
        self.assertEqual(ejercicio_sesion.prescripcion, self.prescripcion)
        self.assertEqual(ejercicio_sesion.series_completadas, 5)
        self.assertTrue(ejercicio_sesion.completado)

        self.assertTrue(sesion.prescripcion_snapshot)
        snapshot_ids = [item['prescripcion_id'] for item in sesion.prescripcion_snapshot]
        self.assertIn(self.prescripcion.id, snapshot_ids)
        snapshot_item = next(item for item in sesion.prescripcion_snapshot if item['prescripcion_id'] == self.prescripcion.id)
        self.assertEqual(snapshot_item['ejercicio'], self.ejercicio.nombre)
        self.assertEqual(snapshot_item['series'], self.prescripcion.series)
        self.assertEqual(snapshot_item['frecuencia_semanal'], self.prescripcion.frecuencia_semanal)

    def test_numero_ejercicios_sesion_coincide_con_datos_entrada(self):
        ejercicio2 = EjercicioRehab.objects.create(
            nombre='Extensión de rodilla isométrica',
            slug='extension-rodilla-isometrica',
            tipo_contraccion='isometrico',
            descripcion_ejecucion='x',
        )
        prescripcion2 = PrescripcionEjercicio.objects.create(
            fase=self.fase1,
            ejercicio=ejercicio2,
            orden=2,
            series=4,
            frecuencia_semanal=4,
            parametros={},
        )

        sesion = registrar_sesion(
            episodio=self.episodio,
            fecha=date(2026, 1, 7),
            estado='PARCIAL',
            dolor_durante=3,
            ejercicios_data=[
                {
                    'prescripcion_id': self.prescripcion.id,
                    'series_completadas': 5,
                    'carga_kg': None,
                    'dolor_ejercicio': 2,
                    'completado': True,
                },
                {
                    'prescripcion_id': prescripcion2.id,
                    'series_completadas': 2,
                    'carga_kg': None,
                    'dolor_ejercicio': 4,
                    'completado': False,
                },
            ],
        )

        self.assertEqual(EjercicioSesionRehab.objects.filter(sesion=sesion).count(), 2)
