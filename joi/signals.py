"""
JOI reactivity signals: invalidate JOI estado when external events occur
(gym sessions with high RPE, lesion reports, etc.)
"""
from django.db.models.signals import post_delete, post_save
from django.db import transaction
from django.dispatch import receiver
from django.core.cache import cache as _cache


@receiver(post_save, sender='diario.ReflexionLibre')
@receiver(post_delete, sender='diario.ReflexionLibre')
def invalidar_contexto_joi_por_reflexion(sender, instance, **kwargs):
    """Un cambio en la memoria invalida su contexto, sin generar presencia JOI."""
    usuario_id = instance.usuario_id
    transaction.on_commit(lambda: _cache.delete(f'joi_ctx_{usuario_id}'))


@receiver(post_save, sender='entrenos.EntrenoRealizado')
def invalidar_joi_por_sesion_alta_rpe(sender, instance, created, **kwargs):
    """
    Cuando se guarda una sesión de gym con RPE alto (>= 8),
    invalida el cache de JOI para que reaccione en la próxima consulta.
    """
    if not created:
        return  # Solo en creación, no en actualización

    try:
        rpe = instance.sesion_detalle.rpe_medio if instance.sesion_detalle else None
        if rpe and rpe >= 8:
            # Invalida cache de JOI estado para este usuario
            # (clave real usada por joi/context_processors.py — antes decía
            # 'joi_estado_...', una clave que nadie lee, así que esto nunca
            # invalidaba nada de verdad)
            cache_key = f'joi_ctx_{instance.cliente.user.id}'
            _cache.delete(cache_key)
    except Exception:
        pass


@receiver(post_save, sender='hyrox.UserInjury')
def invalidar_joi_por_lesion(sender, instance, created, **kwargs):
    """
    Cuando se reporta o actualiza una lesión activa,
    invalida el cache de JOI para que reaccione en la próxima consulta.
    JOI cambiará a estado PROTEGIENDO si la lesión está en fase AGUDA o SUB_AGUDA.
    """
    try:
        if instance.fase in ['AGUDA', 'SUB_AGUDA']:
            # Invalida cache de JOI estado para este usuario.
            # Antes: instance.usuario (UserInjury no tiene ese campo, solo
            # `cliente` — lanzaba AttributeError capturado por el except de
            # abajo, así que esta señal nunca llegó a invalidar nada desde
            # que existe). Y la clave 'joi_estado_...' tampoco la lee nadie
            # — ver joi/context_processors.py, la real es 'joi_ctx_...'.
            cache_key = f'joi_ctx_{instance.cliente.user.id}'
            _cache.delete(cache_key)
    except Exception:
        pass
