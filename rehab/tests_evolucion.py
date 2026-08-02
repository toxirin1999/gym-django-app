from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from rehab.models import EjercicioRehab, FaseProtocolo, PrescripcionEjercicio, ProtocoloRehab, SesionRehab
from rehab.services import iniciar_episodio, registrar_dolor_diario, registrar_sesion
from rehab.services.evolucion_service import construir_evolucion


class EvolucionRehabTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paciente_evolucion', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.login(username='paciente_evolucion', password='x')

        self.protocolo = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana-evolucion',
            version=1,
            nombre='Tendinopatía rotuliana',
            zona='rodilla',
            descripcion='x',
            fuente_referencia='x',
            advertencias='x',
        )
        self.fase1 = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=1, slug='fase-1-evolucion', nombre='Fase 1',
            objetivo='Reducir dolor', duracion_minima_dias=7, duracion_tipica_dias=14,
            reglas_avance={'min_sesiones': 3, 'umbral_dolor': 4, 'min_adherencia': 0.7},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.fase2 = FaseProtocolo.objects.create(
            protocolo=self.protocolo, orden=2, slug='fase-2-evolucion', nombre='Fase 2',
            objetivo='Fortalecer', duracion_minima_dias=14, duracion_tipica_dias=42,
            reglas_avance={'min_sesiones': 4, 'umbral_dolor': 3, 'min_adherencia': 0.6},
            reglas_retroceso={'dolor_post_24h_umbral': 6, 'sesiones_consecutivas_con_dolor': 2},
            descripcion='x',
        )
        self.ejercicio = EjercicioRehab.objects.create(
            nombre='Sentadilla isométrica en pared',
            slug='sentadilla-isometrica-pared-evolucion',
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
            cliente=self.cliente, protocolo=self.protocolo, lateralidad='derecha',
            fecha_inicio=date(2026, 1, 1), dolor_basal_inicial=4,
        )

    def _crear_sesion(self, fase, fecha, dolor_durante=2, estado='COMPLETADA'):
        return SesionRehab.objects.create(
            episodio=self.episodio, fase=fase, fecha=fecha, estado=estado, dolor_durante=dolor_durante,
        )


