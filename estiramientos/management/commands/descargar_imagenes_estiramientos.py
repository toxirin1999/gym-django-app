"""
Comando de Django para descargar imágenes de estiramientos y asignarlas automáticamente.
Uso: python manage.py descargar_imagenes_estiramientos

Coloca este archivo en: estiramientos/management/commands/descargar_imagenes_estiramientos.py
"""

import os
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from estiramientos.models import EstiramientoEjercicio


class Command(BaseCommand):
    help = "Descarga imágenes de estiramientos y las asigna a cada ejercicio."

    # Mapeo de ejercicios a URLs de imágenes
    # Fuente: spotebi.com (ilustraciones de ejercicios gratuitas)
    IMAGENES = {
        # =====================================================
        # TREN SUPERIOR
        # =====================================================
        "Inclinación lateral de cuello (Izquierda)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/neck-stretch-exercise-illustration.gif",
        "Inclinación lateral de cuello (Derecha)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/neck-stretch-exercise-illustration.gif",

        "Estiramiento de hombro cruzado (Izquierdo)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/shoulder-stretch-exercise-illustration.gif",
        "Estiramiento de hombro cruzado (Derecho)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/shoulder-stretch-exercise-illustration.gif",

        "Estiramiento de tríceps (Izquierdo)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/triceps-stretch-exercise-illustration.gif",
        "Estiramiento de tríceps (Derecho)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/triceps-stretch-exercise-illustration.gif",

        "Estiramiento pectoral en pared (Izquierdo)":
            "https://spotebi.com/wp-content/uploads/2015/06/chest-stretch-exercise-illustration.gif",
        "Estiramiento pectoral en pared (Derecho)":
            "https://spotebi.com/wp-content/uploads/2015/06/chest-stretch-exercise-illustration.gif",

        "Estiramiento dorsal en pared (Izquierdo)":
            "https://i.pinimg.com/736x/38/85/9f/38859f61f1ddb93fc35ede3491f864bb.jpg",
        "Estiramiento dorsal en pared (Derecho)":
            "https://i.pinimg.com/736x/38/85/9f/38859f61f1ddb93fc35ede3491f864bb.jpg",

        # =====================================================
        # TREN INFERIOR
        # =====================================================
        "Zancada baja - flexor cadera (Izquierda)":
            "https://cdnl.iconscout.com/lottie/premium/thumb/hombre-haciendo-estiramiento-del-flexor-de-la-cadera-animation-gif-download-10841096.gif",
        "Zancada baja - flexor cadera (Derecha)":
            "https://cdnl.iconscout.com/lottie/premium/thumb/hombre-haciendo-estiramiento-del-flexor-de-la-cadera-animation-gif-download-10841096.gif",

        "Estiramiento de cuádriceps de pie (Izquierdo)":
            "https://i.pinimg.com/1200x/db/2b/ab/db2babfa64e87c6a3142beec71076fc2.jpg",
        "Estiramiento de cuádriceps de pie (Derecho)":
            "https://i.pinimg.com/1200x/db/2b/ab/db2babfa64e87c6a3142beec71076fc2.jpg",

        "Isquiotibiales sentado (Izquierda)":
            "https://i.pinimg.com/1200x/74/0d/06/740d063010b19b6b2fbe7445d79a7ca1.jpg",
        "Isquiotibiales sentado (Derecha)":
            "https://i.pinimg.com/1200x/74/0d/06/740d063010b19b6b2fbe7445d79a7ca1.jpg",

        "Figura 4 - Glúteo/Piriforme (Izquierdo)":
            "https://fisiolution.com/wp-content/uploads/2023/03/FOTO-2-J.L.-oK-440x293.jpg",
        "Figura 4 - Glúteo/Piriforme (Derecho)":
            "https://fisiolution.com/wp-content/uploads/2023/03/FOTO-2-J.L.-oK-440x293.jpg",

        "Estiramiento de aductores (Mariposa)":
            "https://i.pinimg.com/originals/dc/47/b6/dc47b6d6b9d6f5286a0c669a6bfb0064.gif",
        "Estiramiento de aductores (Lateral)":
            "https://i.pinimg.com/originals/dc/47/b6/dc47b6d6b9d6f5286a0c669a6bfb0064.gif",

        "Gemelo en pared (Izquierdo)":
            "https://fisioterapiaenforma.com/wp-content/uploads/2024/06/gemelo.png",
        "Gemelo en pared (Derecho)":
            "https://fisioterapiaenforma.com/wp-content/uploads/2024/06/gemelo.png",

        # =====================================================
        # CUERPO COMPLETO
        # =====================================================
        "Rotación de cuello (suave)":
            "https://i.pinimg.com/originals/72/63/92/726392b158efa5436bd1c94a6551143b.gif",

        "Círculos de hombros":
            "https://i.pinimg.com/originals/51/ae/a1/51aea1df721b5434b30d8ceb618446be.gif",

        "Estiramiento de tríceps (ambos lados)":
            "https://www.spotebi.com/wp-content/uploads/2014/10/triceps-stretch-exercise-illustration.gif",

        "Estiramiento lateral de torso (Izquierda)":
            "https://i.pinimg.com/1200x/a5/5c/2c/a55c2c8781e95a2f3bd334c4b093a8f6.jpg",
        "Estiramiento lateral de torso (Derecha)":
            "https://i.pinimg.com/1200x/a5/5c/2c/a55c2c8781e95a2f3bd334c4b093a8f6.jpg",

        "Gato-Vaca":
            "https://i.pinimg.com/1200x/f9/32/52/f93252cc7d18adf5a78b278cca9e8086.jpg",

        "Zancada con rotación (Izquierda)":
            "https://i.pinimg.com/736x/9b/ee/c5/9beec5e6a133eb192eb44deca35b1d9a.jpg",
        "Zancada con rotación (Derecha)":
            "https://i.pinimg.com/736x/9b/ee/c5/9beec5e6a133eb192eb44deca35b1d9a.jpg",

        "Isquiotibiales de pie (Izquierda)":
            "https://i.pinimg.com/736x/b9/8e/84/b98e84d320fb29d9fd4fd5dc9b77372a.jpg",
        "Isquiotibiales de pie (Derecha)":
            "https://i.pinimg.com/736x/b9/8e/84/b98e84d320fb29d9fd4fd5dc9b77372a.jpg",

        "Estiramiento de glúteo cruzado (Izquierdo)":
            "https://i.pinimg.com/1200x/22/7c/13/227c13c2fea17fef7f6a3504ac6744b7.jpg",
        "Estiramiento de glúteo cruzado (Derecho)":
            "https://i.pinimg.com/1200x/22/7c/13/227c13c2fea17fef7f6a3504ac6744b7.jpg",

        "Flexión hacia adelante (Ragdoll)":
            "https://i.pinimg.com/1200x/d7/b0/1f/d7b01f6eec3665f04269025d54fa635c.jpg",

        "Respiración profunda final":
            "https://www.spotebi.com/wp-content/uploads/2014/10/deep-breathing-exercise-illustration.gif",
    }

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📸 DESCARGANDO IMÁGENES DE ESTIRAMIENTOS")
        self.stdout.write("=" * 60 + "\n")

        # Crear directorio si no existe
        media_dir = os.path.join(settings.MEDIA_ROOT, 'estiramientos')
        os.makedirs(media_dir, exist_ok=True)
        self.stdout.write(f"📁 Directorio: {media_dir}\n")

        # Contadores
        descargadas = 0
        errores = 0
        ya_existentes = 0

        # Obtener todos los ejercicios
        ejercicios = EstiramientoEjercicio.objects.filter(activo=True)
        total = ejercicios.count()

        self.stdout.write(f"🔍 Encontrados {total} ejercicios activos\n")

        for ejercicio in ejercicios:
            nombre = ejercicio.nombre

            # Verificar si ya tiene imagen
            if ejercicio.imagen and os.path.exists(ejercicio.imagen.path):
                self.stdout.write(f"  ⏭️  {nombre[:40]}... (ya tiene imagen)")
                ya_existentes += 1
                continue

            # Buscar URL en el mapeo
            url = self.IMAGENES.get(nombre)

            if not url:
                self.stdout.write(self.style.WARNING(f"  ⚠️  {nombre[:40]}... (sin URL definida)"))
                errores += 1
                continue

            # Descargar imagen
            try:
                self.stdout.write(f"  ⬇️  Descargando: {nombre[:40]}...")

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()

                # Determinar extensión
                content_type = response.headers.get('Content-Type', '')
                if 'gif' in content_type or url.endswith('.gif'):
                    extension = 'gif'
                elif 'png' in content_type or url.endswith('.png'):
                    extension = 'png'
                else:
                    extension = 'jpg'

                # Crear nombre de archivo limpio
                nombre_archivo = self.limpiar_nombre(nombre) + f'.{extension}'

                # Guardar imagen en el modelo
                ejercicio.imagen.save(
                    nombre_archivo,
                    ContentFile(response.content),
                    save=True
                )

                self.stdout.write(self.style.SUCCESS(f"      ✅ Guardado: {nombre_archivo}"))
                descargadas += 1

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"      ❌ Error de descarga: {str(e)[:50]}"))
                errores += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"      ❌ Error: {str(e)[:50]}"))
                errores += 1

        # Resumen final
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 RESUMEN")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(f"  ✅ Descargadas: {descargadas}"))
        self.stdout.write(f"  ⏭️  Ya existentes: {ya_existentes}")
        if errores > 0:
            self.stdout.write(self.style.WARNING(f"  ⚠️  Errores/Sin URL: {errores}"))
        self.stdout.write("=" * 60 + "\n")

        if descargadas > 0:
            self.stdout.write(self.style.SUCCESS("🎉 ¡Imágenes descargadas correctamente!"))
            self.stdout.write("💡 Accede a /estiramientos/ para verlas en acción.\n")

    def limpiar_nombre(self, nombre):
        """Convierte el nombre a un formato válido para archivo."""
        import re
        # Reemplazar caracteres especiales
        nombre = nombre.lower()
        nombre = nombre.replace('á', 'a').replace('é', 'e').replace('í', 'i')
        nombre = nombre.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
        nombre = re.sub(r'[^a-z0-9]+', '_', nombre)
        nombre = nombre.strip('_')
        return nombre[:50]  # Limitar longitud
