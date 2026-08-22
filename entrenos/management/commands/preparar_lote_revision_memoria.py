import json

from django.core.management.base import BaseCommand, CommandError

from core.services.epistemic_review_proposal import preparar_lote_revision


class Command(BaseCommand):
    help = 'Prepara un manifiesto público de revisión epistemológica (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--as-of', dest='as_of', type=str, required=True)
        parser.add_argument('--item', dest='items', action='append', required=True)

    def handle(self, *args, **options):
        try:
            manifest = preparar_lote_revision(
                cliente_id=options['cliente'], as_of=options['as_of'],
                item_refs=options['items'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        for item in manifest['items']:
            self.stdout.write(json.dumps(
                {'tipo_registro': 'item_revision', **item},
                ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            ))
        meta = {key: value for key, value in manifest.items() if key != 'items'}
        self.stdout.write(json.dumps(
            {'tipo_registro': 'meta', **meta},
            ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        ))
