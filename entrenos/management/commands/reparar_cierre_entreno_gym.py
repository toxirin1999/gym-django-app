import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.reparar_cierre_entreno_gym import (
    ReparacionCierreEntrenoError,
    reparar_cierre_entreno_gym,
    restaurar_cierre_entreno_gym,
)


class Command(BaseCommand):
    help = "Repara duración y técnica confirmada de un cierre de entreno (dry-run por defecto)"

    def add_arguments(self, parser):
        parser.add_argument("entreno_id", type=int)
        parser.add_argument("--duracion-minutos", type=int)
        parser.add_argument("--tecnica-buena", action="append", default=[])
        parser.add_argument("--backup-file")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--restore-backup")

    def handle(self, *args, **options):
        try:
            if options["restore_backup"]:
                resultado = restaurar_cierre_entreno_gym(
                    entreno_id=options["entreno_id"], backup_file=options["restore_backup"]
                )
            else:
                if options["duracion_minutos"] is None:
                    raise ReparacionCierreEntrenoError("Debes indicar --duracion-minutos.")
                resultado = reparar_cierre_entreno_gym(
                    entreno_id=options["entreno_id"],
                    duracion_minutos=options["duracion_minutos"],
                    tecnica_buena=options["tecnica_buena"],
                    apply=options["apply"],
                    backup_file=options["backup_file"],
                )
        except (ReparacionCierreEntrenoError, ValueError, json.JSONDecodeError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
