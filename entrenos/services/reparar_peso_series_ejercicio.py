from decimal import Decimal, InvalidOperation

from django.db import transaction

from entrenos.models import (
    ActividadRealizada,
    EjercicioRealizado,
    EntrenoRealizado,
    GymDecisionLog,
    RecordPersonal,
    SerieRealizada,
    SesionEntrenamiento,
)


class ReparacionPesoSeriesError(ValueError):
    pass


def _decimal(valor, etiqueta):
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReparacionPesoSeriesError(f"{etiqueta} no es un peso válido") from exc


def _volumen_canonico(entreno_id, ejercicio_id, nuevo_peso):
    total = Decimal("0.00")
    ejercicios = EjercicioRealizado.objects.filter(entreno_id=entreno_id).only(
        "id", "peso_kg", "series", "repeticiones",
    )
    for ejercicio in ejercicios:
        peso = nuevo_peso if ejercicio.pk == ejercicio_id else _decimal(
            ejercicio.peso_kg, "peso canónico",
        )
        total += peso * ejercicio.series * ejercicio.repeticiones
    return total.quantize(Decimal("0.01"))


@transaction.atomic
def reparar_peso_series_ejercicio(
    *,
    entreno_id,
    ejercicio_realizado_id,
    expected_nombre,
    expected_series,
    expected_reps,
    expected_peso_anterior,
    nuevo_peso,
    apply=False,
):
    peso_anterior = _decimal(expected_peso_anterior, "peso anterior esperado")
    peso_nuevo = _decimal(nuevo_peso, "nuevo peso")
    if peso_nuevo <= 0 or peso_anterior <= 0 or peso_nuevo == peso_anterior:
        raise ReparacionPesoSeriesError("los pesos deben ser positivos y distintos")
    if expected_series <= 0 or expected_reps <= 0:
        raise ReparacionPesoSeriesError("series y repeticiones esperadas deben ser positivas")

    entrenos = EntrenoRealizado.objects
    ejercicios = EjercicioRealizado.objects
    series_qs = SerieRealizada.objects
    if apply:
        entrenos = entrenos.select_for_update()
        ejercicios = ejercicios.select_for_update()
        series_qs = series_qs.select_for_update()

    try:
        entreno = entrenos.get(pk=entreno_id)
    except EntrenoRealizado.DoesNotExist as exc:
        raise ReparacionPesoSeriesError(f"EntrenoRealizado {entreno_id} no existe") from exc
    try:
        ejercicio = ejercicios.get(pk=ejercicio_realizado_id, entreno=entreno)
    except EjercicioRealizado.DoesNotExist as exc:
        raise ReparacionPesoSeriesError(
            f"EjercicioRealizado {ejercicio_realizado_id} no pertenece al entreno {entreno_id}"
        ) from exc

    if ejercicio.nombre_ejercicio != expected_nombre:
        raise ReparacionPesoSeriesError(
            f"nombre esperado no coincide: {ejercicio.nombre_ejercicio!r}"
        )
    if ejercicio.series != expected_series:
        raise ReparacionPesoSeriesError(
            f"series esperadas {expected_series}, guardadas {ejercicio.series}"
        )
    if ejercicio.repeticiones != expected_reps:
        raise ReparacionPesoSeriesError(
            f"repeticiones esperadas {expected_reps}, guardadas {ejercicio.repeticiones}"
        )

    series = list(
        series_qs.filter(entreno=entreno, ejercicio__nombre__iexact=expected_nombre)
        .select_related("ejercicio")
        .order_by("serie_numero", "pk")
    )
    if len(series) != expected_series:
        raise ReparacionPesoSeriesError(
            f"series esperadas {expected_series}, encontradas {len(series)}"
        )
    if [serie.serie_numero for serie in series] != list(range(1, expected_series + 1)):
        raise ReparacionPesoSeriesError("la numeración de series no coincide con la esperada")
    if any(serie.repeticiones != expected_reps for serie in series):
        raise ReparacionPesoSeriesError("las repeticiones guardadas no coinciden con las esperadas")

    pesos_actuales = {_decimal(serie.peso_kg, "peso de serie") for serie in series}
    peso_ejercicio = _decimal(ejercicio.peso_kg, "peso del ejercicio")
    estado_previo = peso_ejercicio == peso_anterior and pesos_actuales == {peso_anterior}
    ya_aplicado = peso_ejercicio == peso_nuevo and pesos_actuales == {peso_nuevo}
    if not estado_previo and not ya_aplicado:
        raise ReparacionPesoSeriesError(
            "el peso actual no coincide íntegramente con el anterior esperado ni con el nuevo"
        )

    volumen_nuevo = _volumen_canonico(entreno.pk, ejercicio.pk, peso_nuevo)
    resultado = {
        "dry_run": not apply,
        "ya_aplicado": ya_aplicado,
        "entreno_id": entreno.pk,
        "ejercicio_realizado_id": ejercicio.pk,
        "nombre": expected_nombre,
        "peso_anterior": f"{peso_anterior:.2f}",
        "peso_nuevo": f"{peso_nuevo:.2f}",
        "volumen_total_nuevo": f"{volumen_nuevo:.2f}",
        "series_actualizadas": 0 if ya_aplicado or not apply else expected_series,
        "records_actualizados": 0,
        "decisiones_actualizadas": 0,
    }
    if not apply:
        return resultado

    if not ya_aplicado:
        ejercicio.peso_kg = float(peso_nuevo)
        ejercicio.save(update_fields=["peso_kg"])
        SerieRealizada.objects.filter(pk__in=[serie.pk for serie in series]).update(
            peso_kg=peso_nuevo,
        )

    record_ids = list(
        RecordPersonal.objects.select_for_update().filter(
            entreno=entreno,
            ejercicio_nombre__iexact=expected_nombre,
            tipo_record="peso_maximo",
            valor=peso_anterior,
        ).values_list("pk", flat=True)
    )
    decision_ids = list(
        GymDecisionLog.objects.select_for_update().filter(
            entreno_origen=entreno,
            ejercicio__iexact=expected_nombre,
            peso_anterior=float(peso_anterior),
        ).values_list("pk", flat=True)
    )
    sesion_ids = list(
        SesionEntrenamiento.objects.select_for_update()
        .filter(entreno=entreno)
        .values_list("pk", flat=True)
    )
    actividad_ids = list(
        ActividadRealizada.objects.select_for_update()
        .filter(entreno_gym=entreno)
        .values_list("pk", flat=True)
    )

    entreno.volumen_total_kg = volumen_nuevo
    entreno.save(update_fields=["volumen_total_kg"])
    SesionEntrenamiento.objects.filter(pk__in=sesion_ids).update(volumen_sesion=volumen_nuevo)
    ActividadRealizada.objects.filter(pk__in=actividad_ids).update(volumen_kg=volumen_nuevo)
    resultado["records_actualizados"] = RecordPersonal.objects.filter(
        pk__in=record_ids,
    ).update(valor=peso_nuevo)
    resultado["decisiones_actualizadas"] = GymDecisionLog.objects.filter(
        pk__in=decision_ids,
    ).update(peso_anterior=float(peso_nuevo))
    return resultado
