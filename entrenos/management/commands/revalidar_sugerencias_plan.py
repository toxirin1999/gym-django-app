from django.core.management.base import BaseCommand

from entrenos.models import SugerenciaPlan
from entrenos.services.contrato_sugerencia_service import (
    PATRON_V1,
    construir_contrato_sugerencia,
)


class Command(BaseCommand):
    help = 'Revalida sugerencias legacy y adjunta evidencia actual solo con --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente-id', type=int)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        qs = SugerenciaPlan.objects.filter(
            patron=PATRON_V1,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
            contrato_snapshot__isnull=True,
        ).select_related('cliente').order_by('pk')
        if options.get('cliente_id'):
            qs = qs.filter(cliente_id=options['cliente_id'])
        candidatas = list(qs[:max(0, options['limit'])])
        elegibles = aplicadas = 0
        for sugerencia in candidatas:
            contrato = construir_contrato_sugerencia(sugerencia.cliente, sugerencia.patron)
            if not contrato['vigente']:
                continue
            elegibles += 1
            if options['apply']:
                sugerencia.contrato_snapshot = contrato
                sugerencia.save(update_fields=['contrato_snapshot'])
                aplicadas += 1
        modo = 'apply' if options['apply'] else 'dry-run'
        self.stdout.write(
            f'mode={modo} candidates={len(candidatas)} eligible={elegibles} applied={aplicadas}'
        )
