import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.services.estrategia_semanal_gym_service import (
    aprobar_estrategia_semanal_gym,
)


class Command(BaseCommand):
    help = 'Previsualiza o aprueba una estrategia semanal Gym versionada.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--objetivo', type=int, required=True)
        parser.add_argument('--minimo', type=int, required=True)
        parser.add_argument('--desde', required=True, help='Lunes de vigencia, YYYY-MM-DD')
        parser.add_argument('--motivo', default='Contrato semanal confirmado por el usuario')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options['cliente']).select_related('user').first()
        if cliente is None:
            raise CommandError(f"No existe Cliente con id={options['cliente']}")
        try:
            desde = date.fromisoformat(options['desde'])
        except ValueError as exc:
            raise CommandError('--desde debe usar YYYY-MM-DD') from exc
        objetivo = options['objetivo']
        minimo = options['minimo']
        if desde.weekday() != 0:
            raise CommandError('--desde debe ser lunes')
        if minimo < 1 or objetivo < minimo or objetivo > 7:
            raise CommandError('Se exige 1 <= mínimo <= objetivo <= 7')

        payload = {
            'cliente_id': cliente.pk,
            'desde': desde.isoformat(),
            'objetivo_sesiones': objetivo,
            'minimo_valido': minimo,
        }
        if not options['apply']:
            payload.update({'modo': 'dry-run', 'solo_lectura': True})
            self.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))
            return

        estrategia = aprobar_estrategia_semanal_gym(
            cliente,
            objetivo_sesiones=objetivo,
            minimo_valido=minimo,
            vigente_desde=desde,
            aprobado_por=cliente.user,
            motivo=options['motivo'],
        )
        payload.update({
            'modo': 'apply',
            'solo_lectura': False,
            'version': estrategia.version,
            'estado': estrategia.estado,
        })
        self.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))
