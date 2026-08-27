import json
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from joi.models import EventoEntrenadorJOI, MensajeJOI


class AuditoriaOutbox10ETests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("audit-outbox")
        self.otro = User.objects.create_user("audit-outbox-otro")
        self.cliente = Cliente.objects.get(user=self.user)
        self.as_of = date(2026, 8, 27)
        self.corte = timezone.make_aware(datetime.combine(self.as_of, time.max))

    def evento(self, **overrides):
        source_id = overrides.pop("source_id", EventoEntrenadorJOI.objects.count() + 1)
        occurred_at = overrides.pop("occurred_at", self.corte - timedelta(hours=1))
        facts = overrides.pop("facts", {"accion": "mantener", "ejercicio": "Press", "confianza": "alta"})
        payload = {
            "schema_version": 1,
            "event_type": "gym_decision_application",
            "source_model": "entrenos.GymDecisionLog",
            "source_id": source_id,
            "occurred_at": occurred_at.isoformat(),
            "epistemic_level": "applied",
            "status": "aplicada",
            "facts": facts,
        }
        payload.update(overrides.pop("payload_extra", {}))
        return EventoEntrenadorJOI.objects.create(
            user=overrides.pop("user", self.user),
            event_type=overrides.pop("event_type", payload["event_type"]),
            source_model=overrides.pop("source_model", payload["source_model"]),
            source_id=source_id,
            status=overrides.pop("status", payload["status"]),
            payload=payload,
            **overrides,
        )

    def test_detecta_backlog_claim_payload_usuario_futuro_e_intentos_sin_texto_privado(self):
        from joi.services_eventos_entrenador import auditar_outbox_entrenador_joi

        viejo = self.evento(source_id=1, occurred_at=self.corte - timedelta(hours=49))
        stale = self.evento(source_id=2, estado="procesando", reclamado_en=self.corte - timedelta(minutes=6))
        mismatch = self.evento(source_id=3, payload_extra={"source_id": 999, "privado": "NO MOSTRAR"})
        future = self.evento(source_id=4, occurred_at=self.corte + timedelta(seconds=1))
        attempts = self.evento(source_id=5, intentos=2, ultimo_error="")
        mensaje_otro = MensajeJOI.objects.create(
            user=self.otro, trigger="decision_plan", mensaje="SECRETO", contexto={},
        )
        usuario_mal = self.evento(source_id=6, estado="publicado", mensaje=mensaje_otro)
        sin_mensaje = self.evento(source_id=7, estado="publicado")
        no_allowlist = self.evento(source_id=8, facts={"accion": "mantener", "nota_privada": "NO MOSTRAR"})

        resultado = auditar_outbox_entrenador_joi(
            as_of="2026-08-27", cliente_id=self.cliente.pk, limit=100,
        )
        codigos = {item["code"] for item in resultado["findings"]}
        self.assertTrue({
            "pending_over_48h", "processing_stale_over_5m", "payload_source_mismatch",
            "future_occurred_at", "attempts_without_error_context", "message_user_mismatch",
            "published_without_message", "payload_not_allowlisted",
        }.issubset(codigos))
        self.assertNotIn("NO MOSTRAR", json.dumps(resultado, ensure_ascii=False))
        self.assertNotIn("SECRETO", json.dumps(resultado, ensure_ascii=False))
        self.assertFalse(resultado["summary"]["contract_ok"])
        self.assertEqual(resultado["summary"]["backlog"]["pendiente"], 5)

    def test_detecta_recibo_semantico_duplicado_aunque_cambie_estado_resultado(self):
        from joi.services_eventos_entrenador import auditar_outbox_entrenador_joi

        self.evento(source_id=20)
        self.evento(source_id=20, status="fallida")
        resultado = auditar_outbox_entrenador_joi(as_of=self.as_of, limit=100)
        self.assertIn("duplicate_semantic_receipt", {
            item["code"] for item in resultado["findings"]
        })

    def test_comando_emite_jsonl_determinista_y_es_estrictamente_solo_lectura(self):
        from io import StringIO

        self.evento(source_id=30, occurred_at=self.corte - timedelta(hours=49))
        before = list(EventoEntrenadorJOI.objects.values_list("pk", "estado", "intentos"))
        out = StringIO()
        call_command(
            "auditar_outbox_entrenador_joi", "--as-of", "2026-08-27",
            "--cliente", str(self.cliente.pk), "--limit", "50", stdout=out,
        )
        lineas = [json.loads(linea) for linea in out.getvalue().splitlines()]
        self.assertEqual(lineas[-1]["tipo_registro"], "resumen")
        self.assertEqual(lineas[0]["tipo_registro"], "hallazgo")
        self.assertEqual(
            before, list(EventoEntrenadorJOI.objects.values_list("pk", "estado", "intentos"))
        )

    def test_limit_declara_filas_truncadas_sin_evaluarlas(self):
        from joi.services_eventos_entrenador import auditar_outbox_entrenador_joi

        self.evento(source_id=40)
        self.evento(source_id=41)
        self.evento(source_id=42)
        resultado = auditar_outbox_entrenador_joi(as_of=self.as_of, limit=2)
        self.assertEqual(resultado["summary"]["evaluados"], 2)
        self.assertEqual(resultado["summary"]["truncados"], 1)
