import json

from django.core.management.base import BaseCommand

from core.services.epistemic_review_queue import planificar_revision_memoria


class Command(BaseCommand):
    help = 'Lista la cola epistemológica de revisión en JSONL (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--as-of', dest='as_of', type=str, required=True)
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        result = planificar_revision_memoria(
            cliente_id=options['cliente'], as_of=options['as_of'],
            limit=options['limit'],
        )
        for item in result['items']:
            self.stdout.write(json.dumps(
                {'tipo_registro': 'revision_memoria', **item},
                ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            ))
        summary = {key: value for key, value in result.items() if key != 'items'}
        self.stdout.write(json.dumps(
            {'tipo_registro': 'resumen', **summary},
            ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        ))
