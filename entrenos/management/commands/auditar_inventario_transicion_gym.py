"""Expone el inventario canónico de transición sin consultar datos personales."""

import json

from django.core.management.base import BaseCommand

from core.services.transition_inventory_service import build_transition_inventory


class Command(BaseCommand):
    help = 'Emite el inventario vivo de transición Gym. Siempre es de solo lectura.'

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(
            build_transition_inventory(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ))

