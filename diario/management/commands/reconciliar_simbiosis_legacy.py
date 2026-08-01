import json

from django.core.management.base import BaseCommand

from diario.services.reconciliacion_simbiosis_legacy import reconciliar_simbiosis_legacy


class Command(BaseCommand):
    help = 'Audita y enlaza interacciones legacy de Simbiosis solo con --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        apply = options['apply']
        resultado = reconciliar_simbiosis_legacy(
            apply=apply,
            user_id=options.get('user_id'),
            limit=options['limit'],
        )
        for hallazgo in resultado['hallazgos']:
            self.stdout.write(json.dumps(hallazgo, default=str, sort_keys=True))
        self.stdout.write(
            f"mode={'apply' if apply else 'dry-run'} "
            f"candidates={resultado['candidatos']} "
            f"eligible={resultado['elegibles']} "
            f"applied={resultado['aplicados']} "
            f"ambiguous={resultado['ambiguos']}"
        )
