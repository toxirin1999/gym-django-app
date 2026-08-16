import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.services.auditoria_eventos_fisicos_service import (
    MAX_LIMIT,
    auditar_eventos_fisicos,
)


class Command(BaseCommand):
    help = "Audita posibles duplicados de carga física en JSONL. Siempre solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", required=True, type=int)
        parser.add_argument("--desde", help="Fecha inicial inclusiva, YYYY-MM-DD")
        parser.add_argument("--hasta", help="Fecha final inclusiva, YYYY-MM-DD")
        parser.add_argument("--limit", type=int, default=MAX_LIMIT)

    def handle(self, *args, **options):
        cliente_id = options["cliente"]
        if not Cliente.objects.filter(pk=cliente_id).exists():
            raise CommandError(f"No existe Cliente con id={cliente_id}")

        hasta = self._date(options.get("hasta"), "--hasta") if options.get("hasta") else timezone.localdate()
        desde = self._date(options.get("desde"), "--desde") if options.get("desde") else hasta - timedelta(days=89)
        if desde > hasta:
            raise CommandError("--desde no puede ser posterior a --hasta")
        if (hasta - desde).days > 365:
            raise CommandError("La ventana máxima es de 366 días")
        limit = options["limit"]
        if not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f"--limit debe estar entre 1 y {MAX_LIMIT}")

        result = auditar_eventos_fisicos(
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
    def _date(value, option):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option} debe usar el formato YYYY-MM-DD") from exc

