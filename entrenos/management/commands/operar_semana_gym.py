"""Ejecuta manualmente la operación semanal Gym correspondiente al día."""

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym


class Command(BaseCommand):
    help = 'Opera la semana Gym. Es dry-run salvo que se indique --apply.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fecha-referencia',
            help='Fecha ISO YYYY-MM-DD; por defecto usa timezone.localdate().',
        )
        parser.add_argument('--apply', action='store_true', dest='aplicar')

    def handle(self, *args, **options):
        referencia = None
        if options['fecha_referencia']:
            try:
                referencia = date.fromisoformat(options['fecha_referencia'])
            except ValueError as exc:
                raise CommandError(
                    'La fecha de referencia debe usar formato YYYY-MM-DD.'
                ) from exc
        payload = operar_semana_gym(
            fecha_referencia=referencia,
            aplicar=options['aplicar'],
        )
        self.stdout.write(json.dumps(
            payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        ))
