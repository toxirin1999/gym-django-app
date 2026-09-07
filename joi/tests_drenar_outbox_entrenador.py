import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clientes.models import Cliente
from joi.models import EventoEntrenadorJOI, MensajeJOI


class DrenarOutboxEntrenadorCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("drenaje-joi")
        self.cliente = Cliente.objects.get(user=self.user)
        self.evento = EventoEntrenadorJOI.objects.create(
            user=self.user,
            event_type="gym_decision_application",
            source_model="entrenos.GymDecisionLog",
            source_id=901,
            status="aplicada",
            payload={"schema_version": 1, "facts": {"accion": "mantener"}},
        )

    def test_dry_run_por_defecto_no_invoca_llm_ni_muta(self):
        out = StringIO()
        with patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes"
        ) as procesar:
            call_command(
                "drenar_outbox_entrenador_joi", "--cliente", str(self.cliente.pk),
                "--limit", "10", stdout=out,
            )

        procesar.assert_not_called()
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        data = json.loads(out.getvalue())
        self.assertEqual(data["modo"], "dry-run")
        self.assertEqual(data["antes"][0]["id"], self.evento.pk)
        self.assertEqual(data["antes"], data["despues"])

    def test_apply_procesa_solo_cliente_y_limite_indicado(self):
        out = StringIO()
        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger="decision_plan", mensaje="Procesado.", contexto={}
        )

        def publicar(cliente, *, limite):
            self.assertEqual(cliente.pk, self.cliente.pk)
            self.assertEqual(limite, 7)
            EventoEntrenadorJOI.objects.filter(pk=self.evento.pk).update(
                estado=EventoEntrenadorJOI.ESTADO_PUBLICADO, mensaje=mensaje,
            )
            return mensaje

        with patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes",
            side_effect=publicar,
        ) as procesar:
            call_command(
                "drenar_outbox_entrenador_joi", "--cliente", str(self.cliente.pk),
                "--limit", "7", "--apply", stdout=out,
            )

        procesar.assert_called_once()
        data = json.loads(out.getvalue())
        self.assertEqual(data["modo"], "apply")
        self.assertEqual(data["resultado_mensaje_id"], mensaje.pk)
        self.assertEqual(data["despues"][0]["estado"], "publicado")

    def test_rechaza_limite_fuera_de_rango(self):
        with self.assertRaises(CommandError):
            call_command(
                "drenar_outbox_entrenador_joi", "--cliente", str(self.cliente.pk),
                "--limit", "101", stdout=StringIO(),
            )
