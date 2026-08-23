import datetime
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.services.epistemic_review_queue import fingerprint_manual
from joi.models import ManualDavid


class ManualAuthorityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manual-authority')
        self.cliente = self.user.cliente_perfil
        self.as_of = datetime.date(2026, 8, 23)

    def _manual(self, entrada, *, days_old=60, **overrides):
        data = {
            'user': self.user, 'entrada': entrada, 'origen': 'patron_detectado',
            'tipo': 'hipotesis', 'estado': 'activa', 'activa': True, 'confianza': 0.7,
        }
        data.update(overrides)
        manual = ManualDavid.objects.create(**data)
        created = self.as_of - datetime.timedelta(days=days_old)
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=timezone.make_aware(datetime.datetime.combine(created, datetime.time(10))),
            ultima_evidencia=None,
        )
        manual.refresh_from_db()
        return manual

    def _apply(self, manual, action, *, as_of=None):
        from joi.services_revision_memoria import aplicar_revision_memoria
        return aplicar_revision_memoria(
            cliente=self.cliente, actor=self.user, manual_id=manual.pk,
            accion=action, expected_fingerprint=fingerprint_manual(manual),
            idempotency_key=uuid.uuid4(), as_of=as_of or self.as_of,
        )

    def test_politica_excluye_descartadas_inactivas_y_ordena_autoridad(self):
        correction = self._manual(
            'Corrección explícita', origen='feedback_error', tipo='limite',
            estado='cuestionada', confianza=0.1, days_old=2,
        )
        confirmed = self._manual('Confirmada')
        automatic = self._manual('Automática', days_old=3)
        self._manual('Descartada', estado='descartada', activa=True)
        self._manual('Inactiva', activa=False)
        self._apply(confirmed, 'confirmar')

        from joi.services_manual_authority import resolver_autoridad_manual
        with CaptureQueriesContext(connection) as queries:
            items = resolver_autoridad_manual(self.user, as_of=self.as_of)

        self.assertEqual([item['id'] for item in items], [correction.pk, confirmed.pk, automatic.pk])
        self.assertEqual([item['authority'] for item in items], [
            'explicit_correction', 'user_confirmed', 'automatic_hypothesis',
        ])
        self.assertLessEqual(len(queries), 2)
        self.assertFalse(any('notas_revision' in str(item) for item in items))

    def test_cuestionar_y_posponer_se_silencian_dia13_y_reaparecen_dia14(self):
        from joi.services_manual_authority import resolver_autoridad_manual
        for action in ('cuestionar', 'posponer'):
            manual = self._manual(action)
            self._apply(manual, action)
            day13 = resolver_autoridad_manual(
                self.user, as_of=self.as_of + datetime.timedelta(days=13),
            )
            day14 = resolver_autoridad_manual(
                self.user, as_of=self.as_of + datetime.timedelta(days=14),
            )
            self.assertNotIn(manual.pk, {item['id'] for item in day13})
            item = next(item for item in day14 if item['id'] == manual.pk)
            expected = 'uncertain_hypothesis' if action == 'cuestionar' else 'automatic_hypothesis'
            self.assertEqual(item['authority'], expected)

    def test_undo_restaura_semantica_previa(self):
        from joi.services_manual_authority import resolver_autoridad_manual
        from joi.services_revision_memoria import deshacer_revision_memoria
        manual = self._manual('Restaurable')
        before = resolver_autoridad_manual(self.user, as_of=self.as_of)[0]
        operation = self._apply(manual, 'cuestionar')
        deshacer_revision_memoria(
            cliente=self.cliente, actor=self.user, operacion_id=operation.pk,
            idempotency_key=uuid.uuid4(), as_of=self.as_of,
        )
        after = resolver_autoridad_manual(self.user, as_of=self.as_of)[0]
        self.assertEqual(after['authority'], before['authority'])
        self.assertEqual(after['confidence'], before['confidence'])

    def test_prompt_separa_confirmacion_de_verdad_y_no_afirma_cuestionada(self):
        confirmed = self._manual('Prefiero sesiones por la mañana')
        uncertain = self._manual('Siempre abandono cuando llueve', estado='cuestionada')
        self._apply(confirmed, 'confirmar')
        from joi.services import _bloque_manual
        with patch('core.ai.gemini_client.generate_text') as ai:
            prompt = _bloque_manual(self.user, incluir_narrativa=False, as_of=self.as_of)
        self.assertIn('CONFIRMACIÓN EXPLÍCITA DEL USUARIO', prompt)
        self.assertIn('no es verdad absoluta ni conocimiento consolidado', prompt)
        self.assertIn('HIPÓTESIS EXPLÍCITAMENTE INCIERTAS', prompt)
        self.assertIn('Nunca las redactes como hechos ni instrucciones', prompt)
        self.assertLess(prompt.index('Prefiero sesiones'), prompt.index('Siempre abandono'))
        ai.assert_not_called()

    def test_contexto_estructurado_expone_provenance_minima_sin_privados(self):
        manual = self._manual('Texto privado')
        operation = self._apply(manual, 'confirmar')
        from joi.services_manual_authority import construir_contexto_autoridad_manual
        context = construir_contexto_autoridad_manual(self.user, as_of=self.as_of)
        self.assertEqual(context['items'][0], {
            'manual_id': manual.pk,
            'authority': 'user_confirmed',
            'provenance': {'source': 'human_review', 'operation_id': operation.pk},
        })
        serialized = str(context)
        for private in ('Texto privado', 'before_snapshot', 'after_snapshot', 'motivo', 'notas_revision'):
            self.assertNotIn(private, serialized)

        from joi.services import construir_contexto
        full_context = construir_contexto(self.cliente)
        self.assertEqual(full_context['manual_authority'], context)

    def test_bloque_manual_no_aumenta_ia_mensajes_ni_triggers(self):
        self._manual('Una hipótesis')
        from joi.models import MensajeJOI
        from joi.services import _bloque_manual
        before_messages = MensajeJOI.objects.count()
        before_triggers = tuple(MensajeJOI._meta.get_field('trigger').choices)
        with patch('joi.services._llamar_haiku') as haiku:
            _bloque_manual(self.user, as_of=self.as_of)
        self.assertEqual(MensajeJOI.objects.count(), before_messages)
        self.assertEqual(tuple(MensajeJOI._meta.get_field('trigger').choices), before_triggers)
        haiku.assert_not_called()
