import logging

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='clientes.FaseCliente')
def _fase_cliente_pre_save(sender, instance, **kwargs):
    """Guarda si fecha_fin era None antes de guardar."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._fecha_fin_era_none = old.fecha_fin is None
        except sender.DoesNotExist:
            instance._fecha_fin_era_none = False
    else:
        instance._fecha_fin_era_none = False


@receiver(post_save, sender='clientes.FaseCliente')
def _fase_cliente_cerrada(sender, instance, created, **kwargs):
    """
    Cuando se cierra una FaseCliente (fecha_fin pasa de None a una fecha),
    genera automáticamente la narrativa de bloque de JOI.
    """
    if created:
        return
    if not instance.fecha_fin:
        return
    if not getattr(instance, '_fecha_fin_era_none', False):
        return

    # La fase acaba de cerrarse
    try:
        from joi.services import generar_narrativa_bloque
        resultado = generar_narrativa_bloque(instance.cliente, instance)
        if resultado:
            logger.info(
                f"[JOI bloque] narrativa de bloque generada automáticamente "
                f"para {instance.cliente.user.username} — {instance.get_fase_display()}"
            )
    except Exception as e:
        logger.error(f"[JOI bloque] señal _fase_cliente_cerrada falló: {e}", exc_info=True)
