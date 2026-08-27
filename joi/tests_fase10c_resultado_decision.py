from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import GymDecisionLog
from joi.models import EventoEntrenadorJOI, MensajeJOI


class ResultadoDecision10CTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joi-fase10c")
        self.cliente = Cliente.objects.get(user=self.user)

    def decision(self, **changes):
        attrs = {
            "cliente": self.cliente,
            "ejercicio": "Press de banca",
            "accion": "mantener",
            "motivo": "TEXTO PRIVADO DEL MOTIVO",
            "motivo_codigo": "tecnica_comprometida",
            "notas_resultado": "TEXTO PRIVADO DEL RESULTADO",
            "motivo_postergacion": "TEXTO PRIVADO DE POSTERGACION",
            "confianza": "alta",
            "estado_aplicacion": "aplicada",
            "fecha_aplicacion": timezone.now(),
        }
        attrs.update(changes)
        return GymDecisionLog.objects.create(**attrs)

    def finalizar(self, decision, resultado):
        from entrenos.services.decision_log_service import _persistir_evaluacion_final

        with self.captureOnCommitCallbacks(execute=True):
            _persistir_evaluacion_final(decision, resultado, "nota privada")

    def test_resultado_null_no_encola(self):
        from joi.services_eventos_entrenador import publicar_evento_resultado_decision

        self.assertIsNone(publicar_evento_resultado_decision(self.decision()))
        self.assertFalse(EventoEntrenadorJOI.objects.exists())

    def test_cada_resultado_evaluado_encola_su_estado(self):
        for resultado in ("validada", "fallida", "neutra"):
            decision = self.decision(ejercicio=f"Ejercicio {resultado}")
            self.finalizar(decision, resultado)

        eventos = EventoEntrenadorJOI.objects.order_by("source_id")
        self.assertEqual(list(eventos.values_list("status", flat=True)), [
            "validada", "fallida", "neutra",
        ])
        for evento in eventos:
            self.assertEqual(evento.event_type, "gym_decision_outcome")
            self.assertEqual(evento.source_model, "entrenos.GymDecisionLog")
            self.assertEqual(evento.payload["epistemic_level"], "evaluated")

    def test_payload_resultado_es_allowlist_y_excluye_texto_privado(self):
        decision = self.decision()
        self.finalizar(decision, "validada")

        payload = EventoEntrenadorJOI.objects.get().payload
        self.assertEqual(set(payload["facts"]), {
            "resultado", "accion", "ejercicio", "motivo_codigo",
            "confianza", "fecha_evaluacion",
        })
        serializado = str(payload)
        self.assertNotIn("TEXTO PRIVADO", serializado)
        self.assertNotIn("notas_resultado", serializado)
        self.assertNotIn("motivo_postergacion", serializado)

    def test_evento_se_encola_solo_en_commit(self):
        from entrenos.services.decision_log_service import _persistir_evaluacion_final

        decision = self.decision()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            _persistir_evaluacion_final(decision, "validada", "nota")
            self.assertFalse(EventoEntrenadorJOI.objects.exists())
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertTrue(EventoEntrenadorJOI.objects.exists())

    def test_publicacion_resultado_es_idempotente(self):
        from joi.services_eventos_entrenador import publicar_evento_resultado_decision

        decision = self.decision(resultado="validada", fecha_evaluacion=timezone.now())
        primero = publicar_evento_resultado_decision(decision)
        segundo = publicar_evento_resultado_decision(decision)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(EventoEntrenadorJOI.objects.count(), 1)

    def test_segundo_cierre_no_reescribe_resultado_final(self):
        from entrenos.services.decision_log_service import _persistir_evaluacion_final

        decision = self.decision()
        self.finalizar(decision, 'validada')
        _persistir_evaluacion_final(decision, 'fallida', 'otra nota')

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'validada')
        self.assertEqual(EventoEntrenadorJOI.objects.count(), 1)

    def test_aplicacion_y_resultado_son_dos_recibos_distintos(self):
        from joi.services_eventos_entrenador import publicar_evento_decision_aplicada

        decision = self.decision()
        publicar_evento_decision_aplicada(decision)
        self.finalizar(decision, "validada")
        self.assertEqual(EventoEntrenadorJOI.objects.count(), 2)
        self.assertEqual(set(EventoEntrenadorJOI.objects.values_list("event_type", flat=True)), {
            "gym_decision_application", "gym_decision_outcome",
        })

    @patch("joi.services.construir_contexto")
    @patch("joi.services._llamar_haiku", return_value="La evaluación validó los ajustes.")
    def test_varios_resultados_comparten_un_mensaje(self, llamar, contexto):
        from joi.services_eventos_entrenador import procesar_eventos_entrenador_pendientes

        self.finalizar(self.decision(ejercicio="Press"), "validada")
        self.finalizar(self.decision(ejercicio="Remo"), "fallida")
        mensaje = procesar_eventos_entrenador_pendientes(self.cliente)

        self.assertIsNotNone(mensaje)
        self.assertEqual(MensajeJOI.objects.filter(trigger="decision_plan").count(), 1)
        self.assertEqual(mensaje.contexto["event_type"], "gym_decision_event_batch")
        self.assertEqual(len(mensaje.contexto["events"]), 2)
        contexto.assert_not_called()
        llamar.assert_called_once()

    def test_fallo_de_mensaje_deja_resultado_reintentable(self):
        from joi.services_eventos_entrenador import procesar_eventos_entrenador_pendientes

        self.finalizar(self.decision(), "neutra")
        with patch("joi.services.generar_mensaje_joi", return_value=None):
            self.assertIsNone(procesar_eventos_entrenador_pendientes(self.cliente))
        evento = EventoEntrenadorJOI.objects.get()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertEqual(evento.intentos, 1)

    def test_prompt_distingue_aplicacion_y_evaluacion_sin_causalidad(self):
        from joi.services import _prompt_decision_plan

        lote = {
            "events": [
                {"event_type": "gym_decision_application", "facts": {
                    "accion": "mantener", "ejercicio": "Press",
                }},
                {"event_type": "gym_decision_outcome", "status": "fallida", "facts": {
                    "resultado": "fallida", "accion": "mantener", "ejercicio": "Press",
                }},
            ],
        }
        prompt = _prompt_decision_plan({}, {"_evento_entrenador": lote}).lower()
        self.assertIn("aplicó", prompt)
        self.assertIn("evaluación", prompt)
        self.assertIn("no sostuvo", prompt)
        self.assertIn("no afirmes causalidad", prompt)
        self.assertIn("no digas que aprendiste", prompt)
