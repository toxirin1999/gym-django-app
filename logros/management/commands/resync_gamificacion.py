# en gamificacion/management/commands/resync_gamificacion.py

from django.core.management.base import BaseCommand
# Opción 1: Si el modelo está en la app 'logros'
from logros.models import GamificationProfile, LogroUsuario  # Ajusta la importación a tu modelo

from entrenos.models import EntrenoRealizado  # Ajusta la importación a tu modelo


class Command(BaseCommand):
    help = 'Resincroniza los contadores de entrenamientos en los perfiles de gamificación.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando resincronización de perfiles de gamificación ---'))

        perfiles = GamificationProfile.objects.all()

        for perfil in perfiles:
            # Contamos los entrenamientos reales desde la base de datos
            entrenos_reales = EntrenoRealizado.objects.filter(cliente=perfil.cliente).count()

            # Comparamos con el valor guardado en el perfil
            if perfil.total_entrenamientos != entrenos_reales:
                self.stdout.write(
                    self.style.WARNING(
                        f'Inconsistencia encontrada para {perfil.cliente.nombre} (ID: {perfil.id}): '
                        f'Perfil dice {perfil.total_entrenamientos}, pero en realidad son {entrenos_reales}.'
                    )
                )

                # Actualizamos el contador en el perfil
                perfil.total_entrenamientos = entrenos_reales
                perfil.save(update_fields=['total_entrenamientos'])

                self.stdout.write(self.style.SUCCESS(f'  -> Perfil de {perfil.cliente.nombre} corregido.'))
            else:
                self.stdout.write(f'Perfil de {perfil.cliente.nombre} (ID: {perfil.id}) está sincronizado.')

        self.stdout.write(self.style.SUCCESS('--- Resincronización completada ---'))
