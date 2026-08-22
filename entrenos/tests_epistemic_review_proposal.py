import datetime
import io
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from joi.models import ManualDavid


class EpistemicReviewProposalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('epistemic-review-proposal')
        self.cliente = self.user.cliente_perfil
        self.as_of = datetime.date(2026, 8, 22)

    def _manual(self, *, days_old=45, **overrides):
        data = {
            'user': self.user,
            'entrada': 'ENTRADA PRIVADA',
            'origen': 'patron_detectado',
            'tipo': 'hipotesis',
            'estado': 'activa',
            'activa': True,
            'confianza': 0.7,
            'notas_revision': 'NOTAS PRIVADAS',
            'hipotesis_contraria': 'CONTRARIA PRIVADA',
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

    def _ref(self, manual):
        from core.services.epistemic_review_queue import planificar_revision_memoria
        item = next(item for item in planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )['items'] if item['id'] == manual.pk)
        return f"{manual.pk}:{item['fingerprint']}"

    def test_prepara_lote_valido_y_manifest_publico_privado(self):
        first = self._manual(estado='cuestionada')
        second = self._manual(days_old=10, tipo='patron')
        from core.services.epistemic_review_proposal import preparar_lote_revision

        result = preparar_lote_revision(
            cliente_id=self.cliente.pk, as_of=self.as_of,
            item_refs=[self._ref(second), self._ref(first)],
        )

        self.assertEqual([item['id'] for item in result['items']], [first.pk, second.pk])
        self.assertFalse(result['execution_enabled'])
        self.assertTrue(result['solo_lectura'])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('ENTRADA PRIVADA', serialized)
        self.assertNotIn('NOTAS PRIVADAS', serialized)
        self.assertNotIn('CONTRARIA PRIVADA', serialized)

    def test_rechaza_stale_no_elegible_duplicado_y_limite(self):
        eligible = self._manual()
        stale_ref = f'{eligible.pk}:' + ('0' * 64)
        excluded = self._manual(origen='feedback_error')
        from core.services.epistemic_review_proposal import preparar_lote_revision

        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of, item_refs=[stale_ref],
            )
        with self.assertRaisesRegex(ValueError, 'no elegible'):
            preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of,
                item_refs=[f'{excluded.pk}:' + ('0' * 64)],
            )
        valid_ref = self._ref(eligible)
        with self.assertRaisesRegex(ValueError, 'duplicado'):
            preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of,
                item_refs=[valid_ref, valid_ref],
            )
        refs = [self._ref(self._manual(days_old=50 + index)) for index in range(8)]
        with self.assertRaisesRegex(ValueError, 'máximo'):
            preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of,
                item_refs=refs + [valid_ref],
            )
        with self.assertRaisesRegex(ValueError, 'al menos'):
            preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of, item_refs=[],
            )

    def test_servicio_es_reproducible_sin_escrituras_ia_ni_cache(self):
        manual = self._manual()
        ref = self._ref(manual)
        from core.services.epistemic_review_proposal import preparar_lote_revision

        with (
            patch('django.core.cache.cache.get') as cache_get,
            patch('django.core.cache.cache.set') as cache_set,
            patch('core.ai.gemini_client.generate_text') as generate_text,
            CaptureQueriesContext(connection) as queries,
        ):
            first = preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of, item_refs=[ref],
            )
            second = preparar_lote_revision(
                cliente_id=self.cliente.pk, as_of=self.as_of, item_refs=[ref],
            )

        self.assertEqual(first, second)
        cache_get.assert_not_called()
        cache_set.assert_not_called()
        generate_text.assert_not_called()
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
            for query in queries.captured_queries
        ))

    def test_comando_jsonl_no_tiene_apply(self):
        manual = self._manual()
        output = io.StringIO()
        call_command(
            'preparar_lote_revision_memoria', cliente=self.cliente.pk,
            as_of=self.as_of.isoformat(), items=[self._ref(manual)], stdout=output,
        )
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(lines[0]['tipo_registro'], 'item_revision')
        self.assertEqual(lines[-1]['tipo_registro'], 'meta')
        self.assertFalse(lines[-1]['execution_enabled'])
        command = load_command_class(
            get_commands()['preparar_lote_revision_memoria'],
            'preparar_lote_revision_memoria',
        )
        parser = command.create_parser('manage.py', 'preparar_lote_revision_memoria')
        self.assertNotIn('--apply', parser._option_string_actions)

    def test_validador_exige_cobertura_acciones_fingerprint_y_json(self):
        first = self._manual()
        second = self._manual(days_old=46)
        from core.services.epistemic_review_proposal import (
            preparar_lote_revision, validar_propuesta_revision,
        )
        manifest = preparar_lote_revision(
            cliente_id=self.cliente.pk, as_of=self.as_of,
            item_refs=[self._ref(first), self._ref(second)],
        )
        fingerprints = {item['id']: item['fingerprint'] for item in manifest['items']}
        proposed = {'schema_version': 1, 'items': [
            {
                'id': first.pk, 'fingerprint': fingerprints[first.pk],
                'action': 'mantener', 'motivo': 'La evidencia sigue siendo consistente.',
                'confidence_delta': 0.05,
            },
            {
                'id': second.pk, 'fingerprint': fingerprints[second.pk],
                'action': 'descartar', 'motivo': 'La hipótesis ya no debe mantenerse.',
            },
        ]}

        self.assertEqual(
            validar_propuesta_revision(json.dumps(proposed), manifest)['items'],
            proposed['items'],
        )
        invalid_cases = [
            '{',
            {'schema_version': 1, 'items': proposed['items'][:1]},
            {'schema_version': 1, 'items': [proposed['items'][0], proposed['items'][0]]},
            {'schema_version': 1, 'items': [
                dict(proposed['items'][0], id=999999), proposed['items'][1],
            ]},
            {'schema_version': 1, 'items': [
                dict(proposed['items'][0], action='inventada'), proposed['items'][1],
            ]},
            {'schema_version': 1, 'items': [
                dict(proposed['items'][0], fingerprint='0' * 64), proposed['items'][1],
            ]},
            {'schema_version': 1, 'items': [
                dict(proposed['items'][0], motivo=''), proposed['items'][1],
            ]},
        ]
        for invalid in invalid_cases:
            with self.assertRaises(ValueError):
                validar_propuesta_revision(invalid, manifest)

    def test_validador_aplica_contrato_estricto_de_delta_y_campos(self):
        manual = self._manual()
        from core.services.epistemic_review_proposal import (
            preparar_lote_revision, validar_propuesta_revision,
        )
        manifest = preparar_lote_revision(
            cliente_id=self.cliente.pk, as_of=self.as_of,
            item_refs=[self._ref(manual)],
        )
        base = {
            'id': manual.pk, 'fingerprint': manifest['items'][0]['fingerprint'],
            'motivo': 'Motivo estructurado',
        }
        valid = [
            dict(base, action='mantener', confidence_delta=0.0),
            dict(base, action='mantener', confidence_delta=0.05),
            dict(base, action='debilitar', confidence_delta=-0.10),
            dict(base, action='cuestionar', confidence_delta=-0.20),
            dict(base, action='descartar'),
        ]
        for item in valid:
            validar_propuesta_revision({'schema_version': 1, 'items': [item]}, manifest)
        invalid = [
            dict(base, action='mantener', confidence_delta=0.06),
            dict(base, action='debilitar', confidence_delta=-0.09),
            dict(base, action='cuestionar', confidence_delta=-0.10),
            dict(base, action='descartar', confidence_delta=0),
            dict(base, action='mantener', confidence_delta=0, extra=True),
            dict(base, action='mantener', confidence_delta=0, motivo='x' * 241),
        ]
        for item in invalid:
            with self.assertRaises(ValueError):
                validar_propuesta_revision({'schema_version': 1, 'items': [item]}, manifest)
