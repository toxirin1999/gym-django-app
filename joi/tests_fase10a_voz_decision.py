from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionLog
from joi.models import EventoEntrenadorJOI, MensajeJOI


class VozDecisionPlan10ATests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joi-fase10a")
        self.cliente = Cliente.objects.get(user=self.user)

    def decision(self, **changes):
        attrs = {
            "cliente": self.cliente,
            "ejercicio": "Press de banca",
            "accion": "mantener",
            "motivo": "TEXTO PRIVADO: la explicación libre nunca cruza",
            "motivo_codigo": "tecnica_comprometida",
            "confianza": "alta",
            "estado_aplicacion": "pendiente",
        }
        attrs.update(changes)
        return GymDecisionLog.objects.create(**attrs)

    @patch("joi.services.generar_mensaje_joi")
    def test_decision_pendiente_no_se_verbaliza_como_aplicada(self, generar):
        self.decision()

        generar.assert_not_called()

    @patch("joi.services._llamar_haiku")
    def test_invocacion_legacy_sin_fuente_estructurada_se_bloquea(self, llamar):
        from joi.services import generar_mensaje_joi

        resultado = generar_mensaje_joi(
            self.cliente,
            "decision_plan",
            {"accion": "bajar_peso", "motivo": "texto libre"},
        )

        self.assertIsNone(resultado)
        llamar.assert_not_called()

    def test_evento_aplicado_es_minimo_y_no_incluye_motivo_libre(self):
        from joi.services_eventos_entrenador import construir_evento_decision_aplicada

        decision = self.decision(estado_aplicacion="aplicada")
        evento = construir_evento_decision_aplicada(decision)

        self.assertEqual(
            set(evento),
            {
                "schema_version", "event_type", "source_model", "source_id",
                "occurred_at", "epistemic_level", "status", "facts",
            },
        )
        self.assertEqual(evento["status"], "aplicada")
        self.assertEqual(evento["epistemic_level"], "applied")
        self.assertEqual(evento["facts"]["motivo_codigo"], "tecnica_comprometida")
        self.assertNotIn("motivo", evento["facts"])
        self.assertNotIn("TEXTO PRIVADO", str(evento))

    def test_motivo_codigo_no_permitido_no_cruza_el_evento(self):
        from joi.services_eventos_entrenador import construir_evento_decision_aplicada

        decision = self.decision(
            estado_aplicacion="aplicada",
            motivo_codigo="codigo_futuro_no_revisado",
        )

        evento = construir_evento_decision_aplicada(decision)

        self.assertNotIn("motivo_codigo", evento["facts"])

    @patch("joi.services_eventos_entrenador.publicar_evento_decision_aplicada")
    def test_aplicacion_emite_solo_despues_del_commit(self, publicar):
        from entrenos.services.plan_dinamico_service import _persistir_estado_aplicacion

        decision = self.decision()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            _persistir_estado_aplicacion(decision, "aplicada", None)
            publicar.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        publicar.assert_called_once()
        self.assertEqual(publicar.call_args.args[0].pk, decision.pk)

    @patch("joi.services.construir_contexto", return_value={})
    @patch("joi.services._llamar_haiku", return_value="El plan consolidó la técnica antes de progresar.")
    def test_mensaje_persiste_solo_contexto_minimo_del_evento(self, _haiku, _contexto):
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        decision = self.decision(estado_aplicacion="aplicada")
        publicar_evento_decision_aplicada(decision)
        mensaje = procesar_eventos_entrenador_pendientes(self.cliente)

        self.assertIsNotNone(mensaje)
        self.assertEqual(mensaje.contexto["events"][0]["source_id"], decision.pk)
        self.assertEqual(mensaje.contexto["status"], "aplicada")
        self.assertNotIn("motivo", mensaje.contexto)
        self.assertNotIn("motivo", mensaje.contexto["events"][0]["facts"])
        self.assertNotIn("TEXTO PRIVADO", str(mensaje.contexto))
        self.assertNotIn("physical_evidence", mensaje.contexto)

    @patch("joi.services.construir_contexto", return_value={})
    @patch("joi.services._llamar_haiku", return_value="El plan aplicó el ajuste confirmado.")
    def test_fuente_y_estado_son_idempotentes(self, llamar, _contexto):
        from joi.services_eventos_entrenador import publicar_evento_decision_aplicada

        decision = self.decision(estado_aplicacion="aplicada")

        primero = publicar_evento_decision_aplicada(decision)
        segundo = publicar_evento_decision_aplicada(decision)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(EventoEntrenadorJOI.objects.count(), 1)
        self.assertEqual(MensajeJOI.objects.filter(trigger="decision_plan").count(), 0)
        llamar.assert_not_called()

    @patch("joi.services.construir_contexto", return_value={})
    @patch("joi.services._llamar_haiku", side_effect=[RuntimeError("llm caído"), "Aplicado."])
    def test_fallo_llm_no_marca_evento_como_comunicado(self, llamar, _contexto):
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        decision = self.decision(estado_aplicacion="aplicada")
        evento = publicar_evento_decision_aplicada(decision)

        self.assertIsNone(procesar_eventos_entrenador_pendientes(self.cliente))
        self.assertFalse(MensajeJOI.objects.filter(trigger="decision_plan").exists())
        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertIsNotNone(procesar_eventos_entrenador_pendientes(self.cliente))
        self.assertEqual(llamar.call_count, 2)

    @patch("joi.services.construir_contexto", return_value={})
    @patch("joi.services._llamar_haiku", return_value="Lectura precisa.")
    def test_prompt_declara_certeza_confirmada_sin_motivo_libre(self, llamar, _contexto):
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        decision = self.decision(estado_aplicacion="aplicada")
        publicar_evento_decision_aplicada(decision)
        procesar_eventos_entrenador_pendientes(self.cliente)

        prompt = llamar.call_args.args[0]
        self.assertIn("HECHOS CONFIRMADOS", prompt)
        self.assertNotIn("TEXTO PRIVADO", prompt)
