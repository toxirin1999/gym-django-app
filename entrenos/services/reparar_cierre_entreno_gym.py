import json
import unicodedata
from pathlib import Path

from django.db import transaction

from entrenos.models import EntrenoRealizado, SerieRealizada


class ReparacionCierreEntrenoError(ValueError):
    pass


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def _parsear_series(especificacion):
    try:
        nombre, numeros = especificacion.rsplit(":", 1)
    except ValueError as exc:
        raise ReparacionCierreEntrenoError(
            f"Formato inválido: {especificacion!r}. Usa 'Ejercicio:1-4' o 'Ejercicio:2'."
        ) from exc
    nombre = nombre.strip()
    if not nombre:
        raise ReparacionCierreEntrenoError("El nombre del ejercicio no puede estar vacío.")
    try:
        if "-" in numeros:
            inicio, fin = (int(valor.strip()) for valor in numeros.split("-", 1))
            if inicio < 1 or fin < inicio:
                raise ValueError
            seleccion = list(range(inicio, fin + 1))
        else:
            seleccion = [int(numeros.strip())]
            if seleccion[0] < 1:
                raise ValueError
    except ValueError as exc:
        raise ReparacionCierreEntrenoError(f"Rango de series inválido: {numeros!r}.") from exc
    return nombre, seleccion


def _resolver_series(entreno, especificaciones):
    todas = list(
        SerieRealizada.objects.filter(entreno=entreno)
        .select_related("ejercicio")
        .order_by("id")
    )
    seleccionadas = {}
    for especificacion in especificaciones:
        nombre, numeros = _parsear_series(especificacion)
        normalizado = _normalizar(nombre)
        coincidencias = [s for s in todas if _normalizar(s.ejercicio.nombre) == normalizado]
        nombres = {s.ejercicio_id for s in coincidencias}
        if not coincidencias:
            raise ReparacionCierreEntrenoError(f"No existe el ejercicio {nombre!r} en el entreno.")
        if len(nombres) != 1:
            raise ReparacionCierreEntrenoError(f"El ejercicio {nombre!r} no identifica un registro único.")
        por_numero = {s.serie_numero: s for s in coincidencias}
        faltantes = [numero for numero in numeros if numero not in por_numero]
        if faltantes:
            raise ReparacionCierreEntrenoError(
                f"No existen las series {faltantes} de {nombre!r}; no se aplicó ningún cambio."
            )
        for numero in numeros:
            seleccionadas[por_numero[numero].pk] = por_numero[numero]
    return list(seleccionadas.values())


def _estado_actual(entreno, series):
    sesion = getattr(entreno, "sesion_detalle", None)
    actividad = getattr(entreno, "hub_actividad", None)
    return {
        "entreno_id": entreno.pk,
        "duracion_entreno": entreno.duracion_minutos,
        "duracion_sesion": sesion.duracion_minutos if sesion else None,
        "actividad_id": actividad.pk if actividad else None,
        "duracion_actividad": actividad.duracion_minutos if actividad else None,
        "series": [{"id": serie.pk, "tecnica_calidad": serie.tecnica_calidad} for serie in series],
    }


def _guardar_backup(ruta, estado):
    path = Path(ruta).expanduser()
    if path.exists():
        existente = json.loads(path.read_text(encoding="utf-8"))
        if existente.get("entreno_id") != estado["entreno_id"]:
            raise ReparacionCierreEntrenoError("El backup existente pertenece a otro entreno.")
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


@transaction.atomic
def reparar_cierre_entreno_gym(*, entreno_id, duracion_minutos, tecnica_buena, apply=False, backup_file=None):
    try:
        entreno = EntrenoRealizado.objects.select_for_update().get(pk=entreno_id)
    except EntrenoRealizado.DoesNotExist as exc:
        raise ReparacionCierreEntrenoError(f"No existe el entreno {entreno_id}.") from exc
    if duracion_minutos is None or duracion_minutos < 1:
        raise ReparacionCierreEntrenoError("La duración debe ser un entero positivo.")
    series = _resolver_series(entreno, tecnica_buena)
    estado = _estado_actual(entreno, series)
    series_a_cambiar = [serie for serie in series if serie.tecnica_calidad != "buena"]
    duraciones_actualizadas = sum(
        valor is not None and valor != duracion_minutos
        for valor in (estado["duracion_entreno"], estado["duracion_sesion"], estado["duracion_actividad"])
    )
    backup_resuelto = None
    if apply:
        if backup_file:
            backup_resuelto = _guardar_backup(backup_file, estado)
        if entreno.duracion_minutos != duracion_minutos:
            entreno.duracion_minutos = duracion_minutos
            entreno.save(update_fields=["duracion_minutos"])
        sesion = getattr(entreno, "sesion_detalle", None)
        if sesion and sesion.duracion_minutos != duracion_minutos:
            sesion.duracion_minutos = duracion_minutos
            sesion.save(update_fields=["duracion_minutos"])
        actividad = getattr(entreno, "hub_actividad", None)
        if actividad and actividad.duracion_minutos != duracion_minutos:
            actividad.duracion_minutos = duracion_minutos
            actividad.save(update_fields=["duracion_minutos"])
        SerieRealizada.objects.filter(pk__in=[s.pk for s in series_a_cambiar]).update(tecnica_calidad="buena")
    return {
        "entreno_id": entreno_id,
        "modo": "apply" if apply else "dry-run",
        "duracion_minutos": duracion_minutos,
        "duraciones_actualizadas": duraciones_actualizadas,
        "series_actualizadas": len(series_a_cambiar),
        "backup_file": backup_resuelto,
        "reversible": bool(backup_file),
    }


@transaction.atomic
def restaurar_cierre_entreno_gym(*, entreno_id, backup_file):
    path = Path(backup_file).expanduser()
    if not path.exists():
        raise ReparacionCierreEntrenoError(f"No existe el backup {path}.")
    datos = json.loads(path.read_text(encoding="utf-8"))
    if datos.get("entreno_id") != entreno_id:
        raise ReparacionCierreEntrenoError("El backup no pertenece al entreno indicado.")
    try:
        entreno = EntrenoRealizado.objects.select_for_update().get(pk=entreno_id)
    except EntrenoRealizado.DoesNotExist as exc:
        raise ReparacionCierreEntrenoError(f"No existe el entreno {entreno_id}.") from exc
    entreno.duracion_minutos = datos["duracion_entreno"]
    entreno.save(update_fields=["duracion_minutos"])
    sesion = getattr(entreno, "sesion_detalle", None)
    if sesion and datos.get("duracion_sesion") is not None:
        sesion.duracion_minutos = datos["duracion_sesion"]
        sesion.save(update_fields=["duracion_minutos"])
    actividad = getattr(entreno, "hub_actividad", None)
    if actividad and datos.get("actividad_id") == actividad.pk:
        actividad.duracion_minutos = datos.get("duracion_actividad")
        actividad.save(update_fields=["duracion_minutos"])
    restauradas = 0
    for item in datos.get("series", []):
        restauradas += SerieRealizada.objects.filter(
            pk=item["id"], entreno_id=entreno_id
        ).update(tecnica_calidad=item.get("tecnica_calidad"))
    return {"entreno_id": entreno_id, "modo": "restore", "series_restauradas": restauradas}
