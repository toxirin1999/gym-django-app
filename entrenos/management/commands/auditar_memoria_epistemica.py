import json

from django.core.management.base import BaseCommand

from core.services.epistemic_registry import construir_resumen, recopilar_memoria


class Command(BaseCommand):
    help = 'Audita la memoria epistemológica en modo de solo lectura (JSONL).'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--desde', type=str)
        parser.add_argument('--hasta', type=str)
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        cliente_id = options['cliente']
        desde = options.get('desde')
        hasta = options.get('hasta')
        limit = max(0, options['limit'])
        resultado = recopilar_memoria(
            cliente_id, desde=desde, hasta=hasta, limit=limit,
        )
        items = [
            {'tipo_registro': 'registro', **record}
            for record in resultado['records']
        ] + resultado['findings']
        items.sort(key=lambda item: (
            item['tipo_registro'], item.get('record_id', ''), item.get('code', ''),
        ))
        for item in items:
            self.stdout.write(json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            ))
        resumen = construir_resumen(
            resultado, cliente_id=cliente_id, desde=desde, hasta=hasta, limit=limit,
        )
        self.stdout.write(json.dumps(
            resumen, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        ))
