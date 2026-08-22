from datetime import date, timedelta
from unittest.mock import patch
from io import StringIO
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionVersion
from rehab.models import (ContratoRiesgoGymFaseRehab, EpisodioRehab,
                          FaseProtocolo, ProtocoloRehab, RegistroDiarioRehab)
from rutinas.models import Rutina


class FrenoRehabGymTests(TestCase):
    def setUp(self):
        self.hoy = date(2026, 8, 22)
        self.cliente = Cliente.objects.get(user=User.objects.create_user('rehab-hold'))
        protocolo = ProtocoloRehab.objects.create(
            slug='rodilla', version=1, nombre='Rodilla', zona='rodilla', descripcion='x',
            fuente_referencia='x', criterios_alta={}, advertencias='x')
        self.fase = FaseProtocolo.objects.create(
            protocolo=protocolo, orden=1, slug='fase-1', nombre='F1', objetivo='x',
            duracion_minima_dias=1, duracion_tipica_dias=7, descripcion='x')
        self.episodio = EpisodioRehab.objects.create(
            cliente=self.cliente, protocolo=protocolo, protocolo_version=1,
            fase_actual=self.fase, lateralidad='bilateral', fecha_inicio=self.hoy-timedelta(days=8),
            fase_actual_desde=self.hoy-timedelta(days=8), dolor_basal_inicial=5)
        self.contrato = ContratoRiesgoGymFaseRehab.objects.create(
            fase=self.fase, version=1, risk_tags=['carga_dominante_rodilla'])

    def _registro(self, pain=5, age=0, red=False):
        return RegistroDiarioRehab.objects.create(
            episodio=self.episodio, fecha=self.hoy-timedelta(days=age), dolor_manana=pain,
            rigidez_manana=2, bandera_roja=red)

    def _habilitar(self):
        from rehab.services.gym_risk_contract_service import publicar_sucesora
        self.contrato = publicar_sucesora(self.contrato, execution_enabled=True)

    def test_disabled_snapshot_is_explicit_and_has_no_execution(self):
        record = self._registro()
        from core.services.physical_snapshot import build_physical_snapshot
        item = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertFalse(item['executive_capacity']['can_derive_restrictions'])
        self.assertEqual(item['executive_capacity']['reason'], 'contract_execution_disabled')
        self.assertEqual(item['executive_assessment']['record_id'], record.pk)
        self.assertTrue(item['executive_assessment']['would_hold'])

    def test_execution_enabled_is_immutable_and_successor_preserves_or_changes_it(self):
        self.contrato.execution_enabled = True
        with self.assertRaisesMessage(ValidationError, 'inmutable'):
            self.contrato.save()
        from rehab.services.gym_risk_contract_service import publicar_sucesora
        successor = publicar_sucesora(self.contrato, execution_enabled=True)
        self.assertFalse(ContratoRiesgoGymFaseRehab.objects.get(pk=self.contrato.pk).activo)
        self.assertTrue(successor.execution_enabled)
        self.assertEqual(successor.version, self.contrato.version + 1)

    def test_snapshot_negative_cases_are_explicit_and_red_flag_never_executes(self):
        self._habilitar()
        from core.services.physical_snapshot import build_physical_snapshot
        no_data = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertEqual(no_data['executive_capacity']['reason'], 'no_daily_record')
        record = self._registro(pain=4)
        low = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertEqual(low['executive_capacity']['reason'], 'pain_below_hold_threshold')
        record.delete()
        record = self._registro(pain=8, age=4)
        stale = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertEqual(stale['executive_capacity']['reason'], 'stale_daily_record')
        record.delete()
        red_record = self._registro(pain=8, red=True)
        red = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertFalse(red['executive_capacity']['can_derive_restrictions'])
        self.assertEqual(red['executive_capacity']['reason'], 'red_flag_reported')
        self.assertEqual(red['red_flag_report']['record_id'], red_record.pk)
        self.assertFalse(red['red_flag_report']['executed_by_rehab_gym_hold'])

    def test_enabled_fresh_pain_embeds_exact_contract_and_assessment(self):
        self._habilitar()
        record = self._registro()
        from core.services.physical_snapshot import build_physical_snapshot
        item = build_physical_snapshot(self.cliente, self.hoy)['signals']['active_rehab']['items'][0]
        self.assertTrue(item['executive_capacity']['can_derive_restrictions'])
        self.assertEqual(item['gym_risk_contract']['id'], self.contrato.pk)
        self.assertEqual(item['gym_risk_contract']['version'], self.contrato.version)
        self.assertEqual(item['gym_risk_contract']['schema_version'], 1)
        self.assertEqual(item['executive_assessment'], {
            'reason': 'rehab_recent_pain_hold', 'record_id': record.pk, 'pain': 5,
            'age_days': 0, 'red_flag': False, 'would_hold': True,
        })

    def test_overlay_caps_post_plan_at_last_baseline_and_is_idempotent(self):
        self._habilitar()
        self._registro()
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='Base'),
            fecha=self.hoy-timedelta(days=2))
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Sentadilla', peso_kg=80, series=3,
            repeticiones=8, completado=True)
        from core.services.physical_snapshot import build_physical_snapshot
        from entrenos.services.freno_rehab_gym_service import aplicar_freno_rehab_gym
        snapshot = build_physical_snapshot(self.cliente, self.hoy)
        entrada = [{'nombre': 'Sentadilla', 'risk_tags': ['carga_dominante_rodilla'],
                    'peso_kg': 90, 'series': 4, 'repeticiones': 10,
                    'progresion_aplicada': True}]
        salida, cambios = aplicar_freno_rehab_gym(self.cliente, entrada, snapshot, self.hoy)
        segunda, cambios_2 = aplicar_freno_rehab_gym(self.cliente, salida, snapshot, self.hoy)
        self.assertEqual((salida[0]['peso_kg'], salida[0]['series'], salida[0]['repeticiones']), (80, 3, 8))
        self.assertEqual(salida, segunda)
        self.assertEqual(cambios, cambios_2)
        self.assertEqual(salida[0]['postura_local'], 'sostener')
        self.assertTrue(salida[0]['progresion_bloqueada'])

    def test_overlay_disabled_unmatched_and_missing_baseline_have_no_quantitative_effect(self):
        self._registro()
        from core.services.physical_snapshot import build_physical_snapshot
        from entrenos.services.freno_rehab_gym_service import aplicar_freno_rehab_gym
        disabled = build_physical_snapshot(self.cliente, self.hoy)
        proposal = [{'nombre': 'Sentadilla', 'risk_tags': ['carga_dominante_rodilla'],
                     'peso_kg': 90, 'series': 4, 'repeticiones': 10}]
        output, changes = aplicar_freno_rehab_gym(self.cliente, proposal, disabled, self.hoy)
        self.assertEqual(output, proposal)
        self.assertEqual(changes, [])
        self._habilitar()
        enabled = build_physical_snapshot(self.cliente, self.hoy)
        unmatched = [{'nombre': 'Press', 'risk_tags': ['hombro'], 'peso_kg': 90}]
        self.assertEqual(aplicar_freno_rehab_gym(
            self.cliente, unmatched, enabled, self.hoy), (unmatched, []))
        output, changes = aplicar_freno_rehab_gym(self.cliente, proposal, enabled, self.hoy)
        self.assertEqual(output[0]['peso_kg'], 90)
        self.assertEqual(changes, [])
        self.assertEqual(output[0]['rehab_evidence'][0]['reason'], 'insufficient_baseline')
        self.assertFalse(output[0]['rehab_evidence'][0]['quantitative_hold_applied'])

    def test_overlay_preserves_post_plan_reduction_and_existing_injury_protection(self):
        self._habilitar()
        self._registro()
        routine = Rutina.objects.create(nombre='Base protectora')
        older = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=routine, fecha=self.hoy-timedelta(days=10),
            fecha_ejecucion=self.hoy-timedelta(days=2))
        future_planned_but_earlier_effective = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=routine, fecha=self.hoy+timedelta(days=2),
            fecha_ejecucion=self.hoy-timedelta(days=1))
        EjercicioRealizado.objects.create(entreno=older, nombre_ejercicio='Sentadilla',
            peso_kg=80, series=4, repeticiones=10)
        latest = EjercicioRealizado.objects.create(
            entreno=future_planned_but_earlier_effective, nombre_ejercicio='Sentadilla',
            peso_kg=70, series=3, repeticiones=8)
        from core.services.physical_snapshot import build_physical_snapshot
        from entrenos.services.freno_rehab_gym_service import aplicar_freno_rehab_gym
        exercise = {'nombre': 'Sentadilla segura', 'nombre_original': 'Sentadilla',
                    'risk_tags': ['carga_dominante_rodilla'], 'peso_kg': 60,
                    'series': 2, 'repeticiones': 6, 'sustituido': True,
                    'motivo_sustitucion': 'lesion', 'is_recovery_load': True}
        output, changes = aplicar_freno_rehab_gym(
            self.cliente, [exercise], build_physical_snapshot(self.cliente, self.hoy), self.hoy)
        final = output[0]
        self.assertEqual((final['peso_kg'], final['series'], final['repeticiones']), (60, 2, 6))
        self.assertEqual(final['nombre'], 'Sentadilla segura')
        self.assertEqual(final['motivo_sustitucion'], 'lesion')
        self.assertTrue(final['is_recovery_load'])
        self.assertEqual(final['rehab_baseline']['exercise_record_id'], latest.pk)
        self.assertEqual(changes[0]['dimensions'], [])

    @patch('entrenos.services.freno_rehab_gym_service.aplicar_freno_rehab_gym')
    @patch('entrenos.services.plan_dinamico_service.aplicar_plan_dinamico')
    @patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy')
    def test_authority_applies_rehab_after_dynamic(self, base, dynamic, rehab):
        exercise = {'nombre': 'Sentadilla', 'series': 4, 'repeticiones': 10}
        base.return_value = {'estado': 'entrenar', 'entrenamiento': {'ejercicios': [exercise]}}
        dynamic.return_value = ([dict(exercise, peso_kg=90)], [{'tipo': 'progresion'}])
        rehab.return_value = ([dict(exercise, peso_kg=80)], [{'tipo': 'freno_rehab_gym'}])
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym
        resolver_autoridad_diaria_gym(self.cliente, self.hoy, physical_snapshot={
            'schema_version': 1, 'cliente_id': self.cliente.pk,
            'as_of_date': self.hoy.isoformat(), 'capabilities': ['active_rehab_v1'],
            'signals': {'active_rehab': {'items': []}}})
        rehab.assert_called_once()
        self.assertEqual(rehab.call_args.args[1][0]['peso_kg'], 90)

    @patch('core.services.physical_snapshot.build_physical_snapshot')
    def test_preview_is_jsonl_and_does_not_mutate_authority(self, build):
        version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=self.hoy, version=1, decision_id='gym-preview',
            schema_version=2, origen='motor', vigente=True, fingerprint='a',
            base_fingerprint='a', postura='empujar', snapshot={
                'entrenamiento': {'ejercicios': [{'nombre': 'Press', 'series': 3}]}})
        build.return_value = {
            'signals': {'active_rehab': {'items': []}}, 'schema_version': 1,
            'cliente_id': self.cliente.pk, 'as_of_date': self.hoy.isoformat()}
        before = list(GymDecisionVersion.objects.values())
        output = StringIO()
        call_command('previsualizar_freno_rehab_gym', '--cliente', str(self.cliente.pk),
                     '--fecha', self.hoy.isoformat(), stdout=output)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([row['type'] for row in rows],
                         ['meta', 'coverage', 'affected', 'unaffected'])
        self.assertFalse(rows[0]['execution_enabled'])
        self.assertEqual(before, list(GymDecisionVersion.objects.values()))
        version.refresh_from_db()
        self.assertTrue(version.vigente)

    @patch('django.core.cache.cache.set')
    def test_preview_simulates_disabled_contract_on_copy_and_writes_nothing(self, cache_set):
        self._registro()
        routine = Rutina.objects.create(nombre='Preview baseline')
        workout = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=routine, fecha=self.hoy-timedelta(days=1))
        EjercicioRealizado.objects.create(
            entreno=workout, nombre_ejercicio='Sentadilla', peso_kg=80,
            series=3, repeticiones=8)
        version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=self.hoy, version=1, decision_id='gym-preview-hold',
            schema_version=2, origen='motor', vigente=True, fingerprint='b',
            base_fingerprint='b', postura='empujar', snapshot={'entrenamiento': {'ejercicios': [{
                'nombre': 'Sentadilla', 'risk_tags': ['carga_dominante_rodilla'],
                'peso_kg': 90, 'series': 4, 'repeticiones': 10}]}})
        contracts_before = list(ContratoRiesgoGymFaseRehab.objects.values())
        authority_before = list(GymDecisionVersion.objects.values())
        output = StringIO()
        call_command('previsualizar_freno_rehab_gym', '--cliente', str(self.cliente.pk),
                     '--fecha', self.hoy.isoformat(), stdout=output)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        meta, coverage = rows[:2]
        self.assertFalse(meta['current_execution_enabled'])
        self.assertTrue(meta['simulated_execution_enabled'])
        self.assertEqual(coverage['affected'], 1)
        self.assertEqual(rows[2]['items'][0]['peso_kg'], 80)
        self.assertEqual(contracts_before, list(ContratoRiesgoGymFaseRehab.objects.values()))
        self.assertEqual(authority_before, list(GymDecisionVersion.objects.values()))
        cache_set.assert_not_called()
        version.refresh_from_db()
        self.assertTrue(version.vigente)
