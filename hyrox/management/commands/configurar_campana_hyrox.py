import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym
from hyrox.models import HyroxObjective
from hyrox.campaign_authority import configurar, previsualizar


class Command(BaseCommand):
    help = 'Previsualiza o crea una versión pasiva del contrato de campaña Hyrox.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--estado', choices=['inactiva', 'exploracion', 'activa', 'finalizada'], required=True)
        parser.add_argument('--objetivo', type=int)
        parser.add_argument('--bloque-gym', type=int)
        parser.add_argument('--version-esperada', type=int)
        parser.add_argument('--motivo', default='Configuración supervisada de campaña Hyrox')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        cliente = Cliente.objects.filter(pk=o['cliente']).first()
        if not cliente:
            raise CommandError('Cliente inexistente.')
        objetivo = HyroxObjective.objects.filter(pk=o.get('objetivo'), cliente=cliente).first() if o.get('objetivo') else None
        bloque = ContratoBloqueGym.objects.filter(pk=o.get('bloque_gym'), cliente=cliente).first() if o.get('bloque_gym') else None
        try:
            data = previsualizar(cliente, o['estado'], objetivo, bloque)
            if o['apply']:
                contrato = configurar(cliente, o['estado'], objetivo, bloque,
                                      motivo=o['motivo'],
                                      version_esperada=o.get('version_esperada'),
                                      actor=cliente.user)
                data.update({'contrato_id': contrato.pk, 'version': contrato.version,
                             'predecesor_id': contrato.predecesor_id,
                             'fingerprint': contrato.fingerprint,
                             'reutilizado': data['contrato_existente_id'] == contrato.pk,
                             'modo': 'apply', 'solo_lectura': False})
            else:
                data.update({'modo': 'dry-run', 'solo_lectura': True})
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(data, sort_keys=True))
