from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from clientes.models import Cliente
from clientes.views import plan_decisiones_view
from entrenos.models import (
    GymDecisionLog,
    GymDecisionTrace,
    GymDecisionTraceEvaluation,
    IntervencionPlan,
    SugerenciaPlan,
)
from entrenos.services.hipotesis_service import (
    aceptar_sugerencia_hipotesis,
    producir_sugerencia_hipotesis,
)


class CentroVerdadBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('centro_verdad', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()
        self.factory = RequestFactory()

    def _trace(self, offset, estado='entrenar'):
        return GymDecisionTrace.objects.create(
            cliente=self.cliente,
            fecha=self.hoy - timedelta(days=offset),
            decision_estado=estado,
            causa_principal='sesion_hoy',
            senales_motor={},
            capas_visibles=[],
            capas_suprimidas=[],
            explicacion_senales=[],
            preferencias_activas=[],
            intervenciones_activas=[],
            lesion_contexto={},
        )

    def _contexto_centro(self, continuidad):
        request = self.factory.get('/clientes/plan/decisiones/')
        request.user = self.user
        capturado = {}

        def render_falso(_request, _template, context):
            capturado.update(context)
            from django.http import HttpResponse
            return HttpResponse('ok')

        with (
            patch('clientes.views.render', side_effect=render_falso),
            patch(
                'core.continuidad.evaluar_continuidad_entrenamiento',
                side_effect=continuidad if isinstance(continuidad, Exception) else None,
                return_value=None if isinstance(continuidad, Exception) else continuidad,
            ),
        ):
            response = plan_decisiones_view(request)
        self.assertEqual(response.status_code, 200)
        return capturado


class TestGetCentroEsPuro(CentroVerdadBase):
    def test_get_repetido_no_escribe_ni_genera_sugerencia(self):
        for offset in (3, 4, 5):
            GymDecisionTraceEvaluation.objects.create(
                trace=self._trace(offset),
                resultado=GymDecisionTraceEvaluation.SENAL_NO_CAPTADA,
                resumen='Señal repetida.',
                senales_posteriores={},
            )
        SugerenciaPlan.objects.all().delete()

        before = {
            'sugerencias': SugerenciaPlan.objects.count(),
            'intervenciones': IntervencionPlan.objects.count(),
            'evaluaciones': GymDecisionTraceEvaluation.objects.count(),
        }
        with patch(
            'entrenos.services.hipotesis_service.generar_sugerencia_hipotesis',
            side_effect=AssertionError('el GET no debe producir'),
        ):
            self._contexto_centro({
                'hay_pausa_significativa': False,
                'nivel': 'sin_pausa',
            })
            self._contexto_centro({
                'hay_pausa_significativa': False,
                'nivel': 'sin_pausa',
            })

        self.assertEqual(before, {
            'sugerencias': SugerenciaPlan.objects.count(),
            'intervenciones': IntervencionPlan.objects.count(),
            'evaluaciones': GymDecisionTraceEvaluation.objects.count(),
        })


class TestProductorExplicito(CentroVerdadBase):
    def test_crear_evaluacion_alcanzando_hipotesis_produce_sin_abrir_centro(self):
        with self.captureOnCommitCallbacks(execute=True):
            for offset in (3, 4, 5):
                GymDecisionTraceEvaluation.objects.create(
                    trace=self._trace(offset),
                    resultado=GymDecisionTraceEvaluation.SENAL_NO_CAPTADA,
                    resumen='Señal repetida.',
                    senales_posteriores={},
                )

        sugerencia = SugerenciaPlan.objects.get(
            cliente=self.cliente,
            patron='hipotesis_senal_entrenar',
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        repetida = producir_sugerencia_hipotesis(self.cliente, fecha_ref=self.hoy)
        self.assertEqual(repetida.pk, sugerencia.pk)
        self.assertEqual(
            SugerenciaPlan.objects.filter(
                cliente=self.cliente,
                patron='hipotesis_senal_entrenar',
                estado=SugerenciaPlan.ESTADO_PENDIENTE,
            ).count(),
            1,
        )


class TestContinuidadSoberana(CentroVerdadBase):
    def test_pausa_significativa_impide_modo_normal_y_llega_a_template(self):
        continuidad = {
            'hay_pausa_significativa': True,
            'nivel': 'clara',
            'dias_sin_gym': 8,
        }
        contexto = self._contexto_centro(continuidad)
        self.assertEqual(contexto['continuidad'], continuidad)
        self.assertNotIn('modo normal', contexto['estado_plan']['narrativa'])

    def test_sin_pausa_confirmada_permite_modo_normal(self):
        continuidad = {
            'hay_pausa_significativa': False,
            'nivel': 'sin_pausa',
            'dias_sin_gym': 2,
        }
        contexto = self._contexto_centro(continuidad)
        self.assertIsNone(contexto['continuidad'])
        self.assertIn('modo normal', contexto['estado_plan']['narrativa'])

    def test_fallo_de_continuidad_degrada_sin_afirmar_ausencia(self):
        contexto = self._contexto_centro(RuntimeError('continuidad no disponible'))
        self.assertIsNone(contexto['continuidad'])
        self.assertNotIn('modo normal', contexto['estado_plan']['narrativa'])
        self.assertIn('no está disponible', contexto['estado_plan']['narrativa'])


class TestVentanaIntervenciones(CentroVerdadBase):
    def _intervencion(self, inicio, fin):
        return IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            fecha_inicio=inicio,
            fecha_fin=fin,
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )

    def test_excluye_futura_e_incluye_frontera_de_hoy(self):
        hoy_activa = self._intervencion(self.hoy, self.hoy)
        self._intervencion(self.hoy + timedelta(days=1), self.hoy + timedelta(days=7))

        contexto = self._contexto_centro({
            'hay_pausa_significativa': False,
            'nivel': 'sin_pausa',
        })
        self.assertEqual([item.pk for item in contexto['intervenciones_activas']], [hoy_activa.pk])


class TestResumenCargaCompleto(CentroVerdadBase):
    def test_incluye_subir_reps_y_no_pierde_ejercicios_despues_del_log_15(self):
        for indice in range(16):
            GymDecisionLog.objects.create(
                cliente=self.cliente,
                ejercicio=f'ejercicio {indice:02d}',
                accion='subir_reps' if indice == 0 else 'mantener',
                motivo='Progresión observable.',
            )

        contexto = self._contexto_centro({
            'hay_pausa_significativa': False,
            'nivel': 'sin_pausa',
        })
        ejercicios = {
            ejercicio
            for grupo in contexto['decisiones_agrupadas']
            for ejercicio in grupo['ejercicios']
        }
        self.assertEqual(len(ejercicios), 16)
        self.assertIn('subir_reps', {g['accion'] for g in contexto['decisiones_agrupadas']})
        self.assertLessEqual(len(contexto['decisiones_carga']), 15)


class TestResponderSugerencia(CentroVerdadBase):
    def _sugerencia(self):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='hipotesis_senal_entrenar',
            texto='Probar observación.',
        )

    def test_aceptar_es_atomico_y_fecha_respuesta_se_asigna(self):
        sugerencia = self._sugerencia()
        intervencion = aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_ACEPTADA)
        self.assertIsNotNone(sugerencia.fecha_respuesta)
        self.assertEqual(intervencion.sugerencia, sugerencia)

    def test_aceptar_revierte_estado_si_falla_crear_intervencion(self):
        sugerencia = self._sugerencia()
        with (
            patch.object(IntervencionPlan.objects, 'create', side_effect=DatabaseError('boom')),
            self.assertRaises(DatabaseError),
        ):
            aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertIsNone(sugerencia.fecha_respuesta)

    def test_ignorar_view_asigna_fecha_respuesta(self):
        sugerencia = self._sugerencia()
        request = self.factory.post('/ignorar/')
        request.user = self.user
        from clientes.views import ignorar_hipotesis_view
        with patch('clientes.views.messages.info'), patch('clientes.views.redirect'):
            ignorar_hipotesis_view(request, sugerencia.pk)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_IGNORADA)
        self.assertIsNotNone(sugerencia.fecha_respuesta)
