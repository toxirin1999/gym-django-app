import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from rehab.services.gym_risk_contract_service import auditar_cobertura


class Command(BaseCommand):
    help = 'Auditoría JSONL determinista y de solo lectura del contrato Rehab→Gym.'

    def add_arguments(self, parser):
        parser.add_argument('--today')

    def handle(self, *args, **options):
        try:
            today = date.fromisoformat(options['today']) if options['today'] else date.today()
        except ValueError as exc:
            raise CommandError('--today debe usar YYYY-MM-DD') from exc
        report = auditar_cobertura(today=today)
        for kind in ('meta', 'coverage', 'episodes'):
            if kind == 'meta':
                row = {k: report[k] for k in ('schema_version', 'catalog_version',
                                               'proposed_risk_tag', 'execution_enabled', 'read_only')}
            elif kind == 'coverage':
                row = {k: report[k] for k in ('exact_matches', 'ambiguous',
                                               'covered_by_existing_tags', 'absent')}
            else:
                row = {'episodes_would_hold': report['episodes_would_hold']}
            self.stdout.write(json.dumps({'type': kind, **row}, sort_keys=True, ensure_ascii=False))
