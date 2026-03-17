from django.core.management.base import BaseCommand
from entrenos.models import Cliente, SesionEntrenamiento
from entrenos.services.logros_service import LogrosService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Inicializa logros predefinidos y procesa entrenamientos antiguos para el Dashboard de Evolución'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO SETUP DE GAMIFICACIÓN PARA DASHBOARD ---'))

        # 1. Inicializar Logros Predefinidos
        self.stdout.write('\n1. Inicializando logros predefinidos...')
        creados, actualizados = LogrosService.inicializar_logros_predefinidos()
        self.stdout.write(self.style.SUCCESS(f'   Logros: {creados} creados, {actualizados} actualizados.'))

        # 2. Procesar sesiones existentes
        self.stdout.write('\n2. Procesando historial de sesiones...')
        clientes = Cliente.objects.all()
        
        for cliente in clientes:
            self.stdout.write(f'   Procesando cliente: {cliente.nombre}')
            
            # Obtener sesiones cronológicamente
            sesiones = SesionEntrenamiento.objects.filter(
                entreno__cliente=cliente
            ).order_by('entreno__fecha')
            
            count = sesiones.count()
            if count == 0:
                self.stdout.write(f'     Sin sesiones registradas.')
                continue

            logros_totales = 0
            for sesion in sesiones:
                try:
                    nuevos = LogrosService.verificar_logros_sesion(sesion)
                    if nuevos:
                        logros_totales += len(nuevos)
                        nombres = ", ".join([l.nombre for l in nuevos])
                        self.stdout.write(f'     [Sesión {sesion.entreno.fecha}] 🏆 {nombres}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'     Error en sesión {sesion.id}: {e}'))

            self.stdout.write(self.style.SUCCESS(f'     Total logros desbloqueados: {logros_totales}'))

        self.stdout.write(self.style.SUCCESS('\n--- SETUP COMPLETADO ---'))
