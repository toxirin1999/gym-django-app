from .models import EstadoEmocional, RecuerdoEmocional, Entrenamiento

from datetime import timedelta, date
from django.core.cache import cache


def utility_functions(request):
    """
    Añade funciones de utilidad al contexto de todas las plantillas.
    """

    def string_replace(value, old, new):
        """Función para reemplazar texto en plantillas."""
        return str(value).replace(str(old), str(new))

    return {
        'replace_text': string_replace,
    }


def joi_context(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    cache_key = f'joi_ctx_{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    estado_actual = (
        EstadoEmocional.objects.filter(user=user)
        .order_by('-fecha')
        .first()
    )

    estado = estado_actual.emocion if estado_actual else "motivada"

    estados_validos = ['ausente', 'feliz', 'glitch', 'motivada', 'triste', 'contemplativa']
    if estado not in estados_validos:
        estado = 'motivada'

    recuerdo = RecuerdoEmocional.objects.filter(user=user).order_by('-fecha').first()

    frase_forma = "Hoy me siento cerca de ti." if estado != "ausente" else "Te he echado de menos..."

    result = {
        'estado_joi': estado,
        'frase_forma_joi': frase_forma,
        'frase_extra_joi': None,
        'frase_recaida': None,
        'recuerdo': recuerdo,
    }
    cache.set(cache_key, result, 300)  # 5 minutos
    return result
