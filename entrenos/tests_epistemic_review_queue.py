import datetime
import io
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command, get_commands, load_command_class
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from joi.models import ManualDavid


class EpistemicReviewQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('epistemic-review-queue')
        self.cliente = self.user.cliente_perfil
        self.as_of = datetime.date(2026, 8, 22)

    def _manual(self, *, creado='2026-08-01', ultima=None, **overrides):
        data = {
            'user': self.user,
            'entrada': 'Contenido privado base',
            'origen': 'patron_detectado',
            'tipo': 'hipotesis',
            'estado': 'activa',
            'activa': True,
            'confianza': 0.7,
        }
        data.update(overrides)
        manual = ManualDavid.objects.create(**data)
        creado_dt = timezone.make_aware(datetime.datetime.fromisoformat(f'{creado}T10:00:00'))
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=creado_dt,
            ultima_evidencia=datetime.date.fromisoformat(ultima) if ultima else None,
        )
        manual.refresh_from_db()
        return manual

    def test_seleccion_y_exclusiones_semanticas(self):
        pendiente = self._manual(creado='2026-08-10', tipo='patron')
        vencida = self._manual(creado='2026-07-01', tipo='contradiccion')
        reciente_revisada = self._manual(creado='2026-06-01', ultima='2026-08-10')
        self._manual(creado='2026-07-01', origen='feedback_error')
        self._manual(creado='2026-07-01', estado='descartada')
        self._manual(creado='2026-07-01', activa=False)
        self._manual(creado='2026-07-01', tipo='preferencia')
        from core.services.epistemic_review_queue import planificar_revision_memoria

        result = planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )

        self.assertEqual(
            {item['id'] for item in result['items']},
            {pendiente.pk, vencida.pk},
        )
        self.assertEqual(
            {item['id']: item['classification'] for item in result['items']},
            {pendiente.pk: 'pendiente_revision', vencida.pk: 'revision_vencida'},
        )
        self.assertEqual(result['evaluados'], 3)
        self.assertEqual(result['total'], 2)
        self.assertNotIn(reciente_revisada.pk, {item['id'] for item in result['items']})

    def test_tipo_patron_entra_en_cola_pero_no_amplia_hallazgos_del_auditor(self):
        manual = self._manual(creado='2026-08-10', tipo='patron')
        from core.services.epistemic_registry import adaptar_manual_david, auditar_registros
        from core.services.epistemic_review_queue import planificar_revision_memoria

        queue = planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )
        findings = auditar_registros(
            [adaptar_manual_david(manual, operaciones_cierre=[])],
            as_of=self.as_of,
        )

        self.assertEqual([item['id'] for item in queue['items']], [manual.pk])
        self.assertEqual(queue['items'][0]['classification'], 'pendiente_revision')
        self.assertFalse({
            'pendiente_revision', 'revision_vencida',
        } & {item['code'] for item in findings})

    def test_orden_prioriza_vencida_cuestionada_despues_vencida_y_pendiente(self):
        pendiente = self._manual(creado='2026-08-01', estado='debilitada')
        vencida_nueva = self._manual(creado='2026-07-10', estado='activa')
        vencida_antigua = self._manual(creado='2026-06-01', estado='activa')
        cuestionada_nueva = self._manual(creado='2026-07-15', estado='cuestionada')
        cuestionada_antigua = self._manual(creado='2026-05-01', estado='cuestionada')
        from core.services.epistemic_review_queue import planificar_revision_memoria

        items = planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )['items']

        self.assertEqual([item['id'] for item in items], [
            cuestionada_antigua.pk, cuestionada_nueva.pk,
            vencida_antigua.pk, vencida_nueva.pk, pendiente.pk,
        ])
        self.assertEqual([item['ordinal'] for item in items], [1, 2, 3, 4, 5])

    def test_salida_no_revela_textos_privados_y_fingerprint_detecta_cambio(self):
        manual = self._manual(
            creado='2026-07-01', entrada='SECRETO ENTRADA',
            notas_revision='SECRETO NOTAS', hipotesis_contraria='SECRETO CONTRARIA',
        )
        from core.services.epistemic_review_queue import planificar_revision_memoria

        primero = planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )['items'][0]
        serializado = json.dumps(primero, ensure_ascii=False)
        self.assertNotIn('SECRETO', serializado)
        self.assertTrue(primero['has_revision_notes'])
        self.assertTrue(primero['has_opposing_hypothesis'])
        self.assertFalse(primero['has_source_message'])

        ManualDavid.objects.filter(pk=manual.pk).update(entrada='SECRETO CAMBIADO')
        segundo = planificar_revision_memoria(
            cliente_id=self.cliente.pk, as_of=self.as_of, limit=100,
        )['items'][0]
        self.assertNotEqual(primero['fingerprint'], segundo['fingerprint'])

    def test_reproducible_limit_y_solo_lectura_sin_ia_ni_cache(self):
        self._manual(creado='2026-06-01')
        self._manual(creado='2026-06-02')
        from core.services.epistemic_review_queue import planificar_revision_memoria

        with (
            patch('django.core.cache.cache.get') as cache_get,
            patch('django.core.cache.cache.set') as cache_set,
            patch('core.ai.gemini_client.generate_text') as generate_text,
            CaptureQueriesContext(connection) as queries,
        ):
            primero = planificar_revision_memoria(
                cliente_id=self.cliente.pk, as_of=self.as_of, limit=1,
            )
            segundo = planificar_revision_memoria(
                cliente_id=self.cliente.pk, as_of=self.as_of, limit=1,
            )

        self.assertEqual(primero, segundo)
        self.assertEqual(primero['emitidos'], 1)
        self.assertEqual(primero['truncados'], 1)
        self.assertTrue(primero['solo_lectura'])
        cache_get.assert_not_called()
        cache_set.assert_not_called()
        generate_text.assert_not_called()
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
            for query in queries.captured_queries
        ))

    def test_comando_jsonl_sin_apply(self):
        self._manual(creado='2026-07-01')
        output = io.StringIO()

        call_command(
            'planificar_revision_memoria', cliente=self.cliente.pk,
            as_of=self.as_of.isoformat(), limit=10, stdout=output,
        )

        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(lines[-1]['tipo_registro'], 'resumen')
        self.assertEqual(lines[-1]['counts_by_classification'], {'revision_vencida': 1})
        self.assertEqual(lines[0]['tipo_registro'], 'revision_memoria')
        command = load_command_class(get_commands()['planificar_revision_memoria'], 'planificar_revision_memoria')
        parser = command.create_parser('manage.py', 'planificar_revision_memoria')
        self.assertNotIn('--apply', parser._option_string_actions)
