import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.reparar_decision_progresion_series import (
    ReparacionDecisionSeriesError,
    reparar_decision_progresion_series,
)


class Command(BaseCommand):
    help = 'Revalida una decisión pendiente con sus series canónicas (dry-run por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('decision_id', type=int)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            resultado = reparar_decision_progresion_series(
                decision_id=options['decision_id'],
                apply=options['apply'],
            )
        except ReparacionDecisionSeriesError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
