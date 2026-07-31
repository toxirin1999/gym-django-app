from django.core.management.base import BaseCommand
from django.db import transaction

from clientes.models import Cliente
from entrenos.services.evaluacion_trace_service import (
    evaluar_traces_pendientes,
    traces_evaluables_qs,
)


class Command(BaseCommand):
    help = 'Evalúa traces maduros pendientes; dry-run por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente-id', type=int)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        apply = options['apply']
        cliente_id = options.get('cliente_id')
        limit = max(0, options['limit'])
        qs = traces_evaluables_qs()
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)
        candidatos = list(qs.values_list('cliente_id', flat=True)[:limit])
        evaluados = 0
        if apply and candidatos:
            restantes = limit
            for cid in dict.fromkeys(candidatos):
                if restantes <= 0:
                    break
                with transaction.atomic():
                    cliente = Cliente.objects.select_for_update().get(pk=cid)
                    n = evaluar_traces_pendientes(cliente, max_batch=restantes)
                evaluados += n
                restantes -= n
        modo = 'apply' if apply else 'dry-run'
        self.stdout.write(
            f'mode={modo} candidates={len(candidatos)} evaluated={evaluados}'
        )
