import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.evaluacion_supervision_gym_service import cerrar_supervisiones_gym


def _fecha(valor):
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError as exc:
        raise CommandError(f'Fecha inválida: {valor}. Usa YYYY-MM-DD.') from exc


class Command(BaseCommand):
    help = 'Cierra factual e idempotentemente supervisiones Gym manuales ya terminadas.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente', type=int, dest='cliente')
        parser.add_argument('--desde')
        parser.add_argument('--hasta')
        parser.add_argument('--limit', type=int, default=500, dest='limite')

    def handle(self, *args, **options):
        if options['limite'] <= 0:
            raise CommandError('--limit debe ser mayor que cero.')
        resumen = cerrar_supervisiones_gym(
            cliente_id=options['cliente'],
            desde=_fecha(options['desde']),
            hasta=_fecha(options['hasta']),
            limite=options['limite'],
            aplicar=options['apply'],
        )
        self.stdout.write(json.dumps(resumen, sort_keys=True, ensure_ascii=False))
