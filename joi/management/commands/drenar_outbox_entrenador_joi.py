import json

from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from joi.models import EventoEntrenadorJOI


class Command(BaseCommand):
    help = (
        "Inspecciona el outbox JOI de un cliente; solo lo procesa con --apply. "
        "No borra eventos ni marca mensajes como leídos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cliente", type=int, required=True)
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--apply", action="store_true")

    @staticmethod
    def _snapshot(cliente, ids):
        return list(
            EventoEntrenadorJOI.objects.filter(user=cliente.user, pk__in=ids)
            .order_by("creado_en", "id")
            .values("id", "estado", "intentos", "mensaje_id")
        )

    def handle(self, *args, **options):
        limite = options["limit"]
        if not 1 <= limite <= 100:
            raise CommandError("--limit debe estar entre 1 y 100")
        try:
            cliente = Cliente.objects.select_related("user").get(pk=options["cliente"])
        except Cliente.DoesNotExist as exc:
            raise CommandError("Cliente no encontrado") from exc

        ids = list(
            EventoEntrenadorJOI.objects.filter(
                user=cliente.user,
                estado__in=(
                    EventoEntrenadorJOI.ESTADO_PENDIENTE,
                    EventoEntrenadorJOI.ESTADO_PROCESANDO,
                ),
            )
            .order_by("creado_en", "id")
            .values_list("id", flat=True)[:limite]
        )
        antes = self._snapshot(cliente, ids)
        mensaje = None
        if options["apply"]:
            from joi.services_eventos_entrenador import procesar_eventos_entrenador_pendientes
            mensaje = procesar_eventos_entrenador_pendientes(cliente, limite=limite)
        despues = self._snapshot(cliente, ids)
        resultado = {
            "cliente_id": cliente.pk,
            "modo": "apply" if options["apply"] else "dry-run",
            "limit": limite,
            "antes": antes,
            "despues": despues,
            "resultado_mensaje_id": mensaje.pk if mensaje else None,
        }
        self.stdout.write(json.dumps(
            resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ))
