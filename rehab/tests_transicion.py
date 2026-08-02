from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from clientes.models import Cliente
from rehab.models import (
    EjercicioRehab,
    FaseProtocolo,
    PrescripcionEjercicio,
    ProtocoloRehab,
    RegistroDiarioRehab,
    SesionRehab,
    TransicionFase,
)
from rehab.services import iniciar_episodio, registrar_dolor_diario, registrar_sesion
from rehab.services.transicion_service import (
    COOLDOWN_DIAS_RETROCESO,
    DIAS_TENDENCIA_CRECIENTE,
    MULTIPLICADOR_ESTANCAMIENTO,
    UMBRAL_DOLOR_RETROCESO_INMEDIATO,
    aplicar_retroceso_automatico,
    confirmar_avance,
    detectar_estancamiento,
    evaluar_elegibilidad_avance,
    evaluar_retroceso,
)


class TransicionRehabTestBase(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paciente_transicion', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana-transicion',
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
            slug='fase-1-transicion',
            nombre='Fase 1',
            objetivo='x',
            duracion_minima_dias=7,
            duracion_tipica_dias=14,
            reglas_avance={'min_sesiones': 3, 'umbral_dolor': 4, 'min_adherencia': 0.7},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.fase2 = FaseProtocolo.objects.create(
            protocolo=self.protocolo,
            orden=2,
            slug='fase-2-transicion',
            nombre='Fase 2',
            objetivo='x',
            duracion_minima_dias=14,
            duracion_tipica_dias=42,
            reglas_avance={'min_sesiones': 4, 'umbral_dolor': 3, 'min_adherencia': 0.6},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.ejercicio = EjercicioRehab.objects.create(
            nombre='Sentadilla isométrica en pared',
            slug='sentadilla-isometrica-pared-transicion',
            tipo_contraccion='isometrico',
            descripcion_ejecucion='x',
        )
        self.prescripcion_fase1 = PrescripcionEjercicio.objects.create(
            fase=self.fase1, ejercicio=self.ejercicio, orden=1, series=5, frecuencia_semanal=5, parametros={},
        )
        self.prescripcion_fase2 = PrescripcionEjercicio.objects.create(
            fase=self.fase2, ejercicio=self.ejercicio, orden=1, series=5, frecuencia_semanal=5, parametros={},
        )
        self.episodio = iniciar_episodio(
            cliente=self.cliente,
            protocolo=self.protocolo,
            lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1),
            dolor_basal_inicial=4,
        )

    def _crear_sesion(self, fase, fecha, dolor_durante=2, estado='COMPLETADA'):
        return SesionRehab.objects.create(
            episodio=self.episodio, fase=fase, fecha=fecha, estado=estado, dolor_durante=dolor_durante,
        )

    def _crear_registro(self, fecha, dolor_manana):
        return RegistroDiarioRehab.objects.create(
            episodio=self.episodio, fecha=fecha, dolor_manana=dolor_manana, rigidez_manana=2,
        )

    def _mover_a_fase2(self, fecha_desde):
        self.episodio.fase_actual = self.fase2
        self.episodio.fase_actual_desde = fecha_desde
        self.episodio.save(update_fields=['fase_actual', 'fase_actual_desde'])


class AvanceNuncaEsAutomaticoTests(TransicionRehabTestBase):
    def test_avance_no_ocurre_automaticamente_al_registrar_sesion_y_dolor(self):
        for i in range(7):
            fecha = date(2026, 1, 2) + timedelta(days=i)
            registrar_sesion(
                episodio=self.episodio,
                fecha=fecha,
                estado='COMPLETADA',
                dolor_durante=2,
                ejercicios_data=[{
                    'prescripcion_id': self.prescripcion_fase1.id,
                    'series_completadas': 5,
                    'carga_kg': None,
                    'dolor_ejercicio': 2,
                    'completado': True,
                }],
            )
        registrar_dolor_diario(episodio=self.episodio, fecha=date(2026, 1, 10), dolor_manana=2, rigidez_manana=1)

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))
        self.assertTrue(resultado['elegible'])

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase1)
        self.assertFalse(
            TransicionFase.objects.filter(episodio=self.episodio, direccion='AVANCE').exists()
        )


