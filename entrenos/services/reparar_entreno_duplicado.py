import json
from pathlib import Path

from django.db import transaction
from django.db.models.deletion import Collector

from entrenos.models import (
    ActividadRealizada,
    EntrenoRealizado,
    GymDecisionLog,
    RecordPersonal,
    SesionProgramada,
)
from hyrox.models import StravaActivityRaw
from logros.models import HistorialPuntos, PerfilGamificacion


class ReparacionDuplicadoError(Exception):
    pass


def _valor_campo(obj, field):
    value = getattr(obj, field.attname)
    return value.isoformat() if hasattr(value, "isoformat") else value


def _snapshot(obj):
    return {
        field.attname: _valor_campo(obj, field)
        for field in obj._meta.concrete_fields
    }


def _firma(queryset, omitidos):
    campos = [
        field for field in queryset.model._meta.concrete_fields
        if field.name not in omitidos and field.attname not in omitidos
    ]
    return sorted(
        [[field.attname, _valor_campo(obj, field)] for field in campos]
        for obj in queryset.order_by("pk")
    )


def _validar_igualdad(duplicado, canonico):
    campos = ("cliente_id", "rutina_id", "fecha", "fecha_ejecucion", "volumen_total_kg")
    distintos = [campo for campo in campos if getattr(duplicado, campo) != getattr(canonico, campo)]
    if distintos:
        raise ReparacionDuplicadoError("Entrenos diferentes en: " + ", ".join(distintos))

    ejercicios_duplicado = _firma(
        duplicado.ejercicios_realizados.all(), {"id", "entreno", "entreno_id", "fecha_creacion"}
    )
    ejercicios_canonico = _firma(
        canonico.ejercicios_realizados.all(), {"id", "entreno", "entreno_id", "fecha_creacion"}
    )
    if ejercicios_duplicado != ejercicios_canonico:
        raise ReparacionDuplicadoError("Los ejercicios no coinciden")

    series_duplicado = _firma(duplicado.series.all(), {"id", "entreno", "entreno_id"})
    series_canonico = _firma(canonico.series.all(), {"id", "entreno", "entreno_id"})
    if series_duplicado != series_canonico:
        raise ReparacionDuplicadoError("Las series no coinciden")


def _validar_bloqueos(duplicado, canonico):
    ids = (duplicado.pk, canonico.pk)
    if SesionProgramada.objects.filter(entreno_realizado_id__in=ids).exists():
        raise ReparacionDuplicadoError("Existe una SesionProgramada vinculada")
    if StravaActivityRaw.objects.filter(entreno_gym_id__in=ids).exists():
        raise ReparacionDuplicadoError("Existe una actividad Strava vinculada")

    for record in RecordPersonal.objects.filter(entreno=duplicado):
        if RecordPersonal.objects.filter(
            entreno=canonico,
            ejercicio_nombre=record.ejercicio_nombre,
            tipo_record=record.tipo_record,
        ).exists():
            raise ReparacionDuplicadoError("Existen records equivalentes o conflictivos en el canónico")


def _evidencia(duplicado, canonico, perfil, puntos):
    collector = Collector(using=duplicado._state.db)
    collector.collect([duplicado])
    cascadas = {}
    for model, objects in collector.data.items():
        etiqueta = model._meta.label
        cascadas[etiqueta] = [_snapshot(obj) for obj in sorted(objects, key=lambda obj: obj.pk)]
    for queryset in collector.fast_deletes:
        etiqueta = queryset.model._meta.label
        cascadas.setdefault(etiqueta, []).extend(_snapshot(obj) for obj in queryset.order_by("pk"))
    return {
        "entreno_duplicado": _snapshot(duplicado),
        "entreno_canonico": _snapshot(canonico),
        "ejercicios": [_snapshot(obj) for obj in duplicado.ejercicios_realizados.all()],
        "series": [_snapshot(obj) for obj in duplicado.series.all()],
        "actividad_hub": [_snapshot(obj) for obj in ActividadRealizada.objects.filter(entreno_gym=duplicado)],
        "decisiones": [_snapshot(obj) for obj in GymDecisionLog.objects.filter(entreno_origen=duplicado)],
        "historial_puntos": [_snapshot(obj) for obj in puntos],
        "records": [_snapshot(obj) for obj in RecordPersonal.objects.filter(entreno=duplicado)],
        "perfil_gamificacion": _snapshot(perfil),
        "cascadas_entreno": cascadas,
    }


def reparar_entreno_duplicado(*, duplicado_id, canonico_id, apply=False, backup_path=None):
    if duplicado_id == canonico_id:
        raise ReparacionDuplicadoError("Duplicado y canónico deben ser distintos")

    with transaction.atomic():
        entrenos = {
            obj.pk: obj for obj in EntrenoRealizado.objects.select_for_update().filter(
                pk__in=(duplicado_id, canonico_id)
            )
        }
        if len(entrenos) != 2:
            raise ReparacionDuplicadoError("No se encontraron ambos entrenamientos")
        duplicado, canonico = entrenos[duplicado_id], entrenos[canonico_id]
        _validar_igualdad(duplicado, canonico)
        _validar_bloqueos(duplicado, canonico)

        perfil = PerfilGamificacion.objects.select_for_update().filter(cliente=duplicado.cliente).first()
        if perfil is None:
            raise ReparacionDuplicadoError("No existe PerfilGamificacion para el cliente")
        puntos = list(HistorialPuntos.objects.filter(entreno=duplicado).order_by("pk"))
        puntos_a_restar = sum(item.puntos for item in puntos)
        if perfil.puntos_totales < puntos_a_restar or perfil.entrenos_totales < 1:
            raise ReparacionDuplicadoError("El PerfilGamificacion no permite el ajuste")

        resultado = {
            "dry_run": not apply,
            "duplicado_id": duplicado_id,
            "canonico_id": canonico_id,
            "puntos_a_restar": puntos_a_restar,
            "entrenos_a_restar": 1,
            "records_a_reasignar": RecordPersonal.objects.filter(entreno=duplicado).count(),
        }
        if not apply:
            return resultado
        if not backup_path:
            raise ReparacionDuplicadoError("--apply exige --backup")
        path = Path(backup_path)
        if path.exists():
            raise ReparacionDuplicadoError("El archivo de backup ya existe")
        if not path.parent.exists():
            raise ReparacionDuplicadoError("El directorio del backup no existe")

        evidencia = _evidencia(duplicado, canonico, perfil, puntos)
        path.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2, default=str) + "\n")

        RecordPersonal.objects.filter(entreno=duplicado).update(entreno=canonico)
        ActividadRealizada.objects.filter(entreno_gym=duplicado).delete()
        GymDecisionLog.objects.filter(entreno_origen=duplicado).delete()
        HistorialPuntos.objects.filter(entreno=duplicado).delete()
        perfil.puntos_totales -= puntos_a_restar
        perfil.entrenos_totales -= 1
        perfil.save(update_fields=("puntos_totales", "entrenos_totales"))
        duplicado.delete()
        resultado["backup"] = str(path)
        return resultado
