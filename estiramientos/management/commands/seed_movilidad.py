"""Crea el catálogo canónico de sesiones activas de movilidad."""

from django.core.management.base import BaseCommand

from estiramientos.models import EstiramientoEjercicio, EstiramientoPaso, EstiramientoPlan


PLANES = (
    {
        "codigo": "mobility-recovery-global",
        "nombre": "Movilidad global de recuperación",
        "fase": "COMPLETO",
        "descripcion": "Movimiento suave de todo el cuerpo para recuperar sin añadir fatiga.",
        "pasos": (
            ("Respiración 90/90 con alcance", "Respiración / Caja torácica", "Respira por la nariz y amplía la espalda sin forzar.", 60),
            ("Gato-vaca segmentado", "Columna", "Mueve la columna vértebra a vértebra, lento y sin rebotes.", 45),
            ("Transiciones 90/90 de cadera", "Cadera", "Alterna ambas caderas manteniendo el torso alto.", 60),
            ("Rotación torácica en cuadrupedia", "Columna torácica", "Sigue la mano con la mirada y conserva la pelvis estable.", 45),
            ("Balanceo de tobillo en zancada", "Tobillo", "Lleva la rodilla hacia delante sin despegar el talón.", 60),
        ),
    },
    {
        "codigo": "mobility-hip-ankle",
        "nombre": "Cadera y tobillo",
        "fase": "INFERIOR",
        "descripcion": "Control activo para mejorar sentadilla, zancada y apoyo del pie.",
        "pasos": (
            ("CARs de cadera en cuadrupedia", "Cadera", "Dibuja un círculo amplio sin girar la pelvis.", 60),
            ("Transición shin box 90/90", "Cadera", "Cambia de lado con control y sin impulso.", 60),
            ("Adductor rock back", "Aductores", "Lleva la cadera atrás manteniendo la espalda larga.", 45),
            ("Rodilla a pared para tobillo", "Tobillo", "Avanza la rodilla alineada con el segundo dedo.", 60),
            ("Elevación activa de puntas y talones", "Pie / Tobillo", "Alterna dorsiflexión y flexión plantar con control.", 45),
        ),
    },
    {
        "codigo": "mobility-thoracic-shoulder",
        "nombre": "Columna torácica y hombros",
        "fase": "SUPERIOR",
        "descripcion": "Rotación torácica y control escapular para mover los brazos con libertad.",
        "pasos": (
            ("CARs de hombro", "Hombro", "Rota el brazo lentamente sin compensar con las costillas.", 60),
            ("Deslizamientos escapulares en pared", "Escápulas", "Sube los brazos conservando cuello y costillas relajados.", 60),
            ("Open book torácico", "Columna torácica", "Abre el pecho sin separar las rodillas.", 60),
            ("Rotación torácica en apoyo", "Columna torácica", "Rota desde la espalda alta, no desde la zona lumbar.", 45),
            ("Flexión activa de hombro en pared", "Hombro / Dorsal", "Alcanza arriba sin arquear la espalda.", 45),
        ),
    },
    {
        "codigo": "mobility-lower-prep",
        "nombre": "Preparación de tren inferior",
        "fase": "INFERIOR",
        "descripcion": "Secuencia dinámica para preparar tobillos, caderas y patrón de sentadilla.",
        "pasos": (
            ("Marcha activa de tobillo", "Tobillo / Pie", "Avanza alternando punta y talón con control.", 45),
            ("Zancada con rotación dinámica", "Cadera / Torso", "Alterna lados y rota hacia la pierna adelantada.", 60),
            ("Sentadilla profunda asistida dinámica", "Cadera / Tobillo", "Usa un apoyo y explora el rango sin dolor.", 60),
            ("Bisagra de cadera con alcance", "Cadera / Isquios", "Lleva la cadera atrás conservando la espalda neutra.", 45),
            ("Sentadilla lateral alterna", "Aductores / Cadera", "Desplaza el peso de lado a lado sin rebotes.", 60),
        ),
    },
    {
        "codigo": "mobility-upper-prep",
        "nombre": "Preparación de tren superior",
        "fase": "SUPERIOR",
        "descripcion": "Secuencia activa para preparar escápulas, hombros y columna torácica.",
        "pasos": (
            ("Círculos activos de brazos", "Hombros", "Aumenta el arco de forma gradual y sin impulso.", 45),
            ("Flexiones escapulares", "Escápulas", "Mantén los codos extendidos y mueve solo las escápulas.", 45),
            ("Wall slides con despegue", "Hombros / Escápulas", "Desliza y separa suavemente las manos de la pared.", 60),
            ("Rotación externa dinámica", "Manguito rotador", "Gira los antebrazos conservando los codos junto al cuerpo.", 45),
            ("Thread the needle dinámico", "Columna torácica", "Alterna rotación cerrada y abierta con respiración.", 60),
        ),
    },
)


class Command(BaseCommand):
    help = "Crea o actualiza los cinco planes canónicos de movilidad."

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
            self.stdout.write(f"Movilidad actualizada: {plan.nombre}")

        self.stdout.write(self.style.SUCCESS("Catálogo de movilidad listo."))
