from datetime import date

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase

from clientes.models import Cliente
from clientes.recibo_supervision_gym_service import construir_recibo_supervision_gym
from entrenos.models import GymDecisionVersion, SesionProgramada


class ReciboSupervisionGymTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("recibo-supervision")
        self.cliente = Cliente.objects.get(user=self.user)
        self.fecha = date(2026, 8, 22)
        self.motor = self._version(
            version=1,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            postura="empujar",
            vigente=False,
        )

    def _version(self, **changes):
        version = changes.pop("version")
        attrs = {
            "cliente": self.cliente,
            "fecha": self.fecha,
            "version": version,
            "decision_id": f"decision-v{version}",
            "origen": GymDecisionVersion.ORIGEN_CORRECCION,
            "vigente": True,
            "fingerprint": f"fingerprint-{version}",
            "base_fingerprint": "base",
            "postura": "sostener",
            "snapshot": {},
            "ajustes": {},
            "motivo_correccion": "Conservar margen hoy.",
        }
        attrs.update(changes)
        return GymDecisionVersion.objects.create(**attrs)

    def _portada(self, *, ejecutable):
        return {
            "decision": {"estado": "OBSERVANDO", "frase": "Decisión vigente."},
            "accion_principal": None,
            "sesion_dominante": {
                "modulo": "gym",
                "datos": {"nombre": "Fuerza A", "rutina_nombre": "Fuerza A"},
                "ejecutable": ejecutable,
            },
            "sesion_alternativa": None,
            "senales": [],
            "aprendizajes": [],
        }

    def test_correccion_sostener_proyecta_recibo_factual_y_ejecutable(self):
        manual = self._version(version=2, reemplaza=self.motor)

        recibo = construir_recibo_supervision_gym(
            cliente=self.cliente,
            fecha=self.fecha,
            portada_hoy=self._portada(ejecutable=True),
        )

        self.assertEqual(recibo["titulo"], "Ajuste supervisado")
        self.assertEqual(recibo["version"], manual.version)
        self.assertEqual(recibo["postura_anterior"], "empujar")
        self.assertEqual(recibo["postura_actual"], "sostener")
        self.assertEqual(recibo["motivo"], "Conservar margen hoy.")
        self.assertTrue(recibo["ejecutable"])
        self.assertIn("ejercicios", recibo["conservacion"].lower())
        self.assertIn("cambios dinámicos", recibo["conservacion"].lower())
        self.assertIn("evidencia física", recibo["conservacion"].lower())
        html = self._render(self._portada(ejecutable=True), manual.snapshot, recibo)
        self.assertIn("Ejecutable", html)
        self.assertIn("rb-gym-receipt-state--ok", html)

    def test_correccion_proteger_sigue_visible_y_no_es_ejecutable(self):
        manual = self._version(
            version=2,
            postura="proteger",
            reemplaza=self.motor,
            motivo_correccion="Priorizar recuperación.",
        )
        portada = self._portada(ejecutable=False)
        recibo = construir_recibo_supervision_gym(
            cliente=self.cliente, fecha=self.fecha, portada_hoy=portada
        )

        html = self._render(portada, manual.snapshot, recibo)

        self.assertIn('data-gym-supervision-receipt', html)
        self.assertIn('data-receipt-executable="false"', html)
        self.assertIn("No ejecutable", html)
        self.assertIn("rb-gym-receipt-state--warn", html)
        self.assertIn("Priorizar recuperación.", html)
        self.assertNotIn('data-gym-correction-form', html)

    def test_reversion_proyecta_restauracion_sin_boton_restaurar(self):
        manual = self._version(version=2, vigente=False, reemplaza=self.motor)
        reversion = self._version(
            version=3,
            origen=GymDecisionVersion.ORIGEN_REVERSION,
            postura="empujar",
            reemplaza=manual,
            motivo_correccion="Volver a la propuesta base.",
        )
        portada = self._portada(ejecutable=True)
        recibo = construir_recibo_supervision_gym(
            cliente=self.cliente, fecha=self.fecha, portada_hoy=portada
        )

        html = self._render(portada, reversion.snapshot, recibo)

        self.assertEqual(recibo["titulo"], "Propuesta restaurada")
        self.assertEqual(recibo["postura_anterior"], "sostener")
        self.assertNotIn("Restaurar propuesta", html)

    def test_motor_vigente_no_proyecta_recibo(self):
        self.motor.vigente = True
        self.motor.save(update_fields=["vigente"])
        self.assertIsNone(construir_recibo_supervision_gym(
            cliente=self.cliente,
            fecha=self.fecha,
            portada_hoy=self._portada(ejecutable=True),
        ))

    def test_recibo_no_duplica_accion_principal_ni_voz_joi(self):
        manual = self._version(version=2, reemplaza=self.motor)
        portada = self._portada(ejecutable=True)
        portada["accion_principal"] = {
            "tipo": "enlace", "label": "Empezar entreno", "url": "/entrenos/"
        }
        recibo = construir_recibo_supervision_gym(
            cliente=self.cliente, fecha=self.fecha, portada_hoy=portada
        )
        html = self._render(portada, manual.snapshot, recibo)
        self.assertLessEqual(html.count("data-primary-action"), 1)
        self.assertLessEqual(html.count("data-joi-voice"), 1)

    def test_portada_moderna_ofrece_mover_solo_la_sesion_canonica_a_manana(self):
        self.motor.vigente = True
        self.motor.save(update_fields=["vigente"])
        sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.fecha,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion="Fuerza A",
        )

        html = self._render(
            self._portada(ejecutable=True),
            self.motor.snapshot,
            None,
            sesion_programada=sesion,
        )

        self.assertIn('data-postpone-session', html)
        self.assertIn('Hacer esta sesión mañana', html)
        self.assertIn(
            f'/clientes/sesion/{sesion.id}/posponer/',
            html,
        )
        self.assertIn('Cuándo entrenar', html)

    def test_portada_moderna_sin_sesion_canonica_no_inventa_accion_de_posponer(self):
        self.motor.vigente = True
        self.motor.save(update_fields=["vigente"])

        html = self._render(self._portada(ejecutable=True), self.motor.snapshot, None)

        self.assertNotIn('data-postpone-session', html)

    def _render(self, portada, autoridad, recibo, sesion_programada=None):
        postura_actual = recibo["postura_actual"] if recibo else "empujar"
        titulo_recibo = recibo["titulo"] if recibo else ""
        version_recibo = recibo["version"] if recibo else 1
        autoridad = {
            "postura": postura_actual,
            "origen_decision": (
                GymDecisionVersion.ORIGEN_CORRECCION
                if titulo_recibo == "Ajuste supervisado"
                else GymDecisionVersion.ORIGEN_REVERSION
            ),
            "version_persistida": version_recibo,
            "decision_id": "decision-vigente",
            **(autoridad or {}),
        }
        return render_to_string("clientes/mockup_demo.html", {
            "cliente": self.cliente,
            "hoy": self.fecha,
            "portada_hoy": portada,
            "estado_sistema": {"estado": "OBSERVANDO", "modulo_operativo": True},
            "autoridad_gym": autoridad,
            "recibo_supervision_gym": recibo,
            "sesion_programada": sesion_programada,
        })
