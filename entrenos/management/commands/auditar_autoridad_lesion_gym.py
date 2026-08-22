import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.services.auditoria_autoridad_lesion_gym_service import (
    MAX_LIMIT,
    auditar_autoridad_lesion_gym,
)


class Command(BaseCommand):
    help = "Audita en JSONL la doble autoridad de lesion Gym. Siempre solo lectura."

    def add_arguments(self, parser):
        selector = parser.add_mutually_exclusive_group(required=True)
        selector.add_argument("--cliente", type=int)
        selector.add_argument("--todos", action="store_true")
        parser.add_argument("--desde")
        parser.add_argument("--hasta")
        parser.add_argument("--limit", type=int, default=MAX_LIMIT)

    def handle(self, *args, **options):
        hasta = self._date(options.get("hasta"), "--hasta") if options.get("hasta") else timezone.localdate()
        desde = self._date(options.get("desde"), "--desde") if options.get("desde") else hasta - timedelta(days=29)
        if desde > hasta:
            raise CommandError("--desde no puede ser posterior a --hasta")
        limit = options["limit"]
        if not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f"--limit debe estar entre 1 y {MAX_LIMIT}")
        cliente_id = options.get("cliente")
        if cliente_id is not None and not Cliente.objects.filter(pk=cliente_id).exists():
            raise CommandError(f"No existe Cliente con id={cliente_id}")
        result = auditar_autoridad_lesion_gym(
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            limit=limit,
            as_of=hasta,
        )
        for record in [*result["findings"], result["summary"]]:
            self.stdout.write(json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ))

    @staticmethod
    def _date(value, option):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option} debe usar el formato YYYY-MM-DD") from exc
