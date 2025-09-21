# estoico/management/commands/crear_datos_estoicos.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date, timedelta
import random

# Importa los modelos necesarios de tu app 'estoico'
from estoico.models import ReflexionDiaria, ContenidoDiario


class Command(BaseCommand):
    help = 'Crear datos de prueba para testing de la sección estoica'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuario',
            type=str,
            help='Username para crear datos de prueba',
            required=True,
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Número de días de reflexiones a crear (default: 7)',
        )

    def handle(self, *args, **options):
        username = options['usuario']
        dias_a_crear = options['dias']

        try:
            usuario = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Usuario "{username}" no existe.'))
            return

        self.stdout.write(f'🎯 Creando hasta {dias_a_crear} días de reflexiones para {username}...')

        hoy = date.today()
        reflexiones_creadas = 0

        for i in range(dias_a_crear):
            fecha_reflexion = hoy - timedelta(days=i)

            # 1. Verificar si ya existe una reflexión para este usuario y fecha
            if ReflexionDiaria.objects.filter(usuario=usuario, fecha=fecha_reflexion).exists():
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️ Ya existe una reflexión para {fecha_reflexion}. Saltando.'))
                continue

            # 2. Obtener el contenido diario correspondiente a la fecha
            dia_del_año = fecha_reflexion.timetuple().tm_yday
            try:
                contenido_del_dia = ContenidoDiario.objects.get(dia=dia_del_año)
            except ContenidoDiario.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'   ❌ No se encontró ContenidoDiario para el día {dia_del_año} (fecha {fecha_reflexion}). No se puede crear la reflexión.'))
                continue  # Saltar a la siguiente iteración si no hay contenido

            # 3. Crear la reflexión de prueba, ahora incluyendo el contenido_dia
            ReflexionDiaria.objects.create(
                usuario=usuario,
                fecha=fecha_reflexion,
                # ¡CORRECCIÓN CLAVE! Asociar el contenido diario.
                contenido_dia=contenido_del_dia,
                reflexion_personal=(
                    f"Reflexión de prueba para el día {fecha_reflexion}. "
                    f"Hoy he aprendido sobre la importancia de la disciplina y la constancia."
                ),
                calificacion_dia=random.randint(3, 5),
                tiempo_reflexion=random.randint(3, 10)
            )

            reflexiones_creadas += 1
            self.stdout.write(f'   ✅ Creada reflexión para {fecha_reflexion}')

        if reflexiones_creadas > 0:
            self.stdout.write(self.style.SUCCESS(f'\n🎉 Se crearon {reflexiones_creadas} nuevas reflexiones.'))
        else:
            self.stdout.write(self.style.WARNING(
                '\n🤷 No se crearon nuevas reflexiones (probablemente ya existían o faltaba contenido).'))

        # Mostrar estadísticas finales
        total_reflexiones = ReflexionDiaria.objects.filter(usuario=usuario).count()
        self.stdout.write(f'📊 Total de reflexiones de {username} ahora: {total_reflexiones}')
