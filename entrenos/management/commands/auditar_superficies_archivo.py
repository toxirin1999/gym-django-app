"""Entrada Django para la auditoría neutral implementada en ``core``."""

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from core.services.archive_audit_service import audit_archive_surfaces


class Command(BaseCommand):
    help = "Audita superficies históricas para un cliente. Siempre read-only."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", required=True, type=int)
        parser.add_argument("--hasta", required=True)
        parser.add_argument("--ventana-dias", type=int, default=90)

    def handle(self, *args, **options):
        try:
            hasta = date.fromisoformat(options["hasta"])
        except (TypeError, ValueError) as exc:
            raise CommandError("--hasta debe usar YYYY-MM-DD") from exc
        if options["ventana_dias"] <= 0:
            raise CommandError("--ventana-dias debe ser positivo")
        try:
            result = audit_archive_surfaces(
                cliente_id=options["cliente"],
                hasta=hasta,
                ventana_dias=options["ventana_dias"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
        ))
