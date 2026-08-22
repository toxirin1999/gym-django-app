import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.services.contrato_bloque_gym_service import proponer_bloque_gym


class Command(BaseCommand):
    help = 'Previsualiza o propone un contrato longitudinal Gym. Dry-run por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--semana-inicio', required=True)
        parser.add_argument('--semanas', type=int, required=True)
        parser.add_argument('--objetivo-principal', required=True)
        parser.add_argument('--objetivo-secundario', action='append', default=[])
        parser.add_argument('--motivo', default='Bloque Gym propuesto por el usuario')
        parser.add_argument('--motor-version', default='actual')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options['cliente']).first()
        if cliente is None:
            raise CommandError(f'No existe Cliente con id={options["cliente"]}')
        try:
            inicio = date.fromisoformat(options['semana_inicio'])
        except ValueError as exc:
            raise CommandError('--semana-inicio debe usar YYYY-MM-DD') from exc
        if inicio.weekday() != 0 or options['semanas'] < 1:
            raise CommandError('El inicio debe ser lunes y --semanas debe ser positivo.')
        payload = {
            'cliente_id': cliente.pk, 'semana_inicio': inicio.isoformat(),
            'semanas_previstas': options['semanas'],
            'objetivo_principal': options['objetivo_principal'],
        }
        if not options['apply']:
            payload.update({'modo': 'dry-run', 'solo_lectura': True})
            self.stdout.write(json.dumps(payload, sort_keys=True))
            return
        bloque = proponer_bloque_gym(
            cliente, semana_inicio=inicio, semanas_previstas=options['semanas'],
            objetivo_principal=options['objetivo_principal'],
            objetivos_secundarios=options['objetivo_secundario'],
            limites_snapshot={'sin_autoajustes': True},
            motor_nombre='Helms', motor_version=options['motor_version'],
            motivo=options['motivo'],
        )
        payload.update({
            'modo': 'apply', 'solo_lectura': False, 'bloque_id': bloque.pk,
            'version': bloque.version, 'estado': bloque.estado,
            'fingerprint': bloque.fingerprint,
        })
        self.stdout.write(json.dumps(payload, sort_keys=True))
