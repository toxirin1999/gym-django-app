from datetime import timedelta

from django.utils import timezone


def validar_estado_animo_post(valor):
    """Devuelve (es_valido, mood) para el valor opcional recibido por POST."""
    if valor in (None, ""):
        return True, None

    try:
        estado_animo = int(valor)
    except (TypeError, ValueError):
        return False, None

    if estado_animo not in range(1, 6):
        return False, None

    return True, estado_animo


def sincronizar_racha_escritura(usuario):
    """Reconstruye la racha usando ReflexionLibre como fuente canónica."""
    from diario.models import RachaEscritura, ReflexionLibre

    fechas = set()
    for instante in ReflexionLibre.objects.filter(usuario=usuario).values_list('fecha', flat=True):
        if timezone.is_aware(instante):
            instante = timezone.localtime(instante)
        fechas.add(instante.date())
    fechas = sorted(fechas)

    racha, _ = RachaEscritura.objects.get_or_create(usuario=usuario)
    if not fechas:
        racha.dias_consecutivos = 0
        racha.fecha_ultima_entrada = None
        racha.racha_maxima = 0
        racha.fecha_racha_maxima = None
        racha.total_dias_escritos = 0
    else:
        racha_en_curso = 1
        racha_maxima = 1
        fecha_racha_maxima = fechas[0]
        for anterior, actual in zip(fechas, fechas[1:]):
            if (actual - anterior).days == 1:
                racha_en_curso += 1
            else:
                racha_en_curso = 1
            if racha_en_curso > racha_maxima:
                racha_maxima = racha_en_curso
                fecha_racha_maxima = actual

        racha_vigente = fechas[-1] >= timezone.localdate() - timedelta(days=1)
        racha.dias_consecutivos = racha_en_curso if racha_vigente else 0
        racha.fecha_ultima_entrada = fechas[-1]
        racha.racha_maxima = racha_maxima
        racha.fecha_racha_maxima = fecha_racha_maxima
        racha.total_dias_escritos = len(fechas)

    racha.save(update_fields=[
        'dias_consecutivos',
        'fecha_ultima_entrada',
        'racha_maxima',
        'fecha_racha_maxima',
        'total_dias_escritos',
    ])
    return racha
