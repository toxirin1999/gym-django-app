"""Integridad de la carga que alimenta el ACWR (incidente del 11-oct-2026).

Una sesión dejada abierta desde el viernes y guardada el domingo envió 2.525
minutos; la carga se apuntó en la fecha planificada; un reintento duplicó otra
sesión; y Strava no encontró el entreno para fusionarse. El ACWR subió a 2,32.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado
from entrenos.services.duracion_sesion_service import (
    DURACION_MAX_MIN,
    estimar_duracion_por_series,
    sanear_duracion_minutos,
)
from rutinas.models import Rutina


class SanearDuracionTests(TestCase):
    def test_duracion_normal_se_respeta(self):
        self.assertEqual(sanear_duracion_minutos('59', 12), (59, False))

    def test_vacia_o_invalida_no_inventa_nada(self):
        self.assertEqual(sanear_duracion_minutos('', 12), (None, False))
        self.assertEqual(sanear_duracion_minutos('abc', 12), (None, False))
        self.assertEqual(sanear_duracion_minutos('-5', 12), (None, False))

    def test_cero_se_conserva(self):
        self.assertEqual(sanear_duracion_minutos('0', 3), (0, False))

    def test_limite_exacto_se_acepta(self):
        self.assertEqual(sanear_duracion_minutos(str(DURACION_MAX_MIN), 3), (DURACION_MAX_MIN, False))

    def test_cronometro_olvidado_se_estima_por_series(self):
        self.assertEqual(sanear_duracion_minutos('2525', 20), (60, True))

    def test_estimacion_acotada(self):
        self.assertEqual(estimar_duracion_por_series(2), 20)
        self.assertEqual(estimar_duracion_por_series(100), 180)
        self.assertIsNone(estimar_duracion_por_series(0))


class GuardadoSesionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='carga', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Carga', 'dias_disponibles': 4},
        )
        Rutina.objects.get_or_create(nombre='Día 4')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        self.hoy = timezone.localdate()

    def _post(self, duracion, fecha=None, ajax=False, series=3):
        data = {
            'fecha': (fecha or self.hoy).isoformat(),
            'rutina_nombre': 'Día 4',
            'sesion_programada_id': '',
            'modo_reducido': '0',
            'duracion_minutos_real': duracion,
            'ej1_nombre': 'Press banca',
            'ej1_tipo_progresion': 'peso_reps',
            'ej1_es_tope_maquina': 'false',
            'ej1_molestia_reportada': 'false',
        }
        for i in range(1, series + 1):
            data[f'ej1_peso_{i}'] = '60'
            data[f'ej1_reps_{i}'] = '8'
            data[f'ej1_rpe_{i}'] = '7'
            data[f'ej1_completado_{i}'] = '1'
        extra = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(self.url, data, **extra)

    def test_duracion_imposible_no_llega_a_la_carga(self):
        self._post('2525', series=10)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.duracion_minutos, 30)
        hub = ActividadRealizada.objects.get(entreno_gym=entreno)
        self.assertEqual(hub.duracion_minutos, 30)
        self.assertLessEqual(hub.carga_ua, 10 * 30)

    def test_duracion_normal_se_guarda_tal_cual(self):
        self._post('59')
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.duracion_minutos, 59)
        self.assertEqual(ActividadRealizada.objects.get(entreno_gym=entreno).duracion_minutos, 59)

    def test_reintento_no_duplica_la_sesion(self):
        r1 = self._post('59', ajax=True)
        r2 = self._post('59', ajax=True)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['success'])
        self.assertEqual(r1.json()['entreno_id'], r2.json()['entreno_id'])
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 1)
        self.assertEqual(ActividadRealizada.objects.filter(cliente=self.cliente).count(), 1)

    def test_otra_rutina_el_mismo_dia_si_se_guarda(self):
        self._post('59', ajax=True)
        Rutina.objects.get_or_create(nombre='Día 1')
        resp = self.client.post(self.url, {
            'fecha': self.hoy.isoformat(), 'rutina_nombre': 'Día 1', 'sesion_programada_id': '',
            'modo_reducido': '0', 'duracion_minutos_real': '40',
            'ej1_nombre': 'Remo', 'ej1_tipo_progresion': 'peso_reps',
            'ej1_peso_1': '50', 'ej1_reps_1': '10', 'ej1_rpe_1': '7', 'ej1_completado_1': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(resp.json()['success'])
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 2)

    def test_la_carga_se_apunta_el_dia_real_de_ejecucion(self):
        planificada = self.hoy - timedelta(days=3)
        self._post('59', fecha=planificada)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        hub = ActividadRealizada.objects.get(entreno_gym=entreno)
        self.assertEqual(hub.fecha, planificada)
        self.assertEqual(hub.fecha_realizado, self.hoy)


class AcwrFechaEfectivaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='acwr', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Acwr', 'dias_disponibles': 4},
        )
        self.hoy = timezone.now().date()
        for dias in range(40, 0, -3):
            d = self.hoy - timedelta(days=dias)
            ActividadRealizada.objects.create(
                cliente=self.cliente, tipo='gym', fecha=d, fecha_realizado=d, carga_ua=400,
            )

    def _acwr(self):
        from entrenos.services.services import EstadisticasService
        return EstadisticasService._analizar_acwr_unificado_calc(self.cliente)

    def test_sesion_adelantada_cuenta_el_dia_que_se_hizo(self):
        base = self._acwr()['carga_aguda']
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', fecha=self.hoy + timedelta(days=3),
            fecha_realizado=self.hoy, carga_ua=500,
        )
        self.assertGreater(self._acwr()['carga_aguda'], base)

    def test_load_manager_usa_la_misma_fecha(self):
        from hyrox.models import HyroxObjective
        from hyrox.training_engine import HyroxLoadManager
        objetivo = HyroxObjective(cliente=self.cliente)
        antes = HyroxLoadManager.calcular_ctl_atl_tsb(objetivo)['atl']
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='gym', fecha=self.hoy + timedelta(days=3),
            fecha_realizado=self.hoy, carga_ua=500,
        )
        self.assertGreater(HyroxLoadManager.calcular_ctl_atl_tsb(objetivo)['atl'], antes)


class StravaCandidatosTests(TestCase):
    def test_entreno_guardado_tarde_aparece_como_candidato(self):
        from hyrox.models import StravaActivityRaw
        user = User.objects.create_user(username='strava', password='x')
        cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Strava', 'dias_disponibles': 4},
        )
        rutina = Rutina.objects.create(nombre='Día 4 strava')
        # Planificado el 8, hecho el 9 (Strava), guardado el 11.
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=rutina, fecha=date(2026, 10, 8),
            fecha_ejecucion=date(2026, 10, 11),
        )
        ActividadRealizada.objects.filter(entreno_gym=entreno).update(fecha_realizado=date(2026, 10, 11))
        act = StravaActivityRaw.objects.create(
            cliente=cliente, strava_id=999001, fecha_actividad=date(2026, 10, 9),
            tipo_strava='WeightTraining', raw_json={},
        )
        self.client.force_login(user)
        resp = self.client.get(reverse('hyrox:strava_reconciliacion'))
        item = next(i for i in resp.context['items'] if i['actividad'].id == act.id)
        self.assertIn(entreno, item['gym_matches'])
        self.assertEqual(item['preselect'], ('gym', entreno.id))


class PlantillaRevisionDuracionTests(TestCase):
    def test_el_resumen_pide_la_duracion_real_si_el_cronometro_lleva_horas(self):
        from pathlib import Path
        t = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('id="duracion-revisar-wrap" hidden', t)
        self.assertIn('id="duracion-real-input"', t)
        self.assertIn('DURACION_REVISAR_MIN = 180', t)
        self.assertIn("value=duracionParaGuardar()", t)
        self.assertIn('if(!duracionRevisadaValida())return;', t)
