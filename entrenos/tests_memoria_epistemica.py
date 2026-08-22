import datetime
import io
import json
import hashlib
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from diario.models import (
    CierreNocturnoOperacion, ProsocheDiario, ProsocheMes, SeguimientoVires,
)
from entrenos.models import (
    GymAdaptationProfile, GymDecisionLog, GymDecisionTrace,
    GymDecisionTraceEvaluation, PreferenciaPlanAprendida,
)
from joi.models import ManualDavid, NarrativaActiva, RecuerdoEmocional


class MemoriaEpistemicaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('epistemic_registry')
        self.cliente = self.user.cliente_perfil
        self.hoy = timezone.localdate()

    def _preferencia(self, **overrides):
        data = {
            'cliente': self.cliente,
            'tipo': PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            'estado': PreferenciaPlanAprendida.ESTADO_ACTIVA,
            'evidencia_count': 2,
            'origen_patron': 'distribucion_dias_reales_menores',
            'descripcion': 'Preferencia confirmada',
            'fecha_inicio': self.hoy,
            'ultima_confirmacion': self.hoy,
            'metadata': {'evidence_refs': ['probe:11', 'probe:14']},
        }
        data.update(overrides)
        return PreferenciaPlanAprendida.objects.create(**data)

    def test_preferencia_contractualmente_consentida_conserva_procedencia_exacta(self):
        preferencia = self._preferencia()
        from core.services.epistemic_registry import adaptar_preferencia_plan, auditar_registros

        record = adaptar_preferencia_plan(preferencia)

        self.assertEqual(record['schema_version'], 1)
        self.assertEqual(record['record_id'], f'entrenos.preferenciaplanaprendida:{preferencia.pk}')
        self.assertEqual(record['subject_id'], f'cliente:{self.cliente.pk}')
        self.assertEqual(record['level'], 'preferencia')
        self.assertEqual(record['evidence_refs'], ['probe:11', 'probe:14'])
        self.assertEqual(record['consent'], {
            'status': 'contract_asserted',
            'source': 'PreferenciaPlanAprendida.CONTRACT',
        })
        codes = {item['code'] for item in auditar_registros([record])}
        self.assertNotIn('preferencia_sin_consentimiento', codes)
        self.assertNotIn('evidencia_count_divergente', codes)

    def test_preferencia_revocada_conserva_historia_y_trazabilidad(self):
        preferencia = self._preferencia(
            estado=PreferenciaPlanAprendida.ESTADO_REVOCADA,
            metadata={
                'evidence_refs': ['probe:11', 'probe:14'],
                'revoked_at': self.hoy.isoformat(),
                'revocation_ref': 'decision:revocar:8',
            },
        )
        from core.services.epistemic_registry import adaptar_preferencia_plan, auditar_registros

        record = adaptar_preferencia_plan(preferencia)

        self.assertEqual(record['status'], 'revocada')
        self.assertEqual(record['valid_until'], self.hoy.isoformat())
        self.assertIn('decision:revocar:8', record['evidence_refs'])
        self.assertNotIn(
            'revocacion_sin_trazabilidad',
            {item['code'] for item in auditar_registros([record])},
        )

    def test_manual_automatico_de_cierre_no_se_presenta_como_corregido(self):
        mes = ProsocheMes.objects.create(usuario=self.user, mes='Agosto', año=self.hoy.year)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=self.hoy, cierre_confirmado_en=timezone.now(),
            cierre_version=1,
        )
        manual = ManualDavid.objects.create(
            user=self.user, entrada='Hipótesis automática', origen='patron_detectado',
            tipo='hipotesis', estado='activa', activa=True,
        )
        operacion = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key='11111111-1111-1111-1111-111111111111',
            expected_version=0, result_version=1, payload_hash='a' * 64,
            estado='completed',
            resultado={
                'schema_version': 2,
                'ledger': {'manual': [{'id': manual.pk, 'created': True}]},
            },
        )
        from core.services.epistemic_registry import adaptar_manual_david

        record = adaptar_manual_david(manual)

        self.assertEqual(record['derived_by'], 'diario.cierre_nocturno')
        self.assertEqual(record['evidence_refs'], [f'diario.cierrenocturnooperacion:{operacion.pk}'])
        self.assertEqual(record['conditions']['automatic_synthesis'], True)
        self.assertEqual(record['conditions']['correction_status'], 'not_recorded')
        self.assertNotEqual(record['consent']['status'], 'confirmed')

    def test_cierre_confirmado_con_operacion_devuelve_registro_exacto(self):
        mes = ProsocheMes.objects.create(usuario=self.user, mes='Agosto', año=self.hoy.year)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=self.hoy, cierre_confirmado_en=timezone.now(),
            cierre_version=2, cierre_payload_hash='b' * 64,
        )
        operacion = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key='22222222-2222-2222-2222-222222222222',
            expected_version=1, result_version=2, payload_hash='b' * 64,
            estado='completed', resultado={'schema_version': 2, 'ledger': {}},
        )
        from core.services.epistemic_registry import adaptar_cierre_diario

        record = adaptar_cierre_diario(entrada)

        self.assertIsInstance(record, dict)
        self.assertEqual(record['record_id'], f'diario.prosochediario:{entrada.pk}')
        self.assertEqual(record['subject_id'], f'user:{self.user.pk}')
        self.assertEqual(record['status'], 'confirmado')
        self.assertEqual(record['evidence_refs'], sorted([
            f'diario.prosochediario:{entrada.pk}',
            f'diario.cierrenocturnooperacion:{operacion.pk}',
        ]))
        self.assertEqual(record['conditions'], {
            'cierre_version': 2,
            'payload_hash_presente': True,
        })

    def test_recopilar_y_comando_aceptan_cierre_confirmado(self):
        mes = ProsocheMes.objects.create(usuario=self.user, mes='Agosto', año=self.hoy.year)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=self.hoy, cierre_confirmado_en=timezone.now(),
            cierre_version=1,
        )
        CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key='33333333-3333-3333-3333-333333333333',
            expected_version=0, result_version=1, payload_hash='c' * 64,
            estado='completed', resultado={'schema_version': 2, 'ledger': {}},
        )
        from core.services.epistemic_registry import recopilar_memoria

        resultado = recopilar_memoria(
            self.cliente.pk, desde=self.hoy, hasta=self.hoy, limit=100,
        )
        cierre_id = f'diario.prosochediario:{entrada.pk}'
        self.assertIn(cierre_id, [record['record_id'] for record in resultado['records']])

        salida = io.StringIO()
        call_command(
            'auditar_memoria_epistemica', cliente=self.cliente.pk,
            desde=self.hoy.isoformat(), hasta=self.hoy.isoformat(), limit=100,
            stdout=salida,
        )
        lineas = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        self.assertIn(cierre_id, [linea.get('record_id') for linea in lineas])

    def test_contradiccion_se_reporta_sin_elegir_ganador(self):
        manual = ManualDavid.objects.create(
            user=self.user, entrada='Necesita estructura fija', origen='patron_detectado',
            tipo='hipotesis', hipotesis_contraria='Necesita flexibilidad',
        )
        from core.services.epistemic_registry import adaptar_manual_david

        record = adaptar_manual_david(manual)

        self.assertEqual(record['contradictions'], [{
            'claim_fingerprint': hashlib.sha256(
                'Necesita flexibilidad'.encode('utf-8')
            ).hexdigest(),
            'status': 'reported',
            'winner': None,
        }])

    def test_perfil_declara_ventana_y_evidencia_ausentes(self):
        perfil = GymAdaptationProfile.objects.create(
            cliente=self.cliente, ejercicio='Press banca', decisiones_totales=3,
            decisiones_validadas=2, decisiones_fallidas=1, confianza='media',
        )
        from core.services.epistemic_registry import adaptar_perfil_adaptacion, auditar_registros

        record = adaptar_perfil_adaptacion(perfil)

        self.assertIn('valid_from', record['missing_fields'])
        self.assertIn('valid_until', record['missing_fields'])
        self.assertIn('evidence_refs', record['missing_fields'])
        self.assertIn('perfil_sin_ventana', {x['code'] for x in auditar_registros([record])})

    def test_puente_diario_expone_solo_senales_estructuradas(self):
        vires = SeguimientoVires.objects.create(
            usuario=self.user, fecha=self.hoy, horas_sueno=7.5,
            nivel_energia=4, molestia_zona='rodilla',
            notas='texto privado', molestia_nota='detalle privado',
        )
        from core.services.epistemic_registry import adaptar_seguimiento_vires

        record = adaptar_seguimiento_vires(vires)

        self.assertEqual(record['domain'], 'diario.puente_fisico')
        self.assertEqual(record['conditions']['signals']['horas_sueno'], 7.5)
        self.assertTrue(record['conditions']['free_text_excluded'])
        serializado = json.dumps(record, ensure_ascii=False)
        self.assertNotIn('texto privado', serializado)
        self.assertNotIn('detalle privado', serializado)

    def test_adaptadores_minimos_conservan_ids_de_modelo(self):
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press banca', accion='mantener',
            motivo='Sin cambio', confianza='media',
        )
        trace = GymDecisionTrace.objects.create(
            cliente=self.cliente, fecha=self.hoy, decision_estado='entrenar',
            causa_principal='sesion_hoy', senales_motor={'schema_version': 1},
        )
        evaluacion = GymDecisionTraceEvaluation.objects.create(
            trace=trace, resultado='neutral', senales_posteriores={'rpe': 7},
        )
        narrativa = NarrativaActiva.objects.create(
            user=self.user, capa_corta='Texto privado', estado='activa', version=1,
        )
        recuerdo = RecuerdoEmocional.objects.create(
            user=self.user, contenido='Contenido privado', contexto='Contexto privado',
        )
        from core.services.epistemic_registry import (
            adaptar_decision_log, adaptar_evaluacion_trace, adaptar_narrativa,
            adaptar_recuerdo, adaptar_trace,
        )

        records = [
            adaptar_decision_log(decision), adaptar_trace(trace),
            adaptar_evaluacion_trace(evaluacion), adaptar_narrativa(narrativa),
            adaptar_recuerdo(recuerdo),
        ]

        self.assertEqual(
            [record['record_id'] for record in records],
            [
                f'entrenos.gymdecisionlog:{decision.pk}',
                f'entrenos.gymdecisiontrace:{trace.pk}',
                f'entrenos.gymdecisiontraceevaluation:{evaluacion.pk}',
                f'joi.narrativaactiva:{narrativa.pk}',
                f'joi.recuerdoemocional:{recuerdo.pk}',
            ],
        )
        serializado = json.dumps(records, ensure_ascii=False)
        self.assertNotIn('Texto privado', serializado)
        self.assertNotIn('Contenido privado', serializado)
        self.assertNotIn('Contexto privado', serializado)

    def test_decision_validada_sigue_siendo_conocimiento_provisional(self):
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press banca', accion='mantener',
            motivo='Respuesta observada', confianza='alta', resultado='validada',
        )
        from core.services.epistemic_registry import adaptar_decision_log, auditar_registros

        record = adaptar_decision_log(decision)

        self.assertEqual(record['level'], 'conocimiento_provisional')
        self.assertEqual(record['conditions']['resultado'], 'validada')
        self.assertTrue(record['conditions']['candidate_for_consolidation'])
        self.assertIn('consolidation_rule', record['missing_fields'])
        self.assertIn('independent_evaluations', record['missing_fields'])
        self.assertNotIn(
            'promocion_sin_evidencia',
            {item['code'] for item in auditar_registros([record])},
        )

    def test_hallazgos_estructurados_no_dependenden_del_texto(self):
        manual = ManualDavid.objects.create(
            user=self.user, entrada='No debe inspeccionarse', origen='patron_detectado',
            tipo='hipotesis', estado='descartada', activa=True,
        )
        preferencia = self._preferencia(metadata={
            'consentimiento': False,
            'evidence_refs': ['probe:1'],
            'manual_david_id': manual.pk,
        })
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press', accion='mantener',
            motivo='No debe inspeccionarse', resultado='validada',
        )
        trace = GymDecisionTrace.objects.create(
            cliente=self.cliente, fecha=self.hoy, decision_estado='entrenar',
            senales_motor={},
        )
        revocada = self._preferencia(
            tipo=PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
            estado='revocada', metadata={'evidence_refs': ['probe:2', 'probe:3']},
        )
        from core.services.epistemic_registry import (
            adaptar_decision_log, adaptar_manual_david, adaptar_preferencia_plan,
            adaptar_trace, auditar_registros,
        )

        records = [
            adaptar_manual_david(manual), adaptar_preferencia_plan(preferencia),
            adaptar_decision_log(decision), adaptar_trace(trace),
            adaptar_preferencia_plan(revocada),
        ]
        sin_owner = dict(records[0], owner=None)
        promocion_sintetica = dict(
            records[2], level='conocimiento_consolidado', evidence_refs=[],
        )
        codes = {
            item['code'] for item in auditar_registros(
                records + [sin_owner, promocion_sintetica],
            )
        }

        self.assertTrue({
            'hipotesis_sin_vigencia', 'manual_descartada_aun_incluida',
            'preferencia_sin_consentimiento', 'preferencia_duplicada_manual_gym',
            'evidencia_count_divergente', 'promocion_sin_evidencia',
            'trace_version_no_identificable', 'revocacion_sin_trazabilidad',
            'registro_sin_owner',
        }.issubset(codes))

    def test_manual_debilitada_o_cuestionada_puede_seguir_activa(self):
        from core.services.epistemic_registry import adaptar_manual_david, auditar_registros

        for estado in ('debilitada', 'cuestionada', 'activa'):
            manual = ManualDavid.objects.create(
                user=self.user, entrada=f'Hipótesis {estado}',
                origen='patron_detectado', tipo='hipotesis',
                estado=estado, activa=True,
            )
            codes = {
                item['code']
                for item in auditar_registros([adaptar_manual_david(manual)])
            }
            self.assertNotIn('manual_descartada_aun_incluida', codes)
            self.assertNotIn('manual_estado_activa_divergente', codes)

        podada = ManualDavid.objects.create(
            user=self.user, entrada='Hipótesis podada', origen='patron_detectado',
            tipo='hipotesis', estado='activa', activa=False,
        )
        codes_poda = {
            item['code']
            for item in auditar_registros([adaptar_manual_david(podada)])
        }
        self.assertNotIn('manual_descartada_aun_incluida', codes_poda)
        self.assertNotIn('manual_estado_activa_divergente', codes_poda)

    def test_manual_descartada_pero_incluida_es_anomalia_operativa(self):
        manual = ManualDavid.objects.create(
            user=self.user, entrada='Hipótesis descartada',
            origen='patron_detectado', tipo='hipotesis',
            estado='descartada', activa=True,
        )
        from core.services.epistemic_registry import adaptar_manual_david, auditar_registros

        findings = auditar_registros([adaptar_manual_david(manual)])
        hallazgo = next(
            item for item in findings
            if item['code'] == 'manual_descartada_aun_incluida'
        )
        self.assertEqual(hallazgo['evidence'], {
            'estado_flag': 'descartada',
            'activa_flag': True,
        })

    def test_coleccion_es_determinista_sin_escrituras_ia_ni_cache(self):
        self._preferencia()
        from core.services.epistemic_registry import recopilar_memoria

        with (
            patch('django.core.cache.cache.get') as cache_get,
            patch('django.core.cache.cache.set') as cache_set,
            patch('core.ai.gemini_client.generate_text') as generate_text,
            CaptureQueriesContext(connection) as queries,
        ):
            primero = recopilar_memoria(self.cliente.pk, desde=self.hoy, hasta=self.hoy)
            segundo = recopilar_memoria(self.cliente.pk, desde=self.hoy, hasta=self.hoy)

        self.assertEqual(primero, segundo)
        cache_get.assert_not_called()
        cache_set.assert_not_called()
        generate_text.assert_not_called()
        mutaciones = [
            q['sql'] for q in queries.captured_queries
            if q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
        ]
        self.assertEqual(mutaciones, [])

    def test_comando_trunca_y_emite_resumen_estable(self):
        self._preferencia()
        ManualDavid.objects.create(
            user=self.user, entrada='Hipótesis', origen='patron_detectado', tipo='hipotesis',
        )
        salida = io.StringIO()

        call_command(
            'auditar_memoria_epistemica', cliente=self.cliente.pk,
            desde=self.hoy.isoformat(), hasta=self.hoy.isoformat(), limit=1,
            stdout=salida,
        )

        lineas = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        resumen = lineas[-1]
        self.assertEqual(resumen['tipo_registro'], 'resumen')
        self.assertEqual(resumen['emitidos'], 1)
        self.assertGreaterEqual(resumen['truncados'], 1)
        self.assertTrue(resumen['solo_lectura'])
        self.assertEqual(lineas[:-1], sorted(lineas[:-1], key=lambda x: (
            x['tipo_registro'], x.get('record_id', ''), x.get('code', ''),
        )))
