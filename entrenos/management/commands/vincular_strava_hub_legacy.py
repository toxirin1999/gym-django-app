import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.services.vincular_strava_hub_legacy_service import (
    vincular_strava_hub_legacy,
)


class Command(BaseCommand):
    help = "Vincula Strava legacy al hub. Dry-run por defecto; --apply es explícito."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", required=True, type=int)
        parser.add_argument("--desde")
        parser.add_argument("--hasta")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        cliente_id = options["cliente"]
        if not Cliente.objects.filter(pk=cliente_id).exists():
            raise CommandError(f"No existe Cliente con id={cliente_id}")
        hasta = self._date(options.get("hasta"), "--hasta") if options.get("hasta") else timezone.localdate()
        desde = self._date(options.get("desde"), "--desde") if options.get("desde") else hasta - timedelta(days=365)
        if desde > hasta:
            raise CommandError("--desde no puede ser posterior a --hasta")

        result = vincular_strava_hub_legacy(
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            apply=options["apply"],
        )
        for record in [*result["candidates"], *result["ambiguous"], result["summary"]]:
            self.stdout.write(json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ))

    @staticmethod
    def _date(value, option):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option} debe usar el formato YYYY-MM-DD") from exc

