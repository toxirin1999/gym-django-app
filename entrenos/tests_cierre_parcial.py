from datetime import date, timedelta
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import BitacoraDiaria, Cliente
from core.bio_context import BioContextProvider
from entrenos.models import (
    EjercicioOmitidoEntreno,
    EntrenoRealizado,
    GymDecisionLog,
    SesionProgramada,
    AusenciaPlanificadaGym,
)
from entrenos.services.sesion_recomendada import cerrar_sesion_programada
from entrenos.services.calendario_plan_service import _determinar_estado
from entrenos.services.decision_trace_service import humanizar_trace
from entrenos.services.distribucion_semanal_contractual_service import _clasificar_sesion
from entrenos.services.trayectoria_plan_service import _serializar_sesion
from entrenos.services.retorno_ausencia_service import (
    es_primera_sesion_tras_ausencia,
    limitar_series_retorno,
)
from rutinas.models import Rutina


class CierreParcialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-parcial', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.rutina = Rutina.objects.create(nombre='Día parcial')
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def _post(self, **extra):
        data = {
            'fecha': date.today().isoformat(), 'rutina_nombre': self.rutina.nombre,
            'ej1_nombre': 'Sentadilla', 'ej1_tipo_progresion': 'peso_reps',
            'ej1_peso_1': '60', 'ej1_reps_1': '5', 'ej1_rpe_1': '8', 'ej1_completado_1': '1',
            'ej2_nombre': 'Curl femoral', 'ej2_tipo_progresion': 'peso_reps',
            'ej2_peso_1': '30', 'ej2_reps_1': '10',
        }
        data.update(extra)
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_parcial_exige_motivo_y_no_persiste_a_medias(self):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(EntrenoRealizado.objects.count(), 0)

    def test_omite_planificados_sin_series_y_frena_sin_inventar_rendimiento(self):
        response = self._post(motivo_cierre='fatiga')
        self.assertEqual(response.status_code, 200)
        entreno = EntrenoRealizado.objects.get()
        self.assertEqual(entreno.estado_cierre, EntrenoRealizado.ESTADO_PARCIAL)
        self.assertEqual(entreno.motivo_cierre, 'fatiga')
        self.assertEqual(
            list(entreno.ejercicios_omitidos.values_list('nombre_ejercicio', flat=True)),
            ['Curl femoral'],
        )
        decision = GymDecisionLog.objects.get(entreno_origen=entreno, ejercicio_normalizado='curl femoral')
        self.assertEqual(decision.accion, 'mantener')
        self.assertIsNone(decision.peso_anterior)
        self.assertIsNone(decision.reps_anteriores)
        self.assertEqual(
            GymDecisionLog.objects.filter(entreno_origen=entreno, ejercicio_normalizado='curl femoral').count(), 1
        )
        self.assertEqual(
            GymDecisionLog.objects.get(entreno_origen=entreno, ejercicio_normalizado='sentadilla').accion,
            'mantener',
        )

    def test_post_parcial_con_varios_realizados_y_varios_omitidos_por_fatiga(self):
        response = self._post(
            motivo_cierre='fatiga',
            ej2_completado_1='1', ej2_rpe_1='9',
            ej3_nombre='Press banca', ej3_tipo_progresion='peso_reps',
            ej3_peso_1='50', ej3_reps_1='8',
            ej4_nombre='Remo sentado', ej4_tipo_progresion='peso_reps',
            ej4_peso_1='45', ej4_reps_1='10',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        entreno = EntrenoRealizado.objects.get()
        self.assertEqual(entreno.estado_cierre, EntrenoRealizado.ESTADO_PARCIAL)
        self.assertEqual(entreno.ejercicios_realizados.count(), 2)
        self.assertEqual(
            set(entreno.ejercicios_omitidos.values_list('nombre_ejercicio', flat=True)),
            {'Press banca', 'Remo sentado'},
        )
        self.assertEqual(
            entreno.ejercicios_omitidos.filter(motivo='fatiga').count(),
            2,
        )

    def test_rechaza_cierre_sin_ninguna_serie(self):
        response = self._post(motivo_cierre='tiempo', ej1_completado_1='')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(EntrenoRealizado.objects.count(), 0)

    def test_sesion_programada_termina_parcial(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, estado_cierre=EntrenoRealizado.ESTADO_PARCIAL,
            motivo_cierre='tiempo', fecha_ejecucion=date.today(),
        )
        sp = SesionProgramada.objects.create(cliente=self.cliente, fecha_prevista=date.today())
        cerrar_sesion_programada(sp.pk, entreno)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PARCIAL)

    def test_entrenamiento_activo_no_renderiza_ejercicios_con_cero_series(self):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.pk])
        ejercicios = [
            {
                'nombre': 'Sentadilla válida', 'series': 3, 'repeticiones': 5,
                'peso_recomendado_kg': 60, 'tipo_ejercicio': 'compuesto_principal',
                '_autoridad_gym_materializada': True,
            },
            {
                'nombre': 'Curl fantasma', 'series': 0, 'repeticiones': 10,
                'peso_recomendado_kg': 20, 'tipo_ejercicio': 'accesorio',
                '_autoridad_gym_materializada': True,
            },
        ]

        response = self.client.get(url, {
            'fecha': date.today().isoformat(),
            'rutina_nombre': self.rutina.nombre,
            'ejercicios': json.dumps(ejercicios),
        })

        self.assertEqual(response.status_code, 200)
        planificados = response.context['ejercicios_planificados']
        self.assertEqual([ejercicio['nombre'] for ejercicio in planificados], ['Sentadilla válida'])
        self.assertContains(response, 'Sentadilla válida')
        self.assertNotContains(response, 'Curl fantasma')


