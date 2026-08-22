import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from rehab.models import (
    ContratoRiesgoGymFaseRehab, EpisodioRehab, FaseProtocolo,
    ProtocoloRehab, RegistroDiarioRehab,
)
from rehab.services.gym_risk_contract_service import (
    CATALOGO_RIESGO_GYM_V2, auditar_cobertura, etiquetar_catalogo,
    publicar_sucesora,
)
from rutinas.models import EjercicioBase


class ContractFixture(TestCase):
    def setUp(self):
        self.protocol = ProtocoloRehab.objects.create(
            slug='tendinopatia-rotuliana', version=1, nombre='Tendinopatía rotuliana',
            zona='rodilla', descripcion='x', fuente_referencia='x', advertencias='x',
        )
        self.phase = FaseProtocolo.objects.create(
            protocolo=self.protocol, orden=1, slug='fase-1-isometrica', nombre='Fase 1',
            objetivo='x', duracion_minima_dias=7, duracion_tipica_dias=14, descripcion='x',
        )

    def contract(self, **overrides):
        data = dict(
            fase=self.phase, version=1, schema_version=1,
            risk_tags=['carga_dominante_rodilla'], pain_hold_min=5, freshness_days=3,
            action='sostener', scope='matching_exercises', red_flag_action='proteger', activo=True,
        )
        data.update(overrides)
        return ContratoRiesgoGymFaseRehab.objects.create(**data)


class ContractModelTests(ContractFixture):
    def test_validates_typed_policy_and_tags(self):
        for changes in (
            {'version': 0}, {'schema_version': 0}, {'risk_tags': 'rodilla'},
            {'risk_tags': ['']}, {'action': 'inventar'}, {'scope': 'all_session'},
            {'red_flag_action': ''}, {'pain_hold_min': 11}, {'freshness_days': 0},
        ):
            data = dict(fase=self.phase, version=1, schema_version=1,
                        risk_tags=['carga_dominante_rodilla'], pain_hold_min=5, freshness_days=3,
                        action='sostener', scope='matching_exercises', red_flag_action='proteger')
            data.update(changes)
            obj = ContratoRiesgoGymFaseRehab(**data)
            with self.assertRaises(ValidationError): obj.full_clean()

    def test_published_contract_is_immutable_and_successor_deactivates_it(self):
        original = self.contract()
        original.pain_hold_min = 6
        with self.assertRaises(ValidationError): original.save()
        successor = publicar_sucesora(original, risk_tags=['carga_dominante_rodilla', 'impacto_vertical'])
        original.refresh_from_db()
        self.assertFalse(original.activo)
        original.activo = True
        with self.assertRaises(ValidationError): original.save()
        self.assertEqual(successor.version, 2)
        self.assertTrue(successor.activo)

    def test_only_one_active_and_successor_is_idempotent(self):
        original = self.contract()
        first = publicar_sucesora(original, risk_tags=['carga_dominante_rodilla'])
        second = publicar_sucesora(original, risk_tags=['carga_dominante_rodilla'])
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ContratoRiesgoGymFaseRehab.objects.filter(fase=self.phase, activo=True).count(), 1)

    def test_successor_does_not_silently_return_inactive_version_conflict(self):
        original = self.contract()
        self.contract(version=2, activo=False, pain_hold_min=6)
        with self.assertRaisesMessage(ValidationError, 'versión sucesora'):
            publicar_sucesora(original, risk_tags=['carga_dominante_rodilla'])
        original.refresh_from_db()
        self.assertTrue(original.activo)


