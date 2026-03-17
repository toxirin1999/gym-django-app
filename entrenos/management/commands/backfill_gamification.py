from django.core.management.base import BaseCommand
from django.utils import timezone
from entrenos.models import Cliente, EntrenoRealizado
from logros.services import CodiceService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Procesa entrenamientos antiguos para popular el sistema de gamificación usando el servicio centralizado'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO BACKFILL DE GAMIFICACIÓN CENTRALIZADO ---'))

        # 1. Procesar entrenamientos
        clientes = Cliente.objects.all()
        for cliente in clientes:
            self.stdout.write(f'\nProcesando cliente: {cliente.nombre}')
            
            # Obtener entrenos cronológicamente
            entrenos = EntrenoRealizado.objects.filter(cliente=cliente).order_by('fecha', 'hora_inicio')
            count = entrenos.count()
            
            if count == 0:
                self.stdout.write(f'   Sin entrenamientos.')
                continue

            self.stdout.write(f'   Encontrados {count} entrenamientos. Procesando con CodiceService...')
            
            procesados = 0
            for entreno in entrenos:
                try:
                    # Forzar recalcular volumen antes de procesar si es necesario
                    # (CodiceService._asegurar_sesion_entrenamiento lo hará internamente ahora)
                    
                    # LLAMADA CENTRALIZADA
                    CodiceService.procesar_entreno_completo(entreno)
                    
                    # Marcar como procesado si el modelo tiene ese campo
                    if hasattr(entreno, 'procesado_gamificacion'):
                        entreno.procesado_gamificacion = True
                        entreno.save(update_fields=['procesado_gamificacion'])
                    
                    procesados += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   Error procesando entreno {entreno.id}: {e}'))

            self.stdout.write(self.style.SUCCESS(f'   Cliente {cliente.nombre}: {procesados}/{count} entrenos procesados.'))

        self.stdout.write(self.style.SUCCESS('\n--- BACKFILL COMPLETADO ---'))
