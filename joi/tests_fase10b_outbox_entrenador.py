from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import GymDecisionLog
from joi.models import MensajeJOI


class OutboxEntrenador10BTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joi-fase10b")
        self.cliente = Cliente.objects.get(user=self.user)

    def decision(self, cliente=None, **changes):
        attrs = {
            "cliente": cliente or self.cliente,
            "ejercicio": "Press de banca",
            "accion": "mantener",
            "motivo": "TEXTO PRIVADO que nunca debe cruzar",
            "motivo_codigo": "tecnica_comprometida",
            "confianza": "alta",
            "estado_aplicacion": "aplicada",
        }
        attrs.update(changes)
        return GymDecisionLog.objects.create(**attrs)

    def test_encolar_no_llama_llm_y_guarda_contexto_minimo(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import publicar_evento_decision_aplicada

        decision = self.decision()
        with patch("joi.services.generar_mensaje_joi") as generar:
            evento = publicar_evento_decision_aplicada(decision)

        generar.assert_not_called()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertEqual(evento.source_id, decision.pk)
        self.assertNotIn("motivo", evento.payload["facts"])
        self.assertNotIn("TEXTO PRIVADO", str(evento.payload))

    def test_fuente_es_idempotente_en_outbox(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import publicar_evento_decision_aplicada

        decision = self.decision()
        primero = publicar_evento_decision_aplicada(decision)
        segundo = publicar_evento_decision_aplicada(decision)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(EventoEntrenadorJOI.objects.count(), 1)

    @patch("joi.services.construir_contexto")
    @patch("joi.services._llamar_haiku", return_value="El plan consolidó dos ajustes confirmados.")
    def test_dos_decisiones_hermanas_producen_un_mensaje(self, llamar, contexto_global):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        d1 = self.decision(ejercicio="Press de banca")
        d2 = self.decision(ejercicio="Remo")
        publicar_evento_decision_aplicada(d1)
        publicar_evento_decision_aplicada(d2)

        mensaje = procesar_eventos_entrenador_pendientes(self.cliente)

        self.assertIsNotNone(mensaje)
        self.assertEqual(MensajeJOI.objects.filter(trigger="decision_plan").count(), 1)
        self.assertEqual(
            EventoEntrenadorJOI.objects.filter(
                estado=EventoEntrenadorJOI.ESTADO_PUBLICADO,
                mensaje=mensaje,
            ).count(),
            2,
        )
        self.assertEqual(len(mensaje.contexto["events"]), 2)
        self.assertNotIn("TEXTO PRIVADO", str(mensaje.contexto))
        contexto_global.assert_not_called()
        llamar.assert_called_once()

    def test_fallo_de_generacion_retorna_todo_el_lote_a_pendiente(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        evento = publicar_evento_decision_aplicada(self.decision())
        with patch("joi.services.generar_mensaje_joi", return_value=None):
            self.assertIsNone(procesar_eventos_entrenador_pendientes(self.cliente))

        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertEqual(evento.intentos, 1)
        self.assertEqual(evento.ultimo_error, "message_not_created")

        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger="decision_plan", mensaje="Aplicado.", contexto={}
        )
        with patch("joi.services.generar_mensaje_joi", return_value=mensaje):
            self.assertEqual(
                procesar_eventos_entrenador_pendientes(self.cliente).pk,
                mensaje.pk,
            )
        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PUBLICADO)
        self.assertEqual(evento.intentos, 2)

    def test_procesador_aisla_clientes(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        otro_user = User.objects.create_user("joi-fase10b-otro")
        otro = Cliente.objects.get(user=otro_user)
        propio = publicar_evento_decision_aplicada(self.decision())
        ajeno = publicar_evento_decision_aplicada(self.decision(cliente=otro))
        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger="decision_plan", mensaje="Aplicado.", contexto={}
        )

        with patch("joi.services.generar_mensaje_joi", return_value=mensaje):
            procesar_eventos_entrenador_pendientes(self.cliente)

        propio.refresh_from_db()
        ajeno.refresh_from_db()
        self.assertEqual(propio.estado, EventoEntrenadorJOI.ESTADO_PUBLICADO)
        self.assertEqual(ajeno.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)

    def test_decision_pendiente_no_entra_en_outbox(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import publicar_evento_decision_aplicada

        decision = self.decision(estado_aplicacion="pendiente")

        self.assertIsNone(publicar_evento_decision_aplicada(decision))
        self.assertFalse(EventoEntrenadorJOI.objects.exists())

    def test_claim_caducado_se_recupera_y_publica(self):
        from joi.models import EventoEntrenadorJOI
        from joi.services_eventos_entrenador import (
            procesar_eventos_entrenador_pendientes,
            publicar_evento_decision_aplicada,
        )

        evento = publicar_evento_decision_aplicada(self.decision())
        evento.estado = EventoEntrenadorJOI.ESTADO_PROCESANDO
        evento.reclamado_en = timezone.now() - timedelta(minutes=6)
        evento.save(update_fields=['estado', 'reclamado_en'])
        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger='decision_plan', mensaje='Aplicado.', contexto={}
        )

        with patch('joi.services.generar_mensaje_joi', return_value=mensaje):
            procesar_eventos_entrenador_pendientes(self.cliente)

        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PUBLICADO)
        self.assertEqual(evento.mensaje_id, mensaje.pk)

    def test_context_processor_preserva_mensaje_no_leido_antes_de_drenar(self):
        from joi.context_processors import _get_mensaje_gym

        esperado = MensajeJOI.objects.create(
            user=self.user, trigger="decision_plan", mensaje="Aplicado.", contexto={}
        )
        with patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes",
            return_value=esperado,
        ) as procesar:
            obtenido = _get_mensaje_gym(self.user)

        self.assertEqual(obtenido.pk, esperado.pk)
        procesar.assert_not_called()