class CommandsAndAuditTests(ContractFixture):
    def test_seed_is_dry_run_by_default_and_apply_is_idempotent(self):
        out = StringIO()
        call_command('sembrar_contrato_riesgo_gym_rehab', stdout=out)
        self.assertEqual(ContratoRiesgoGymFaseRehab.objects.count(), 0)
        self.assertEqual(json.loads(out.getvalue())['operation'], 'dry_run')
        call_command('sembrar_contrato_riesgo_gym_rehab', '--apply', stdout=StringIO())
        call_command('sembrar_contrato_riesgo_gym_rehab', '--apply', stdout=StringIO())
        self.assertEqual(ContratoRiesgoGymFaseRehab.objects.count(), 1)

    def test_audit_is_deterministic_read_only_and_reports_coverage(self):
        self.contract(risk_tags=['carga_dominante_rodilla', 'impacto_vertical'])
        exact = EjercicioBase.objects.create(nombre='Sentadilla Trasera con Barra', grupo_muscular='Pierna')
        covered = EjercicioBase.objects.create(
            nombre='Salto a caja', grupo_muscular='Pierna', risk_tags=['impacto_vertical'],
        )
        ambiguous_a = EjercicioBase.objects.create(nombre='Sentadilla Búlgara', grupo_muscular='Pierna')
        ambiguous_b = EjercicioBase.objects.create(
            nombre='Sentadilla  Bulgara', grupo_muscular='Pierna', risk_tags=['carga_dominante_rodilla'],
        )
        EjercicioBase.objects.create(nombre='Press banca', grupo_muscular='Pecho')
        before = list(EjercicioBase.objects.values_list('pk', 'risk_tags'))
        report = auditar_cobertura(today=date(2026, 8, 22))
        self.assertIn({'exercise_id': exact.pk, 'name': exact.nombre, 'current_risk_tags': []},
                      report['exact_matches'])
        self.assertIn({'exercise_id': covered.pk, 'name': covered.nombre,
                       'matched_tags': ['impacto_vertical']}, report['covered_by_existing_tags'])
        self.assertEqual(report['ambiguous'], [{
            'normalized_name': 'sentadilla bulgara',
            'candidates': [
                {'exercise_id': ambiguous_b.pk, 'name': 'Sentadilla  Bulgara',
                 'current_risk_tags': ['carga_dominante_rodilla']},
                {'exercise_id': ambiguous_a.pk, 'name': 'Sentadilla Búlgara', 'current_risk_tags': []},
            ],
        }])
        self.assertIn('Prensa de Piernas', report['absent'])
        self.assertEqual(before, list(EjercicioBase.objects.values_list('pk', 'risk_tags')))
        out1, out2 = StringIO(), StringIO()
        call_command('auditar_cobertura_riesgo_gym_rehab', '--today=2026-08-22', stdout=out1)
        call_command('auditar_cobertura_riesgo_gym_rehab', '--today=2026-08-22', stdout=out2)
        self.assertEqual(out1.getvalue(), out2.getvalue())
        for line in out1.getvalue().splitlines(): json.loads(line)

    def _episode(self, pain=None, age=0, red=False, future=False):
        user = User.objects.create_user(username=f'u{User.objects.count()}')
        client = Cliente.objects.get(user=user)
        ep = EpisodioRehab.objects.create(
            cliente=client, protocolo=self.protocol, protocolo_version=1, fase_actual=self.phase,
            lateralidad='bilateral', fecha_inicio=date(2026, 8, 2),
            fase_actual_desde=date(2026, 8, 2), estado='ACTIVO', dolor_basal_inicial=5,
        )
        if pain is not None:
            day = date(2026, 8, 22) + timedelta(days=1 if future else -age)
            RegistroDiarioRehab.objects.create(
                episodio=ep, fecha=day, dolor_manana=pain, rigidez_manana=5, bandera_roja=red,
            )
        return ep

    def test_audit_lists_only_episodes_that_would_hold(self):
        self.contract()
        yes = self._episode(5, age=3)
        self._episode(4)
        self._episode(5, age=4)
        self._episode(5, future=True)
        self._episode(None)
        report = auditar_cobertura(today=date(2026, 8, 22))
        self.assertEqual([e['episode_id'] for e in report['episodes_would_hold']], [yes.pk])
        self.assertFalse(report['execution_enabled'])


