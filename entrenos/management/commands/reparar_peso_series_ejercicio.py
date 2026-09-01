import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from entrenos.services.reparar_peso_series_ejercicio import (
    ReparacionPesoSeriesError,
    reparar_peso_series_ejercicio,
)


class Command(BaseCommand):
    help = "Repara de forma segura el peso de las series de un ejercicio (dry-run por defecto)"

    def add_arguments(self, parser):
        parser.add_argument("entreno_id", type=int)
        parser.add_argument("ejercicio_realizado_id", type=int)
        parser.add_argument("--expected-nombre", required=True)
        parser.add_argument("--expected-series", required=True, type=int)
        parser.add_argument("--expected-reps", required=True, type=int)
        parser.add_argument("--expected-peso-anterior", required=True, type=Decimal)
        parser.add_argument("--nuevo-peso", required=True, type=Decimal)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            resultado = reparar_peso_series_ejercicio(
                entreno_id=options["entreno_id"],
                ejercicio_realizado_id=options["ejercicio_realizado_id"],
                expected_nombre=options["expected_nombre"],
                expected_series=options["expected_series"],
                expected_reps=options["expected_reps"],
                expected_peso_anterior=options["expected_peso_anterior"],
                nuevo_peso=options["nuevo_peso"],
                apply=options["apply"],
            )
        except ReparacionPesoSeriesError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))

