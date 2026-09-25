from unittest.mock import patch
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from clientes import views
from hyrox.models import DailyRecoveryEntry, UserInjury
from entrenos.models import SesionProgramada


class PortadaEvidenciaRealTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("evidencia-real", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.url = reverse("clientes:mockup_demo")

    def test_consistencia_portada_usa_sesiones_programadas_persistidas(self):
        hoy = timezone.localdate()
        SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=hoy, estado=SesionProgramada.ESTADO_COMPLETADA,
        )

        self.assertEqual(views._consistencia_semanal_programada(self.cliente, hoy), 100)

    def test_consistencia_sin_sesiones_programadas_es_desconocida(self):
        self.assertIsNone(
            views._consistencia_semanal_programada(self.cliente, timezone.localdate())
        )

    @patch("core.bio_context.BioContextProvider.get_readiness_score", side_effect=RuntimeError("provider down"))
    def test_bio_readiness_fallido_queda_no_disponible(self, _provider):
        readiness, restricciones = views._ctx_bio(self.cliente)

        self.assertFalse(readiness["available"])
        self.assertIsNone(readiness["score"])
        self.assertIsNone(readiness["volume_modifier"])
        self.assertEqual(restricciones, {})

    @patch("core.bio_context.BioContextProvider.get_readiness_score", return_value={"score": 0.8})
    def test_bio_readiness_incompleto_queda_no_disponible(self, _provider):
        readiness, _ = views._ctx_bio(self.cliente)

        self.assertFalse(readiness["available"])
        self.assertIsNone(readiness["volume_modifier"])

    def test_sliders_usan_ultimo_registro_real_sin_escribir_en_get(self):
        lesion = UserInjury.objects.create(
            cliente=self.cliente, zona_afectada="Rodilla", fase="AGUDA", activa=True, gravedad=5
        )
        DailyRecoveryEntry.objects.create(
            lesion=lesion, dolor_reposo=2, dolor_movimiento=4,
            inflamacion_percibida=3, rango_movimiento=7,
        )
        before = DailyRecoveryEntry.objects.count()

        sliders, has_previous = views._lesion_sliders_desde_evidencia(lesion)

        self.assertTrue(has_previous)
        self.assertEqual([campo["val"] for campo in sliders], [2, 4, 3, 7])
        self.assertEqual(DailyRecoveryEntry.objects.count(), before)

    def test_sliders_sin_historial_declaran_ausencia_de_evidencia(self):
        lesion = UserInjury.objects.create(
            cliente=self.cliente, zona_afectada="Rodilla", fase="AGUDA", activa=True, gravedad=5
        )

        sliders, has_previous = views._lesion_sliders_desde_evidencia(lesion)

        self.assertFalse(has_previous)
        self.assertTrue(all(campo["is_neutral_default"] for campo in sliders))

    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_portada_sin_plan_no_inventa_descanso_recuperacion_ni_cta(self, decision):
        decision.return_value = {
            "tipo": None, "estado": None, "entrenamiento": None,
            "sesion_programada": None, "mensaje": "", "causa_principal": None,
            "modo_reducido": False, "distribucion_aviso": None,
        }

        response = self.client.get(self.url)

        self.assertContains(response, "Sin sesión programada")
        self.assertContains(response, "Sin datos suficientes")
        self.assertNotContains(response, "Día de descanso · Recuperación activa")
        self.assertNotContains(response, "Ver Estoico")

    @patch(
        "clientes.views.timezone.now",
        return_value=datetime(2026, 8, 28, 12, tzinfo=dt_timezone.utc),
    )
    def test_portada_representa_sesion_pospuesta_con_identidad_y_fecha_efectiva(self, _now):
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 8, 28),
            pospuesta_hasta=date(2026, 8, 29),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Día 5 - Fuerza — Avanzada",
            motivo_estado="El usuario indicó que hoy no podía entrenar.",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sesión guardada para mañana")
        self.assertContains(response, "Día 5 - Fuerza — Avanzada")
        self.assertContains(response, "sábado 29", html=False)
        self.assertNotContains(response, "Sin sesión programada")
        self.assertNotContains(response, "Sin datos suficientes")
        self.assertNotContains(response, "data-primary-action")

    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_ejercicio_sin_series_reps_no_recibe_prescripcion_generica(self, decision):
        decision.return_value = {
            "tipo": "programada", "estado": "entrenar",
            "entrenamiento": {"nombre": "Sesión evidencia", "rutina_nombre": "Sesión evidencia", "ejercicios": [{"nombre": "Sentadilla"}]},
            "sesion_programada": None, "mensaje": "", "causa_principal": "sesion_hoy",
            "modo_reducido": False, "distribucion_aviso": None,
        }

        response = self.client.get(self.url)

        self.assertContains(response, "Sin prescripción")
        self.assertNotContains(response, "4 × 4–6")

    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_portada_distingue_carga_aguda_y_volumen_historico(self, decision):
        decision.return_value = {
            "tipo": None, "estado": None, "entrenamiento": None,
            "sesion_programada": None, "mensaje": "", "causa_principal": None,
            "modo_reducido": False, "distribucion_aviso": None,
        }

        response = self.client.get(self.url)

        self.assertContains(response, "Carga aguda")
        self.assertContains(response, "UA")
        self.assertContains(response, "Volumen histórico")
        self.assertContains(response, "Cumpl. sem.")
        self.assertNotContains(response, "Carga semanal")
        self.assertNotContains(response, "Consist.")

    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_portada_pluraliza_sesion_sin_tilde_incorrecta(self, decision):
        decision.return_value = {
            "tipo": None, "estado": None, "entrenamiento": None,
            "sesion_programada": None, "mensaje": "", "causa_principal": None,
            "modo_reducido": False, "distribucion_aviso": None,
        }
        with patch("clientes.views._ctx_analisis_semanal", return_value={
            "hay_datos": True,
            "sesiones_completadas": 3,
        }):
            response = self.client.get(self.url)

        self.assertContains(response, "sesiones")
        self.assertNotContains(response, "sesiónes")

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    @patch("clientes.views._ctx_bio")
    def test_badge_descarga_explica_que_no_hay_reduccion_adicional(self, ctx_bio, decision):
        ctx_bio.return_value = ({
            "available": True,
            "score": 1.0,
            "volume_modifier": 1.0,
            "needs_deload": False,
            "sources": {},
        }, {})
        decision.return_value = {
            "decision_id": "gym-descarga-test",
            "postura": "empujar",
            "tipo": "programada", "estado": "entrenar",
            "entrenamiento": {
                "nombre": "Descarga activa", "rutina_nombre": "Descarga activa",
                "ejercicios": [{"nombre": "Curl", "series": 2, "repeticiones": 10}],
                "es_deload": True,
            },
            "sesion_programada": None, "mensaje": "", "causa_principal": "sesion_hoy",
            "modo_reducido": False, "distribucion_aviso": None,
        }

        response = self.client.get(self.url)

        self.assertContains(response, "100% del plan de descarga")
        self.assertContains(response, "sin reducción adicional")
        self.assertNotContains(response, "100% · Óptimo")
