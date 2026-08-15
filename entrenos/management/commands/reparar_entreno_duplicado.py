import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.reparar_entreno_duplicado import (
    ReparacionDuplicadoError,
    reparar_entreno_duplicado,
)


class Command(BaseCommand):
    help = "Repara un EntrenoRealizado duplicado conservando otro como canónico"

    def add_arguments(self, parser):
        parser.add_argument("duplicado_id", type=int)
        parser.add_argument("canonico_id", type=int)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup")

    def handle(self, *args, **options):
        try:
            resultado = reparar_entreno_duplicado(
                duplicado_id=options["duplicado_id"],
                canonico_id=options["canonico_id"],
                apply=options["apply"],
                backup_path=options["backup"],
            )
        except ReparacionDuplicadoError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, default=str))

