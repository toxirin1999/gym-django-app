from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from joi.models import EventoEntrenadorJOI, MensajeJOI


class AperturaCanonica10ETests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("joi-fase10e")
        self.cliente = Cliente.objects.get(user=self.user)

    def evento(self, *, occurred_at=None, source_id=1):
        occurred_at = occurred_at or timezone.now()
        payload = {
            "schema_version": 1,
            "event_type": "gym_decision_application",
            "source_model": "entrenos.GymDecisionLog",
            "source_id": source_id,
            "occurred_at": occurred_at.isoformat(),
            "epistemic_level": "applied",
            "status": "aplicada",
            "facts": {"accion": "mantener", "ejercicio": "Press", "confianza": "alta"},
        }
        return EventoEntrenadorJOI.objects.create(
            user=self.user,
            event_type=payload["event_type"],
            source_model=payload["source_model"],
            source_id=source_id,
            status=payload["status"],
            payload=payload,
        )

    @patch("joi.services_eventos_entrenador.timezone.localdate")
    @patch("joi.services.generar_mensaje_joi")
    def test_sin_eventos_crea_una_apertura_normal_con_fecha_local(self, generar, localdate):
        from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador

        localdate.return_value = date(2026, 8, 27)
        generar.side_effect = lambda cliente, trigger, datos=None: MensajeJOI.objects.create(
            user=cliente.user, trigger=trigger, mensaje="Apertura normal.", contexto=datos or {},
        )

        mensaje = resolver_apertura_diaria_entrenador(self.cliente)

        self.assertEqual(mensaje.trigger, "apertura_manana")
        generar.assert_called_once_with(self.cliente, "apertura_manana")
        localdate.assert_called_once()

    @patch("joi.services.generar_mensaje_joi")
    def test_apertura_existente_es_inmutable_e_idempotente(self, generar):
        from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador

        apertura = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Original.", contexto={}, leido=True,
        )
        self.assertIsNone(resolver_apertura_diaria_entrenador(self.cliente))
        self.assertIsNone(resolver_apertura_diaria_entrenador(self.cliente))
        apertura.refresh_from_db()
        self.assertEqual(apertura.mensaje, "Original.")
        generar.assert_not_called()
        self.assertEqual(MensajeJOI.objects.filter(trigger="apertura_manana").count(), 1)

    @patch("joi.services.generar_mensaje_joi", return_value=None)
    def test_fallo_con_eventos_no_crea_apertura_limpia(self, _generar):
        from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador

        evento = self.evento()
        self.assertIsNone(resolver_apertura_diaria_entrenador(self.cliente))
        evento.refresh_from_db()
        self.assertEqual(evento.estado, "pendiente")
        self.assertFalse(MensajeJOI.objects.filter(trigger="apertura_manana").exists())

    @patch("joi.services.generar_mensaje_joi")
    def test_lote_reciente_se_integra_y_el_antiguo_permanece(self, generar):
        from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador

        reciente = self.evento(source_id=1)
        antiguo = self.evento(occurred_at=timezone.now() - timedelta(hours=49), source_id=2)
        generar.side_effect = lambda cliente, trigger, datos=None: MensajeJOI.objects.create(
            user=cliente.user, trigger=trigger, mensaje="Integrada.", contexto=datos["_evento_entrenador"],
        )
        mensaje = resolver_apertura_diaria_entrenador(self.cliente)
        reciente.refresh_from_db(); antiguo.refresh_from_db()
        self.assertEqual(mensaje.trigger, "apertura_manana")
        self.assertEqual(reciente.estado, "publicado")
        self.assertEqual(antiguo.estado, "pendiente")

    @patch("joi.services_eventos_entrenador.resolver_apertura_diaria_entrenador")
    def test_tarea_celery_usa_el_resolvedor_canonico(self, resolver):
        from joi.tasks import generar_apertura_manana

        resolver.return_value = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Programada.", contexto={},
        )
        resultado = generar_apertura_manana.run()
        resolver.assert_called_once_with(self.cliente)
        self.assertEqual(resultado["generados"], 1)

