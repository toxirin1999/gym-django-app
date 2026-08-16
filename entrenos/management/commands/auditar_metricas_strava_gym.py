import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.services.auditoria_metricas_strava_gym_service import MAX_LIMIT, auditar_metricas_strava_gym


class Command(BaseCommand):
    help = "Audita en JSONL métricas Strava/Gym/hub. Siempre es de solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", type=int, required=True)
        parser.add_argument("--desde")
        parser.add_argument("--hasta")
        parser.add_argument("--limit", type=int, default=MAX_LIMIT)

    def handle(self, *args, **options):
        hasta = self._fecha(options["hasta"], "--hasta") if options.get("hasta") else timezone.localdate()
        desde = self._fecha(options["desde"], "--desde") if options.get("desde") else hasta - timedelta(days=29)
        if desde > hasta:
            raise CommandError("--desde no puede ser posterior a --hasta")
        if (hasta - desde).days > 365:
            raise CommandError("La ventana máxima es de 366 días")
        if not 1 <= options["limit"] <= MAX_LIMIT:
            raise CommandError(f"--limit debe estar entre 1 y {MAX_LIMIT}")
        if not Cliente.objects.filter(pk=options["cliente"]).exists():
            raise CommandError(f"No existe Cliente con id={options['cliente']}")
        result = auditar_metricas_strava_gym(cliente_id=options["cliente"], desde=desde,
                                              hasta=hasta, limit=options["limit"])
        for record in [*result["findings"], result["summary"]]:
            self.stdout.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    @staticmethod
    def _fecha(value, option):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{option} debe usar el formato YYYY-MM-DD") from exc