class ConstruirEvolucionServicioTests(EvolucionRehabTestBase):
    def test_registros_diarios_aparecen_como_puntos_ordenados(self):
        registrar_dolor_diario(episodio=self.episodio, fecha=date(2026, 1, 3), dolor_manana=6, rigidez_manana=2)
        registrar_dolor_diario(episodio=self.episodio, fecha=date(2026, 1, 1), dolor_manana=8, rigidez_manana=3)
        registrar_dolor_diario(episodio=self.episodio, fecha=date(2026, 1, 2), dolor_manana=7, rigidez_manana=2)

        evolucion = construir_evolucion(self.episodio, fecha=date(2026, 1, 5))

        fechas = [p['fecha'] for p in evolucion['puntos']]
        self.assertEqual(fechas, [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)])
        self.assertEqual(evolucion['puntos'][0]['dolor_manana'], 8)
        self.assertEqual(evolucion['puntos'][1]['dolor_manana'], 7)
        self.assertEqual(evolucion['puntos'][2]['dolor_manana'], 6)

    def test_sesion_sin_registro_diario_mismo_dia_dolor_manana_es_none(self):
        self._crear_sesion(self.fase1, date(2026, 1, 4), dolor_durante=5)

        evolucion = construir_evolucion(self.episodio, fecha=date(2026, 1, 5))

        puntos_dia = [p for p in evolucion['puntos'] if p['fecha'] == date(2026, 1, 4)]
        self.assertEqual(len(puntos_dia), 1)
        self.assertIsNone(puntos_dia[0]['dolor_manana'])
        self.assertEqual(puntos_dia[0]['dolor_durante'], 5)

    def test_dos_sesiones_mismo_dia_usa_dolor_durante_maximo(self):
        self._crear_sesion(self.fase1, date(2026, 1, 4), dolor_durante=3)
        self._crear_sesion(self.fase1, date(2026, 1, 4), dolor_durante=7)

        evolucion = construir_evolucion(self.episodio, fecha=date(2026, 1, 5))

        puntos_dia = [p for p in evolucion['puntos'] if p['fecha'] == date(2026, 1, 4)]
        self.assertEqual(len(puntos_dia), 1)
        self.assertEqual(puntos_dia[0]['dolor_durante'], 7)

    def test_dato_fuera_de_la_ventana_no_aparece(self):
        self.episodio.estado = 'ALTA'
        self.episodio.save(update_fields=['estado'])
        episodio_largo = iniciar_episodio(
            cliente=self.cliente, protocolo=self.protocolo, lateralidad='izquierda',
            fecha_inicio=date(2025, 1, 1), dolor_basal_inicial=4,
        )
        registrar_dolor_diario(episodio=episodio_largo, fecha=date(2025, 1, 5), dolor_manana=9, rigidez_manana=3)
        registrar_dolor_diario(episodio=episodio_largo, fecha=date(2026, 6, 1), dolor_manana=2, rigidez_manana=1)

        evolucion = construir_evolucion(episodio_largo, fecha=date(2026, 6, 5), dias_ventana=60)

        fechas = [p['fecha'] for p in evolucion['puntos']]
        self.assertNotIn(date(2025, 1, 5), fechas)
        self.assertIn(date(2026, 6, 1), fechas)

    def test_fecha_desde_respeta_fecha_inicio_episodio_reciente(self):
        evolucion = construir_evolucion(self.episodio, fecha=date(2026, 1, 5), dias_ventana=60)

        self.assertEqual(evolucion['fecha_desde'], date(2026, 1, 1))
        self.assertEqual(evolucion['fecha_hasta'], date(2026, 1, 5))

    def test_eventos_contiene_transiciones_de_fase_en_rango(self):
        evolucion = construir_evolucion(self.episodio, fecha=date(2026, 1, 5))

        self.assertEqual(len(evolucion['eventos']), 1)
        evento = evolucion['eventos'][0]
        self.assertEqual(evento['fecha'], date(2026, 1, 1))
        self.assertEqual(evento['direccion'], 'INICIO')
        self.assertEqual(evento['fase_nombre'], self.fase1.nombre)

    def test_sin_datos_puntos_vacio(self):
        self.episodio.estado = 'ALTA'
        self.episodio.save(update_fields=['estado'])
        episodio_nuevo = iniciar_episodio(
            cliente=self.cliente, protocolo=self.protocolo, lateralidad='izquierda',
            fecha_inicio=date(2026, 3, 1), dolor_basal_inicial=4,
        )

        evolucion = construir_evolucion(episodio_nuevo, fecha=date(2026, 3, 1))

        self.assertEqual(evolucion['puntos'], [])


class EvolucionViewTests(EvolucionRehabTestBase):
    def test_sin_episodio_activo_muestra_invitacion(self):
        self.episodio.estado = 'ALTA'
        self.episodio.save(update_fields=['estado'])

        response = self.client.get(reverse('rehab:evolucion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Iniciar un episodio de rehabilitación')

    def test_con_episodio_pero_sin_datos_muestra_mensaje(self):
        self.episodio.estado = 'ALTA'
        self.episodio.save(update_fields=['estado'])
        iniciar_episodio(
            cliente=self.cliente, protocolo=self.protocolo, lateralidad='izquierda',
            fecha_inicio=timezone.localdate(), dolor_basal_inicial=4,
        )

        response = self.client.get(reverse('rehab:evolucion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Todavía no hay datos suficientes para mostrar evolución.')

    def test_con_datos_reales_muestra_valores_en_tabla(self):
        hoy = timezone.localdate()
        self.episodio.fecha_inicio = hoy - timedelta(days=1)
        self.episodio.fase_actual_desde = hoy - timedelta(days=1)
        self.episodio.save(update_fields=['fecha_inicio', 'fase_actual_desde'])
        registrar_dolor_diario(episodio=self.episodio, fecha=hoy, dolor_manana=6, rigidez_manana=2)
        registrar_sesion(
            episodio=self.episodio, fecha=hoy, estado='COMPLETADA',
            dolor_durante=4, ejercicios_data=[],
        )

        response = self.client.get(reverse('rehab:evolucion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hoy.strftime('%Y-%m-%d'))
        self.assertContains(response, '<td>6</td>', html=False)
        self.assertContains(response, '<td>4</td>', html=False)


class EnlaceEvolucionEnHoyViewTests(EvolucionRehabTestBase):
    def test_enlace_aparece_cuando_hay_episodio_activo(self):
        response = self.client.get(reverse('rehab:hoy'))

        self.assertContains(response, reverse('rehab:evolucion'))
