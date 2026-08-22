import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from rehab.services.gym_risk_contract_service import etiquetar_catalogo


class Command(BaseCommand):
    help = 'Etiqueta de forma curada, transaccional y reversible el catálogo Gym.'

    def add_arguments(self, parser):
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument('--apply', action='store_true')
        actions.add_argument('--revert', action='store_true')

    def handle(self, *args, **options):
        try:
            report = etiquetar_catalogo(apply=options['apply'], revert=options['revert'])
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc

        meta_keys = (
            'schema_version', 'risk_tag', 'operation', 'applied', 'reversible',
            'execution_enabled',
        )
        self.stdout.write(json.dumps(
            {'type': 'meta', **{key: report[key] for key in meta_keys}},
            sort_keys=True, ensure_ascii=False,
        ))
        self.stdout.write(json.dumps(
            {'type': 'candidate', 'candidates': report['candidates']},
            sort_keys=True, ensure_ascii=False,
        ))
