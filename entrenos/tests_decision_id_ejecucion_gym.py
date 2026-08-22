"""Fase 6.2: identidad de la decisión desde el CTA hasta la ejecución."""

import json
from datetime import date
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from core.organismo import resolver_estado_sistema_hoy
from entrenos.models import GymDecisionVersion


class DecisionIdEjecucionGymTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("fase62", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro_user = User.objects.create_user("fase62_otro", password="x")
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.client.login(username="fase62", password="x")
        self.fecha = date(2026, 8, 22)
        self.ejercicios = [{
            "nombre": "Press banca",
            "series": 3,
            "repeticiones": 6,
            "peso_kg": 70,
            "tipo_ejercicio": "compuesto_principal",
            "_autoridad_gym_materializada": True,
            "_autoridad_gym_decision_id": "gym-vigente",
        }]

    def tearDown(self):
        cache.clear()

    def _autoridad(self, decision_id="gym-vigente"):
        return {
            "decision_id": decision_id,
            "estado": "entrenar",
            "postura": "avanzar",
            "entrenamiento": {"ejercicios": self.ejercicios},
        }

    def test_cta_del_organismo_incluye_decision_id_vigente(self):
        estado = resolver_estado_sistema_hoy(
            self.user,
            decision_gym=self._autoridad(),
        )
        query = parse_qs(urlparse(estado["accion_url"]).query)
        self.assertEqual(query["decision_id"], ["gym-vigente"])

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_briefing_transporta_decision_id_hasta_sesion_activa(self, resolver):
        resolver.return_value = self._autoridad()
        url = reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-vigente",
            "ejercicios": json.dumps(self.ejercicios),
        })
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.context["url_sesion"]).query)
        self.assertEqual(query["decision_id"], ["gym-vigente"])

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_briefing_rechaza_decision_obsoleta_antes_de_aceptar_payload(self, resolver):
        resolver.return_value = self._autoridad("gym-corregida")
        url = reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-antigua",
            "ejercicios": json.dumps(self.ejercicios),
        })
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("Press banca", response.content.decode())

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_sesion_activa_rechaza_correccion_entre_pasos_antes_de_leer_token(self, resolver):
        resolver.return_value = self._autoridad("gym-corregida")
        token = "payload-antiguo"
        cache.set(f"transporte_ejercicios_mod_{token}", self.ejercicios, 900)
        url = reverse("entrenos:entrenamiento_activo", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-antigua",
            "ejercicios_token": token,
        })
        self.assertEqual(response.status_code, 409)
        resolver.assert_called_once_with(self.cliente, self.fecha)

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_sesion_activa_acepta_id_vigente(self, resolver):
        resolver.return_value = self._autoridad()
        GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=self.fecha,
            version=1,
            decision_id="gym-vigente",
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True,
            fingerprint="fingerprint-vigente",
            base_fingerprint="base-vigente",
            postura="avanzar",
            snapshot=resolver.return_value,
        )
        token = "payload-vigente"
        cache.set(f"transporte_ejercicios_mod_{token}", self.ejercicios, 900)
        url = reverse("entrenos:entrenamiento_activo", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-vigente",
            "ejercicios_token": token,
        })
        self.assertEqual(response.status_code, 200)

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_briefing_protegido_es_revision_sin_cta_de_inicio(self, resolver):
        protegida = self._autoridad()
        protegida.update({"estado": "recuperar", "postura": "proteger"})
        resolver.return_value = protegida
        url = reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-vigente",
            "ejercicios": json.dumps(self.ejercicios),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["puede_iniciar_sesion"])
        self.assertNotContains(response, "Comenzar sesión")
        self.assertContains(response, "La sesión está protegida")

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_sesion_activa_rechaza_decision_vigente_pero_protegida(self, resolver):
        protegida = self._autoridad()
        protegida.update({"estado": "recuperar", "postura": "proteger"})
        resolver.return_value = protegida
        url = reverse("entrenos:entrenamiento_activo", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "decision_id": "gym-vigente",
            "ejercicios": json.dumps(self.ejercicios),
        })
        self.assertEqual(response.status_code, 409)

    def test_acceso_legacy_sin_decision_id_conserva_fallback(self):
        url = reverse("entrenos:briefing_entrenamiento", args=[self.cliente.id])
        response = self.client.get(url, {
            "fecha": self.fecha.isoformat(),
            "ejercicios": "[]",
        })
        self.assertEqual(response.status_code, 200)

    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_briefing_y_sesion_activa_exigen_propiedad_antes_de_validar_id(self, resolver):
        briefing = reverse("entrenos:briefing_entrenamiento", args=[self.otro.id])
        activa = reverse("entrenos:entrenamiento_activo", args=[self.otro.id])
        params = {"fecha": self.fecha.isoformat(), "decision_id": "decision-ajena"}
        self.assertEqual(self.client.get(briefing, params).status_code, 404)
        self.assertEqual(self.client.get(activa, params).status_code, 404)
        resolver.assert_not_called()
