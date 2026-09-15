import math

def es_primera_sesion_tras_ausencia(cliente, fecha, dias_minimos=6):
    """Solo una ausencia confirmada de duración suficiente activa el retorno."""
    from django.db.models import Q
    from entrenos.models import AusenciaPlanificadaGym, EntrenoRealizado

    ausencias = AusenciaPlanificadaGym.objects.filter(
        cliente=cliente,
        fin__lt=fecha,
        cancelada_en__isnull=True,
    ).order_by('-fin', '-id')
    ausencia = next(
        (
            item for item in ausencias
            if (item.fin - item.inicio).days + 1 >= dias_minimos
        ),
        None,
    )
    if ausencia is None:
        return False

    # Tras registrar cualquier ejecución posterior al fin, el retorno ya fue
    # consumido y las sesiones siguientes recuperan el plan normal.
    return not EntrenoRealizado.objects.filter(cliente=cliente).filter(
        Q(fecha_ejecucion__gt=ausencia.fin, fecha_ejecucion__lte=fecha)
        | Q(fecha_ejecucion__isnull=True, fecha__gt=ausencia.fin, fecha__lte=fecha)
    ).exists()


def limitar_series_retorno(ejercicios, proporcion=0.75):
    """Limita el total y recorta accesorios antes de tocar los principales."""
    total = sum(max(0, int(ejercicio.get('series', 0) or 0)) for ejercicio in ejercicios)
    objetivo = math.floor(total * proporcion)
    por_retirar = total - objetivo
    if por_retirar <= 0:
        return ejercicios

    for es_principal in (False, True):
        for ejercicio in reversed(ejercicios):
            principal = ejercicio.get('tipo_ejercicio') == 'compuesto_principal'
            if principal != es_principal or por_retirar <= 0:
                continue
            actuales = max(0, int(ejercicio.get('series', 0) or 0))
            retirar = min(actuales, por_retirar)
            ejercicio['series'] = actuales - retirar
            ejercicio['reduccion_fuente'] = 'retorno_ausencia'
            por_retirar -= retirar
    ejercicios[:] = [
        ejercicio for ejercicio in ejercicios
        if int(ejercicio.get('series', 0) or 0) > 0
    ]
    return ejercicios
