from copy import deepcopy
from datetime import date
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.autoridad_diaria_gym_service import (
    AutoridadGymCorreccionInvalida,
    corregir_autoridad_diaria_gym,
    resolver_autoridad_diaria_gym,
    revertir_correccion_autoridad_diaria_gym,
)


class SupervisionInmutableGymTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="supervision-inmutable")
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.cliente.nombre = "Supervision"
        self.cliente.save(update_fields=["nombre"])
        self.fecha = date(2026, 8, 21)
        self.physical = {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.fecha.isoformat(),
            "status": "available",
            "fingerprint": "fisico-inmutable",
            "signals": {"energy": {"value": 7, "source": "checkin"}},
        }
        self.base = {
            "tipo": "programada_hoy",
            "estado": "entrenar",
            "causa_principal": "sesion_hoy",
            "mensaje": "Propuesta original del motor.",
            "contexto_fisico": {"energia_baja": False},
            "entrenamiento": {
                "rutina_nombre": "Full body",
                "ejercicios": [{"nombre": "Sentadilla", "series": 3, "repeticiones": 5}],
            },
        }
        self.cambios = [{"tipo": "progresion", "ejercicio": "Sentadilla"}]

    def tearDown(self):
        cache.clear()

    def _resolver_motor(self, obtener_base, aplicar_plan):
        obtener_base.return_value = deepcopy(self.base)
        aplicar_plan.return_value = (
            deepcopy(self.base["entrenamiento"]["ejercicios"]),
            deepcopy(self.cambios),
        )
        return resolver_autoridad_diaria_gym(
            self.cliente, self.fecha, physical_snapshot=self.physical
        )

    def _ids_ejercicios(self, autoridad):
        return {
            ejercicio.get("_autoridad_gym_decision_id")
            for ejercicio in autoridad["entrenamiento"]["ejercicios"]
        }

    def _sin_identidad(self, valor):
        if isinstance(valor, dict):
            return {
                clave: self._sin_identidad(contenido)
                for clave, contenido in valor.items()
                if clave not in {
                    "decision_id", "origen_decision", "version_persistida",
                    "motivo_correccion", "_autoridad_gym_decision_id",
                    "_autoridad_gym_materializada",
                }
            }
        if isinstance(valor, list):
            return [self._sin_identidad(item) for item in valor]
        return valor

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_correcciones_sucesivas_parten_siempre_del_snapshot_motor_compatible(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        primera = corregir_autoridad_diaria_gym(
            self.cliente,
            self.fecha,
            decision_id_esperada=motor["decision_id"],
            ajustes={"postura": "sostener", "mensaje": "Texto manual transitorio."},
            motivo="Conservar margen.",
        )
        segunda = corregir_autoridad_diaria_gym(
            self.cliente,
            self.fecha,
            decision_id_esperada=primera["decision_id"],
            ajustes={"postura": "proteger"},
            motivo="Proteger hoy.",
        )
        snapshot_motor = GymDecisionVersion.objects.get(origen="motor").snapshot

        self.assertEqual(segunda["mensaje"], snapshot_motor["mensaje"])
        self.assertEqual(segunda["estado"], "recuperar")
        self.assertEqual(segunda["postura"], "proteger")
        self.assertFalse(segunda.get("modo_reducido", False))
        self.assertEqual(self._ids_ejercicios(primera), {primera["decision_id"]})
        self.assertEqual(self._ids_ejercicios(segunda), {segunda["decision_id"]})
        for campo in (
            "physical_snapshot",
            "physical_snapshot_fingerprint",
            "entrenamiento",
            "cambios_materializados",
            "fingerprint",
            "contexto_fisico",
        ):
            if campo == "entrenamiento":
                self.assertEqual(
                    self._sin_identidad(segunda[campo]),
                    self._sin_identidad(snapshot_motor[campo]),
                    campo,
                )
            else:
                self.assertEqual(segunda[campo], snapshot_motor[campo], campo)

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_sostener_y_proteger_tienen_semantica_ejecutiva_conservadora(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        sostenida = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=motor["decision_id"],
            ajustes={"postura": "sostener"}, motivo="Reducir.",
        )
        protegida = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=sostenida["decision_id"],
            ajustes={"postura": "proteger"}, motivo="No ejecutar.",
        )

        self.assertEqual(sostenida["estado"], "version_reducida")
        self.assertTrue(sostenida["modo_reducido"])
        self.assertEqual(protegida["estado"], "recuperar")
        self.assertEqual(protegida["postura"], "proteger")
        snapshot_motor = GymDecisionVersion.objects.get(origen="motor").snapshot
        self.assertEqual(
            self._sin_identidad(protegida["entrenamiento"]),
            self._sin_identidad(snapshot_motor["entrenamiento"]),
        )
        self.assertEqual(
            protegida["cambios_materializados"], snapshot_motor["cambios_materializados"]
        )

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_reversion_copia_integro_el_snapshot_motor_y_crea_historial_nuevo(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        manual = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=motor["decision_id"],
            ajustes={"postura": "sostener", "mensaje": "Manual."}, motivo="Reducir.",
        )
        fila_manual = GymDecisionVersion.objects.get(decision_id=manual["decision_id"])
        snapshot_contaminado = deepcopy(fila_manual.snapshot)
        snapshot_contaminado["entrenamiento"]["ejercicios"][0]["series"] = 99
        snapshot_contaminado["cambios_materializados"] = [{"tipo": "manual_indebido"}]
        fila_manual.snapshot = snapshot_contaminado
        fila_manual.save(update_fields=["snapshot"])
        cache.clear()

        revertida = revertir_correccion_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=manual["decision_id"], motivo="Volver al motor.",
        )

        self.assertEqual(self._ids_ejercicios(revertida), {revertida["decision_id"]})

        snapshot_motor = GymDecisionVersion.objects.get(origen="motor").snapshot
        self.assertEqual(
            self._sin_identidad(revertida),
            self._sin_identidad(snapshot_motor),
        )
        versiones = list(GymDecisionVersion.objects.filter(cliente=self.cliente, fecha=self.fecha))
        self.assertEqual([v.origen for v in versiones], ["motor", "correccion_manual", "reversion_manual"])
        self.assertEqual(
            self._sin_identidad(versiones[-1].snapshot["entrenamiento"]),
            self._sin_identidad(snapshot_motor["entrenamiento"]),
        )
        self.assertEqual(versiones[-1].reemplaza, versiones[-2])

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_cambio_de_base_antes_de_corregir_invalida_decision_id_obsoleta(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        nueva_base = deepcopy(self.base)
        nueva_base["mensaje"] = "El plan cambió antes de supervisarlo."
        nueva_base["entrenamiento"]["rutina_nombre"] = "Plan actualizado"
        obtener_base.return_value = nueva_base
        aplicar_plan.return_value = (
            deepcopy(nueva_base["entrenamiento"]["ejercicios"]),
            deepcopy(self.cambios),
        )
        cache.clear()

        with self.assertRaises(AutoridadGymCorreccionInvalida):
            corregir_autoridad_diaria_gym(
                self.cliente, self.fecha,
                decision_id_esperada=motor["decision_id"],
                ajustes={"postura": "sostener"},
                motivo="Esta orden ya es antigua.",
            )

        self.assertFalse(
            GymDecisionVersion.objects.filter(
                cliente=self.cliente,
                fecha=self.fecha,
                origen=GymDecisionVersion.ORIGEN_CORRECCION,
            ).exists()
        )
        vigente = GymDecisionVersion.objects.get(
            cliente=self.cliente, fecha=self.fecha, vigente=True
        )
        self.assertEqual(vigente.origen, GymDecisionVersion.ORIGEN_MOTOR)
        self.assertNotEqual(vigente.decision_id, motor["decision_id"])

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_correccion_vigente_pasa_del_cta_al_briefing_con_su_identidad(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        manual = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=motor["decision_id"],
            ajustes={"postura": "sostener"}, motivo="Reducir.",
        )
        response = self.client.get(
            reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id]),
            {
                "fecha": self.fecha.isoformat(),
                "decision_id": manual["decision_id"],
                "ejercicios": json.dumps(manual["entrenamiento"]["ejercicios"]),
            },
        )
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.context["url_sesion"]).query)
        self.assertEqual(query["decision_id"], [manual["decision_id"]])

    @patch("entrenos.services.plan_dinamico_service.aplicar_plan_dinamico")
    @patch("entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy")
    def test_reversion_vigente_pasa_del_cta_al_briefing_con_su_identidad(
        self, obtener_base, aplicar_plan
    ):
        motor = self._resolver_motor(obtener_base, aplicar_plan)
        manual = corregir_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=motor["decision_id"],
            ajustes={"postura": "sostener"}, motivo="Reducir.",
        )
        revertida = revertir_correccion_autoridad_diaria_gym(
            self.cliente, self.fecha,
            decision_id_esperada=manual["decision_id"], motivo="Restaurar.",
        )
        response = self.client.get(
            reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id]),
            {
                "fecha": self.fecha.isoformat(),
                "decision_id": revertida["decision_id"],
                "ejercicios": json.dumps(revertida["entrenamiento"]["ejercicios"]),
            },
        )
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.context["url_sesion"]).query)
        self.assertEqual(query["decision_id"], [revertida["decision_id"]])
