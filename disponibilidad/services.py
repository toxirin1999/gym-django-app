from datetime import timedelta

from django.utils import timezone

from .models import RegistroDisponibilidad

UMBRAL_HORAS_SIN_REGISTRO = 6
PENALIZACION_MAXIMA_HUECO = 50
PENALIZACION_POR_HORA = 5
PENALIZACION_MAYORIA_RECURSO = 15
BONUS_ULTIMO_COMPLETA = 10
VENTANA_MEZCLA_HORAS = 24


def calcular_energia_disponible(cliente):
    """Fase 1 de PLAN_ENERGIA_DISPONIBLE.md — score determinista, sin IA, sin cruzar con entrenos todavía."""
    ultimo = RegistroDisponibilidad.objects.filter(cliente=cliente).order_by('-timestamp').first()
    if not ultimo:
        return {'score': None, 'motivo': 'sin_datos'}

    ahora = timezone.now()
    horas_desde_ultimo = (ahora - ultimo.timestamp).total_seconds() / 3600

    score = 100.0

    if horas_desde_ultimo > UMBRAL_HORAS_SIN_REGISTRO:
        penalizacion_hueco = min(
            PENALIZACION_MAXIMA_HUECO,
            (horas_desde_ultimo - UMBRAL_HORAS_SIN_REGISTRO) * PENALIZACION_POR_HORA,
        )
        score -= penalizacion_hueco

    ventana = RegistroDisponibilidad.objects.filter(
        cliente=cliente, timestamp__gte=ahora - timedelta(hours=VENTANA_MEZCLA_HORAS)
    )
    n_total = ventana.count()
    n_recurso = ventana.filter(nivel=RegistroDisponibilidad.NIVEL_RECURSO).count()
    if n_total > 0 and n_recurso > n_total / 2:
        score -= PENALIZACION_MAYORIA_RECURSO

    if ultimo.nivel == RegistroDisponibilidad.NIVEL_COMPLETA and horas_desde_ultimo <= VENTANA_MEZCLA_HORAS:
        score += BONUS_ULTIMO_COMPLETA

    score = max(0, min(100, round(score)))

    return {
        'score': score,
        'horas_desde_ultimo': round(horas_desde_ultimo, 1),
        'ultimo_nivel': ultimo.get_nivel_display(),
    }
