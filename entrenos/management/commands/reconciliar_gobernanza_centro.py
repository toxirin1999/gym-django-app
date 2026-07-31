import json

from django.core.management.base import BaseCommand

from entrenos.services.reconciliacion_gobernanza_service import reconciliar


class Command(BaseCommand):
    help = 'Audita gobernanza del Centro; solo expira intervenciones con --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente-id', type=int)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        resultado = reconciliar(
            cliente_id=options.get('cliente_id'),
            limit=max(0, options['limit']),
            apply=options['apply'],
        )
        modo = 'apply' if options['apply'] else 'dry-run'
        for hallazgo in resultado['hallazgos']:
            self.stdout.write(json.dumps(hallazgo, default=str, sort_keys=True))
        self.stdout.write(
            f"mode={modo} findings={len(resultado['hallazgos'])} "
            f"applied={resultado['aplicados']}"
        )
