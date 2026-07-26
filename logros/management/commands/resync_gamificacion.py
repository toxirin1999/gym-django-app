# logros/management/commands/resync_gamificacion.py

from django.core.management.base import BaseCommand
from logros.models import PerfilGamificacion
from entrenos.models import EntrenoRealizado


class Command(BaseCommand):
    help = 'Resincroniza los contadores de entrenamientos en los perfiles de gamificación.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando resincronización de perfiles de gamificación ---'))

        perfiles = PerfilGamificacion.objects.select_related('cliente').all()

        for perfil in perfiles:
            # Contamos los entrenamientos reales desde la base de datos
            entrenos_reales = EntrenoRealizado.objects.filter(cliente=perfil.cliente).count()

            # Comparamos con el valor guardado en el perfil
            if perfil.entrenos_totales != entrenos_reales:
                self.stdout.write(
                    self.style.WARNING(
                        f'Inconsistencia encontrada para {perfil.cliente.nombre} (ID: {perfil.id}): '
                        f'Perfil dice {perfil.entrenos_totales}, pero en realidad son {entrenos_reales}.'
                    )
                )

                # Actualizamos el contador en el perfil
                perfil.entrenos_totales = entrenos_reales
                perfil.save(update_fields=['entrenos_totales'])

                self.stdout.write(self.style.SUCCESS(f'  -> Perfil de {perfil.cliente.nombre} corregido.'))
            else:
                self.stdout.write(f'Perfil de {perfil.cliente.nombre} (ID: {perfil.id}) está sincronizado.')

        self.stdout.write(self.style.SUCCESS('--- Resincronización completada ---'))
