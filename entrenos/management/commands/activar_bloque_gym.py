import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.models import ContratoBloqueGym
from entrenos.services.contrato_bloque_gym_service import (
    ActorBloqueNoAutorizado, ConflictoVersionBloque, SolapeBloqueGym,
    TransicionBloqueInvalida,
    activar_bloque_gym,
)


class Command(BaseCommand):
    help = 'Previsualiza o activa una propuesta de bloque Gym.'

    def add_arguments(self, parser):
        parser.add_argument('--bloque', type=int, required=True)
        parser.add_argument('--version-esperada', type=int, required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        bloque = ContratoBloqueGym.objects.select_related('cliente__user').filter(pk=options['bloque']).first()
        if bloque is None:
            raise CommandError(f'No existe bloque {options["bloque"]}.')
        payload = {
            'bloque_id': bloque.pk, 'version': bloque.version,
            'version_esperada': options['version_esperada'], 'estado_actual': bloque.estado,
        }
        if not options['apply']:
            payload.update({'modo': 'dry-run', 'solo_lectura': True})
            self.stdout.write(json.dumps(payload, sort_keys=True))
            return
        try:
            bloque = activar_bloque_gym(
                bloque, version_esperada=options['version_esperada'], actor=bloque.cliente.user,
            )
        except (
            ActorBloqueNoAutorizado, ConflictoVersionBloque,
            SolapeBloqueGym, TransicionBloqueInvalida,
        ) as exc:
            raise CommandError(str(exc)) from exc
        payload.update({'modo': 'apply', 'solo_lectura': False, 'estado': bloque.estado})
        self.stdout.write(json.dumps(payload, sort_keys=True))
