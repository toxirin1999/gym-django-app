import datetime
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.services.epistemic_review_queue import fingerprint_manual
from joi.models import ManualDavid, RevisionManualDavidOperacion


class RevisionMemoriaUITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('revision-ui')
        self.cliente = self.user.cliente_perfil
        self.other = User.objects.create_user('revision-ui-ajena')
        self.as_of = datetime.date(2026, 8, 22)

    def _manual(self, user=None, *, entrada='Memoria bajo revisión'):
        manual = ManualDavid.objects.create(
            user=user or self.user, entrada=entrada, origen='patron_detectado',
            tipo='hipotesis', estado='activa', activa=True, confianza=0.7,
        )
        created = self.as_of - datetime.timedelta(days=60)
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=timezone.make_aware(datetime.datetime.combine(created, datetime.time(10))),
            ultima_evidencia=None,
        )
        manual.refresh_from_db()
        return manual

    def _apply_url(self, manual, accion):
        return reverse('joi:joi_revision_memoria', args=[manual.pk, accion])

    def _payload(self, manual):
        return {
            'expected_fingerprint': fingerprint_manual(manual),
            'idempotency_key': str(uuid.uuid4()),
        }

    def test_endpoints_rechazan_get_anonimo_y_csrf(self):
        manual = self._manual()
        apply_url = self._apply_url(manual, 'confirmar')
        undo_url = reverse('joi:joi_deshacer_revision_memoria', args=[999])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(apply_url).status_code, 405)
        self.assertEqual(self.client.get(undo_url).status_code, 405)

        anonymous = Client()
        self.assertEqual(anonymous.post(apply_url, self._payload(manual)).status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(apply_url, self._payload(manual)).status_code, 403)

    def test_cuatro_acciones_crean_receipt_y_hacen_prg(self):
        self.client.force_login(self.user)
        expected_states = {
            'confirmar': ('activa', True),
            'cuestionar': ('cuestionada', True),
            'descartar': ('descartada', False),
            'posponer': ('activa', True),
        }
        for accion, expected in expected_states.items():
            manual = self._manual(entrada=accion)
            with patch('joi.views.timezone.localdate', return_value=self.as_of):
                response = self.client.post(
                    self._apply_url(manual, accion), self._payload(manual),
                )
            self.assertRedirects(response, reverse('joi:joi_habitacion'), fetch_redirect_response=False)
            manual.refresh_from_db()
            self.assertEqual((manual.estado, manual.activa), expected)
            self.assertTrue(RevisionManualDavidOperacion.objects.filter(
                manual=manual, actor=self.user, accion=accion,
            ).exists())

    def test_ownership_stale_y_cooldown_tienen_respuesta_neutra(self):
        own = self._manual()
        foreign = self._manual(user=self.other, entrada='Privada ajena')
        self.client.force_login(self.user)
        cases = [
            (foreign, self._payload(foreign)),
            (own, {**self._payload(own), 'expected_fingerprint': '0' * 64}),
        ]
        for manual, payload in cases:
            with patch('joi.views.timezone.localdate', return_value=self.as_of):
                response = self.client.post(self._apply_url(manual, 'confirmar'), payload, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'No se pudo aplicar esa revisión.')
            self.assertNotContains(response, 'Privada ajena')
            self.assertNotContains(response, 'fingerprint actual no coincide')

        from joi.services_revision_memoria import aplicar_revision_memoria
        delayed = self._manual()
        aplicar_revision_memoria(
            cliente=self.cliente, actor=self.user, manual_id=delayed.pk,
            accion='posponer', expected_fingerprint=fingerprint_manual(delayed),
            idempotency_key=uuid.uuid4(), as_of=self.as_of,
        )
        delayed.refresh_from_db()
        with patch('joi.views.timezone.localdate', return_value=self.as_of + datetime.timedelta(days=1)):
            response = self.client.post(
                self._apply_url(delayed, 'confirmar'), self._payload(delayed), follow=True,
            )
        self.assertContains(response, 'No se pudo aplicar esa revisión.')
        self.assertNotContains(response, 'aplazada hasta')

    def test_payload_invalido_es_neutro_y_no_escribe(self):
        manual = self._manual()
        self.client.force_login(self.user)
        response = self.client.post(self._apply_url(manual, 'confirmar'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se pudo aplicar esa revisión.')
        self.assertFalse(RevisionManualDavidOperacion.objects.exists())

    def test_deshacer_solo_operacion_propia_reciente_y_no_doble(self):
        manual = self._manual()
        self.client.force_login(self.user)
        with patch('joi.views.timezone.localdate', return_value=self.as_of):
            response = self.client.post(self._apply_url(manual, 'descartar'), self._payload(manual))
        receipt = RevisionManualDavidOperacion.objects.get(manual=manual, accion='descartar')
        undo_url = reverse('joi:joi_deshacer_revision_memoria', args=[receipt.pk])
        with patch('joi.views.timezone.localdate', return_value=self.as_of):
            undone = self.client.post(undo_url, {'idempotency_key': str(uuid.uuid4())})
        self.assertRedirects(undone, reverse('joi:joi_habitacion'), fetch_redirect_response=False)
        manual.refresh_from_db()
        self.assertTrue(manual.activa)
        self.assertEqual(manual.estado, 'activa')

        with patch('joi.views.timezone.localdate', return_value=self.as_of):
            doubled = self.client.post(undo_url, {'idempotency_key': str(uuid.uuid4())}, follow=True)
        self.assertContains(doubled, 'No se pudo deshacer esa revisión.')

        foreign_manual = self._manual(user=self.other)
        from joi.services_revision_memoria import aplicar_revision_memoria
        foreign_receipt = aplicar_revision_memoria(
            cliente=self.other.cliente_perfil, actor=self.other,
            manual_id=foreign_manual.pk, accion='confirmar',
            expected_fingerprint=fingerprint_manual(foreign_manual),
            idempotency_key=uuid.uuid4(), as_of=self.as_of,
        )
        response = self.client.post(
            reverse('joi:joi_deshacer_revision_memoria', args=[foreign_receipt.pk]),
            {'idempotency_key': str(uuid.uuid4())}, follow=True,
        )
        self.assertContains(response, 'No se pudo deshacer esa revisión.')

    def test_deshacer_stale_es_neutro(self):
        manual = self._manual()
        self.client.force_login(self.user)
        with patch('joi.views.timezone.localdate', return_value=self.as_of):
            self.client.post(self._apply_url(manual, 'confirmar'), self._payload(manual))
        receipt = RevisionManualDavidOperacion.objects.get(manual=manual, accion='confirmar')
        ManualDavid.objects.filter(pk=manual.pk).update(confianza=0.31)
        response = self.client.post(
            reverse('joi:joi_deshacer_revision_memoria', args=[receipt.pk]),
            {'idempotency_key': str(uuid.uuid4())}, follow=True,
        )
        self.assertContains(response, 'No se pudo deshacer esa revisión.')
        self.assertNotContains(response, 'cambió desde')

    def test_template_renderiza_una_memoria_cuatro_labels_y_undo_efimero(self):
        current = {
            'id': 7, 'texto': 'Memoria única', 'estado': 'activa',
            'estado_label': 'En uso', 'classification_label': 'Necesita una nueva mirada',
            'age_days': 45, 'ordinal': 1, 'total': 3,
            'expected_fingerprint': 'a' * 64,
            'action_keys': {action: str(uuid.uuid4()) for action in (
                'confirmar', 'cuestionar', 'descartar', 'posponer',
            )},
        }
        context = {
            'estado': 'calla', 'joi_estado': 'SILENCIO', 'hay_sedimento': False,
            'texto_vigilia': 'Presente.', 'joi_texto_motivo': 'Sin señales.',
            'joi_motivo': 'sin_senales', 'mensaje': None, 'narrativa': None,
            'entrenos_totales': None,
            'memoria_revision': {'count': 3, 'current': current, 'previous_id': None, 'next_id': 8},
            'revision_feedback': {'texto': 'Revisión guardada.', 'undo_operation_id': 22,
                                  'undo_idempotency_key': str(uuid.uuid4())},
        }
        with patch('core.ai.gemini_client.generate_text') as ai:
            html = render_to_string('joi/habitacion.html', context)
        block = html.split('data-testid="memoria-review"', 1)[1].split('</details>', 1)[0]
        for label in ('Sigue siendo cierto', 'No estoy seguro', 'Ya no encaja', 'Ahora no'):
            self.assertEqual(block.count(label), 1)
        self.assertEqual(html.count('data-testid="memoria-review"'), 1)
        self.assertIn('Revisión guardada.', html)
        self.assertIn('>Deshacer<', html)
        self.assertIn('min-height: 44px', html)
        ai.assert_not_called()
