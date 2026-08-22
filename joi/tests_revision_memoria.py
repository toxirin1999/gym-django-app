import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from joi.models import ManualDavid


class RevisionMemoriaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('revision-memoria')
        self.cliente = self.user.cliente_perfil
        self.other = User.objects.create_user('revision-ajena')
        self.as_of = datetime.date(2026, 8, 22)

    def _manual(self, user=None, *, days_old=45, **overrides):
        ultima_evidencia = overrides.pop('ultima_evidencia', None)
        data = {
            'user': user or self.user,
            'entrada': 'Hipótesis privada', 'origen': 'patron_detectado',
            'tipo': 'hipotesis', 'estado': 'activa', 'activa': True,
            'confianza': 0.70, 'notas_revision': 'No sobrescribir',
        }
        data.update(overrides)
        manual = ManualDavid.objects.create(**data)
        created = self.as_of - datetime.timedelta(days=days_old)
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=timezone.make_aware(datetime.datetime.combine(created, datetime.time(10))),
            ultima_evidencia=ultima_evidencia,
        )
        manual.refresh_from_db()
        return manual

    def _apply(self, manual, action, **overrides):
        from core.services.epistemic_review_queue import fingerprint_manual
        from joi.services_revision_memoria import aplicar_revision_memoria
        data = {
            'cliente': self.cliente, 'actor': self.user, 'manual_id': manual.pk,
            'accion': action, 'expected_fingerprint': fingerprint_manual(manual),
            'idempotency_key': uuid.uuid4(), 'as_of': self.as_of,
            'motivo': 'Decisión humana explícita',
        }
        data.update(overrides)
        return aplicar_revision_memoria(**data)

    def test_cuatro_acciones_persisten_receipt_y_semantica_exacta(self):
        from joi.models import RevisionManualDavidOperacion

        confirmar = self._manual(confianza=0.98)
        op_confirmar = self._apply(confirmar, 'confirmar')
        confirmar.refresh_from_db()
        self.assertEqual((confirmar.estado, confirmar.activa, confirmar.confianza), ('activa', True, 1.0))
        self.assertEqual(confirmar.ultima_evidencia, self.as_of)

        cuestionar = self._manual()
        op_cuestionar = self._apply(cuestionar, 'cuestionar')
        cuestionar.refresh_from_db()
        self.assertEqual((cuestionar.estado, cuestionar.activa, cuestionar.confianza), ('cuestionada', True, 0.5))
        self.assertIsNone(cuestionar.ultima_evidencia)
        self.assertEqual(op_cuestionar.aplazada_hasta, self.as_of + datetime.timedelta(days=14))

        descartar = self._manual()
        op_descartar = self._apply(descartar, 'descartar')
        descartar.refresh_from_db()
        self.assertEqual((descartar.estado, descartar.activa, descartar.confianza), ('descartada', False, 0.0))
        self.assertEqual(descartar.ultima_evidencia, self.as_of)

        posponer = self._manual()
        before = (posponer.estado, posponer.activa, posponer.confianza, posponer.ultima_evidencia, posponer.notas_revision)
        op_posponer = self._apply(posponer, 'posponer')
        posponer.refresh_from_db()
        self.assertEqual(
            (posponer.estado, posponer.activa, posponer.confianza, posponer.ultima_evidencia, posponer.notas_revision),
            before,
        )
        self.assertEqual(op_posponer.aplazada_hasta, self.as_of + datetime.timedelta(days=14))
        self.assertEqual(RevisionManualDavidOperacion.objects.count(), 4)
        for operation in (op_confirmar, op_cuestionar, op_descartar, op_posponer):
            self.assertIn('fingerprint', operation.before_snapshot)
            self.assertIn('fingerprint', operation.after_snapshot)
            self.assertEqual(operation.schema_version, 1)

    def test_cola_reaparece_exactamente_dia_14_para_cuestionar_y_posponer(self):
        from core.services.epistemic_review_queue import planificar_revision_memoria
        for action in ('cuestionar', 'posponer'):
            manual = self._manual(days_old=60)
            self._apply(manual, action)
            day13 = planificar_revision_memoria(
                cliente_id=self.cliente.pk, as_of=self.as_of + datetime.timedelta(days=13), limit=100,
            )
            day14 = planificar_revision_memoria(
                cliente_id=self.cliente.pk, as_of=self.as_of + datetime.timedelta(days=14), limit=100,
            )
            self.assertNotIn(manual.pk, {item['id'] for item in day13['items']})
            self.assertIn(manual.pk, {item['id'] for item in day14['items']})

    def test_servicio_directo_rechaza_cooldown_dia13_y_acepta_dia14(self):
        from core.services.epistemic_review_queue import fingerprint_manual
        from joi.services_revision_memoria import aplicar_revision_memoria

        for initial_action in ('cuestionar', 'posponer'):
            manual = self._manual(days_old=60)
            self._apply(manual, initial_action)
            manual.refresh_from_db()
            request = {
                'cliente': self.cliente, 'actor': self.user, 'manual_id': manual.pk,
                'accion': 'confirmar', 'expected_fingerprint': fingerprint_manual(manual),
                'motivo': 'Revisión posterior al aplazamiento',
            }
            with self.assertRaisesRegex(ValueError, 'aplazada'):
                aplicar_revision_memoria(
                    **request, idempotency_key=uuid.uuid4(),
                    as_of=self.as_of + datetime.timedelta(days=13),
                )
            receipt = aplicar_revision_memoria(
                **request, idempotency_key=uuid.uuid4(),
                as_of=self.as_of + datetime.timedelta(days=14),
            )
            self.assertEqual(receipt.accion, 'confirmar')

    def test_stale_ownership_e_idempotencia_colision(self):
        from joi.services_revision_memoria import aplicar_revision_memoria
        manual = self._manual()
        key = uuid.uuid4()
        receipt = self._apply(manual, 'confirmar', idempotency_key=key)
        same = self._apply(
            manual, 'confirmar', idempotency_key=key,
            expected_fingerprint=receipt.expected_fingerprint,
        )
        self.assertEqual(receipt.pk, same.pk)
        with self.assertRaisesRegex(ValueError, 'colisión'):
            self._apply(
                manual, 'descartar', idempotency_key=key,
                expected_fingerprint=receipt.expected_fingerprint,
            )
        stale = self._manual()
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self._apply(stale, 'confirmar', expected_fingerprint='0' * 64)
        foreign = self._manual(user=self.other)
        with self.assertRaisesRegex(ValueError, 'pertenece'):
            self._apply(foreign, 'confirmar')

    def test_transaccion_revierte_manual_si_falla_receipt(self):
        manual = self._manual()
        before = (manual.estado, manual.activa, manual.confianza, manual.ultima_evidencia)
        with patch('joi.models.RevisionManualDavidOperacion.objects.create', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self._apply(manual, 'descartar')
        manual.refresh_from_db()
        self.assertEqual((manual.estado, manual.activa, manual.confianza, manual.ultima_evidencia), before)

    def test_deshacer_restaura_cada_accion_y_es_idempotente(self):
        from joi.services_revision_memoria import deshacer_revision_memoria
        for action in ('confirmar', 'cuestionar', 'descartar', 'posponer'):
            manual = self._manual()
            before = (manual.estado, manual.activa, manual.confianza, manual.ultima_evidencia)
            original = self._apply(manual, action)
            key = uuid.uuid4()
            undo = deshacer_revision_memoria(
                cliente=self.cliente, actor=self.user, operacion_id=original.pk,
                idempotency_key=key, as_of=self.as_of,
            )
            manual.refresh_from_db()
            self.assertEqual((manual.estado, manual.activa, manual.confianza, manual.ultima_evidencia), before)
            self.assertEqual(undo.reversa_de_id, original.pk)
            same = deshacer_revision_memoria(
                cliente=self.cliente, actor=self.user, operacion_id=original.pk,
                idempotency_key=key, as_of=self.as_of,
            )
            self.assertEqual(same.pk, undo.pk)
            with self.assertRaisesRegex(ValueError, 'deshecha'):
                deshacer_revision_memoria(
                    cliente=self.cliente, actor=self.user, operacion_id=original.pk,
                    idempotency_key=uuid.uuid4(), as_of=self.as_of,
                )

    def test_deshacer_rechaza_estado_stale_y_actor_ajeno(self):
        from joi.services_revision_memoria import deshacer_revision_memoria
        manual = self._manual()
        original = self._apply(manual, 'confirmar')
        ManualDavid.objects.filter(pk=manual.pk).update(confianza=0.33)
        with self.assertRaisesRegex(ValueError, 'cambió'):
            deshacer_revision_memoria(
                cliente=self.cliente, actor=self.user, operacion_id=original.pk,
                idempotency_key=uuid.uuid4(), as_of=self.as_of,
            )
        with self.assertRaisesRegex(ValueError, 'actor'):
            deshacer_revision_memoria(
                cliente=self.cliente, actor=self.other, operacion_id=original.pk,
                idempotency_key=uuid.uuid4(), as_of=self.as_of,
            )

    def test_confirmacion_humana_aporta_consentimiento_y_procedencia_sin_consolidar(self):
        manual = self._manual()
        operation = self._apply(manual, 'confirmar')
        manual.refresh_from_db()
        from core.services.epistemic_registry import adaptar_manual_david
        record = adaptar_manual_david(manual, operaciones_cierre=[])
        self.assertEqual(record['consent']['status'], 'user_confirmed')
        self.assertIn(f'joi.revisionmanualdavidoperacion:{operation.pk}', record['evidence_refs'])
        self.assertNotEqual(record['level'], 'conocimiento_consolidado')

    def test_guard_legacy_excluye_feedback_reciente_y_aplazada(self):
        eligible = self._manual(days_old=60)
        feedback = self._manual(days_old=60, origen='feedback_error', entrada='FEEDBACK')
        recent = self._manual(days_old=60, ultima_evidencia=self.as_of - datetime.timedelta(days=10), entrada='RECIENTE')
        postponed = self._manual(days_old=60, entrada='APLAZADA')
        self._apply(postponed, 'posponer')
        fake_response = SimpleNamespace(content=[SimpleNamespace(
            text=f'{eligible.pk}|MANTENER|Sigue vigente',
        )])
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: fake_response))
        from joi.services import revisar_manual_david
        with (
            patch('joi.services._cliente_anthropic', return_value=fake_client),
            patch('joi.services.construir_contexto', return_value={}),
        ):
            result = revisar_manual_david(self.cliente, as_of=self.as_of)
        self.assertEqual(result['revisadas'], 1)
        self.assertEqual(result['actualizadas'], 1)
        for manual in (feedback, recent, postponed):
            manual.refresh_from_db()
            self.assertEqual(manual.notas_revision, 'No sobrescribir')

    def test_modelo_migration_es_portable_mysql_y_servicio_no_usa_ia(self):
        from joi.models import RevisionManualDavidOperacion
        conditional = [
            constraint for constraint in RevisionManualDavidOperacion._meta.constraints
            if getattr(constraint, 'condition', None) is not None
        ]
        self.assertEqual(conditional, [])
        self.assertTrue(RevisionManualDavidOperacion._meta.indexes)
        manual = self._manual()
        with patch('core.ai.gemini_client.generate_text') as generate_text:
            self._apply(manual, 'posponer')
        generate_text.assert_not_called()

    def test_traduccion_futura_no_inventa_debilitar_como_accion_humana(self):
        from core.services.epistemic_review_proposal import traducir_accion_a_revision_humana
        self.assertEqual(traducir_accion_a_revision_humana('mantener'), 'confirmar')
        self.assertEqual(traducir_accion_a_revision_humana('cuestionar'), 'cuestionar')
        self.assertEqual(traducir_accion_a_revision_humana('descartar'), 'descartar')
        with self.assertRaisesRegex(ValueError, 'debilitar'):
            traducir_accion_a_revision_humana('debilitar')
