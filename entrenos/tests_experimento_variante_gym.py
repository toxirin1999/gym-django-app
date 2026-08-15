from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, ExperimentoVarianteGym, GymDecisionLog,
)
from rutinas.models import Rutina


class ExperimentoVarianteGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("experimento_variante")
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre="Push")
        self.hoy = timezone.localdate()
        self.decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio="Press Banca", accion="cambiar_variante",
            motivo="Sin progresión en 3 sesiones consecutivas.", peso_anterior=80,
            reps_anteriores=8,
        )
        self.original = {"nombre": "Press Banca con Barra", "peso_kg": 80, "repeticiones": 8}
        self.variante = {"nombre": "Press Inclinado con Mancuernas", "peso_kg": 30, "repeticiones": 8}

    def test_creacion_desde_estancamiento_es_idempotente_y_fija_variante(self):
        from entrenos.services.experimento_variante_gym_service import asegurar_experimento_variante

        primero = asegurar_experimento_variante(self.decision, self.original, self.variante)
        segundo = asegurar_experimento_variante(
            self.decision, self.original, {"nombre": "Cruce de Poleas"},
        )

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(ExperimentoVarianteGym.objects.count(), 1)
        self.assertEqual(segundo.variante["nombre"], "Press Inclinado con Mancuernas")
        self.assertEqual(segundo.baseline["version"], 1)
        self.assertEqual(segundo.estado, ExperimentoVarianteGym.ESTADO_ACTIVA)
        self.assertEqual(segundo.vence_en.date(), (timezone.now() + timedelta(days=21)).date())

    @patch("entrenos.services.plan_dinamico_service._elegir_alternativa")
    @patch("entrenos.services.plan_dinamico_service._ejercicios_recientes", return_value=set())
    @patch("entrenos.services.briefing_service.necesita_deload_gym", return_value=False)
    def test_plan_reutiliza_variante_persistida_y_no_la_reelige(self, _deload, _recientes, elegir):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico

        elegir.return_value = ("Press Inclinado con Mancuernas", "estímulo fijo")
        entrada = [dict(self.original, grupo_muscular="pecho")]
        primera, _ = aplicar_plan_dinamico(self.cliente, entrada, self.hoy)
        elegir.return_value = ("Cruce de Poleas", "otra")
        segunda, _ = aplicar_plan_dinamico(self.cliente, entrada, self.hoy + timedelta(days=1))

        self.assertEqual(primera[0]["nombre"], "Press Inclinado con Mancuernas")
        self.assertEqual(segunda[0]["nombre"], "Press Inclinado con Mancuernas")
        self.assertEqual(elegir.call_count, 1)
        self.assertEqual(primera[0]["experimento_variante_id"], segunda[0]["experimento_variante_id"])

    def _experimento(self):
        from entrenos.services.experimento_variante_gym_service import asegurar_experimento_variante
        return asegurar_experimento_variante(self.decision, self.original, self.variante)

    def _ejecucion(self, *, fecha, peso=30, reps=8, rpe=8, molestia=False, fallo=False):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, fecha_ejecucion=fecha,
        )
        return EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=self.variante["nombre"], peso_kg=peso,
            repeticiones=reps, series=3, rpe=rpe, completado=True,
            molestia_reportada=molestia, fallo_muscular=fallo,
        )

    def test_dos_ejecuciones_seguras_no_peores_cierran_favorable_y_quedan_enlazadas(self):
        experimento = self._experimento()
        primera = self._ejecucion(fecha=self.hoy, peso=30, reps=8)
        segunda = self._ejecucion(fecha=self.hoy + timedelta(days=7), peso=31, reps=8, rpe=8.5)

        experimento.refresh_from_db(); primera.refresh_from_db(); segunda.refresh_from_db()
        self.assertEqual(experimento.estado, ExperimentoVarianteGym.ESTADO_FAVORABLE)
        self.assertEqual(primera.experimento_variante_id, experimento.pk)
        self.assertEqual(segunda.experimento_variante_id, experimento.pk)
        self.assertIsNotNone(experimento.finalizada_en)
        tercera = self._ejecucion(fecha=self.hoy + timedelta(days=14), peso=32, reps=8)
        tercera.refresh_from_db()
        self.assertIsNone(tercera.experimento_variante_id)

    def test_decision_ajena_a_estancamiento_no_crea_experimento(self):
        from entrenos.services.experimento_variante_gym_service import asegurar_experimento_variante
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio="Press Banca", accion="cambiar_variante",
            motivo="Molestia recurrente en hombro.",
        )
        self.assertIsNone(asegurar_experimento_variante(decision, self.original, self.variante))
        self.assertEqual(ExperimentoVarianteGym.objects.count(), 0)

    def test_nueva_decision_puede_crear_tras_cierre_sin_reactivar_la_anterior(self):
        from entrenos.services.experimento_variante_gym_service import asegurar_experimento_variante
        anterior = self._experimento()
        ExperimentoVarianteGym.objects.filter(pk=anterior.pk).update(
            estado=ExperimentoVarianteGym.ESTADO_INSUFICIENTE,
            finalizada_en=timezone.now(),
        )
        self.assertEqual(
            asegurar_experimento_variante(self.decision, self.original, self.variante).pk,
            anterior.pk,
        )
        nueva_decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio="Press Banca", accion="cambiar_variante",
            motivo="Sin progresión en 3 sesiones nuevas.",
        )
        nuevo = asegurar_experimento_variante(
            nueva_decision, self.original, {"nombre": "Cruce de Poleas"},
        )
        self.assertNotEqual(nuevo.pk, anterior.pk)
        self.assertEqual(nuevo.estado, ExperimentoVarianteGym.ESTADO_ACTIVA)

    def test_dos_decisiones_reutilizan_unico_activo_por_cliente_y_original(self):
        from entrenos.services.experimento_variante_gym_service import asegurar_experimento_variante
        primero = self._experimento()
        otra = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio="Press Banca", accion="cambiar_variante",
            motivo="Sin progresión confirmada de nuevo.",
        )
        segundo = asegurar_experimento_variante(
            otra, self.original, {"nombre": "Cruce de Poleas"},
        )
        self.assertEqual(segundo.pk, primero.pk)
        self.assertEqual(segundo.variante["nombre"], self.variante["nombre"])
        self.assertEqual(ExperimentoVarianteGym.objects.filter(estado="activa").count(), 1)

    def test_no_enlaza_ejecucion_anterior_al_inicio(self):
        experimento = self._experimento()
        ExperimentoVarianteGym.objects.filter(pk=experimento.pk).update(
            iniciada_en=timezone.now(),
        )
        ejecucion = self._ejecucion(fecha=self.hoy - timedelta(days=1))
        ejecucion.refresh_from_db()
        self.assertIsNone(ejecucion.experimento_variante_id)

    @patch("entrenos.services.plan_dinamico_service._persistir_estado_aplicacion")
    @patch("entrenos.services.plan_dinamico_service._elegir_alternativa")
    @patch("entrenos.services.plan_dinamico_service._ejercicios_recientes", return_value=set())
    @patch("entrenos.services.briefing_service.necesita_deload_gym", return_value=False)
    def test_aplicar_variante_marca_decision_aplicada(
        self, _deload, _recientes, elegir, persistir,
    ):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        elegir.return_value = (self.variante["nombre"], "fija")
        aplicar_plan_dinamico(
            self.cliente, [dict(self.original, grupo_muscular="pecho")], self.hoy,
        )
        persistir.assert_called_once_with(self.decision, 'aplicada', None)

    @patch("entrenos.services.plan_dinamico_service._persistir_estado_aplicacion")
    @patch("entrenos.services.plan_dinamico_service._ejercicios_recientes", return_value=set())
    @patch("entrenos.services.briefing_service.necesita_deload_gym", return_value=False)
    def test_aplicar_experimento_tolera_decision_origen_eliminada(
        self, _deload, _recientes, persistir,
    ):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        experimento = self._experimento()
        self.decision.delete()
        experimento.refresh_from_db()
        self.assertIsNone(experimento.decision_origen_id)

        salida, _ = aplicar_plan_dinamico(
            self.cliente, [dict(self.original, grupo_muscular="pecho")], self.hoy,
        )

        self.assertEqual(salida[0]["nombre"], self.variante["nombre"])
        persistir.assert_not_called()

    def test_evaluacion_general_ignora_decision_gestionada_por_experimento(self):
        from entrenos.models import GymAdaptationProfile
        from entrenos.services.decision_log_service import evaluar_decisiones_para_entreno
        self._experimento()
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio="Press Banca", peso_kg=80,
            repeticiones=8, rpe=8, completado=True,
        )
        evaluar_decisiones_para_entreno(entreno)
        self.decision.refresh_from_db()
        self.assertIsNone(self.decision.resultado)
        self.assertFalse(GymAdaptationProfile.objects.filter(
            cliente=self.cliente, ejercicio="press banca",
        ).exists())

    def test_evaluacion_general_ignora_cambiar_variante_sin_experimento(self):
        from entrenos.models import GymAdaptationProfile
        from entrenos.services.decision_log_service import evaluar_decisiones_para_entreno
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio="Press Banca", peso_kg=80,
            repeticiones=8, rpe=8, completado=True,
        )

        evaluar_decisiones_para_entreno(entreno)

        self.decision.refresh_from_db()
        self.assertIsNone(self.decision.resultado)
        self.assertFalse(GymAdaptationProfile.objects.filter(
            cliente=self.cliente, ejercicio="press banca",
        ).exists())

    def test_detector_estancamiento_ancla_decision_al_entreno_y_nombre_normalizado(self):
        entrenos = []
        for offset in range(3):
            entreno = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina,
                fecha=self.hoy - timedelta(days=2 - offset),
            )
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio="  Press   Banca ", peso_kg=80,
                repeticiones=8, rpe=8, completado=True,
            )
            entreno.save()
            entrenos.append(entreno)

        decision = GymDecisionLog.objects.filter(
            accion="cambiar_variante", motivo__icontains="Sin progresión",
            entreno_origen__isnull=False,
        ).get()
        self.assertEqual(decision.entreno_origen, entrenos[-1])
        self.assertEqual(decision.ejercicio_normalizado, "press banca")

    def test_molestia_cierra_fallida_y_plan_vuelve_al_original(self):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        experimento = self._experimento()
        self._ejecucion(fecha=self.hoy, molestia=True)
        experimento.refresh_from_db()
        self.assertEqual(experimento.estado, ExperimentoVarianteGym.ESTADO_FALLIDA)

        salida, _ = aplicar_plan_dinamico(
            self.cliente, [dict(self.original, grupo_muscular="pecho")], self.hoy + timedelta(days=1),
        )
        self.assertEqual(salida[0]["nombre"], self.original["nombre"])

    def test_vencimiento_con_una_ejecucion_es_insuficiente(self):
        from entrenos.services.experimento_variante_gym_service import evaluar_experimento
        experimento = self._experimento()
        self._ejecucion(fecha=self.hoy)
        ExperimentoVarianteGym.objects.filter(pk=experimento.pk).update(
            vence_en=timezone.now() - timedelta(seconds=1),
        )
        experimento.refresh_from_db()

        evaluar_experimento(experimento)

        experimento.refresh_from_db()
        self.assertEqual(experimento.estado, ExperimentoVarianteGym.ESTADO_INSUFICIENTE)
