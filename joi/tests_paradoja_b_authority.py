import datetime
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.services.epistemic_review_queue import fingerprint_manual
from joi.models import ManualDavid, RevisionManualDavidOperacion
from joi.services import generar_mensaje_joi
from joi.services_revision_memoria import (
    aplicar_revision_memoria,
    deshacer_revision_memoria,
)


class ParadojaBAuthorityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('paradoja-b')
        self.cliente = self.user.cliente_perfil
        self.as_of = datetime.date(2026, 8, 23)

    def _manual(self, *, entrada='Patrón de resistencia psicológica al empezar'):
        manual = ManualDavid.objects.create(
            user=self.user,
            entrada=entrada,
            origen='patron_detectado',
            tipo='hipotesis',
            estado='activa',
            activa=True,
            confianza=0.7,
        )
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=timezone.make_aware(datetime.datetime(2026, 6, 1, 10)),
        )
        manual.refresh_from_db()
        return manual

    def _review(self, manual, accion):
        return aplicar_revision_memoria(
            cliente=self.cliente,
            actor=self.user,
            manual_id=manual.pk,
            accion=accion,
            expected_fingerprint=fingerprint_manual(manual),
            idempotency_key=uuid.uuid4(),
            as_of=self.as_of,
        )

    def _ctx(self, paradoja='B'):
        return {
            'semaforo': {
                'estado': 'verde',
                'tipo_fatiga': 'flojera',
                'paradoja': paradoja,
                'datos_raw': {'energia': 3},
            },
            'ultima_actividad': {'dias_hace': 0, 'tipo': 'gym'},
        }

    def _generar_y_capturar_prompt(self, ctx):
        captured = []

        def fake_call(prompt, **kwargs):
            captured.append(prompt)
            return 'Lectura controlada.'

        with (
            patch('joi.services.construir_contexto', return_value=ctx),
            patch('joi.services._bloque_marco_narrativo', return_value=''),
            patch('joi.services._bloque_manual', return_value=''),
            patch('joi.services._bloque_memoria', return_value=''),
            patch('joi.services._bloque_temporal', return_value=''),
            patch('joi.services.build_continuidad_context', return_value={}),
            patch('joi.services._bloque_continuidad', return_value=''),
            patch('joi.services._llamar_haiku', side_effect=fake_call) as ai,
        ):
            mensaje = generar_mensaje_joi(self.cliente, 'apertura_manana', {})

        self.assertIsNotNone(mensaje)
        self.assertEqual(ai.call_count, 1)
        self.assertEqual(len(captured), 1)
        return captured[0]

    def test_paradoja_b_incorpora_memoria_confirmada_sin_declararla_verdad_absoluta(self):
        manual = self._manual()
        self._review(manual, 'confirmar')

        with patch('joi.services.timezone.localdate', return_value=self.as_of):
            prompt = self._generar_y_capturar_prompt(self._ctx())

        self.assertIn('PATRÓN REVISADO POR EL USUARIO', prompt)
        self.assertIn('resistencia psicológica al empezar', prompt)
        self.assertIn('no es verdad absoluta', prompt)
        self.assertNotIn('Primera detección', prompt)

    def test_paradoja_b_prioriza_correccion_explicita(self):
        self._manual(entrada='Hipótesis de resistencia psicológica automática')
        ManualDavid.objects.create(
            user=self.user,
            entrada='Corrección: la resistencia psicológica no explica este caso',
            origen='feedback_error',
            tipo='dato_usuario',
            estado='activa',
            activa=True,
            confianza=1.0,
        )

        with patch('joi.services.timezone.localdate', return_value=self.as_of):
            prompt = self._generar_y_capturar_prompt(self._ctx())

        self.assertIn('CORRECCIÓN EXPLÍCITA DEL USUARIO', prompt)
        self.assertIn('no explica este caso', prompt)
        self.assertNotIn('Hipótesis de resistencia psicológica automática', prompt)

    def test_pospuesta_cuestionada_y_descartada_no_son_evidencia_de_paradoja_b(self):
        for accion in ('posponer', 'cuestionar', 'descartar'):
            with self.subTest(accion=accion):
                RevisionManualDavidOperacion.objects.all().delete()
                ManualDavid.objects.all().delete()
                manual = self._manual(entrada=f'Resistencia psicológica {accion}')
                self._review(manual, accion)

                with patch('joi.services.timezone.localdate', return_value=self.as_of):
                    prompt = self._generar_y_capturar_prompt(self._ctx())

                self.assertIn('Primera detección', prompt)
                self.assertNotIn(f'Resistencia psicológica {accion}', prompt)

    def test_deshacer_confirmacion_restaura_lenguaje_provisional(self):
        manual = self._manual()
        receipt = self._review(manual, 'confirmar')
        with patch('joi.services.timezone.localdate', return_value=self.as_of):
            confirmed = self._generar_y_capturar_prompt(self._ctx())
        self.assertIn('PATRÓN REVISADO POR EL USUARIO', confirmed)

        deshacer_revision_memoria(
            cliente=self.cliente,
            actor=self.user,
            operacion_id=receipt.pk,
            idempotency_key=uuid.uuid4(),
            as_of=self.as_of,
        )
        with patch('joi.services.timezone.localdate', return_value=self.as_of):
            restored = self._generar_y_capturar_prompt(self._ctx())

        self.assertIn('HIPÓTESIS AUTOMÁTICA VIGENTE', restored)
        self.assertIn('lenguaje provisional', restored)
        self.assertNotIn('PATRÓN REVISADO POR EL USUARIO', restored)

    def test_rama_a_no_consulta_memoria_de_paradoja_b_y_mantiene_una_llamada(self):
        self._manual()
        with (
            patch(
                'joi.services_manual_authority.resolver_autoridad_manual',
                side_effect=AssertionError('la rama A no debe consultar Paradoja B'),
            ),
            patch('joi.services.timezone.localdate', return_value=self.as_of),
        ):
            prompt = self._generar_y_capturar_prompt(self._ctx(paradoja='A'))

        self.assertIn('PARADOJA A', prompt)
        self.assertNotIn('resistencia psicológica', prompt)
