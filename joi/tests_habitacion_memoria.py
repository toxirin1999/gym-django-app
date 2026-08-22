import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from joi.models import ManualDavid


class HabitacionMemoriaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('habitacion-memoria')
        self.cliente = self.user.cliente_perfil
        self.other = User.objects.create_user('habitacion-ajena')
        self.as_of = datetime.date(2026, 8, 22)

    def _manual(self, user=None, *, days_old=45, **overrides):
        data = {
            'user': user or self.user,
            'entrada': 'Una lectura que merece revisión',
            'origen': 'patron_detectado',
            'tipo': 'hipotesis',
            'estado': 'activa',
            'activa': True,
            'confianza': 0.7,
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

    def test_servicio_oculta_bloque_si_cola_vacia(self):
        from joi.services_memoria_habitacion import construir_memoria_habitacion

        self.assertIsNone(construir_memoria_habitacion(
            cliente=self.cliente, as_of=self.as_of,
        ))

    def test_servicio_expone_una_memoria_con_conteo_y_clasificacion_humana(self):
        first = self._manual(estado='cuestionada', entrada='Primera memoria')
        self._manual(days_old=10, entrada='Segunda memoria')
        from joi.services_memoria_habitacion import construir_memoria_habitacion

        result = construir_memoria_habitacion(
            cliente=self.cliente, as_of=self.as_of, requested_id=first.pk,
        )

        self.assertEqual(result['count'], 2)
        self.assertEqual(result['current']['id'], first.pk)
        self.assertEqual(result['current']['texto'], 'Primera memoria')
        self.assertEqual(result['current']['classification_label'], 'Necesita una nueva mirada')
        self.assertEqual(result['current']['estado_label'], 'Cuestionada')
        self.assertEqual(result['current']['ordinal'], 1)
        self.assertEqual(result['current']['total'], 2)
        self.assertEqual(result['current']['age_days'], 45)
        self.assertNotIn('notas_revision', result['current'])
        self.assertNotIn('hipotesis_contraria', result['current'])

    def test_query_valida_selecciona_y_ajena_cae_al_primero_sin_filtrar_existencia(self):
        first = self._manual(entrada='Propia uno')
        second = self._manual(days_old=44, entrada='Propia dos')
        foreign = self._manual(user=self.other, entrada='AJENA PRIVADA')
        from joi.services_memoria_habitacion import construir_memoria_habitacion

        valid = construir_memoria_habitacion(
            cliente=self.cliente, as_of=self.as_of, requested_id=second.pk,
        )
        foreign_attempt = construir_memoria_habitacion(
            cliente=self.cliente, as_of=self.as_of, requested_id=foreign.pk,
        )
        invalid = construir_memoria_habitacion(
            cliente=self.cliente, as_of=self.as_of, requested_id=999999,
        )

        self.assertEqual(valid['current']['id'], second.pk)
        self.assertEqual(foreign_attempt['current']['id'], first.pk)
        self.assertEqual(invalid['current']['id'], first.pk)
        self.assertNotIn('AJENA PRIVADA', str(foreign_attempt))

    def test_estado_interno_se_traduce_con_fallback_neutro(self):
        activa = self._manual(entrada='Activa')
        debilitada = self._manual(days_old=46, estado='debilitada', entrada='Débil')
        legacy = self._manual(days_old=47, estado='legacy', entrada='Legacy')
        from joi.services_memoria_habitacion import construir_memoria_habitacion

        labels = {}
        for manual in (activa, debilitada, legacy):
            result = construir_memoria_habitacion(
                cliente=self.cliente, as_of=self.as_of, requested_id=manual.pk,
            )
            labels[manual.pk] = result['current']['estado_label']

        self.assertEqual(labels, {
            activa.pk: 'En uso',
            debilitada.pk: 'Con reservas',
            legacy.pk: 'En revisión',
        })

    def test_feedback_error_no_aparece_y_servicio_no_escribe_ni_usa_ia_cache(self):
        self._manual()
        self._manual(origen='feedback_error', entrada='Corrección privada')
        from joi.services_memoria_habitacion import construir_memoria_habitacion

        with (
            patch('django.core.cache.cache.get') as cache_get,
            patch('django.core.cache.cache.set') as cache_set,
            patch('core.ai.gemini_client.generate_text') as generate_text,
            CaptureQueriesContext(connection) as queries,
        ):
            result = construir_memoria_habitacion(
                cliente=self.cliente, as_of=self.as_of,
            )

        self.assertEqual(result['count'], 1)
        cache_get.assert_not_called()
        cache_set.assert_not_called()
        generate_text.assert_not_called()
        self.assertFalse(any(
            query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
            for query in queries.captured_queries
        ))

    def test_template_escapa_texto_y_solo_ofrece_navegacion_get(self):
        context = {
            'estado': 'calla', 'joi_estado': 'SILENCIO', 'hay_sedimento': False,
            'texto_vigilia': 'Presente.', 'joi_texto_motivo': 'Sin señales.',
            'joi_motivo': 'sin_senales', 'mensaje': None, 'narrativa': None,
            'entrenos_totales': None,
            'memoria_revision': {
                'count': 2,
                'current': {
                    'id': 7, 'texto': '<script>privado</script>', 'estado': 'activa',
                    'estado_label': 'En uso',
                    'classification_label': 'Necesita una nueva mirada',
                    'age_days': 45, 'ordinal': 1, 'total': 2,
                },
                'previous_id': None, 'next_id': 8,
            },
        }

        html = render_to_string('joi/habitacion.html', context)
        block = html.split('data-testid="memoria-review"', 1)[1].split('</details>', 1)[0]

        self.assertIn('Memoria · 2 por revisar', html)
        self.assertIn('&lt;script&gt;privado&lt;/script&gt;', html)
        self.assertNotIn('<script>privado</script>', html)
        self.assertIn('?memoria=8', block)
        self.assertNotIn('<form', block)
        self.assertNotIn('<button', block)
        self.assertNotIn('method="post"', block.lower())
        self.assertNotIn('--apply', block)
        self.assertNotIn(' open', block.split('>', 1)[0])
        self.assertIn('Estado En uso', block)
        self.assertIn('white-space: pre-wrap', html)
        self.assertIn('overflow-wrap: anywhere', html)
        self.assertIn('max-height:', html)
        self.assertIn('overflow-y: auto', html)

    def test_view_requiere_auth_resuelve_contexto_y_no_revela_memoria_ajena(self):
        own = self._manual(entrada='Propia visible')
        foreign = self._manual(user=self.other, entrada='AJENA OCULTA')
        self.assertEqual(self.client.get(reverse('joi:joi_habitacion')).status_code, 302)
        self.client.force_login(self.user)

        with (
            patch('joi.services.generar_mensaje_joi', return_value=None),
            patch('django.core.cache.cache.get', return_value=None),
            patch('django.core.cache.cache.set'),
        ):
            response = self.client.get(
                reverse('joi:joi_habitacion'), {'memoria': foreign.pk},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['memoria_revision']['current']['id'], own.pk)
        self.assertContains(response, 'Propia visible')
        self.assertNotContains(response, 'AJENA OCULTA')
        self.assertContains(
            response,
            'aria-label="JOI Habitación estado SILENCIO">',
            html=False,
        )

    def test_bloque_memoria_esta_entre_motivo_y_postura(self):
        html = render_to_string('joi/habitacion.html', {
            'estado': 'calla', 'joi_estado': 'SILENCIO', 'hay_sedimento': False,
            'texto_vigilia': 'Presente.', 'joi_texto_motivo': 'Sin señales.',
            'joi_motivo': 'sin_senales', 'mensaje': None,
            'narrativa': SimpleNamespace(capa_corta='Postura', capa_media='', capa_larga=''),
            'entrenos_totales': None,
            'memoria_revision': {
                'count': 1,
                'current': {
                    'id': 7, 'texto': 'Memoria', 'estado': 'activa',
                    'estado_label': 'En uso',
                    'classification_label': 'Pendiente de primera revisión',
                    'age_days': 10, 'ordinal': 1, 'total': 1,
                },
                'previous_id': None, 'next_id': None,
            },
        })

        self.assertLess(html.index('Por qué este estado'), html.index('data-testid="memoria-review"'))
        self.assertLess(html.index('data-testid="memoria-review"'), html.index('id="postura-zona"'))

    def test_reverse_habitacion_permanece_estable(self):
        self.assertEqual(reverse('joi:joi_habitacion'), '/joi/habitacion/')
