from django.core.management.base import BaseCommand
from entrenos.models import EjercicioBase

EJERCICIOS_PREDEFINIDOS = [
    ("Press en máquina", "Hombros"),
    ("Elevaciones laterales", "Hombros"),
    ("Elevaciones frontales", "Hombros"),
    ("Pájaros (elevaciones posteriores)", "Hombros"),
    ("Face pull", "Hombros"),
    ("Encogimientos con mancuernas", "Hombros"),
    ("Curl con barra", "Bíceps"),
    ("Curl alterno con mancuernas", "Bíceps"),
    ("Curl martillo", "Bíceps"),
    ("Curl concentración", "Bíceps"),
    ("Curl en banco scott", "Bíceps"),
    ("Curl en polea baja", "Bíceps"),
    ("Fondos en paralelas (tríceps)", "Tríceps"),
    ("Extensión en polea alta", "Tríceps"),
    ("Press francés", "Tríceps"),
    ("Patada de tríceps", "Tríceps"),
    ("Extensión con mancuerna sobre cabeza", "Tríceps"),
    ("Crunch abdominal", "Core"),
    ("Crunch en máquina", "Core"),
    ("Plancha", "Core"),
    ("Elevaciones de piernas colgado", "Core"),
    ("Tijeras abdominales", "Core"),
    ("Rueda abdominal", "Core"),
    ("Twist ruso con disco", "Core"),
    ("Cinta de correr", "Cardio"),
    ("Bicicleta estática", "Cardio"),
    ("Elíptica", "Cardio"),
    ("Remo ergómetro", "Cardio"),
    ("Cuerda para saltar", "Cardio"),
    ("Burpees", "Cardio"),
    ("Mountain climbers", "Cardio"),
    ("Battle ropes", "Cardio"),

]


class Command(BaseCommand):
    help = 'Carga la base de datos con ejercicios predefinidos'

    def cargar_ejercicios():
        # Limpiar tabla antes de insertar para evitar duplicados

        print("Tabla EjercicioBase limpiada")

        nuevos = 0
        for nombre, grupo in EJERCICIOS_PREDEFINIDOS:
            obj, creado = EjercicioBase.objects.update_or_create(
                nombre=nombre,
                defaults={'grupo_muscular': grupo}
            )
            if creado:
                print(f"Creado: {nombre} ({grupo})")
                nuevos += 1
            else:
                print(f"Actualizado: {nombre} ({grupo})")

        print(f"Ejercicios creados: {nuevos}")

    def handle(self, *args, **options):
        self.stdout.write("Limpiando tabla EjercicioBase...")

        self.stdout.write("Tabla EjercicioBase limpiada")

        nuevos = 0
        for nombre, grupo in EJERCICIOS_PREDEFINIDOS:
            EjercicioBase.objects.create(nombre=nombre, grupo_muscular=grupo)
            self.stdout.write(f"Creado: {nombre} ({grupo})")
            nuevos += 1

        self.stdout.write(f"Ejercicios creados: {nuevos}")
