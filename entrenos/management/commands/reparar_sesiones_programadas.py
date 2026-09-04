import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from entrenos.models import EntrenoRealizado, SesionProgramada


def _normalizar(valor):
    return " ".join((valor or "").casefold().split())


def _fecha_entreno(entreno):
    return entreno.fecha_ejecucion or entreno.fecha


class Command(BaseCommand):
    help = "Repara de forma dirigida sesiones falsamente completadas (dry-run por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--cliente", type=int, required=True)
        parser.add_argument("--restaurar-sesion", type=int, required=True)
        parser.add_argument("--vincular-sesion", type=int, required=True)
        parser.add_argument("--entreno", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            restaurar = self._sesion(options["restaurar_sesion"], options["cliente"])
            vincular = self._sesion(options["vincular_sesion"], options["cliente"])
            entreno = self._entreno(options["entreno"], options["cliente"])
            self._validar(restaurar, vincular, entreno)

            payload = {
                "modo": "apply" if options["apply"] else "dry-run",
                "cliente_id": options["cliente"],
                "restaurar_sesion_id": restaurar.pk,
                "vincular_sesion_id": vincular.pk,
                "entreno_id": entreno.pk,
            }
            if options["apply"]:
                restaurar.estado = SesionProgramada.ESTADO_PENDIENTE
                restaurar.fecha_realizada = None
                restaurar.entreno_realizado = None
                restaurar.save(update_fields=[
                    "estado", "fecha_realizada", "entreno_realizado", "actualizada_en",
                ])
                vincular.estado = SesionProgramada.ESTADO_COMPLETADA
                vincular.fecha_realizada = _fecha_entreno(entreno)
                vincular.entreno_realizado = entreno
                vincular.save(update_fields=[
                    "estado", "fecha_realizada", "entreno_realizado", "actualizada_en",
                ])
            else:
                transaction.set_rollback(True)
            self.stdout.write(json.dumps(payload, sort_keys=True))

    def _sesion(self, pk, cliente_id):
        try:
            sesion = SesionProgramada.objects.select_for_update().get(pk=pk)
        except SesionProgramada.DoesNotExist as exc:
            raise CommandError(f"Sesión {pk} inexistente.") from exc
        if sesion.cliente_id != cliente_id:
            raise CommandError(f"Sesión {pk} no pertenece al cliente {cliente_id}.")
        return sesion

    def _entreno(self, pk, cliente_id):
        try:
            entreno = EntrenoRealizado.objects.select_for_update().select_related("rutina").get(pk=pk)
        except EntrenoRealizado.DoesNotExist as exc:
            raise CommandError(f"Entreno {pk} inexistente.") from exc
        if entreno.cliente_id != cliente_id:
            raise CommandError(f"Entreno {pk} no pertenece al cliente {cliente_id}.")
        return entreno

    def _validar(self, restaurar, vincular, entreno):
        restauracion_ya_aplicada = (
            restaurar.estado == SesionProgramada.ESTADO_PENDIENTE
            and restaurar.fecha_realizada is None
            and restaurar.entreno_realizado_id is None
        )
        if not restauracion_ya_aplicada and not (
            restaurar.estado == SesionProgramada.ESTADO_COMPLETADA
            and restaurar.fecha_realizada is not None
            and restaurar.entreno_realizado_id is None
        ):
            raise CommandError("La sesión a restaurar no tiene el patrón seguro de falso completado.")

        vinculo_ya_aplicado = (
            vincular.estado == SesionProgramada.ESTADO_COMPLETADA
            and vincular.entreno_realizado_id == entreno.pk
            and vincular.fecha_realizada == _fecha_entreno(entreno)
        )
        if not vinculo_ya_aplicado and not (
            vincular.estado == SesionProgramada.ESTADO_PENDIENTE
            and vincular.entreno_realizado_id is None
            and vincular.fecha_realizada is None
        ):
            raise CommandError("La sesión a vincular no está pendiente ni ya reparada.")
        if not entreno.rutina_id or _normalizar(entreno.rutina.nombre) != _normalizar(vincular.nombre_sesion):
            raise CommandError("El nombre de la rutina no coincide con la sesión a vincular.")
        if _fecha_entreno(entreno) != vincular.fecha_prevista:
            raise CommandError("La fecha efectiva del entreno no coincide con la fecha prevista.")
        usado_por = SesionProgramada.objects.filter(entreno_realizado=entreno).exclude(pk=vincular.pk).first()
        if usado_por:
            raise CommandError(f"El entreno ya está vinculado a la sesión {usado_por.pk}.")