class EnergiaActualTests(TestCase):
    def test_solo_hoy_y_preserva_cero(self):
        user = User.objects.create_user('energia-hoy')
        cliente = Cliente.objects.get(user=user)
        vieja = BitacoraDiaria.objects.create(cliente=cliente, energia_subjetiva=9)
        BitacoraDiaria.objects.filter(pk=vieja.pk).update(fecha=timezone.localdate() - timedelta(days=1))
        self.assertIsNone(BioContextProvider.get_bio_signals(cliente)['energia'])
        hoy = BitacoraDiaria.objects.create(cliente=cliente, energia_subjetiva=0)
        self.assertEqual(BioContextProvider.get_bio_signals(cliente)['energia'], 0)


class ContratoTemplateCierreParcialTests(TestCase):
    def test_ui_contiene_motivos_y_guardas(self):
        source = open('entrenos/templates/entrenos/entrenamiento_activo.html', encoding='utf-8').read()
        for value in ('fatiga', 'tiempo', 'molestia', 'equipo', 'otro'):
            self.assertIn(f'value="{value}"', source)
        self.assertIn('motivo_cierre', source)
        self.assertIn('No puedes cerrar una sesión sin completar al menos una serie', source)

    def test_retorno_24_a_18_conserva_principales(self):
        ejercicios = [
            {'nombre': str(i), 'series': 3,
             'tipo_ejercicio': 'compuesto_principal' if i < 2 else 'accesorio'}
            for i in range(8)
        ]
        limitar_series_retorno(ejercicios)
        self.assertEqual(sum(e['series'] for e in ejercicios), 18)
        self.assertEqual(len(ejercicios), 6)
        self.assertNotIn(0, [e['series'] for e in ejercicios])
        self.assertEqual([e['series'] for e in ejercicios[:2]], [3, 3])

    def test_gap_sin_ausencia_confirmada_no_activa_retorno(self):
        user = User.objects.create_user('gap-no-es-ausencia')
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='Gap casual')
        EntrenoRealizado.objects.create(
            cliente=cliente, rutina=rutina, fecha=date.today() - timedelta(days=10),
            fecha_ejecucion=date.today() - timedelta(days=10),
        )
        self.assertFalse(es_primera_sesion_tras_ausencia(cliente, date.today()))

    def test_ausencia_confirmada_de_seis_dias_activa_primera_sesion(self):
        user = User.objects.create_user('retorno-ausencia')
        cliente = Cliente.objects.get(user=user)
        hoy = date.today()
        AusenciaPlanificadaGym.objects.create(
            cliente=cliente, inicio=hoy - timedelta(days=6), fin=hoy - timedelta(days=1),
            motivo=AusenciaPlanificadaGym.MOTIVO_VIAJE,
        )
        self.assertTrue(es_primera_sesion_tras_ausencia(cliente, hoy))

    def test_js_bloquea_doble_submit_y_restaura_en_error(self):
        source = open('entrenos/templates/entrenos/entrenamiento_activo.html', encoding='utf-8').read()
        self.assertIn('if (_envioCierreEnCurso) return;', source)
        self.assertIn('_envioCierreEnCurso = true;', source)
        self.assertIn('confirmarBtn.disabled = true;', source)
        self.assertIn('_envioCierreEnCurso = false;', source)
        self.assertIn('confirmarBtn.disabled = false;', source)

    def test_js_confirmacion_del_servidor_no_falla_por_limpieza_local_o_refresh_joi(self):
        source = open('entrenos/templates/entrenos/entrenamiento_activo.html', encoding='utf-8').read()
        success_branch = source.split('if (data.success) {', 1)[1].split('} else {', 1)[0]
        self.assertIn('try { limpiarCheckpoint(); } catch', success_branch)
        self.assertIn('try { localStorage.removeItem(_WK_KEY); } catch', success_branch)
        self.assertIn("try { fetch('/joi/api/pulso-actual/')", success_branch)
        self.assertIn('window.location.href =', success_branch)

    def test_js_muestra_error_real_y_solo_conserva_checkpoint_en_fallo(self):
        source = open('entrenos/templates/entrenos/entrenamiento_activo.html', encoding='utf-8').read()
        self.assertIn("window.alert(error.message || 'No se pudo guardar", source)
        catch_branch = source.split('.catch(error => {', 1)[1].split('});', 1)[0]
        self.assertNotIn('limpiarCheckpoint()', catch_branch)
        self.assertNotIn('localStorage.removeItem(_WK_KEY)', catch_branch)


class IntegracionTransversalCierreParcialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('parcial-transversal')
        self.cliente = Cliente.objects.get(user=self.user)
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date.today(),
            estado=SesionProgramada.ESTADO_PARCIAL,
        )

    def test_serializadores_y_calendario_reconocen_ejecucion_parcial(self):
        dato = _serializar_sesion(self.sp)
        self.assertTrue(dato['realizada'])
        self.assertTrue(dato['parcial'])
        self.assertFalse(dato['completa'])
        self.assertEqual(_determinar_estado(self.sp, None, date.today(), date.today()), 'parcial')

    def test_distribucion_expone_resultado_parcial(self):
        self.assertEqual(_clasificar_sesion(self.sp)['resultado'], 'parcial')

    def test_trace_distingue_ejecucion_parcial(self):
        class Trace:
            fecha = date.today()
            decision_estado = 'entrenar'
            sesion_programada = self.sp
            capas_visibles = []
            capas_suprimidas = []
            lesion_contexto = {}
            evaluacion = None
            def get_explicacion_humana(self): return 'Lectura.'
        self.assertEqual(humanizar_trace(Trace())['execution_state'], 'executed_partial')

    def test_servicios_declaran_conteos_realizados_parciales_sin_romper_completadas(self):
        for ruta in (
            'entrenos/services/estrategia_semanal_gym_service.py',
            'entrenos/services/centro_decisiones_service.py',
            'entrenos/services/proyeccion_bloque_gym_service.py',
            'entrenos/services/ciclo_intervencion_esenciales_service.py',
            'entrenos/services/evaluacion_semanal_gym_service.py',
        ):
            source = open(ruta, encoding='utf-8').read()
            self.assertIn('sesiones_realizadas', source, ruta)
            self.assertIn('sesiones_parciales', source, ruta)
            self.assertIn('sesiones_completadas', source, ruta)

    def test_template_calendario_incluye_leyenda_y_clase_parcial(self):
        source = open('clientes/templates/clientes/mockup_demo.html', encoding='utf-8').read()
        self.assertIn('cal-dot--parcial', source)
        self.assertIn('Parcial', source)
