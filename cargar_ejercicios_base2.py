from django.core.management.base import BaseCommand
from entrenos.models import EjercicioBase

EJERCICIOS_PREDEFINIDOS = [
    ("Press banca", "Pecho"),
    ("Press inclinado con barra", "Pecho"),
    ("Press inclinado con mancuernas", "Pecho"),
    ("Press declinado", "Pecho"),
    ("Press en máquina", "Pecho"),
    ("Aperturas con mancuernas", "Pecho"),
    ("Aperturas en contractor", "Pecho"),
    ("Fondos en paralelas (pecho)", "Pecho"),
    ("Dominadas", "Espalda"),
    ("Jalón al pecho", "Espalda"),
    ("Jalón tras nuca", "Espalda"),
    ("Remo con barra", "Espalda"),
    ("Remo en polea baja", "Espalda"),
    ("Remo con mancuernas", "Espalda"),
    ("Remo en máquina Hammer", "Espalda"),
    ("Pull-over en polea", "Espalda"),
    ("Sentadilla libre", "Piernas"),
    ("Sentadilla en multipower", "Piernas"),
    ("Prensa inclinada", "Piernas"),
    ("Zancadas caminando", "Piernas"),
    ("Zancadas búlgaras", "Piernas"),
    ("Peso muerto rumano", "Piernas"),
    ("Peso muerto sumo", "Piernas"),
    ("Curl femoral tumbado", "Piernas"),
    ("Curl femoral sentado", "Piernas"),
    ("Extensiones de cuádriceps", "Piernas"),
    ("Elevación de talones sentado", "Piernas"),
    ("Elevación de talones de pie", "Piernas"),
    ("Hip thrust", "Glúteos"),
    ("Patada de glúteo", "Glúteos"),
    ("Abducción de cadera", "Glúteos"),
    ("Step up con mancuernas", "Glúteos"),
    ("Press militar con barra", "Hombros"),
    ("Press militar con mancuernas", "Hombros"),
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

    def handle(self, *args, **options):
        self.stdout.write("Limpiando tabla EjercicioBase...")
        EjercicioBase.objects.all().delete()
        self.stdout.write("Tabla EjercicioBase limpiada")

        nuevos = 0
        for nombre, grupo in EJERCICIOS_PREDEFINIDOS:
            EjercicioBase.objects.create(nombre=nombre, grupo_muscular=grupo)
            self.stdout.write(f"Creado: {nombre} ({grupo})")
            nuevos += 1

        self.stdout.write(f"Ejercicios creados: {nuevos}")
