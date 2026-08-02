from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

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
from rehab.services import iniciar_episodio, registrar_dolor_diario
from rehab.services.prescripcion_service import UMBRAL_DOLOR_PARADA, prescripcion_de_hoy


class PrescripcionDeHoyTestBase(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paciente_prescripcion', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana-presc',
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
            reglas_avance={'min_sesiones': 6, 'umbral_dolor': 3, 'min_adherencia': 0.8},
            reglas_retroceso={'dolor_post_24h_umbral': 5, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.ejercicio = EjercicioRehab.objects.create(
            nombre='Sentadilla isométrica en pared',
            slug='sentadilla-isometrica-pared-presc',
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
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )


class SinEpisodioTests(TestCase):
    def test_sin_episodio_activo_devuelve_sin_episodio(self):
        user = User.objects.create_user(username='sin_episodio', password='x')
        cliente = Cliente.objects.get(user=user)

        resultado = prescripcion_de_hoy(cliente, fecha=date(2026, 1, 10))

        self.assertEqual(resultado['estado'], 'SIN_EPISODIO')
        self.assertEqual(resultado['ejercicios'], [])
        self.assertFalse(resultado['puede_entrenar'])
        self.assertIsNone(resultado['dias_en_fase'])
        self.assertIsNone(resultado['criterio_avance_texto'])
        self.assertIsNone(resultado['progreso_hacia_avance'])

    def test_sin_episodio_activo_ninguna_otra_rama_se_evalua(self):
        user = User.objects.create_user(username='sin_episodio_otra_rama', password='x')
        cliente = Cliente.objects.get(user=user)

        resultado = prescripcion_de_hoy(cliente, fecha=date(2026, 1, 10))

        self.assertEqual(resultado['estado'], 'SIN_EPISODIO')
        self.assertNotEqual(resultado['estado'], 'PARAR')
        self.assertNotEqual(resultado['estado'], 'SIN_DATOS')


class BanderaRojaTests(PrescripcionDeHoyTestBase):
    def test_bandera_roja_marcada_hoy_fuerza_parar(self):
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 5),
            dolor_manana=2,
            rigidez_manana=2,
            bandera_roja=True,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'PARAR')
        self.assertEqual(resultado['motivo'], 'bandera_roja')
        self.assertFalse(resultado['puede_entrenar'])
        self.assertEqual(resultado['ejercicios'], [])
        self.assertIn('Bandera roja', resultado['alerta'])


class DolorHoyAltoTests(PrescripcionDeHoyTestBase):
    def test_dolor_hoy_mayor_o_igual_umbral_para_fuerza_parar(self):
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 5),
            dolor_manana=UMBRAL_DOLOR_PARADA,
            rigidez_manana=5,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'PARAR')
        self.assertEqual(resultado['motivo'], 'dolor_hoy_umbral')
        self.assertFalse(resultado['puede_entrenar'])
        self.assertEqual(resultado['ejercicios'], [])


class DolorMatinalPersistenteTests(PrescripcionDeHoyTestBase):
    def test_dolor_matinal_persistente_fuerza_parar(self):
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 4), dolor_manana=5, rigidez_manana=3,
        )
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 5), dolor_manana=5, rigidez_manana=3,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'PARAR')
        self.assertEqual(resultado['motivo'], 'dolor_matinal_persistente')
        self.assertFalse(resultado['puede_entrenar'])


class SinDatosTests(PrescripcionDeHoyTestBase):
    def test_sin_registro_diario_hoy_devuelve_sin_datos(self):
        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'SIN_DATOS')
        self.assertEqual(resultado['ejercicios'], [])
        self.assertFalse(resultado['puede_entrenar'])


class DescansoProgramadoTests(PrescripcionDeHoyTestBase):
    def test_frecuencia_semanal_cumplida_devuelve_descanso_programado(self):
        for i in range(5):
            fecha_sesion = date(2026, 1, 2) + timedelta(days=i)
            SesionRehab.objects.create(
                episodio=self.episodio,
                fase=self.fase1,
                fecha=fecha_sesion,
                estado='COMPLETADA',
                dolor_durante=2,
            )
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 7), dolor_manana=2, rigidez_manana=2,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 7))

        self.assertEqual(resultado['estado'], 'DESCANSO_PROGRAMADO')
        self.assertEqual(resultado['motivo'], 'frecuencia_semanal_cumplida')
        self.assertFalse(resultado['puede_entrenar'])
        self.assertEqual(resultado['ejercicios'], [])


class PrecaucionTests(PrescripcionDeHoyTestBase):
    def test_dolor_moderado_devuelve_precaucion_con_volumen_reducido(self):
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 5), dolor_manana=5, rigidez_manana=3,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'PRECAUCION')
        self.assertTrue(resultado['puede_entrenar'])
        self.assertEqual(len(resultado['ejercicios']), 1)
        self.assertEqual(resultado['ejercicios'][0]['series'], 3)

    def test_precaucion_no_muta_prescripcion_en_bd(self):
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 5), dolor_manana=5, rigidez_manana=3,
        )

        prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.prescripcion.refresh_from_db()
        self.assertEqual(self.prescripcion.series, 5)


class EntrenarHoyTests(PrescripcionDeHoyTestBase):
    def test_dolor_bajo_devuelve_entrenar_hoy_con_prescripciones_integras(self):
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 5), dolor_manana=2, rigidez_manana=1,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'ENTRENAR_HOY')
        self.assertTrue(resultado['puede_entrenar'])
        self.assertEqual(len(resultado['ejercicios']), 1)
        self.assertEqual(resultado['ejercicios'][0]['series'], 5)


class PrecedenciaTests(PrescripcionDeHoyTestBase):
    def test_bandera_roja_gana_sobre_precaucion(self):
        RegistroDiarioRehab.objects.create(
            episodio=self.episodio,
            fecha=date(2026, 1, 5),
            dolor_manana=5,
            rigidez_manana=3,
            bandera_roja=True,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 5))

        self.assertEqual(resultado['estado'], 'PARAR')
        self.assertEqual(resultado['motivo'], 'bandera_roja')


class DiasEnFaseYProgresoTests(PrescripcionDeHoyTestBase):
    def test_dias_en_fase_y_progreso_hacia_avance_con_datos_conocidos(self):
        for i in range(4):
            fecha_sesion = date(2026, 1, 2) + timedelta(days=i)
            SesionRehab.objects.create(
                episodio=self.episodio,
                fase=self.fase1,
                fecha=fecha_sesion,
                estado='COMPLETADA',
                dolor_durante=3,
            )
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 6), dolor_manana=2, rigidez_manana=1,
        )

        resultado = prescripcion_de_hoy(self.cliente, fecha=date(2026, 1, 6))

        self.assertEqual(resultado['dias_en_fase'], 5)
        self.assertEqual(resultado['progreso_hacia_avance']['sesiones_completadas'], 4)
        self.assertEqual(resultado['progreso_hacia_avance']['sesiones_requeridas'], 6)
        self.assertEqual(resultado['progreso_hacia_avance']['dolor_maximo_reciente'], 3)
        self.assertAlmostEqual(resultado['progreso_hacia_avance']['adherencia_14d'], 4 / 10)
        self.assertIn('4 de 6 sesiones', resultado['criterio_avance_texto'])
