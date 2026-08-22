import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.models import ContratoBloqueGym
from entrenos.services.contrato_bloque_gym_service import auditar_deriva_bloque_gym


class Command(BaseCommand):
    help = 'Audita deriva factual de un bloque Gym. Siempre es de solo lectura.'

    def add_arguments(self, parser):
        parser.add_argument('--bloque', type=int, required=True)

    def handle(self, *args, **options):
        bloque = ContratoBloqueGym.objects.filter(pk=options['bloque']).first()
        if bloque is None:
            raise CommandError(f'No existe bloque {options["bloque"]}.')
        resultado = auditar_deriva_bloque_gym(bloque)
        for semana in resultado.pop('semanas'):
            self.stdout.write(json.dumps({'tipo': 'semana', **semana}, sort_keys=True))
        self.stdout.write(json.dumps({'tipo': 'resumen', **resultado}, sort_keys=True))
