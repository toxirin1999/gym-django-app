from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

# Importa TODOS los modelos que deben crearse junto con un User
from .models import PerfilEstoico, EstadisticaUsuario, ConfiguracionNotificacion
from clientes.models import Cliente  # ¡Importante! También importamos el modelo Cliente


@receiver(post_save, sender=User)
def crear_perfiles_asociados(sender, instance, created, **kwargs):
    """
    Esta función se ejecuta automáticamente DESPUÉS de que un User es creado.
    Se encarga de crear todos los perfiles necesarios en las diferentes apps.

    'created' es un booleano que es True solo la primera vez que se guarda el objeto.
    """
    if created:
        # 1. Crear el PerfilEstoico.
        #    Ya no pasamos argumentos extra, Django usará los 'default' del modelo.
        PerfilEstoico.objects.create(usuario=instance)

        # 2. Crear las EstadisticasUsuario.
        EstadisticaUsuario.objects.create(usuario=instance)

        # 3. Crear la ConfiguracionNotificacion.
        ConfiguracionNotificacion.objects.create(usuario=instance)

        # 4. Crear el Cliente.
        #    Esto es crucial para que la vista 'panel_cliente' funcione.
        Cliente.objects.create(user=instance, nombre=instance.username, email=instance.email)

        print(f"✅ Perfiles creados para el nuevo usuario: {instance.username}")
