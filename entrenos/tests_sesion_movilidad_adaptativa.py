import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos import models as entrenos_models
from entrenos.models import ActividadRealizada, GymDecisionLog, SesionProgramada
from estiramientos.models import (
    EstiramientoEjercicio,
    EstiramientoPaso,
    EstiramientoPlan,
)


class SesionMovilidadAdaptativaContractTests(TestCase):
    """Contrato de dominio del MVP: movilidad factual y resolución explícita del Gym."""

    HOY = date(2026, 9, 23)

    def setUp(self):
        self.user = User.objects.create_user("movilidad-mvp", password="x")
        self.otro_user = User.objects.create_user("movilidad-mvp-otro", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.plan = EstiramientoPlan.objects.create(
            nombre="Movilidad completa", fase="COMPLETO", transicion_segundos=5,
        )
        ejercicio = EstiramientoEjercicio.objects.create(
            nombre="Rotación torácica", fase_recomendada="COMPLETO",
        )
        EstiramientoPaso.objects.create(
            plan=self.plan, ejercicio=ejercicio, orden=1, duracion_segundos=60,
        )
        self.sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Día 3 — Fuerza",
        )

    def _completar(self, **overrides):
        from entrenos.services.sesion_movilidad_adaptativa_service import (
            completar_sesion_movilidad,
        )

        params = {
            "cliente": self.cliente,
            "plan": self.plan,
            "fecha": self.HOY,
            "duracion_minutos": 20,
            "rpe": 3,
            "resolucion": "anadir",
            "sesion_programada": self.sesion,
            "idempotency_key": "movilidad-2026-09-23-1",
        }
        params.update(overrides)
        return completar_sesion_movilidad(**params)

    def test_modelo_audita_la_movilidad_y_enlaza_una_actividad_hub(self):
        registro = self._completar()

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertIsInstance(registro, modelo)
        self.assertEqual(registro.cliente, self.cliente)
        self.assertEqual(registro.plan, self.plan)
        self.assertEqual(registro.sesion_programada, self.sesion)
        self.assertEqual(registro.resolucion, "anadir")
        self.assertEqual(registro.duracion_minutos, 20)
        self.assertEqual(registro.rpe, 3)
        self.assertEqual(registro.actividad.tipo, "estiramientos")
        self.assertEqual(registro.actividad.cliente, self.cliente)
        self.assertEqual(registro.actividad.fecha_realizado, self.HOY)
        self.assertEqual(registro.actividad.carga_ua, 60.0)
        self.assertEqual(ActividadRealizada.objects.count(), 1)

    def test_anadir_movilidad_no_resuelve_ni_mueve_el_entreno(self):
        self._completar(resolucion="anadir")

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(self.sesion.fecha_prevista, self.HOY)
        self.assertIsNone(self.sesion.pospuesta_hasta)
        self.assertIsNone(self.sesion.entreno_realizado_id)

    def test_posponer_conserva_identidad_y_mueve_a_fecha_compatible(self):
        destino = self.HOY + timedelta(days=1)

        registro = self._completar(resolucion="posponer", fecha_destino=destino)

        self.sesion.refresh_from_db()
        self.assertEqual(registro.resolucion, "posponer")
        self.assertEqual(self.sesion.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(self.sesion.fecha_prevista, self.HOY)
        self.assertEqual(self.sesion.pospuesta_hasta, destino)
        self.assertIn("movilidad", self.sesion.motivo_estado.lower())

    def test_sustituir_cierra_sin_deuda_traslado_ni_progresion_inventada(self):
        self.assertTrue(hasattr(SesionProgramada, "ESTADO_SUSTITUIDA_RECUPERACION"))
        decisiones_antes = GymDecisionLog.objects.count()

        registro = self._completar(resolucion="sustituir")

        self.sesion.refresh_from_db()
        self.assertEqual(
            self.sesion.estado,
            SesionProgramada.ESTADO_SUSTITUIDA_RECUPERACION,
        )
        self.assertEqual(registro.resolucion, "sustituir")
        self.assertIsNone(self.sesion.pospuesta_hasta)
        self.assertIsNone(self.sesion.entreno_realizado_id)
        self.assertEqual(GymDecisionLog.objects.count(), decisiones_antes)
        self.assertIn("sin deuda", self.sesion.motivo_estado.lower())

    def test_reintento_con_misma_clave_es_idempotente(self):
        primero = self._completar()
        segundo = self._completar()

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(modelo.objects.count(), 1)
        self.assertEqual(ActividadRealizada.objects.count(), 1)

    def test_misma_clave_con_otro_comando_se_rechaza(self):
        self._completar(resolucion="anadir")

        with self.assertRaisesMessage(ValueError, "idempotencia"):
            self._completar(resolucion="sustituir")

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(ActividadRealizada.objects.count(), 1)

    def test_rechaza_sesion_ajena_sin_escrituras(self):
        ajena = SesionProgramada.objects.create(
            cliente=self.otro,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )

        with self.assertRaisesMessage(ValueError, "pertenece"):
            self._completar(sesion_programada=ajena)

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertFalse(modelo.objects.exists())
        self.assertFalse(ActividadRealizada.objects.exists())
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_colision_al_posponer_hace_rollback_completo(self):
        destino = self.HOY + timedelta(days=1)
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=destino,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Día 4 — Fuerza",
        )

        with self.assertRaisesMessage(ValueError, "ocupada"):
            self._completar(resolucion="posponer", fecha_destino=destino)

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertFalse(modelo.objects.exists())
        self.assertFalse(ActividadRealizada.objects.exists())
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(self.sesion.pospuesta_hasta)

    def test_estado_no_pendiente_hace_rollback_completo(self):
        self.sesion.estado = SesionProgramada.ESTADO_COMPLETADA
        self.sesion.save(update_fields=["estado"])

        with self.assertRaisesMessage(ValueError, "pendiente"):
            self._completar(resolucion="sustituir")

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertFalse(modelo.objects.exists())
        self.assertFalse(ActividadRealizada.objects.exists())

    def test_duracion_y_rpe_son_obligatorios_y_validos(self):
        casos = (
            ({"duracion_minutos": None}, "duración"),
            ({"duracion_minutos": 0}, "duración"),
            ({"rpe": None}, "RPE"),
            ({"rpe": 0}, "RPE"),
            ({"rpe": 11}, "RPE"),
        )
        for valores, mensaje in casos:
            with self.subTest(valores=valores):
                with self.assertRaisesMessage(ValueError, mensaje):
                    self._completar(
                        idempotency_key=f"invalida-{valores}", **valores,
                    )

        modelo = getattr(entrenos_models, "SesionMovilidadAdaptativa")
        self.assertFalse(modelo.objects.exists())
        self.assertFalse(ActividadRealizada.objects.exists())


