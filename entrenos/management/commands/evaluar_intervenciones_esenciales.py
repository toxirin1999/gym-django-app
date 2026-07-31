from datetime import date

from django.core.management.base import BaseCommand

from entrenos.services.ciclo_intervencion_esenciales_service import candidatos, evaluar_intervencion


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente-id', type=int)
        parser.add_argument('--limit', type=int)
        parser.add_argument('--fecha', type=date.fromisoformat)

    def handle(self, *args, **opts):
        items = candidatos(opts['fecha'], opts['cliente_id'], opts['limit'])
        evaluated = 0
        for iv in items:
            resultado = evaluar_intervencion(iv, opts['fecha'], aplicar=opts['apply'])
            if opts['apply'] and resultado:
                evaluated += 1
        self.stdout.write(
            f"mode={'apply' if opts['apply'] else 'dry-run'} candidates={len(items)} evaluated={evaluated}"
        )
