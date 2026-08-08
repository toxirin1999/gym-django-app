import argparse
import json

from django.core.management.base import BaseCommand

from diario.services.auditoria_logos_service import auditar_logos


def limite_seguro(valor):
    limite = int(valor)
    if not 1 <= limite <= 10000:
        raise argparse.ArgumentTypeError("limit debe estar entre 1 y 10000")
    return limite


class Command(BaseCommand):
    help = "Audita integridad operativa de Logos en modo estrictamente read-only."

    def add_arguments(self, parser):
        parser.add_argument("--usuario-id", type=int)
        parser.add_argument("--limit", type=limite_seguro, default=1000)

    def handle(self, *args, **options):
        resultado = auditar_logos(
            usuario_id=options.get("usuario_id"), limit=options["limit"]
        )
        for hallazgo in resultado["hallazgos"]:
            self.stdout.write(json.dumps(hallazgo, sort_keys=True, separators=(",", ":")))
        resumen = {
            "tipo": "resumen",
            "conteos_por_codigo": resultado["conteos_por_codigo"],
            "total_hallazgos": resultado["total_hallazgos"],
            "emitidos": resultado["emitidos"],
            "truncados": resultado["truncados"],
            "tema_del_dia_id": resultado["tema_del_dia_id"],
        }
        self.stdout.write(json.dumps(resumen, sort_keys=True, separators=(",", ":")))
