import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef

from entrenos.models import ActividadRealizada
from hyrox.models import StravaActivityRaw


FORMATO_BACKUP = "reparar_carga_strava_gym"
VERSION_BACKUP = 1
TOLERANCIA_MIN = 0.8
TOLERANCIA_MAX = 1.25


class Command(BaseCommand):
    help = (
        "Repara exclusivamente cargas Gym históricas con una fusión Strava "
        "demostrable. Por defecto solo audita."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cliente", type=int, default=None)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup-file", default=None)
        parser.add_argument("--rollback-file", default=None)

    def handle(self, *args, **options):
        aplicar = options["apply"]
        backup_file = options["backup_file"]
        rollback_file = options["rollback_file"]
        cliente_id = options["cliente"]

        if aplicar and rollback_file:
            raise CommandError("--apply y --rollback-file son excluyentes")
        if rollback_file:
            if backup_file:
                raise CommandError("--backup-file solo se admite con --apply")
            return self._rollback(Path(rollback_file))
        if backup_file and not aplicar:
            raise CommandError("--backup-file requiere --apply")
        if aplicar and cliente_id is None:
            raise CommandError("--apply exige --cliente")
        if aplicar and not backup_file:
            raise CommandError("--apply exige --backup-file explícito")

        if aplicar:
            return self._aplicar(cliente_id, Path(backup_file))
        return self._auditar(cliente_id)

    def _queryset_base(self, cliente_id=None):
        raw_fusionado = StravaActivityRaw.objects.filter(
            cliente_id=OuterRef("cliente_id"),
            entreno_gym_id=OuterRef("entreno_gym_id"),
            estado="merged",
        )
        qs = (
            ActividadRealizada.objects
            .filter(
                fuente__in=("manual", "liftin"),
                tipo="gym",
                entreno_gym__isnull=False,
                sesion_hyrox__isnull=True,
                rpe_medio__isnull=False,
                duracion_minutos__isnull=False,
            )
            .annotate(_raw_fusionado=Exists(raw_fusionado))
            .filter(_raw_fusionado=True)
            .order_by("id")
        )
        if cliente_id is not None:
            qs = qs.filter(cliente_id=cliente_id)
        return qs

    @staticmethod
    def _propuesta(actividad):
        return round(float(actividad.rpe_medio) * float(actividad.duracion_minutos), 1)

    @classmethod
    def _fuera_tolerancia(cls, actividad, propuesta):
        if actividad.carga_ua is None:
            return True
        actual = float(actividad.carga_ua)
        if actual <= 0:
            return True
        ratio = actual / propuesta if propuesta > 0 else 1.0
        return not (TOLERANCIA_MIN <= ratio <= TOLERANCIA_MAX)

    def _candidatos(self, qs):
        candidatos = []
        for actividad in qs.iterator():
            propuesta = self._propuesta(actividad)
            if not self._fuera_tolerancia(actividad, propuesta):
                continue
            raw = (
                StravaActivityRaw.objects
                .filter(
                    cliente_id=actividad.cliente_id,
                    entreno_gym_id=actividad.entreno_gym_id,
                    estado="merged",
                )
                .order_by("id")
                .first()
            )
            candidatos.append((actividad, propuesta, raw))
        return candidatos

    def _auditar(self, cliente_id):
        candidatos = self._candidatos(self._queryset_base(cliente_id))
        for actividad, propuesta, raw in candidatos:
            self._emitir_candidato(actividad, propuesta, raw)
        self._json_line(
            tipo_registro="resumen",
            cliente_id=cliente_id,
            candidatos=len(candidatos),
            solo_lectura=True,
        )

    def _aplicar(self, cliente_id, backup_path):
        if backup_path.exists():
            raise CommandError(f"El backup ya existe: {backup_path}")
        if not backup_path.parent.exists():
            raise CommandError(f"La carpeta del backup no existe: {backup_path.parent}")

        with transaction.atomic():
            qs = self._queryset_base(cliente_id).select_for_update()
            candidatos = self._candidatos(qs)
            cambios = [
                self._entrada_backup(actividad, propuesta, raw)
                for actividad, propuesta, raw in candidatos
            ]
            documento = {
                "formato": FORMATO_BACKUP,
                "version": VERSION_BACKUP,
                "cliente_id": cliente_id,
                "cambios": cambios,
            }
            self._crear_backup_exclusivo(backup_path, documento)
            for actividad, propuesta, _raw in candidatos:
                actividad.carga_ua = propuesta
            if candidatos:
                ActividadRealizada.objects.bulk_update(
                    [actividad for actividad, _propuesta, _raw in candidatos],
                    ["carga_ua"],
                    batch_size=500,
                )

        self._json_line(
            tipo_registro="resumen_apply",
            cliente_id=cliente_id,
            aplicados=len(candidatos),
            backup_file=str(backup_path),
        )

    def _rollback(self, backup_path):
        documento = self._leer_backup(backup_path)
        restaurados = 0
        conflictos = 0
        inexistentes = 0

        with transaction.atomic():
            for cambio in documento["cambios"]:
                actividad = (
                    ActividadRealizada.objects
                    .select_for_update()
                    .filter(pk=cambio["id"], cliente_id=documento["cliente_id"])
                    .first()
                )
                if actividad is None:
                    inexistentes += 1
                    self._json_line(
                        tipo_registro="inexistente",
                        id=cambio["id"],
                        accion="omitido",
                    )
                    continue
                if not self._mismo_valor(actividad.carga_ua, cambio["after"]):
                    conflictos += 1
                    self._json_line(
                        tipo_registro="conflicto",
                        id=actividad.pk,
                        actual=actividad.carga_ua,
                        after_esperado=cambio["after"],
                        accion="omitido",
                    )
                    continue
                actividad.carga_ua = cambio["before"]
                actividad.save(update_fields=["carga_ua"])
                restaurados += 1

        self._json_line(
            tipo_registro="resumen_rollback",
            restaurados=restaurados,
            conflictos=conflictos,
            inexistentes=inexistentes,
        )

    @staticmethod
    def _mismo_valor(actual, esperado):
        if actual is None or esperado is None:
            return actual is None and esperado is None
        return abs(float(actual) - float(esperado)) < 1e-9

    @staticmethod
    def _entrada_backup(actividad, propuesta, raw):
        return {
            "id": actividad.pk,
            "before": actividad.carga_ua,
            "after": propuesta,
            "evidencia": {
                "entreno_gym_id": actividad.entreno_gym_id,
                "strava_raw_id": raw.pk,
                "strava_estado": raw.estado,
                "fuente": actividad.fuente,
                "tipo": actividad.tipo,
                "rpe_medio": actividad.rpe_medio,
                "duracion_minutos": actividad.duracion_minutos,
            },
        }

    def _emitir_candidato(self, actividad, propuesta, raw):
        ratio = None
        if actividad.carga_ua not in (None, 0):
            ratio = round(propuesta / float(actividad.carga_ua), 2)
        self._json_line(
            tipo_registro="candidato",
            id=actividad.pk,
            before=actividad.carga_ua,
            after=propuesta,
            ratio_propuesto_actual=ratio,
            entreno_gym_id=actividad.entreno_gym_id,
            strava_raw_id=raw.pk,
            fuente=actividad.fuente,
        )

    @staticmethod
    def _crear_backup_exclusivo(path, documento):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise CommandError(f"El backup ya existe: {path}") from exc
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                json.dump(documento, archivo, sort_keys=True, separators=(",", ":"))
                archivo.write("\n")
                archivo.flush()
                os.fsync(archivo.fileno())
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _leer_backup(path):
        try:
            with path.open(encoding="utf-8") as archivo:
                documento = json.load(archivo)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Backup ilegible o inválido: {path}") from exc
        if not isinstance(documento, dict):
            raise CommandError("Formato de backup inválido")
        if documento.get("formato") != FORMATO_BACKUP:
            raise CommandError("El archivo no pertenece a reparar_carga_strava_gym")
        if documento.get("version") != VERSION_BACKUP:
            raise CommandError("Versión de backup no soportada")
        if not isinstance(documento.get("cliente_id"), int):
            raise CommandError("cliente_id inválido en backup")
        cambios = documento.get("cambios")
        if not isinstance(cambios, list):
            raise CommandError("Lista de cambios inválida en backup")
        for cambio in cambios:
            if not isinstance(cambio, dict) or not {"id", "before", "after"} <= cambio.keys():
                raise CommandError("Entrada de cambio inválida en backup")
        return documento

    def _json_line(self, **payload):
        self.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))