class CatalogLabelingTests(TestCase):
    NAMES = (
        'Sentadilla Trasera con Barra',
        'Sentadilla Frontal con Barra',
        'Sentadilla Hack',
        'Sentadilla Búlgara',
        'Prensa de Piernas',
        'Zancadas con Mancuernas',
        'Extensiones de Cuádriceps en Máquina',
        'Sissy Squat',
    )
    EXCLUDED = (
        'Abducción de Cadera en Máquina', 'Hip Thrust con Barra',
        'Patada de Glúteo en Polea', 'Peso Muerto Sumo',
    )

    def setUp(self):
        for index, name in enumerate(self.NAMES):
            tags = ['tag_preexistente'] if index == 0 else []
            EjercicioBase.objects.create(nombre=name, grupo_muscular='Pierna', risk_tags=tags)
        for name in self.EXCLUDED:
            EjercicioBase.objects.create(nombre=name, grupo_muscular='Pierna')

    def test_v2_contains_exactly_the_eight_curated_names(self):
        self.assertEqual(CATALOGO_RIESGO_GYM_V2['schema_version'], 2)
        self.assertTupleEqual(CATALOGO_RIESGO_GYM_V2['exact_names'], self.NAMES)

    def test_dry_run_is_deterministic_and_writes_nothing(self):
        before = list(EjercicioBase.objects.order_by('pk').values_list('pk', 'risk_tags'))
        first = etiquetar_catalogo()
        second = etiquetar_catalogo()
        self.assertEqual(first, second)
        self.assertEqual(before, list(EjercicioBase.objects.order_by('pk').values_list('pk', 'risk_tags')))
        self.assertFalse(first['applied'])
        self.assertTrue(first['reversible'])
        self.assertFalse(first['execution_enabled'])
        self.assertEqual([row['name'] for row in first['candidates']], list(self.NAMES))

    def test_apply_preserves_tags_excludes_non_catalog_and_is_idempotent(self):
        first = etiquetar_catalogo(apply=True)
        second = etiquetar_catalogo(apply=True)
        self.assertTrue(first['applied'])
        self.assertTrue(second['applied'])
        selected = EjercicioBase.objects.filter(nombre__in=self.NAMES).order_by('pk')
        self.assertTrue(all('carga_dominante_rodilla' in row.risk_tags for row in selected))
        self.assertEqual(
            EjercicioBase.objects.get(nombre=self.NAMES[0]).risk_tags,
            ['tag_preexistente', 'carga_dominante_rodilla'],
        )
        self.assertTrue(all(
            'carga_dominante_rodilla' not in row.risk_tags
            for row in EjercicioBase.objects.filter(nombre__in=self.EXCLUDED)
        ))
        state_after_second = list(selected.values_list('pk', 'risk_tags'))
        etiquetar_catalogo(apply=True)
        self.assertEqual(state_after_second, list(selected.values_list('pk', 'risk_tags')))

    def test_revert_removes_only_own_tag_and_is_idempotent(self):
        etiquetar_catalogo(apply=True)
        first = etiquetar_catalogo(revert=True)
        second = etiquetar_catalogo(revert=True)
        self.assertTrue(first['applied'])
        self.assertTrue(second['applied'])
        self.assertEqual(EjercicioBase.objects.get(nombre=self.NAMES[0]).risk_tags, ['tag_preexistente'])
        self.assertTrue(all(
            'carga_dominante_rodilla' not in row.risk_tags
            for row in EjercicioBase.objects.filter(nombre__in=self.NAMES)
        ))

    def test_missing_name_aborts_without_any_write(self):
        EjercicioBase.objects.get(nombre=self.NAMES[-1]).delete()
        with self.assertRaisesMessage(ValidationError, 'catálogo incompleto'):
            etiquetar_catalogo(apply=True)
        self.assertFalse(any(
            'carga_dominante_rodilla' in (tags or [])
            for tags in EjercicioBase.objects.values_list('risk_tags', flat=True)
        ))

    def test_ambiguous_normalized_name_aborts_without_any_write(self):
        original = EjercicioBase.objects.get(nombre='Sentadilla Búlgara')
        original.nombre = 'Sentadilla Bulgara'
        original.save(update_fields=['nombre'])
        EjercicioBase.objects.create(
            nombre='Sentadilla  Búlgara', grupo_muscular='Pierna', risk_tags=['otro'],
        )
        with self.assertRaisesMessage(ValidationError, 'ambiguo'):
            etiquetar_catalogo(apply=True)
        self.assertFalse(any(
            'carga_dominante_rodilla' in (tags or [])
            for tags in EjercicioBase.objects.values_list('risk_tags', flat=True)
        ))

    def test_command_jsonl_and_mutually_exclusive_flags(self):
        out = StringIO()
        call_command('etiquetar_catalogo_riesgo_gym_rehab', stdout=out)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([row['type'] for row in rows], ['meta', 'candidate'])
        self.assertEqual(len(rows[1]['candidates']), 8)
        self.assertFalse(rows[0]['execution_enabled'])
        with self.assertRaises(CommandError):
            call_command(
                'etiquetar_catalogo_riesgo_gym_rehab', '--apply', '--revert',
                stdout=StringIO(), stderr=StringIO(),
            )

    def test_existing_audit_reflects_v2_coverage_after_apply(self):
        etiquetar_catalogo(apply=True)
        report = auditar_cobertura(today=date(2026, 8, 22))
        self.assertEqual(report['absent'], [])
        self.assertEqual(len(report['exact_matches']), 8)
        covered_names = {row['name'] for row in report['covered_by_existing_tags']}
        self.assertEqual(covered_names, set(self.NAMES))
