from django.core.management.base import BaseCommand
from entrenos.models import EjercicioBase
from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE

class Command(BaseCommand):
    help = 'Sincroniza la tabla EjercicioBase con la base de datos de ejercicios del planificador Helms'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando sincronización de ejercicios...")
        
        nuevos = 0
        actualizados = 0
        
        for grupo, categorias in EJERCICIOS_DATABASE.items():
            for categoria, ejercicios in categorias.items():
                for ej_data in ejercicios:
                    nombre = ej_data.get('nombre')
                    if not nombre:
                        continue
                        
                    # Mapear 'pecho' -> 'Pecho', 'espalda' -> 'Espalda', etc.
                    nombre_grupo = grupo.capitalize()
                    
                    obj, creado = EjercicioBase.objects.update_or_create(
                        nombre=nombre,
                        defaults={
                            'grupo_muscular': nombre_grupo
                        }
                    )
                    
                    if creado:
                        self.stdout.write(self.style.SUCCESS(f"  + Creado: {nombre} ({nombre_grupo})"))
                        nuevos += 1
                    else:
                        actualizados += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"\nSincronización completada: {nuevos} nuevos, {actualizados} actualizados."
        ))
