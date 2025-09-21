from .models import EstadoEmocional, RecuerdoEmocional, Entrenamiento

from datetime import timedelta, date


def joi_context(request):
    if request.user.is_authenticated:
        estado_joi = obtener_estado_joi(request.user)  # función que devuelve el estado emocional actual
        return {'estado_joi': estado_joi}
    return {}


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

    estado_actual = (
        EstadoEmocional.objects.filter(user=user)
        .order_by('-fecha')
        .first()
    )

    estado = estado_actual.emocion if estado_actual else "motivada"

    # Control de estados válidos
    estados_validos = ['ausente', 'feliz', 'glitch', 'motivada', 'triste', 'contemplativa']
    if estado not in estados_validos:
        estado = 'motivada'

    entrenos_recientes = Entrenamiento.objects.filter(user=user, fecha__gte=date.today() - timedelta(days=7))
    recuerdo = RecuerdoEmocional.objects.filter(user=user).order_by('-fecha').first()

    # Mensajes Joi
    frase_forma = "Hoy me siento cerca de ti." if estado != "ausente" else "Te he echado de menos..."
    frase_extra = None
    frase_recaida = None

    return {
        'estado_joi': estado,
        'frase_forma_joi': frase_forma,
        'frase_extra_joi': frase_extra,
        'frase_recaida': frase_recaida,
        'recuerdo': recuerdo,
    }
