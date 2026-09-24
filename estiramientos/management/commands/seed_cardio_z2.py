"""Crea el catálogo canónico de sesiones de Cardio Z2 / recuperación activa.

Sigue exactamente el mismo patrón que seed_movilidad.py: los planes se crean
como modalidad "movilidad" (para reutilizar el flujo real de "Iniciar y
registrar" ya existente: reproductor, duración/RPE real, sustitución de la
sesión de fuerza del día, etc.), y se distinguen por fase="CARDIO".
"""

from django.core.management.base import BaseCommand

from estiramientos.models import EstiramientoEjercicio, EstiramientoPaso, EstiramientoPlan


PLANES = (
    {
        "codigo": "cardio-z2-bici-remo",
        "nombre": "Bici o remo en Zona 2",
        "fase": "CARDIO",
        "descripcion": "30 min a ritmo constante en Zona 2 (RPE 3-4) para sumar recuperación activa sin acumular fatiga.",
        "pasos": (
            ("Calentamiento progresivo en bici o remo", "Cardiovascular", "Sube el ritmo poco a poco hasta notar la respiración algo más profunda, RPE 2-3.", 300),
            ("Bloque principal Zona 2 (bici o remo)", "Cardiovascular / Piernas", "Mantén un ritmo constante donde puedas hablar en frases cortas, RPE 3-4.", 1200),
            ("Enfriamiento suave", "Cardiovascular", "Baja la intensidad poco a poco hasta recuperar el ritmo respiratorio normal.", 300),
        ),
    },
    {
        "codigo": "cardio-z2-caminata-inclinada",
        "nombre": "Caminata inclinada activa",
        "fase": "CARDIO",
        "descripcion": "20 min de caminata con inclinación para sumar recuperación activa sin impacto.",
        "pasos": (
            ("Calentamiento a ritmo llano", "Cardiovascular / Piernas", "Camina a paso ligero sin inclinación los primeros minutos.", 240),
            ("Bloque con inclinación", "Piernas / Glúteo", "Sube la inclinación de la cinta (o busca una cuesta) y mantén un ritmo cómodo, RPE 3-4.", 900),
            ("Vuelta a la calma", "Cardiovascular", "Baja la inclinación y camina suave hasta normalizar la respiración.", 60),
        ),
    },
)


class Command(BaseCommand):
    help = "Crea o actualiza los planes canónicos de Cardio Z2 / recuperación activa."

    def handle(self, *args, **options):
        for datos in PLANES:
            plan, _ = EstiramientoPlan.objects.update_or_create(
                codigo=datos["codigo"],
                defaults={
                    "nombre": datos["nombre"],
                    "modalidad": EstiramientoPlan.MODALIDAD_MOVILIDAD,
                    "fase": datos["fase"],
                    "descripcion": datos["descripcion"],
                    "transicion_segundos": 5,
                    "activo": True,
                },
            )
            ejercicios = []
            for nombre, musculo, descripcion, duracion in datos["pasos"]:
                ejercicio, _ = EstiramientoEjercicio.objects.update_or_create(
                    nombre=nombre,
                    defaults={
                        "fase_recomendada": datos["fase"],
                        "musculo_objetivo": musculo,
                        "descripcion_corta": descripcion,
                        "activo": True,
                    },
                )
                ejercicios.append((ejercicio, duracion))

            plan.pasos.all().delete()
            EstiramientoPaso.objects.bulk_create([
                EstiramientoPaso(
                    plan=plan, ejercicio=ejercicio, orden=orden,
                    duracion_segundos=duracion,
                )
                for orden, (ejercicio, duracion) in enumerate(ejercicios, 1)
            ])
            self.stdout.write(f"Cardio Z2 actualizado: {plan.nombre}")

        self.stdout.write(self.style.SUCCESS("Catálogo de Cardio Z2 listo."))
