import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.services.auditoria_snapshot_fisico_service import (
    MAX_LIMIT,
    auditar_snapshots_fisicos,
)


class Command(BaseCommand):
    help = "Audita en JSONL snapshots físicos Gym persistidos. Siempre es de solo lectura."

    def add_arguments(self, parser):
        selector = parser.add_mutually_exclusive_group(required=True)
        selector.add_argument("--cliente", type=int)
        selector.add_argument("--todos", action="store_true")
        parser.add_argument("--desde", help="Fecha inicial inclusiva, YYYY-MM-DD")
        parser.add_argument("--hasta", help="Fecha final inclusiva, YYYY-MM-DD")
        parser.add_argument("--limit", type=int, default=MAX_LIMIT)

    def handle(self, *args, **options):
        hasta = (
            self._fecha(options.get("hasta"), "--hasta")
            if options.get("hasta")
            else timezone.localdate()
        )
        desde = (
            self._fecha(options.get("desde"), "--desde")
            if options.get("desde")
            else hasta - timedelta(days=29)
        )
        if desde > hasta:
            raise CommandError("--desde no puede ser posterior a --hasta")
        if (hasta - desde).days > 365:
            raise CommandError("La ventana máxima es de 366 días")
        limit = options["limit"]
        if not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f"--limit debe estar entre 1 y {MAX_LIMIT}")

        cliente_id = options.get("cliente")
        if cliente_id is not None and not Cliente.objects.filter(pk=cliente_id).exists():
            raise CommandError(f"No existe Cliente con id={cliente_id}")

        result = auditar_snapshots_fisicos(
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            limit=limit,
        )
        for record in [*result["findings"], result["summary"]]:
            self.stdout.write(json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ))

    @staticmethod
    def _fecha(value, option):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option} debe usar el formato YYYY-MM-DD") from exc
