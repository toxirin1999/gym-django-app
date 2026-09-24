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
        "nombre": "Bici / Remo Zona 2",
        "fase": "CARDIO",
        "descripcion": "Enfoque regenerativo FC < 130 bpm",
        "pasos": (
            # Una sola sesión continua de 30 min (1 ejercicio), no segmentada.
            ("Bici / remo continuo en Zona 2", "Cardiovascular", "Mantén la frecuencia cardíaca por debajo de 130 lpm con un ritmo cómodo y constante durante todo el bloque.", 1800),
        ),
    },
    {
        "codigo": "cardio-z2-caminata-inclinada",
        "nombre": "Caminata Inclinada Activa",
        "fase": "CARDIO",
        "descripcion": "Ritmo constante Z2",
        "pasos": (
            # Una sola sesión continua de 20 min (1 ejercicio), no segmentada.
            ("Caminata inclinada continua en Zona 2", "Cardiovascular / Piernas", "Sube la inclinación de la cinta (o busca una cuesta) y mantén un ritmo cómodo y constante, RPE 3-4.", 1200),
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