class EvaluarElegibilidadAvanceTests(TransicionRehabTestBase):
    def test_elegible_true_cuando_todas_las_condiciones_se_cumplen(self):
        for i in range(7):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))

        self.assertTrue(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'criterios_cumplidos')
        self.assertEqual(resultado['siguiente_fase'], self.fase2)
        self.assertEqual(resultado['evidencia']['sesiones_completadas'], 7)
        self.assertEqual(resultado['evidencia']['dolor_maximo_reciente'], 2)
        self.assertGreaterEqual(resultado['evidencia']['adherencia_14d'], 0.7)
        self.assertEqual(resultado['evidencia']['dias_en_fase'], 9)

    def test_dias_minimos_no_cumplidos(self):
        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 4))

        self.assertFalse(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'dias_minimos_no_cumplidos')

    def test_sesiones_insuficientes(self):
        self._crear_sesion(self.fase1, date(2026, 1, 3), dolor_durante=2)

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))

        self.assertFalse(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'sesiones_insuficientes')

    def test_dolor_por_encima_del_umbral(self):
        for i in range(3):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)
        self._crear_sesion(self.fase1, date(2026, 1, 6), dolor_durante=6)

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))

        self.assertFalse(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'dolor_por_encima_del_umbral')

    def test_adherencia_insuficiente(self):
        for i in range(3):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))

        self.assertFalse(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'adherencia_insuficiente')

    def test_cooldown_retroceso_bloquea_avance(self):
        for i in range(7):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)
        TransicionFase.objects.create(
            episodio=self.episodio, fase_desde=self.fase2, fase_hasta=self.fase1,
            fecha=date(2026, 1, 5), direccion='RETROCESO', motivo='test',
            automatica=True, confirmada_por_usuario=False, evidencia={},
        )

        resultado = evaluar_elegibilidad_avance(self.episodio, date(2026, 1, 10))

        self.assertFalse(resultado['elegible'])
        self.assertEqual(resultado['motivo'], 'cooldown_retroceso')

    def test_cooldown_expira_tras_ventana(self):
        for i in range(7):
            self._crear_sesion(self.fase1, date(2026, 1, 20) + timedelta(days=i), dolor_durante=2)
        TransicionFase.objects.create(
            episodio=self.episodio, fase_desde=self.fase2, fase_hasta=self.fase1,
            fecha=date(2026, 1, 5), direccion='RETROCESO', motivo='test',
            automatica=True, confirmada_por_usuario=False, evidencia={},
        )

        fecha_eval = date(2026, 1, 5) + timedelta(days=COOLDOWN_DIAS_RETROCESO + 13)
        resultado = evaluar_elegibilidad_avance(self.episodio, fecha_eval)

        self.assertTrue(resultado['elegible'])


class ConfirmarAvanceTests(TransicionRehabTestBase):
    def test_confirmar_avance_con_elegible_true(self):
        for i in range(7):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)

        transicion = confirmar_avance(self.episodio, date(2026, 1, 10))

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase2)
        self.assertEqual(self.episodio.fase_actual_desde, date(2026, 1, 10))
        self.assertEqual(transicion.direccion, 'AVANCE')
        self.assertEqual(transicion.fase_desde, self.fase1)
        self.assertEqual(transicion.fase_hasta, self.fase2)
        self.assertFalse(transicion.automatica)
        self.assertTrue(transicion.confirmada_por_usuario)

    def test_confirmar_avance_con_elegible_false_lanza_validation_error(self):
        with self.assertRaises(ValidationError):
            confirmar_avance(self.episodio, date(2026, 1, 4))

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase1)

    def test_confirmar_avance_forzado_true_aplica_igual(self):
        transicion = confirmar_avance(self.episodio, date(2026, 1, 4), forzado=True)

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase2)
        self.assertEqual(transicion.evidencia.get('forzado'), True)


class EvaluarRetrocesoTests(TransicionRehabTestBase):
    def setUp(self):
        super().setUp()
        self._mover_a_fase2(date(2026, 2, 1))

    def test_condicion_sesiones_consecutivas_con_dolor(self):
        self._crear_sesion(self.fase2, date(2026, 2, 10), dolor_durante=7)
        self._crear_sesion(self.fase2, date(2026, 2, 11), dolor_durante=8)

        resultado = evaluar_retroceso(self.episodio, date(2026, 2, 11))

        self.assertTrue(resultado['aplica'])
        self.assertEqual(resultado['motivo'], 'dolor_sesiones_consecutivas')

    def test_condicion_tendencia_dolor_creciente(self):
        for i, dolor in enumerate([2, 3, 4, 5, 6]):
            self._crear_registro(date(2026, 2, 10) + timedelta(days=i), dolor)

        self.assertEqual(len([2, 3, 4, 5, 6]), DIAS_TENDENCIA_CRECIENTE)
        resultado = evaluar_retroceso(self.episodio, date(2026, 2, 14))

        self.assertTrue(resultado['aplica'])
        self.assertEqual(resultado['motivo'], 'tendencia_dolor_creciente')

    def test_condicion_dolor_puntual_alto(self):
        self._crear_registro(date(2026, 2, 5), dolor_manana=UMBRAL_DOLOR_RETROCESO_INMEDIATO + 1)

        resultado = evaluar_retroceso(self.episodio, date(2026, 2, 5))

        self.assertTrue(resultado['aplica'])
        self.assertEqual(resultado['motivo'], 'dolor_matutino_inmediato')

    def test_sin_ninguna_condicion_no_aplica(self):
        self._crear_sesion(self.fase2, date(2026, 2, 10), dolor_durante=2)
        self._crear_registro(date(2026, 2, 10), dolor_manana=2)

        resultado = evaluar_retroceso(self.episodio, date(2026, 2, 10))

        self.assertFalse(resultado['aplica'])

    def test_primera_fase_sin_retroceso_posible(self):
        self.episodio.fase_actual = self.fase1
        self.episodio.fase_actual_desde = date(2026, 1, 1)
        self.episodio.save(update_fields=['fase_actual', 'fase_actual_desde'])
        self._crear_registro(date(2026, 1, 5), dolor_manana=UMBRAL_DOLOR_RETROCESO_INMEDIATO + 1)

        resultado = evaluar_retroceso(self.episodio, date(2026, 1, 5))

        self.assertFalse(resultado['aplica'])
        self.assertEqual(resultado['motivo'], 'primera_fase_sin_retroceso_posible')