class CompletarMovilidadHttpContractTests(TestCase):
    HOY = date(2026, 9, 23)

    def setUp(self):
        self.user = User.objects.create_user("movilidad-http", password="x")
        self.otro_user = User.objects.create_user("movilidad-http-otro", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.client.force_login(self.user)
        self.plan = EstiramientoPlan.objects.create(
            nombre="Movilidad superior", fase="SUPERIOR",
        )
        ejercicio = EstiramientoEjercicio.objects.create(nombre="CARs hombro")
        EstiramientoPaso.objects.create(
            plan=self.plan, ejercicio=ejercicio, orden=1, duracion_segundos=60,
        )
        self.sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Torso",
        )

    def _post(self, **overrides):
        payload = {
            "sesion_programada_id": self.sesion.pk,
            "resolucion": "anadir",
            "duracion_minutos": 12,
            "rpe": 2,
            "fecha": self.HOY.isoformat(),
            "idempotency_key": "http-movilidad-1",
        }
        payload.update(overrides)
        return self.client.post(
            reverse("estiramientos:completar_plan", args=[self.plan.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_post_completa_y_devuelve_identidad_persistida(self):
        response = self._post()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["sesion_movilidad_id"])
        self.assertTrue(body["actividad_id"])
        registro = getattr(entrenos_models, "SesionMovilidadAdaptativa").objects.get(
            pk=body["sesion_movilidad_id"],
        )
        self.assertEqual(registro.actividad_id, body["actividad_id"])

    def test_post_no_puede_resolver_sesion_de_otro_cliente(self):
        ajena = SesionProgramada.objects.create(
            cliente=self.otro,
            fecha_prevista=self.HOY,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )

        response = self._post(sesion_programada_id=ajena.pk)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ActividadRealizada.objects.exists())

    def test_player_transporta_contexto_y_tiene_una_sola_accion_final_primaria(self):
        response = self.client.get(
            reverse("estiramientos:iniciar_plan", args=[self.plan.pk]),
            {"sesion_programada_id": self.sesion.pk, "resolucion": "posponer"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-sesion-programada-id="{self.sesion.pk}"')
        self.assertContains(response, 'data-resolucion="posponer"')
        self.assertContains(response, 'data-completion-url=')
        self.assertContains(response, "Duración real")
        self.assertContains(response, "RPE real")
        self.assertEqual(response.content.count(b"data-primary-action"), 1)

    def test_panel_ofrece_tres_resoluciones_sin_duplicar_cta_principal(self):
        response = self.client.get(
            reverse("estiramientos:panel"),
            {"sesion_programada_id": self.sesion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="anadir"')
        self.assertContains(response, 'value="posponer"')
        self.assertContains(response, 'value="sustituir"')
        self.assertContains(response, "¿Qué hacemos con tu entrenamiento programado?")
        self.assertEqual(response.content.count(b"data-primary-action"), 1)
