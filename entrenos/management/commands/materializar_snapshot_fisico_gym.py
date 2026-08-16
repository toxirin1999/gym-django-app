import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.autoridad_diaria_gym_service import _snapshot_fisico_valido


class Command(BaseCommand):
    help = (
        "Inspecciona o materializa el snapshot físico V1 de la autoridad Gym vigente. "
        "Dry-run por defecto."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cliente", type=int, required=True)
        parser.add_argument("--fecha", help="Fecha a inspeccionar, YYYY-MM-DD")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options["cliente"]).first()
        if cliente is None:
            raise CommandError(f"No existe Cliente con id={options['cliente']}")
        fecha_local = timezone.localdate()
        fecha = self._fecha(options.get("fecha")) if options.get("fecha") else fecha_local
        apply = options["apply"]
        if apply and fecha != fecha_local:
            raise CommandError("--apply solo permite materializar la fecha local de hoy")

        vigente = (
            GymDecisionVersion.objects.filter(
                cliente=cliente,
                fecha=fecha,
                vigente=True,
            )
            .order_by("-version", "-pk")
            .first()
        )
        estado = self._estado(vigente, cliente, fecha)
        if not apply or estado != "candidate":
            self._emitir(cliente.pk, fecha, vigente, estado, solo_lectura=not apply)
            return

        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym

        resolver_autoridad_diaria_gym(cliente, fecha, force_refresh=True)
        nueva = (
            GymDecisionVersion.objects.filter(
                cliente=cliente,
                fecha=fecha,
                vigente=True,
            )
            .order_by("-version", "-pk")
            .first()
        )
        if nueva is not None and _snapshot_fisico_valido(
            (nueva.snapshot or {}).get("physical_snapshot"), cliente, fecha,
        ):
            estado = "materialized"
        else:
            estado = "failed_snapshot_unavailable"
        self._emitir(cliente.pk, fecha, nueva or vigente, estado, solo_lectura=False)

    @staticmethod
    def _estado(vigente, cliente, fecha):
        if vigente is None:
            return "skip_no_decision"
        if vigente.origen != GymDecisionVersion.ORIGEN_MOTOR:
            return "skip_manual_supervision"
        physical = (
            vigente.snapshot.get("physical_snapshot")
            if isinstance(vigente.snapshot, dict)
            else None
        )
        if _snapshot_fisico_valido(physical, cliente, fecha):
            return "skip_already_materialized"
        return "candidate"

    def _emitir(self, cliente_id, fecha, version, estado, *, solo_lectura):
        payload = {
            "tipo_registro": "materializacion_snapshot_fisico",
            "schema_version": 1,
            "cliente_id": cliente_id,
            "fecha": fecha.isoformat(),
            "version_id": version.pk if version else None,
            "version": version.version if version else None,
            "origen": version.origen if version else None,
            "estado": estado,
            "solo_lectura": solo_lectura,
        }
        self.stdout.write(json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ))

    @staticmethod
    def _fecha(value):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError("--fecha debe usar el formato YYYY-MM-DD") from exc
