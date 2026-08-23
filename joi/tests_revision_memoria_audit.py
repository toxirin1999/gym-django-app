import datetime
import io
import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.services.epistemic_review_queue import fingerprint_manual
from joi.models import ManualDavid, RevisionManualDavidOperacion
from joi.services_revision_memoria import aplicar_revision_memoria, deshacer_revision_memoria


class RevisionMemoriaAuditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('audit-revision')
        self.cliente = self.user.cliente_perfil
        self.other = User.objects.create_user('audit-revision-other')
        self.as_of = datetime.date(2026, 8, 23)

    def _manual(self, *, user=None, entrada='Texto privado de memoria'):
        manual = ManualDavid.objects.create(
            user=user or self.user,
            entrada=entrada,
            notas_revision='Nota privada que nunca debe salir',
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

    def _apply(self, manual, action, *, as_of=None, motivo='Motivo privado'):
        return aplicar_revision_memoria(
            cliente=self.cliente,
            actor=self.user,
            manual_id=manual.pk,
            accion=action,
            expected_fingerprint=fingerprint_manual(manual),
            idempotency_key=uuid.uuid4(),
            as_of=as_of or self.as_of,
            motivo=motivo,
        )

    def _audit(self, *, as_of=None, limit=500):
        from joi.services_revision_memoria_audit import auditar_revision_memoria
        return auditar_revision_memoria(
            cliente_id=self.cliente.pk,
            as_of=as_of or self.as_of,
            limit=limit,
        )

    def test_ledger_limpio_confirmar_descartar_y_undo_no_emite_hallazgos(self):
        confirmado = self._manual(entrada='Confirmada privada')
        self._apply(confirmado, 'confirmar')
        descartado = self._manual(entrada='Descartada privada')
        self._apply(descartado, 'descartar')
        restaurado = self._manual(entrada='Restaurada privada')
        original = self._apply(restaurado, 'confirmar')
        deshacer_revision_memoria(
            cliente=self.cliente,
            actor=self.user,
            operacion_id=original.pk,
            idempotency_key=uuid.uuid4(),
            as_of=self.as_of,
        )

        result = self._audit()

        self.assertEqual(result['findings'], [])
        self.assertEqual(result['summary']['totals']['manuals'], 3)
        self.assertEqual(result['summary']['totals']['operations'], 4)
        self.assertEqual(result['summary']['totals']['effective'], 2)
        self.assertTrue(result['summary']['solo_lectura'])

    def test_detecta_ownership_snapshot_semantica_y_stale_como_codigos_separados(self):
        ownership = self._manual()
        op_owner = self._apply(ownership, 'confirmar')
        RevisionManualDavidOperacion.objects.filter(pk=op_owner.pk).update(actor=self.other)

        malformed = self._manual(entrada='Malformed privada')
        op_bad = self._apply(malformed, 'posponer')
        after = dict(op_bad.after_snapshot)
        after['fingerprint'] = 'no-es-sha256'
        after['confianza'] = 0.1
        RevisionManualDavidOperacion.objects.filter(pk=op_bad.pk).update(after_snapshot=after)

        stale = self._manual(entrada='Stale privado')
        self._apply(stale, 'confirmar')
        ManualDavid.objects.filter(pk=stale.pk).update(confianza=0.33)

        codes = [item['code'] for item in self._audit()['findings']]

        self.assertIn('operation_actor_mismatch', codes)
        self.assertIn('snapshot_fingerprint_invalid', codes)
        self.assertIn('action_semantics_mismatch', codes)
        self.assertIn('current_state_stale_external', codes)

    def test_cooldown_dia13_y_dia14_coincide_con_cola_y_authority(self):
        for action in ('posponer', 'cuestionar'):
            with self.subTest(action=action):
                RevisionManualDavidOperacion.objects.all().delete()
                ManualDavid.objects.all().delete()
                manual = self._manual(entrada=f'Cooldown privado {action}')
                self._apply(manual, action)

                day13 = self._audit(as_of=self.as_of + datetime.timedelta(days=13))
                day14 = self._audit(as_of=self.as_of + datetime.timedelta(days=14))

                self.assertEqual(day13['findings'], [])
                self.assertEqual(day13['summary']['totals']['queue'], 0)
                self.assertEqual(day13['summary']['totals']['authority'], 0)
                self.assertEqual(day14['findings'], [])
                self.assertEqual(day14['summary']['totals']['queue'], 1)
                self.assertEqual(day14['summary']['totals']['authority'], 1)

    def test_salida_es_privada_determinista_y_limit_solo_trunca_hallazgos(self):
        manual = self._manual(entrada='SECRETO ENTRADA')
        op = self._apply(manual, 'posponer', motivo='SECRETO MOTIVO')
        RevisionManualDavidOperacion.objects.filter(pk=op.pk).update(
            expected_fingerprint='x', schema_version=99,
        )

        first = self._audit(limit=1)
        second = self._audit(limit=1)
        serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)

        self.assertEqual(first, second)
        self.assertEqual(len(first['findings']), 1)
        self.assertGreater(first['summary']['hallazgos_total'], 1)
        self.assertEqual(
            first['summary']['truncados'],
            first['summary']['hallazgos_total'] - 1,
        )
        for private in ('SECRETO ENTRADA', 'SECRETO MOTIVO', 'before_snapshot', 'after_snapshot'):
            self.assertNotIn(private, serialized)

    def test_comando_jsonl_no_apply_no_escribe_ni_usa_ia_o_cache(self):
        manual = self._manual()
        self._apply(manual, 'confirmar')
        before = (
            ManualDavid.objects.count(),
            RevisionManualDavidOperacion.objects.count(),
        )
        output = io.StringIO()

        with (
            patch('core.ai.gemini_client.generate_text') as ai,
            patch('django.core.cache.cache.set') as cache_set,
        ):
            call_command(
                'auditar_revision_memoria',
                cliente=self.cliente.pk,
                as_of=self.as_of.isoformat(),
                limit=100,
                stdout=output,
            )

        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows[-1]['tipo_registro'], 'resumen')
        self.assertTrue(rows[-1]['solo_lectura'])
        self.assertEqual(before, (
            ManualDavid.objects.count(),
            RevisionManualDavidOperacion.objects.count(),
        ))
        ai.assert_not_called()
        cache_set.assert_not_called()
        with self.assertRaises((CommandError, TypeError)):
            call_command(
                'auditar_revision_memoria', cliente=self.cliente.pk,
                as_of=self.as_of.isoformat(), apply=True,
            )
