"""Emite la distribución contractual semanal como un único JSON estable."""

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.services.distribucion_semanal_contractual_service import (
    analizar_distribucion_semanal_contractual,
)


class Command(BaseCommand):
    help = 'Audita en modo solo lectura la distribución semanal contractual Gym.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--hasta', help='Fecha máxima inclusiva, YYYY-MM-DD')

    def handle(self, *args, **options):
        try:
            cliente = Cliente.objects.get(pk=options['cliente'])
        except Cliente.DoesNotExist as exc:
            raise CommandError(
                f"No existe Cliente con id={options['cliente']}"
            ) from exc

        hasta = None
        if options.get('hasta'):
            try:
                hasta = date.fromisoformat(options['hasta'])
            except ValueError as exc:
                raise CommandError('--hasta debe usar el formato YYYY-MM-DD') from exc

        resultado = analizar_distribucion_semanal_contractual(cliente, hasta=hasta)
        self.stdout.write(json.dumps(
            resultado,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ))
