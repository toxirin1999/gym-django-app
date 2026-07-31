"""Etapa 3A — gobernanza operativa del Centro de decisiones.

Estos tests fijan tres garantías: evaluación automática fuera del request,
comandos de mantenimiento seguros por defecto y aceptación atómica.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import (
    GymDecisionLog,
    GymDecisionTrace,
    GymDecisionTraceEvaluation,
    IntervencionPlan,
    SugerenciaPlan,
)
from entrenos.services.sugerencias_service import aceptar_sugerencia
from entrenos.services.reconciliacion_gobernanza_service import detectar_hallazgos


class Gobernanza3ABase(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user(username="gob3a", password="x")
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={"nombre": "Gobernanza 3A", "dias_disponibles": 4},
        )

    def crear_trace(self, *, cliente=None, dias=3, estado="posponer"):
        return GymDecisionTrace.objects.create(
            cliente=cliente or self.cliente,
            fecha=self.hoy - timedelta(days=dias),
            decision_estado=estado,
            causa_principal="energia_baja",
            senales_motor={},
            capas_visibles=[],
            capas_suprimidas=[],
            explicacion_senales=[],
            preferencias_activas=[],
            intervenciones_activas=[],
            lesion_contexto={},
        )

    def crear_sugerencia(self, *, cliente=None, estado=SugerenciaPlan.ESTADO_PENDIENTE):
        return SugerenciaPlan.objects.create(
            cliente=cliente or self.cliente,
            patron="carga_alta_sostenida",
            texto="Mantener cargas esta semana.",
            estado=estado,
        )

    def crear_decision(self, *, estado_aplicacion, fecha_aplicacion):
        return GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio="Sentadilla",
            accion="mantener",
            motivo="Decisión de prueba para gobernanza.",
            estado_aplicacion=estado_aplicacion,
            fecha_aplicacion=fecha_aplicacion,
        )

    def crear_intervencion(
        self,
        *,
        cliente=None,
        sugerencia=None,
        inicio=None,
        fin=None,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        tipo=IntervencionPlan.TIPO_NO_SUBIR,
    ):
        return IntervencionPlan.objects.create(
            cliente=cliente or self.cliente,
            sugerencia=sugerencia,
            tipo=tipo,
            origen_patron="carga_alta_sostenida",
            fecha_inicio=inicio or self.hoy - timedelta(days=7),
            fecha_fin=fin or self.hoy + timedelta(days=1),
            estado=estado,
        )


class SignalEvaluacionBacklogTests(Gobernanza3ABase):
    def test_on_commit_evalua_otros_maduros_no_actual_ni_inmaduro(self):
        maduro = self.crear_trace(dias=4)
        inmaduro = self.crear_trace(dias=1)

        with patch(
            "entrenos.services.evaluacion_trace_service._recopilar_senales_posteriores",
            return_value={"sesiones_posteriores": 0},
        ):
            with self.captureOnCommitCallbacks(execute=True):
                actual = self.crear_trace(dias=0, estado="entrenar")

        self.assertTrue(
            GymDecisionTraceEvaluation.objects.filter(trace=maduro).exists()
        )
        self.assertFalse(
            GymDecisionTraceEvaluation.objects.filter(trace=inmaduro).exists()
        )
        self.assertFalse(
            GymDecisionTraceEvaluation.objects.filter(trace=actual).exists()
        )

    def test_on_commit_es_idempotente(self):
        maduro = self.crear_trace(dias=4)
        with patch(
            "entrenos.services.evaluacion_trace_service._recopilar_senales_posteriores",
            return_value={"sesiones_posteriores": 0},
        ):
            with self.captureOnCommitCallbacks(execute=True):
                self.crear_trace(dias=0)
            with self.captureOnCommitCallbacks(execute=True):
                self.crear_trace(dias=-1)

        self.assertEqual(
            GymDecisionTraceEvaluation.objects.filter(trace=maduro).count(), 1
        )

    def test_error_del_backlog_se_loguea_y_no_rompe_el_guardado(self):
        with patch(
            "entrenos.services.evaluacion_trace_service.evaluar_traces_pendientes",
            side_effect=RuntimeError("fallo controlado"),
        ):
            with self.assertLogs("entrenos.signals", level="ERROR") as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    trace = self.crear_trace(dias=0)

        self.assertTrue(GymDecisionTrace.objects.filter(pk=trace.pk).exists())
        self.assertIn("fallo controlado", "\n".join(logs.output))


class EvaluarTracesCommandTests(Gobernanza3ABase):
    def test_dry_run_es_el_default_y_no_escribe(self):
        self.crear_trace(dias=3)
        salida = StringIO()
        call_command("evaluar_traces_pendientes", stdout=salida)

        self.assertEqual(GymDecisionTraceEvaluation.objects.count(), 0)
        self.assertIn("dry-run", salida.getvalue().lower())

    def test_apply_evalua_traces_maduros(self):
        maduro = self.crear_trace(dias=3)
        with patch(
            "entrenos.services.evaluacion_trace_service._recopilar_senales_posteriores",
            return_value={"sesiones_posteriores": 0},
        ):
            call_command("evaluar_traces_pendientes", "--apply", stdout=StringIO())

        self.assertTrue(
            GymDecisionTraceEvaluation.objects.filter(trace=maduro).exists()
        )

    def test_cliente_limit_y_ventana_restringen_el_lote(self):
        otro_user = User.objects.create_user(username="gob3a_otro", password="x")
        otro, _ = Cliente.objects.get_or_create(
            user=otro_user, defaults={"nombre": "Otro", "dias_disponibles": 3}
        )
        maduros = [self.crear_trace(dias=d) for d in (5, 4)]
        inmaduro = self.crear_trace(dias=1)
        trace_otro = self.crear_trace(cliente=otro, dias=5)

        with patch(
            "entrenos.services.evaluacion_trace_service._recopilar_senales_posteriores",
            return_value={"sesiones_posteriores": 0},
        ):
            call_command(
                "evaluar_traces_pendientes",
                "--apply",
                "--cliente-id",
                str(self.cliente.pk),
                "--limit",
                "1",
                stdout=StringIO(),
            )

        evaluados = set(
            GymDecisionTraceEvaluation.objects.values_list("trace_id", flat=True)
        )
        self.assertEqual(len(evaluados.intersection({t.pk for t in maduros})), 1)
        self.assertNotIn(inmaduro.pk, evaluados)
        self.assertNotIn(trace_otro.pk, evaluados)


class ReconciliarGobernanzaCommandTests(Gobernanza3ABase):
    def test_decision_pospuesta_con_fecha_aplicacion_es_coherente(self):
        decision = self.crear_decision(
            estado_aplicacion="pospuesta",
            fecha_aplicacion=timezone.now(),
        )

        hallazgos = detectar_hallazgos(cliente_id=self.cliente.pk)

        self.assertFalse(any(
            h["code"] == "decision_estado_fecha_incoherente"
            and h["pk"] == decision.pk
            for h in hallazgos
        ))

    def test_decision_pospuesta_sin_fecha_aplicacion_es_incoherente(self):
        decision = self.crear_decision(
            estado_aplicacion="pospuesta",
            fecha_aplicacion=None,
        )

        hallazgos = detectar_hallazgos(cliente_id=self.cliente.pk)

        self.assertTrue(any(
            h["code"] == "decision_estado_fecha_incoherente"
            and h["pk"] == decision.pk
            for h in hallazgos
        ))

    def test_decision_aplicada_requiere_fecha_aplicacion(self):
        coherente = self.crear_decision(
            estado_aplicacion="aplicada",
            fecha_aplicacion=timezone.now(),
        )
        incoherente = self.crear_decision(
            estado_aplicacion="aplicada",
            fecha_aplicacion=None,
        )

        ids_incoherentes = {
            h["pk"] for h in detectar_hallazgos(cliente_id=self.cliente.pk)
            if h["code"] == "decision_estado_fecha_incoherente"
        }

        self.assertNotIn(coherente.pk, ids_incoherentes)
        self.assertIn(incoherente.pk, ids_incoherentes)

    def test_evaluacion_stale_solo_si_trace_cambio_despues(self):
        trace = self.crear_trace(dias=40)
        evaluacion = GymDecisionTraceEvaluation.objects.create(
            trace=trace,
            resultado=GymDecisionTraceEvaluation.NEUTRO,
            resumen="Evaluación original.",
            senales_posteriores={},
        )
        GymDecisionTrace.objects.filter(pk=trace.pk).update(
            actualizado_en=evaluacion.creado_en + timedelta(minutes=1),
        )

        hallazgos = detectar_hallazgos(cliente_id=self.cliente.pk)

        self.assertTrue(any(
            h["code"] == "evaluacion_trace_stale" and h["pk"] == evaluacion.pk
            for h in hallazgos
        ))

    def test_evaluacion_antigua_sin_cambio_del_trace_no_es_stale(self):
        trace = self.crear_trace(dias=40)
        evaluacion = GymDecisionTraceEvaluation.objects.create(
            trace=trace,
            resultado=GymDecisionTraceEvaluation.NEUTRO,
            resumen="Evaluación aún vigente.",
            senales_posteriores={},
        )

        hallazgos = detectar_hallazgos(cliente_id=self.cliente.pk)

        self.assertFalse(any(
            h["code"] == "evaluacion_trace_stale" and h["pk"] == evaluacion.pk
            for h in hallazgos
        ))

    def test_dry_run_reporta_pero_no_muta_incoherencias(self):
        vencida = self.crear_intervencion(fin=self.hoy - timedelta(days=1))
        self.crear_intervencion()
        self.crear_intervencion()
        huerfana = self.crear_sugerencia(estado=SugerenciaPlan.ESTADO_ACEPTADA)
        pendiente = self.crear_sugerencia()
        ligada = self.crear_intervencion(sugerencia=pendiente)

        salida = StringIO()
        call_command("reconciliar_gobernanza_centro", stdout=salida)

        vencida.refresh_from_db()
        pendiente.refresh_from_db()
        ligada.refresh_from_db()
        texto = salida.getvalue().lower()
        self.assertEqual(vencida.estado, IntervencionPlan.ESTADO_ACTIVA)
        self.assertEqual(pendiente.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertEqual(ligada.estado, IntervencionPlan.ESTADO_ACTIVA)
        self.assertIn("dry-run", texto)
        self.assertIn("duplic", texto)
        self.assertIn(str(huerfana.pk), texto)

    def test_apply_solo_expira_vencidas_y_no_repara_otras_incoherencias(self):
        vencida = self.crear_intervencion(fin=self.hoy - timedelta(days=1))
        vigente_a = self.crear_intervencion()
        vigente_b = self.crear_intervencion()
        pendiente = self.crear_sugerencia()
        ligada = self.crear_intervencion(sugerencia=pendiente)

        call_command(
            "reconciliar_gobernanza_centro", "--apply", stdout=StringIO()
        )

        for obj in (vencida, vigente_a, vigente_b, pendiente, ligada):
            obj.refresh_from_db()
        self.assertEqual(vencida.estado, IntervencionPlan.ESTADO_EXPIRADA)
        self.assertEqual(vigente_a.estado, IntervencionPlan.ESTADO_ACTIVA)
        self.assertEqual(vigente_b.estado, IntervencionPlan.ESTADO_ACTIVA)
        self.assertEqual(pendiente.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertEqual(ligada.estado, IntervencionPlan.ESTADO_ACTIVA)

    def test_filtros_cliente_y_limit_acotan_expiraciones(self):
        otro_user = User.objects.create_user(username="gob3a_rec_otro", password="x")
        otro, _ = Cliente.objects.get_or_create(
            user=otro_user, defaults={"nombre": "Otro rec", "dias_disponibles": 3}
        )
        propias = [
            self.crear_intervencion(fin=self.hoy - timedelta(days=d))
            for d in (1, 2)
        ]
        ajena = self.crear_intervencion(
            cliente=otro, fin=self.hoy - timedelta(days=1)
        )

        call_command(
            "reconciliar_gobernanza_centro",
            "--apply",
            "--cliente-id",
            str(self.cliente.pk),
            "--limit",
            "1",
            stdout=StringIO(),
        )

        estados_propios = []
        for intervencion in propias:
            intervencion.refresh_from_db()
            estados_propios.append(intervencion.estado)
        ajena.refresh_from_db()
        self.assertEqual(estados_propios.count(IntervencionPlan.ESTADO_EXPIRADA), 1)
        self.assertEqual(ajena.estado, IntervencionPlan.ESTADO_ACTIVA)


class AceptarSugerenciaAtomicidadTests(Gobernanza3ABase):
    def test_error_al_actualizar_sugerencia_revierte_intervencion(self):
        sugerencia = self.crear_sugerencia()

        with patch.object(
            SugerenciaPlan,
            "save",
            autospec=True,
            side_effect=RuntimeError("fallo al persistir respuesta"),
        ):
            with self.assertRaises(RuntimeError):
                aceptar_sugerencia(sugerencia, fecha_ref=self.hoy)

        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(
            IntervencionPlan.objects.filter(sugerencia=sugerencia).exists()
        )
