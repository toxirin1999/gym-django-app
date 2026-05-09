from .models import EstadoEmocional, RecuerdoEmocional, Entrenamiento

import datetime
from django.core.cache import cache


def utility_functions(request):
    def string_replace(value, old, new):
        return str(value).replace(str(old), str(new))

    return {'replace_text': string_replace}


def _apertura_on_demand(user):
    """
    Genera apertura_manana síncronamente si no existe ninguna para hoy.
    Lock de caché de 10 min para no llamar a Haiku en cada request.
    Retorna el MensajeJOI generado, o None si ya existe / falla.
    """
    hoy = datetime.date.today()
    lock_key = f'joi_apertura_lock_{user.id}_{hoy}'
    if cache.get(lock_key):
        return None

    from joi.models import MensajeJOI
    ya_existe = MensajeJOI.objects.filter(
        user=user, trigger='apertura_manana', creado_en__date=hoy
    ).exists()
    if ya_existe:
        return None

    # Poner el lock antes de llamar a Haiku para evitar llamadas paralelas
    cache.set(lock_key, True, 600)
    try:
        from clientes.models import Cliente
        from joi.services import generar_mensaje_joi
        cliente = Cliente.objects.filter(user=user).first()
        if not cliente:
            return None
        return generar_mensaje_joi(cliente, 'apertura_manana')
    except Exception:
        # Si falla, liberar el lock para que lo reintente en 10 min
        cache.delete(lock_key)
        return None


def _get_mensaje_gym(user):
    """
    Mensaje sin leer más reciente de triggers NO-Hyrox (gym, apertura, resumen...).
    Si no hay ninguno, intenta generar apertura_manana on-demand.
    """
    from joi.models import MensajeJOI
    mensaje = (
        MensajeJOI.objects
        .filter(user=user, leido=False)
        .exclude(trigger__startswith='hyrox_')
        .first()
    )
    if mensaje:
        return mensaje
    return _apertura_on_demand(user)


def _get_mensaje_hyrox(user):
    """
    Mensaje sin leer más reciente de triggers Hyrox.
    No genera on-demand — los mensajes Hyrox los crean signals y tareas Celery.
    """
    from joi.models import MensajeJOI
    return (
        MensajeJOI.objects
        .filter(user=user, leido=False, trigger__startswith='hyrox_')
        .first()
    )


def joi_context(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    cache_key = f'joi_ctx_{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        cached['joi_mensaje_pendiente'] = _get_mensaje_gym(user)
        cached['joi_mensaje_hyrox']     = _get_mensaje_hyrox(user)
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
        'estado_joi':      estado,
        'frase_forma_joi': frase_forma,
        'frase_extra_joi': None,
        'frase_recaida':   None,
        'recuerdo':        recuerdo,
    }
    cache.set(cache_key, result, 300)
    result['joi_mensaje_pendiente'] = _get_mensaje_gym(user)
    result['joi_mensaje_hyrox']     = _get_mensaje_hyrox(user)
    return result
