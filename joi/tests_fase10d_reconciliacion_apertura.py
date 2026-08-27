from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from joi.models import EventoEntrenadorJOI, MensajeJOI


class ReconciliacionApertura10DTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("joi-fase10d")
        self.cliente = Cliente.objects.get(user=self.user)

    def evento(self, *, event_type="gym_decision_application", status="aplicada", occurred_at=None, source_id=None):
        occurred_at = occurred_at or timezone.now()
        source_id = source_id or EventoEntrenadorJOI.objects.count() + 1
        epistemic = "evaluated" if event_type == "gym_decision_outcome" else "applied"
        facts = {
            "accion": "mantener",
            "ejercicio": f"Ejercicio {source_id}",
            "confianza": "alta",
        }
        if epistemic == "evaluated":
            facts["resultado"] = status
            facts["fecha_evaluacion"] = occurred_at.isoformat()
        payload = {
            "schema_version": 1,
            "event_type": event_type,
            "source_model": "entrenos.GymDecisionLog",
            "source_id": source_id,
            "occurred_at": occurred_at.isoformat(),
            "epistemic_level": epistemic,
            "status": status,
            "facts": facts,
        }
        return EventoEntrenadorJOI.objects.create(
            user=self.user,
            event_type=event_type,
            source_model="entrenos.GymDecisionLog",
            source_id=source_id,
            status=status,
            payload=payload,
        )

    def test_primero_devuelve_mensaje_no_leido_sin_reclamar_eventos(self):
        from joi.context_processors import _get_mensaje_gym

        historico = MensajeJOI.objects.create(
            user=self.user, trigger="decision_plan", mensaje="Sigo pendiente.", contexto={}
        )
        self.evento()
        with patch(
            "joi.services_eventos_entrenador.reconciliar_eventos_en_apertura",
        ) as reconciliar, patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes",
        ) as decision:
            resultado = _get_mensaje_gym(self.user)

        self.assertEqual(resultado.pk, historico.pk)
        reconciliar.assert_not_called()
        decision.assert_not_called()

    def test_apertura_nueva_integra_lote_reciente_ordenado_y_publica_recibos(self):
        from joi.context_processors import _get_mensaje_gym

        ahora = timezone.now()
        outcome = self.evento(
            event_type="gym_decision_outcome", status="validada",
            occurred_at=ahora - timedelta(hours=1), source_id=1,
        )
        applied = self.evento(
            occurred_at=ahora - timedelta(hours=1), source_id=1,
        )

        def generar(cliente, trigger, datos):
            self.assertEqual(trigger, "apertura_manana")
            eventos = datos["_evento_entrenador"]["events"]
            self.assertEqual(
                [item["epistemic_level"] for item in eventos],
                ["applied", "evaluated"],
            )
            return MensajeJOI.objects.create(
                user=cliente.user,
                trigger=trigger,
                mensaje="Apertura con lo aplicado y lo evaluado.",
                contexto=datos["_evento_entrenador"],
            )

        with patch("joi.services.generar_mensaje_joi", side_effect=generar) as llamada:
            mensaje = _get_mensaje_gym(self.user)

        self.assertEqual(mensaje.trigger, "apertura_manana")
        llamada.assert_called_once()
        for evento in (applied, outcome):
            evento.refresh_from_db()
            self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PUBLICADO)
            self.assertEqual(evento.mensaje_id, mensaje.pk)

    def test_fallo_devuelve_todo_a_pendiente_y_no_crea_apertura_parcial(self):
        from joi.context_processors import _get_mensaje_gym

        evento = self.evento()
        with patch("joi.services.generar_mensaje_joi", return_value=None), patch(
            "joi.context_processors._apertura_on_demand"
        ) as apertura_simple:
            self.assertIsNone(_get_mensaje_gym(self.user))

        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertFalse(MensajeJOI.objects.filter(trigger="apertura_manana").exists())
        apertura_simple.assert_not_called()

    def test_apertura_existente_no_se_reescribe_y_evento_nuevo_usa_decision_plan(self):
        from joi.context_processors import _get_mensaje_gym

        apertura = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Apertura original.",
            contexto={}, leido=True,
        )
        self.evento()
        def crear_decision(*args, **kwargs):
            return MensajeJOI.objects.create(
                user=self.user, trigger="decision_plan", mensaje="Ajuste posterior.", contexto={},
            )
        with patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes",
            side_effect=crear_decision,
        ) as procesar, patch(
            "joi.services_eventos_entrenador.reconciliar_eventos_en_apertura",
        ) as reconciliar:
            resultado = _get_mensaje_gym(self.user)

        self.assertEqual(resultado.trigger, "decision_plan")
        apertura.refresh_from_db()
        self.assertEqual(apertura.mensaje, "Apertura original.")
        procesar.assert_called_once()
        reconciliar.assert_not_called()

    def test_evento_mayor_de_48h_no_entra_ni_se_pierde(self):
        from joi.context_processors import _get_mensaje_gym

        antiguo = self.evento(occurred_at=timezone.now() - timedelta(hours=49))
        apertura = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Apertura limpia.", contexto={}
        )
        with patch("joi.context_processors._apertura_on_demand", return_value=apertura):
            resultado = _get_mensaje_gym(self.user)

        self.assertEqual(resultado.pk, apertura.pk)
        antiguo.refresh_from_db()
        self.assertEqual(antiguo.estado, EventoEntrenadorJOI.ESTADO_PENDIENTE)
        self.assertNotIn("events", resultado.contexto)

    def test_reclamo_se_limita_a_20_eventos(self):
        from joi.services_eventos_entrenador import reconciliar_eventos_en_apertura

        for source_id in range(1, 23):
            self.evento(source_id=source_id)
        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Lote.", contexto={}
        )
        with patch("joi.services.generar_mensaje_joi", return_value=mensaje):
            resultado, habia_eventos = reconciliar_eventos_en_apertura(self.cliente)

        self.assertTrue(habia_eventos)
        self.assertEqual(resultado.pk, mensaje.pk)
        self.assertEqual(
            EventoEntrenadorJOI.objects.filter(estado="publicado").count(), 20
        )
        self.assertEqual(
            EventoEntrenadorJOI.objects.filter(estado="pendiente").count(), 2
        )

    @patch("joi.services.construir_contexto", return_value={})
    @patch("joi.services._llamar_haiku", return_value="Apertura integrada.")
    def test_bloque_ejecutivo_respeta_allowlist_y_separa_aplicacion_de_evaluacion(
        self, llamar, _contexto,
    ):
        from joi.services_eventos_entrenador import reconciliar_eventos_en_apertura

        aplicado = self.evento(source_id=40)
        evaluado = self.evento(
            event_type="gym_decision_outcome", status="validada", source_id=40,
        )
        aplicado.payload["facts"]["motivo"] = "TEXTO PRIVADO"
        aplicado.payload["secreto"] = "NO CRUZAR"
        aplicado.save(update_fields=["payload"])

        mensaje, _ = reconciliar_eventos_en_apertura(self.cliente)

        self.assertIsNotNone(mensaje)
        prompt = llamar.call_args.args[0]
        self.assertIn("HECHOS EJECUTIVOS RECIENTES", prompt)
        self.assertIn("el motor aplicó", prompt)
        self.assertIn("resultados evaluados", prompt)
        self.assertNotIn("TEXTO PRIVADO", prompt)
        self.assertNotIn("NO CRUZAR", prompt)
        self.assertNotIn("TEXTO PRIVADO", str(mensaje.contexto))
        self.assertEqual(
            [item["epistemic_level"] for item in mensaje.contexto["events"]],
            ["applied", "evaluated"],
        )

    def test_claim_stale_se_recupera_antes_de_reconciliar(self):
        from joi.services_eventos_entrenador import reconciliar_eventos_en_apertura

        evento = self.evento()
        EventoEntrenadorJOI.objects.filter(pk=evento.pk).update(
            estado="procesando",
            reclamado_en=timezone.now() - timedelta(minutes=6),
        )
        mensaje = MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Recuperado.", contexto={}
        )
        with patch("joi.services.generar_mensaje_joi", return_value=mensaje):
            reconciliar_eventos_en_apertura(self.cliente)

        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoEntrenadorJOI.ESTADO_PUBLICADO)
        self.assertEqual(evento.mensaje_id, mensaje.pk)

    @patch("joi.context_processors.timezone.localdate")
    def test_apertura_del_dia_usa_fecha_local(self, localdate):
        from joi.context_processors import _get_mensaje_gym

        localdate.return_value = date(2026, 8, 27)
        MensajeJOI.objects.create(
            user=self.user, trigger="apertura_manana", mensaje="Ya existe.",
            contexto={}, leido=True,
        )
        with patch(
            "joi.services_eventos_entrenador.procesar_eventos_entrenador_pendientes",
            return_value=None,
        ):
            _get_mensaje_gym(self.user)

        localdate.assert_called()
