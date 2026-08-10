import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.models import EstrategiaSemanalGym
from entrenos.services.estrategia_semanal_gym_service import (
    ContratoSemanalIncompleto,
    materializar_contrato_semanal_gym,
    previsualizar_contrato_semanal_gym,
)


class Command(BaseCommand):
    help = 'Previsualiza o materializa las sesiones de un contrato semanal Gym.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--semana', required=True, help='Lunes, YYYY-MM-DD')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options['cliente']).first()
        if cliente is None:
            raise CommandError(f"No existe Cliente con id={options['cliente']}")
        try:
            semana = date.fromisoformat(options['semana'])
            propuestas = previsualizar_contrato_semanal_gym(cliente, semana)
        except (ValueError, EstrategiaSemanalGym.DoesNotExist, ContratoSemanalIncompleto) as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            'cliente_id': cliente.pk,
            'semana': semana.isoformat(),
            'sesiones_previstas': len(propuestas),
            'sesiones': [
                {
                    'fecha': fecha.isoformat(),
                    'dia_numero': entrenamiento.get('dia'),
                    'nombre': entrenamiento.get('rutina_nombre'),
                }
                for fecha, entrenamiento in propuestas
            ],
        }
        if not options['apply']:
            payload.update({'modo': 'dry-run', 'solo_lectura': True})
            self.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))
            return

        try:
            contrato = materializar_contrato_semanal_gym(cliente, semana)
        except (ValueError, EstrategiaSemanalGym.DoesNotExist, ContratoSemanalIncompleto) as exc:
            raise CommandError(str(exc)) from exc
        payload.update({
            'modo': 'apply',
            'solo_lectura': False,
            'contrato_id': contrato.pk,
            'sesiones_materializadas': contrato.sesiones.count(),
        })
        self.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))
