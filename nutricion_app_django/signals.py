from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='clientes.PesoDiario')
def recalcular_perfil_en_nuevo_peso(sender, instance, created, **kwargs):
    """
    Cada vez que se registra un nuevo peso, recalcula la masa magra
    del PerfilNutricional del cliente.
    """
    if not created:
        return
    try:
        perfil = instance.cliente.perfil_nutricional
        perfil.save()  # dispara _calcular_navy() y _get_peso_actual()
    except Exception:
        pass  # cliente sin perfil nutricional configurado


@receiver(post_save, sender='clientes.Cliente')
def recalcular_perfil_en_cambio_medidas(sender, instance, **kwargs):
    """
    Si cambian cintura, cuello o caderas en el perfil del cliente,
    recalcula la composición corporal.
    """
    try:
        perfil = instance.perfil_nutricional
        perfil.save()
    except Exception:
        pass


@receiver(post_save, sender='entrenos.EntrenoRealizado')
def regenerar_target_tras_entreno(sender, instance, created, **kwargs):
    """
    Cuando se registra un nuevo entrenamiento, regenera el target nutricional
    del día para reflejar el tipo correcto (carga/moderado/descarga).
    """
    if not created:
        return
    from .services import generar_target_diario
    try:
        generar_target_diario(instance.cliente, instance.fecha)
    except Exception:
        pass
