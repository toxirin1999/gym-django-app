import json

from django.core.management.base import BaseCommand

from joi.services_revision_memoria_audit import auditar_revision_memoria


class Command(BaseCommand):
    help = 'Audita el ledger de revisión de memoria en JSONL (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--as-of', dest='as_of', type=str, required=True)
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        result = auditar_revision_memoria(
            cliente_id=options['cliente'],
            as_of=options['as_of'],
            limit=options['limit'],
        )
        for item in result['findings']:
            self.stdout.write(json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            ))
        self.stdout.write(json.dumps(
            result['summary'],
            ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        ))

