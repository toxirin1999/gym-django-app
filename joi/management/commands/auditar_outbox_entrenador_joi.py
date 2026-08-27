import json

from django.core.management.base import BaseCommand

from joi.services_eventos_entrenador import auditar_outbox_entrenador_joi


class Command(BaseCommand):
    help = "Audita el outbox del entrenador JOI en JSONL (solo lectura)."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", dest="as_of", required=True)
        parser.add_argument("--cliente", type=int)
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        result = auditar_outbox_entrenador_joi(
            as_of=options["as_of"],
            cliente_id=options.get("cliente"),
            limit=options["limit"],
        )
        for item in result["findings"]:
            self.stdout.write(json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ))
        self.stdout.write(json.dumps(
            result["summary"],
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ))
