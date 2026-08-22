import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from clientes.models import Cliente
from hyrox.campaign_authority import auditar_campana


class Command(BaseCommand):
    help = 'Audita en solo lectura la autoridad y fugas legacy de Hyrox.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--fecha', default=str(date.today()))

    def handle(self, *args, **o):
        cliente = Cliente.objects.filter(pk=o['cliente']).first()
        if not cliente:
            raise CommandError('Cliente inexistente.')
        try:
            fecha = date.fromisoformat(o['fecha'])
        except ValueError as exc:
            raise CommandError('--fecha debe ser YYYY-MM-DD') from exc
        reporte = auditar_campana(cliente, fecha)
        self.stdout.write(json.dumps({'tipo': 'meta', 'solo_lectura': True, 'cliente_id': cliente.pk, 'fecha': str(fecha), **reporte['autoridad']}, sort_keys=True))
        for item in reporte['inventario']:
            self.stdout.write(json.dumps({'tipo': 'inventario', **item}, sort_keys=True))
        for item in reporte['riesgos_estaticos']:
            self.stdout.write(json.dumps({'tipo': 'riesgo_estatico', **item}, sort_keys=True))
        for item in reporte['hallazgos']:
            self.stdout.write(json.dumps({'tipo': 'hallazgo', **item}, sort_keys=True))
        self.stdout.write(json.dumps({'tipo': 'resumen', 'hallazgos': len(reporte['hallazgos']), 'inventario': len(reporte['inventario']), 'solo_lectura': True}, sort_keys=True))
