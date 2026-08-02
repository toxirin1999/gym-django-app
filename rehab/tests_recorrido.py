from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from rehab.models import EjercicioRehab, FaseProtocolo, PrescripcionEjercicio, ProtocoloRehab, SesionRehab
from rehab.services import confirmar_avance, iniciar_episodio, registrar_dolor_diario
from rehab.services.recorrido_service import construir_recorrido


class RecorridoRehabTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paciente_recorrido', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.login(username='paciente_recorrido', password='x')

        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana-recorrido',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        self.fase1 = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=1, slug='fase-1-recorrido', nombre='Fase 1',
            objetivo='Reducir dolor', duracion_minima_dias=7, duracion_tipica_dias=14,
            reglas_avance={'min_sesiones': 3, 'umbral_dolor': 4, 'min_adherencia': 0.7},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.fase2 = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=2, slug='fase-2-recorrido', nombre='Fase 2',
            objetivo='Fortalecer', duracion_minima_dias=14, duracion_tipica_dias=42,
            reglas_avance={'min_sesiones': 4, 'umbral_dolor': 3, 'min_adherencia': 0.6},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.fase3 = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=3, slug='fase-3-recorrido', nombre='Fase 3',
            objetivo='Retorno a la actividad', duracion_minima_dias=14, duracion_tipica_dias=28,
            descripcion='x',
        )
        self.ejercicio = EjercicioRehab.objects.create(
            nombre='Sentadilla isométrica en pared',
            slug='sentadilla-isometrica-pared-recorrido',
            tipo_contraccion='isometrico',
            descripcion_ejecucion='x',
        )
        self.prescripcion_fase1 = PrescripcionEjercicio.objects.create(
            fase=self.fase1, ejercicio=self.ejercicio, orden=1, series=5, frecuencia_semanal=5, parametros={},
        )
        self.prescripcion_fase2 = PrescripcionEjercicio.objects.create(
            fase=self.fase2, ejercicio=self.ejercicio, orden=1, series=5, frecuencia_semanal=5, parametros={},
        )
        self.prescripcion_fase3 = PrescripcionEjercicio.objects.create(
            fase=self.fase3, ejercicio=self.ejercicio, orden=1, series=5, frecuencia_semanal=5, parametros={},
        )
        self.episodio = iniciar_episodio(
            cliente=self.cliente, protocolo=self.protocolo, lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1), dolor_basal_inicial=4,
        )

    def _crear_sesion(self, fase, fecha, dolor_durante=2, estado='COMPLETADA'):
        return SesionRehab.objects.create(
            episodio=self.episodio, fase=fase, fecha=fecha, estado=estado, dolor_durante=dolor_durante,
        )

    def _avanzar_a_fase2(self):
        for i in range(7):
            self._crear_sesion(self.fase1, date(2026, 1, 2) + timedelta(days=i), dolor_durante=2)
        confirmar_avance(self.episodio, date(2026, 1, 10))


class ConstruirRecorridoEpisodioReciénIniciadoTests(RecorridoRehabTestBase):
    def test_fase1_actual_fase2_y_3_futuras(self):
        recorrido = construir_recorrido(self.episodio, fecha=date(2026, 1, 5))

        self.assertEqual(len(recorrido), 3)
        item1, item2, item3 = recorrido

        self.assertEqual(item1['fase'], self.fase1)
        self.assertEqual(item1['estado'], 'actual')
        self.assertEqual(item1['fecha_inicio'], date(2026, 1, 1))
        self.assertIsNone(item1['fecha_fin'])
        self.assertEqual(item1['duracion_dias'], 4)

        for item in (item2, item3):
            self.assertEqual(item['estado'], 'futura')
            self.assertIsNone(item['fecha_inicio'])
            self.assertIsNone(item['fecha_fin'])
            self.assertIsNone(item['duracion_dias'])
            self.assertTrue(len(item['ejercicios']) > 0)


class ConstruirRecorridoTrasAvanceConfirmadoTests(RecorridoRehabTestBase):
    def test_fase1_completada_fase2_actual(self):
        self._avanzar_a_fase2()

        recorrido = construir_recorrido(self.episodio, fecha=date(2026, 1, 15))
        item1, item2, item3 = recorrido

        self.assertEqual(item1['estado'], 'completada')
        self.assertEqual(item1['fecha_inicio'], date(2026, 1, 1))
        self.assertEqual(item1['fecha_fin'], date(2026, 1, 10))
        self.assertEqual(item1['duracion_dias'], 9)

        self.assertEqual(item2['estado'], 'actual')
        self.assertEqual(item2['fecha_inicio'], date(2026, 1, 10))
        self.assertIsNone(item2['fecha_fin'])
        self.assertEqual(item2['duracion_dias'], 5)

        self.assertEqual(item3['estado'], 'futura')


class ConstruirRecorridoTrasRetrocesoAutomaticoTests(RecorridoRehabTestBase):
    def test_fase1_vuelve_a_actual_no_completada(self):
        self._avanzar_a_fase2()

        registrar_dolor_diario(
            episodio=self.episodio, fecha=date(2026, 1, 15), dolor_manana=9, rigidez_manana=3,
        )
        self.episodio.refresh_from_db()
        self.assertEqual(self.episodio.fase_actual, self.fase1)

        recorrido = construir_recorrido(self.episodio, fecha=date(2026, 1, 20))
        item1, item2, item3 = recorrido

        self.assertEqual(item1['estado'], 'actual')
        self.assertEqual(item1['fecha_inicio'], date(2026, 1, 15))
        self.assertIsNone(item1['fecha_fin'])
        self.assertEqual(item1['duracion_dias'], 5)

        self.assertEqual(item2['estado'], 'futura')
        self.assertIsNone(item2['fecha_inicio'])

        self.assertEqual(item3['estado'], 'futura')


class RecorridoViewTests(RecorridoRehabTestBase):
    def test_sin_episodio_activo_muestra_invitacion(self):
        self.episodio.estado = 'ALTA'
        self.episodio.save(update_fields=['estado'])

        response = self.client.get(reverse('rehab:recorrido'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Iniciar un episodio de rehabilitación')

    def test_con_episodio_activo_muestra_las_3_fases(self):
        response = self.client.get(reverse('rehab:recorrido'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.fase1.nombre)
        self.assertContains(response, self.fase2.nombre)
        self.assertContains(response, self.fase3.nombre)
        self.assertContains(response, self.ejercicio.nombre)


class EnlaceRecorridoEnHoyViewTests(RecorridoRehabTestBase):
    def test_enlace_aparece_cuando_hay_episodio_activo(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertContains(response, reverse('rehab:recorrido'))
