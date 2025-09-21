# logros/management/commands/actualizar_rankings.py

import sys
from django.core.management.base import BaseCommand
from logros.views import RankingService  # Importamos el servicio desde views.py

# Aseguramos la codificación correcta para la salida en la terminal
sys.stdout.reconfigure(encoding='utf-8')


class Command(BaseCommand):
    help = 'Calcula y actualiza todas las tablas de clasificación (rankings) para la temporada activa.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando la actualización de los rankings...")

        try:
            # Llamamos al método principal del servicio que hace todo el trabajo
            RankingService.actualizar_rankings()

            self.stdout.write(self.style.SUCCESS("\n✅ ¡Todos los rankings han sido actualizados correctamente!"))
            self.stdout.write("El leaderboard ahora mostrará las posiciones más recientes.")

        except Exception as e:
            # Capturamos cualquier posible error durante la actualización para un diagnóstico claro
            self.stdout.write(self.style.ERROR(f"\n❌ Ocurrió un error durante la actualización de rankings: {e}"))
            self.stdout.write("Por favor, revisa la lógica en RankingService y los modelos relacionados.")
