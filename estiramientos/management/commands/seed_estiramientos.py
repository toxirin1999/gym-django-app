"""
Comando de Django para crear planes de estiramientos predefinidos.
Uso: python manage.py seed_estiramientos

Coloca este archivo en: estiramientos/management/commands/seed_estiramientos.py
(Crea las carpetas management/commands/ si no existen, con __init__.py vacíos)
"""

from django.core.management.base import BaseCommand
from estiramientos.models import EstiramientoPlan, EstiramientoPaso, EstiramientoEjercicio


class Command(BaseCommand):
    help = "Crea planes y ejercicios de estiramiento por defecto (Superior/Inferior/Completo)."

    def handle(self, *args, **options):
        # =====================================================
        # CREAR/ACTUALIZAR LOS 3 PLANES
        # =====================================================
        planes_data = [
            ("Tren Superior", "SUPERIOR", 5),
            ("Tren Inferior", "INFERIOR", 5),
            ("Cuerpo Completo", "COMPLETO", 5),
        ]

        plan_objs = {}
        for nombre, fase, transicion in planes_data:
            plan, created = EstiramientoPlan.objects.get_or_create(
                fase=fase,
                defaults={
                    "nombre": nombre,
                    "transicion_segundos": transicion,
                    "activo": True
                }
            )
            if not created:
                plan.nombre = nombre
                plan.transicion_segundos = transicion
                plan.activo = True
                plan.save()
            plan_objs[fase] = plan
            status = "✅ Creado" if created else "🔄 Actualizado"
            self.stdout.write(f"  {status}: {nombre}")

        # =====================================================
        # FUNCIÓN HELPER PARA CREAR EJERCICIOS
        # =====================================================
        def crear_ejercicio(nombre, fase, musculo, descripcion):
            """Crea o actualiza un ejercicio de estiramiento."""
            obj, created = EstiramientoEjercicio.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "fase_recomendada": fase,
                    "musculo_objetivo": musculo,
                    "descripcion_corta": descripcion,
                    "activo": True,
                }
            )
            if not created:
                obj.fase_recomendada = fase
                obj.musculo_objetivo = musculo
                obj.descripcion_corta = descripcion
                obj.activo = True
                obj.save()
            return obj

        # =====================================================
        # EJERCICIOS TREN SUPERIOR (10 ejercicios, ~5-6 min)
        # =====================================================
        self.stdout.write("\n📌 Creando ejercicios Tren Superior...")

        ejercicios_superior = [
            # Cuello
            crear_ejercicio(
                "Inclinación lateral de cuello (Izquierda)",
                "SUPERIOR", "Cuello / Trapecio",
                "Lleva la oreja al hombro suavemente. Mantén el hombro contrario abajo."
            ),
            crear_ejercicio(
                "Inclinación lateral de cuello (Derecha)",
                "SUPERIOR", "Cuello / Trapecio",
                "Respira profundo. No fuerces, solo deja caer la cabeza por su peso."
            ),
            # Hombros
            crear_ejercicio(
                "Estiramiento de hombro cruzado (Izquierdo)",
                "SUPERIOR", "Deltoides posterior",
                "Cruza el brazo por delante del pecho. Empuja suave con la otra mano."
            ),
            crear_ejercicio(
                "Estiramiento de hombro cruzado (Derecho)",
                "SUPERIOR", "Deltoides posterior",
                "Mantén el hombro relajado, no lo subas hacia la oreja."
            ),
            # Tríceps
            crear_ejercicio(
                "Estiramiento de tríceps (Izquierdo)",
                "SUPERIOR", "Tríceps",
                "Lleva la mano detrás de la cabeza. Empuja el codo hacia abajo."
            ),
            crear_ejercicio(
                "Estiramiento de tríceps (Derecho)",
                "SUPERIOR", "Tríceps",
                "Mantén la cabeza recta, no la inclines hacia adelante."
            ),
            # Pectorales
            crear_ejercicio(
                "Estiramiento pectoral en pared (Izquierdo)",
                "SUPERIOR", "Pectoral",
                "Brazo en 90° contra la pared. Gira el torso hacia el lado contrario."
            ),
            crear_ejercicio(
                "Estiramiento pectoral en pared (Derecho)",
                "SUPERIOR", "Pectoral",
                "Siente el estiramiento en el pecho. Respira lento y profundo."
            ),
            # Dorsales
            crear_ejercicio(
                "Estiramiento dorsal en pared (Izquierdo)",
                "SUPERIOR", "Dorsal ancho",
                "Manos en la pared, caderas hacia atrás. Hunde el pecho hacia el suelo."
            ),
            crear_ejercicio(
                "Estiramiento dorsal en pared (Derecho)",
                "SUPERIOR", "Dorsal ancho",
                "Brazos extendidos, siente el estiramiento en el lateral del torso."
            ),
        ]

        # =====================================================
        # EJERCICIOS TREN INFERIOR (12 ejercicios, ~6-7 min)
        # =====================================================
        self.stdout.write("📌 Creando ejercicios Tren Inferior...")

        ejercicios_inferior = [
            # Flexores de cadera
            crear_ejercicio(
                "Zancada baja - flexor cadera (Izquierda)",
                "INFERIOR", "Psoas / Flexor de cadera",
                "Rodilla trasera en el suelo. Aprieta el glúteo y empuja la cadera adelante."
            ),
            crear_ejercicio(
                "Zancada baja - flexor cadera (Derecha)",
                "INFERIOR", "Psoas / Flexor de cadera",
                "Mantén el torso erguido. No arquees la espalda baja."
            ),
            # Cuádriceps
            crear_ejercicio(
                "Estiramiento de cuádriceps de pie (Izquierdo)",
                "INFERIOR", "Cuádriceps",
                "Agarra el tobillo y lleva el talón al glúteo. Rodillas juntas."
            ),
            crear_ejercicio(
                "Estiramiento de cuádriceps de pie (Derecho)",
                "INFERIOR", "Cuádriceps",
                "Si necesitas equilibrio, apóyate en una pared."
            ),
            # Isquiotibiales
            crear_ejercicio(
                "Isquiotibiales sentado (Izquierda)",
                "INFERIOR", "Isquiotibiales",
                "Pierna estirada, flexiona desde la cadera. Espalda recta."
            ),
            crear_ejercicio(
                "Isquiotibiales sentado (Derecha)",
                "INFERIOR", "Isquiotibiales",
                "Llega hasta donde puedas sin redondear la espalda."
            ),
            # Glúteos / Piriforme
            crear_ejercicio(
                "Figura 4 - Glúteo/Piriforme (Izquierdo)",
                "INFERIOR", "Glúteo / Piriforme",
                "Tumbado boca arriba. Tobillo sobre rodilla contraria. Tira de la pierna base."
            ),
            crear_ejercicio(
                "Figura 4 - Glúteo/Piriforme (Derecho)",
                "INFERIOR", "Glúteo / Piriforme",
                "Mantén la cabeza en el suelo. Relaja los hombros."
            ),
            # Aductores
            crear_ejercicio(
                "Estiramiento de aductores (Mariposa)",
                "INFERIOR", "Aductores",
                "Plantas de los pies juntas. Deja caer las rodillas suavemente."
            ),
            crear_ejercicio(
                "Estiramiento de aductores (Lateral)",
                "INFERIOR", "Aductores",
                "Piernas abiertas, inclínate hacia un lado. Mantén 15s cada lado."
            ),
            # Gemelos
            crear_ejercicio(
                "Gemelo en pared (Izquierdo)",
                "INFERIOR", "Gemelo",
                "Manos en pared, pierna atrás estirada. Talón pegado al suelo."
            ),
            crear_ejercicio(
                "Gemelo en pared (Derecho)",
                "INFERIOR", "Gemelo",
                "Inclínate hacia la pared hasta sentir el estiramiento."
            ),
        ]

        # =====================================================
        # EJERCICIOS CUERPO COMPLETO (14 ejercicios, ~7-8 min)
        # Combinación de los mejores de superior e inferior
        # =====================================================
        self.stdout.write("📌 Creando ejercicios Cuerpo Completo...")

        ejercicios_completo = [
            # Cuello
            crear_ejercicio(
                "Rotación de cuello (suave)",
                "COMPLETO", "Cuello",
                "Gira lentamente la cabeza en círculos. 5 en cada dirección."
            ),
            # Hombros y brazos
            crear_ejercicio(
                "Círculos de hombros",
                "COMPLETO", "Hombros",
                "Brazos relajados. Haz círculos grandes con los hombros hacia atrás."
            ),
            crear_ejercicio(
                "Estiramiento de tríceps (ambos lados)",
                "COMPLETO", "Tríceps",
                "30 segundos: 15s cada brazo. Codo apuntando arriba."
            ),
            # Torso
            crear_ejercicio(
                "Estiramiento lateral de torso (Izquierda)",
                "COMPLETO", "Oblicuos / Dorsal",
                "Brazo arriba, inclínate al lado contrario. Siente el costado."
            ),
            crear_ejercicio(
                "Estiramiento lateral de torso (Derecha)",
                "COMPLETO", "Oblicuos / Dorsal",
                "Mantén las caderas quietas, solo mueve el torso superior."
            ),
            crear_ejercicio(
                "Gato-Vaca",
                "COMPLETO", "Columna",
                "En cuadrupedia: arquea y redondea la espalda alternadamente."
            ),
            # Cadera y piernas
            crear_ejercicio(
                "Zancada con rotación (Izquierda)",
                "COMPLETO", "Flexor cadera / Torso",
                "En zancada, rota el torso hacia la pierna adelantada."
            ),
            crear_ejercicio(
                "Zancada con rotación (Derecha)",
                "COMPLETO", "Flexor cadera / Torso",
                "Combina estiramiento de cadera con movilidad de columna."
            ),
            crear_ejercicio(
                "Isquiotibiales de pie (Izquierda)",
                "COMPLETO", "Isquiotibiales",
                "Pierna en superficie elevada. Flexiona desde la cadera."
            ),
            crear_ejercicio(
                "Isquiotibiales de pie (Derecha)",
                "COMPLETO", "Isquiotibiales",
                "Mantén la espalda recta, no redondees."
            ),
            crear_ejercicio(
                "Estiramiento de glúteo cruzado (Izquierdo)",
                "COMPLETO", "Glúteo",
                "De pie o sentado, cruza tobillo sobre rodilla."
            ),
            crear_ejercicio(
                "Estiramiento de glúteo cruzado (Derecho)",
                "COMPLETO", "Glúteo",
                "Inclínate hacia adelante manteniendo la espalda recta."
            ),
            # Final - Relajación
            crear_ejercicio(
                "Flexión hacia adelante (Ragdoll)",
                "COMPLETO", "Isquios / Espalda",
                "De pie, déjate caer hacia adelante. Brazos colgando, relaja el cuello."
            ),
            crear_ejercicio(
                "Respiración profunda final",
                "COMPLETO", "Relajación",
                "De pie, brazos arriba al inhalar, abajo al exhalar. 5 respiraciones."
            ),
        ]

        # =====================================================
        # ASIGNAR EJERCICIOS A CADA PLAN
        # =====================================================
        def asignar_pasos(plan, ejercicios, duracion=30):
            """Elimina pasos anteriores y crea nuevos."""
            EstiramientoPaso.objects.filter(plan=plan).delete()
            for i, ejercicio in enumerate(ejercicios, start=1):
                EstiramientoPaso.objects.create(
                    plan=plan,
                    ejercicio=ejercicio,
                    orden=i,
                    duracion_segundos=duracion
                )
            self.stdout.write(f"  → {len(ejercicios)} pasos asignados a {plan.nombre}")

        self.stdout.write("\n📋 Asignando ejercicios a planes...")
        asignar_pasos(plan_objs["SUPERIOR"], ejercicios_superior, duracion=30)
        asignar_pasos(plan_objs["INFERIOR"], ejercicios_inferior, duracion=30)
        asignar_pasos(plan_objs["COMPLETO"], ejercicios_completo, duracion=30)

        # =====================================================
        # RESUMEN FINAL
        # =====================================================
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("✅ ¡Planes de estiramientos creados correctamente!"))
        self.stdout.write("=" * 50)

        for fase, plan in plan_objs.items():
            count = plan.pasos.count()
            tiempo = count * 30 // 60  # minutos aprox
            self.stdout.write(f"  • {plan.nombre}: {count} ejercicios (~{tiempo} min)")

        self.stdout.write("\n💡 Ahora puedes acceder a /estiramientos/ para verlos.")
        self.stdout.write("📸 Recuerda subir imágenes desde el panel de admin.\n")