class AplicarRetrocesoAutomaticoTests(TransicionRehabTestBase):
    def setUp(self):
        super().setUp()
        self._mover_a_fase2(date(2026, 2, 1))

    def test_aplica_retroceso_y_crea_transicion(self):
        self._crear_registro(date(2026, 2, 5), dolor_manana=UMBRAL_DOLOR_RETROCESO_INMEDIATO + 1)

        transicion = aplicar_retroceso_automatico(self.episodio, date(2026, 2, 5))

        self.episodio.refresh_from_db()
        self.assertIsNotNone(transicion)
        self.assertEqual(self.episodio.fase_actual, self.fase1)
        self.assertEqual(self.episodio.fase_actual_desde, date(2026, 2, 5))
        self.assertEqual(transicion.direccion, 'RETROCESO')
        self.assertTrue(transicion.automatica)
        self.assertFalse(transicion.confirmada_por_usuario)
        self.assertEqual(transicion.fase_desde, self.fase2)
        self.assertEqual(transicion.fase_hasta, self.fase1)

    def test_no_aplica_devuelve_none_sin_escribir(self):
        self._crear_registro(date(2026, 2, 5), dolor_manana=2)

        transicion = aplicar_retroceso_automatico(self.episodio, date(2026, 2, 5))

        self.assertIsNone(transicion)
        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase2)
        self.assertEqual(
            TransicionFase.objects.filter(episodio=self.episodio, direccion='RETROCESO').count(), 0
        )


class WiringRetrocesoAutomaticoTests(TransicionRehabTestBase):
    def setUp(self):
        super().setUp()
        self._mover_a_fase2(date(2026, 2, 1))

    def test_registrar_dolor_diario_dispara_retroceso_automatico(self):
        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 2, 5),
            dolor_manana=UMBRAL_DOLOR_RETROCESO_INMEDIATO + 1, rigidez_manana=3,
        )

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase1)
        self.assertEqual(
            TransicionFase.objects.filter(
                episodio=self.episodio, direccion='RETROCESO', automatica=True
            ).count(),
            1,
        )

    def test_registrar_sesion_dispara_retroceso_automatico(self):
        self._crear_sesion(self.fase2, date(2026, 2, 9), dolor_durante=7)
        registrar_sesion(
            episodio=self.episodio,
            fecha=date(2026, 2, 10),
            estado='COMPLETADA',
            dolor_durante=8,
            ejercicios_data=[{
                'prescripcion_id': self.prescripcion_fase2.id,
                'series_completadas': 5,
                'carga_kg': None,
                'dolor_ejercicio': 8,
                'completado': True,
            }],
        )

        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase1)


class DetectarEstancamientoTests(TransicionRehabTestBase):
    def test_estancado_true_cuando_supera_duracion_tipica_y_no_es_elegible(self):
        limite = self.fase1.duracion_tipica_dias * MULTIPLICADOR_ESTANCAMIENTO
        fecha = date(2026, 1, 1) + timedelta(days=int(limite) + 5)

        resultado = detectar_estancamiento(self.episodio, fecha)

        self.assertTrue(resultado['estancado'])
        self.assertIsNotNone(resultado['mensaje'])
        self.assertIn('profesional', resultado['mensaje'].lower())

    def test_no_estancado_dentro_de_plazo(self):
        fecha = date(2026, 1, 1) + timedelta(days=10)

        resultado = detectar_estancamiento(self.episodio, fecha)

        self.assertFalse(resultado['estancado'])
        self.assertIsNone(resultado['mensaje'])
