"""CLI JSON Lines para la auditoría histórica de gamificación."""

import json

from django.core.management.base import BaseCommand, CommandError

from logros.auditoria_integridad_gamificacion_service import (
    auditar_integridad_gamificacion,
)


class Command(BaseCommand):
    help = "Audita la integridad histórica de gamificación. Siempre solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", required=True, type=int)
        parser.add_argument("--limit", type=int, default=1000)

    def handle(self, *args, **options):
        try:
            result = auditar_integridad_gamificacion(
                cliente_id=options["cliente"], limit=options["limit"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        for row in [*result["findings"], result["summary"]]:
            self.stdout.write(json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ))
