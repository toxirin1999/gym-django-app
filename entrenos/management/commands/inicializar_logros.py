"""
Comando de gestión para inicializar logros predefinidos
Uso: python manage.py inicializar_logros
"""

from django.core.management.base import BaseCommand
from entrenos.services.logros_service import LogrosService


class Command(BaseCommand):
    help = 'Inicializa los logros predefinidos en la base de datos'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Inicializando logros predefinidos...'))
        
        try:
            creados, actualizados = LogrosService.inicializar_logros_predefinidos()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Logros inicializados correctamente:\n'
                    f'   - {creados} logros creados\n'
                    f'   - {actualizados} logros actualizados'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error inicializando logros: {e}')
            )
