from .models import EstadoEmocional, RecuerdoEmocional, Entrenamiento

from django.core.cache import cache
from django.utils import timezone

# Triggers que solo deben aparecer en /joi/habitacion/.
# No se inyectan en el context processor global — permanecen en la habitación.
# Razón: tratan ausencia, retorno o interpretación personal profunda.
# JOI permanece; no aparece por toda la app reclamando presencia.
TRIGGERS_SOLO_HABITACION = frozenset({
    'ausencia_detectada',
    'hyrox_ausencia',
    'dialogo_respondido',
    'sintesis_joi',
})


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
    try:
        from clientes.models import Cliente
        from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador
        cliente = Cliente.objects.filter(user=user).first()
        if not cliente:
            return None
        return resolver_apertura_diaria_entrenador(cliente)
    except Exception:
        # Antes: cache.delete(lock_key) — liberaba el lock al instante pese a que
        # el comentario decía "reintentar en 10 min". Si Anthropic está caído de
        # forma sostenida, esto hacía que CADA request de CADA página de la app
        # (joi_context es un context processor global) reintentara la llamada
        # síncrona a Haiku. Ahora se deja el lock puesto — expira solo con su
        # propio TTL de 600s, que es el cooldown real que el comentario pretendía.
        return None


def _get_mensaje_gym(user):
    """
    Mensaje sin leer más reciente de triggers NO-Hyrox (gym, apertura, resumen...).
    Excluye TRIGGERS_SOLO_HABITACION: esos mensajes solo se muestran en /joi/habitacion/.
    Si no hay ninguno, intenta generar apertura_manana on-demand.
    """
    from joi.models import MensajeJOI
    # Triggers a excluir: hyrox_* y los de solo habitación sin prefijo hyrox_
    excluir_triggers = [t for t in TRIGGERS_SOLO_HABITACION if not t.startswith('hyrox_')]
    mensaje = (
        MensajeJOI.objects
        .filter(user=user, leido=False)
        .exclude(trigger__startswith='hyrox_')
        .exclude(trigger__in=excluir_triggers)
        .order_by('-creado_en')
        .first()
    )
    if mensaje:
        return mensaje

    # Con hechos ejecutivos pendientes entramos directamente por el resolvedor
    # canónico: un fallo no debe caer después en una apertura limpia. Sin cola
    # conservamos el seam histórico de apertura bajo demanda.
    from joi.models import EventoEntrenadorJOI
    if EventoEntrenadorJOI.objects.filter(user=user, estado='pendiente').exists():
        try:
            from clientes.models import Cliente
            from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador
            cliente = Cliente.objects.filter(user=user).first()
            return resolver_apertura_diaria_entrenador(cliente) if cliente else None
        except Exception:
            return None
    return _apertura_on_demand(user)


def _get_mensaje_hyrox(user):
    """
    Mensaje sin leer más reciente de triggers Hyrox.
    Excluye hyrox_ausencia: pertenece a la habitación, no debe aparecer fuera.
    No genera on-demand — los mensajes Hyrox los crean signals y tareas Celery.
    """
    from hyrox.campaign_authority import objetivo_autorizado_campana
    try:
        cliente = user.cliente_perfil
    except Exception:
        return None
    if objetivo_autorizado_campana(cliente, accion='joi_hyrox') is None:
        return None

    from joi.models import MensajeJOI
    hyrox_solo_habitacion = [t for t in TRIGGERS_SOLO_HABITACION if t.startswith('hyrox_')]
    return (
        MensajeJOI.objects
        .filter(user=user, leido=False, trigger__startswith='hyrox_')
        .exclude(trigger__in=hyrox_solo_habitacion)
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
    frase_forma = "Hoy me siento cerca de ti." if estado != "ausente" else "La habitación siguió aquí."

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
