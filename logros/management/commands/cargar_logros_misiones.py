from django.core.management.base import BaseCommand
from logros.models import TipoLogro, Logro, TipoQuest, Quest
from django.utils import timezone
from clientes.models import Cliente
from rutinas.models import Ejercicio


class Command(BaseCommand):
    help = 'Carga los nuevos tipos de logros y misiones en la base de datos'

    def handle(self, *args, **options):
        # Crear tipos de logros
        self.stdout.write(self.style.SUCCESS('Creando tipos de logros...'))

        for categoria, nombre in [
            ('consistencia', 'Consistencia'),
            ('superacion', 'Superación'),
            ('exploracion', 'Exploración'),
            ('equilibrio', 'Equilibrio'),
            ('social', 'Social'),
            ('tecnica', 'Técnica'),
            ('recuperacion', 'Recuperación'),
        ]:
            tipo, created = TipoLogro.objects.get_or_create(
                categoria=categoria,
                defaults={
                    'nombre': nombre,
                    'descripcion': f'Logros relacionados con {nombre.lower()}'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Creado tipo de logro: {nombre}'))
            else:
                self.stdout.write(f'El tipo de logro {nombre} ya existe')

        # Crear tipos de misiones
        self.stdout.write(self.style.SUCCESS('Creando tipos de misiones...'))

        for periodo, nombre, duracion in [
            ('diaria', 'Diaria', 1),
            ('semanal', 'Semanal', 7),
            ('mensual', 'Mensual', 30),
            ('progresiva', 'Progresiva', 0),
            ('especial', 'Especial', 0),
        ]:
            tipo, created = TipoQuest.objects.get_or_create(
                periodo=periodo,
                defaults={
                    'nombre': nombre,
                    'duracion_dias': duracion,
                    'descripcion': f'Misiones de tipo {nombre.lower()}'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Creado tipo de misión: {nombre}'))
            else:
                self.stdout.write(f'El tipo de misión {nombre} ya existe')

        # Crear ejemplos de logros
        self.crear_logros_consistencia()
        self.crear_logros_superacion()
        self.crear_logros_exploracion()
        self.crear_logros_equilibrio()
        self.crear_logros_social()
        self.crear_logros_tecnica()
        self.crear_logros_recuperacion()

        # Crear ejemplos de misiones
        self.crear_misiones_diarias()
        self.crear_misiones_semanales()
        self.crear_misiones_mensuales()
        self.crear_misiones_especiales()
        self.crear_misiones_progresivas()

        self.stdout.write(self.style.SUCCESS('Carga de logros y misiones completada'))

    def crear_logros_consistencia(self):
        """Crear ejemplos de logros de consistencia"""
        self.stdout.write('Creando logros de consistencia...')

        tipo = TipoLogro.objects.get(categoria='consistencia')

        logros = [
            {
                'nombre': 'Rutina Establecida',
                'descripcion': 'Entrena el mismo día de la semana durante 4 semanas consecutivas',
                'icono': '📅',
                'meta_valor': 4,
                'puntos_recompensa': 100
            },
            {
                'nombre': 'Reloj Suizo',
                'descripcion': 'Completa 10 entrenamientos a la misma hora del día',
                'icono': '⏰',
                'meta_valor': 10,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Maestro de la Constancia',
                'descripcion': 'Mantén una racha de entrenamientos de 30 días',
                'icono': '🔄',
                'meta_valor': 30,
                'puntos_recompensa': 300
            },
            {
                'nombre': 'Entrenador de Fin de Semana',
                'descripcion': 'Entrena 8 fines de semana consecutivos',
                'icono': '🏖️',
                'meta_valor': 8,
                'puntos_recompensa': 200
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_superacion(self):
        """Crear ejemplos de logros de superación"""
        self.stdout.write('Creando logros de superación...')

        tipo = TipoLogro.objects.get(categoria='superacion')

        logros = [
            {
                'nombre': 'Rompe Barreras',
                'descripcion': 'Supera tu récord personal en cualquier ejercicio 5 veces',
                'icono': '💪',
                'meta_valor': 5,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Más Allá del Límite',
                'descripcion': 'Aumenta el peso en un ejercicio por 3 semanas consecutivas',
                'icono': '📈',
                'meta_valor': 3,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Maestro del Progreso',
                'descripcion': 'Logra un aumento del 50% en el peso de un ejercicio desde tu primer registro',
                'icono': '🚀',
                'meta_valor': 50,
                'puntos_recompensa': 300
            },
            {
                'nombre': 'Desafío Aceptado',
                'descripcion': 'Completa un entrenamiento con un 20% más de volumen que tu promedio',
                'icono': '🏋️',
                'meta_valor': 20,
                'puntos_recompensa': 200
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_exploracion(self):
        """Crear ejemplos de logros de exploración"""
        self.stdout.write('Creando logros de exploración...')

        tipo = TipoLogro.objects.get(categoria='exploracion')

        logros = [
            {
                'nombre': 'Aventurero del Fitness',
                'descripcion': 'Prueba 10 ejercicios diferentes',
                'icono': '🧭',
                'meta_valor': 10,
                'puntos_recompensa': 100
            },
            {
                'nombre': 'Maestro Versátil',
                'descripcion': 'Completa entrenamientos para todos los grupos musculares principales',
                'icono': '🌐',
                'meta_valor': 5,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Explorador de Rutinas',
                'descripcion': 'Prueba 5 rutinas diferentes',
                'icono': '📚',
                'meta_valor': 5,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Maestro de Técnicas',
                'descripcion': 'Realiza ejercicios con 3 tipos diferentes de equipamiento',
                'icono': '🔧',
                'meta_valor': 3,
                'puntos_recompensa': 150
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_equilibrio(self):
        """Crear ejemplos de logros de equilibrio"""
        self.stdout.write('Creando logros de equilibrio...')

        tipo = TipoLogro.objects.get(categoria='equilibrio')

        logros = [
            {
                'nombre': 'Entrenamiento Holístico',
                'descripcion': 'Entrena todos los grupos musculares principales en una semana',
                'icono': '⚖️',
                'meta_valor': 1,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Cuerpo Simétrico',
                'descripcion': 'Mantén un equilibrio entre ejercicios de empuje y tracción durante 5 entrenamientos',
                'icono': '🔄',
                'meta_valor': 5,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Maestro del Equilibrio',
                'descripcion': 'Mantén una proporción equilibrada entre entrenamiento de fuerza y cardio durante un mes',
                'icono': '🧘',
                'meta_valor': 1,
                'puntos_recompensa': 250
            },
            {
                'nombre': 'Desarrollo Completo',
                'descripcion': 'Alcanza un nivel similar de fuerza en ejercicios antagonistas',
                'icono': '🔄',
                'meta_valor': 3,
                'puntos_recompensa': 300
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_social(self):
        """Crear ejemplos de logros sociales"""
        self.stdout.write('Creando logros sociales...')

        tipo = TipoLogro.objects.get(categoria='social')

        logros = [
            {
                'nombre': 'Entrenamiento en Equipo',
                'descripcion': 'Completa 5 entrenamientos con un compañero',
                'icono': '👥',
                'meta_valor': 5,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Inspirador',
                'descripcion': 'Motiva a 3 amigos a unirse al gimnasio',
                'icono': '🌟',
                'meta_valor': 3,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Competidor Amistoso',
                'descripcion': 'Participa en 3 desafíos o competencias con otros usuarios',
                'icono': '🏆',
                'meta_valor': 3,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Mentor del Fitness',
                'descripcion': 'Ayuda a 5 personas con su técnica o rutina',
                'icono': '👨‍🏫',
                'meta_valor': 5,
                'puntos_recompensa': 250
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_tecnica(self):
        """Crear ejemplos de logros de técnica"""
        self.stdout.write('Creando logros de técnica...')

        tipo = TipoLogro.objects.get(categoria='tecnica')

        logros = [
            {
                'nombre': 'Forma Perfecta',
                'descripcion': 'Realiza 10 series con técnica perfecta validada por un entrenador',
                'icono': '✅',
                'meta_valor': 10,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Maestro del Tempo',
                'descripcion': 'Completa 5 entrenamientos controlando perfectamente el tempo de los ejercicios',
                'icono': '⏱️',
                'meta_valor': 5,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Precisión Milimétrica',
                'descripcion': 'Realiza 20 repeticiones con rango de movimiento completo en ejercicios compuestos',
                'icono': '📏',
                'meta_valor': 20,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Control Total',
                'descripcion': 'Domina la técnica avanzada en 3 ejercicios diferentes',
                'icono': '🎯',
                'meta_valor': 3,
                'puntos_recompensa': 250
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_logros_recuperacion(self):
        """Crear ejemplos de logros de recuperación"""
        self.stdout.write('Creando logros de recuperación...')

        tipo = TipoLogro.objects.get(categoria='recuperacion')

        logros = [
            {
                'nombre': 'Maestro del Descanso',
                'descripcion': 'Mantén un patrón de sueño regular durante 2 semanas',
                'icono': '😴',
                'meta_valor': 14,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Hidratación Perfecta',
                'descripcion': 'Registra un consumo adecuado de agua durante 10 días',
                'icono': '💧',
                'meta_valor': 10,
                'puntos_recompensa': 100
            },
            {
                'nombre': 'Maestro de la Flexibilidad',
                'descripcion': 'Realiza estiramientos después de 15 entrenamientos',
                'icono': '🧘‍♂️',
                'meta_valor': 15,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Nutrición Óptima',
                'descripcion': 'Mantén un balance nutricional adecuado durante 20 días',
                'icono': '🥗',
                'meta_valor': 20,
                'puntos_recompensa': 250
            }
        ]

        for logro_data in logros:
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults={
                    'descripcion': logro_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': logro_data['meta_valor'],
                    'puntos_recompensa': logro_data['puntos_recompensa'],
                    'icono': logro_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creado logro: {logro.nombre}')

    def crear_misiones_diarias(self):
        """Crear ejemplos de misiones diarias"""
        self.stdout.write('Creando misiones diarias...')

        tipo = TipoQuest.objects.get(periodo='diaria')

        misiones = [
            {
                'nombre': 'Entrenamiento Express',
                'descripcion': 'Completa un entrenamiento de alta intensidad en menos de 30 minutos',
                'icono': '⚡',
                'meta_valor': 1,
                'puntos_recompensa': 50
            },
            {
                'nombre': 'Desafío de Hidratación',
                'descripcion': 'Bebe al menos 2 litros de agua durante el día',
                'icono': '💧',
                'meta_valor': 1,
                'puntos_recompensa': 30
            },
            {
                'nombre': 'Superación Diaria',
                'descripcion': 'Supera tu récord personal en un ejercicio',
                'icono': '📈',
                'meta_valor': 1,
                'puntos_recompensa': 50
            },
            {
                'nombre': 'Técnica Perfecta',
                'descripcion': 'Realiza todas las series de hoy con técnica perfecta',
                'icono': '✅',
                'meta_valor': 1,
                'puntos_recompensa': 40
            },
            {
                'nombre': 'Entrenamiento Completo',
                'descripcion': 'Completa todas las series programadas para hoy sin saltarte ninguna',
                'icono': '🏁',
                'meta_valor': 1,
                'puntos_recompensa': 50
            }
        ]

        for mision_data in misiones:
            mision, created = Quest.objects.get_or_create(
                nombre=mision_data['nombre'],
                defaults={
                    'descripcion': mision_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': mision_data['meta_valor'],
                    'puntos_recompensa': mision_data['puntos_recompensa'],
                    'icono': mision_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creada misión: {mision.nombre}')

    def crear_misiones_semanales(self):
        """Crear ejemplos de misiones semanales"""
        self.stdout.write('Creando misiones semanales...')

        tipo = TipoQuest.objects.get(periodo='semanal')

        misiones = [
            {
                'nombre': 'Consistencia Semanal',
                'descripcion': 'Completa 4 entrenamientos esta semana',
                'icono': '📅',
                'meta_valor': 4,
                'puntos_recompensa': 100
            },
            {
                'nombre': 'Entrenamiento Equilibrado',
                'descripcion': 'Entrena todos los grupos musculares principales esta semana',
                'icono': '⚖️',
                'meta_valor': 5,
                'puntos_recompensa': 120
            },
            {
                'nombre': 'Desafío de Volumen',
                'descripcion': 'Alcanza un volumen total de entrenamiento de 10,000 kg esta semana',
                'icono': '🏋️',
                'meta_valor': 10000,
                'puntos_recompensa': 150
            },
            {
                'nombre': 'Explorador Semanal',
                'descripcion': 'Prueba 3 ejercicios nuevos esta semana',
                'icono': '🧭',
                'meta_valor': 3,
                'puntos_recompensa': 100
            },
            {
                'nombre': 'Maestro de la Recuperación',
                'descripcion': 'Realiza 3 sesiones de estiramiento o movilidad esta semana',
                'icono': '🧘‍♂️',
                'meta_valor': 3,
                'puntos_recompensa': 80
            }
        ]

        for mision_data in misiones:
            mision, created = Quest.objects.get_or_create(
                nombre=mision_data['nombre'],
                defaults={
                    'descripcion': mision_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': mision_data['meta_valor'],
                    'puntos_recompensa': mision_data['puntos_recompensa'],
                    'icono': mision_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creada misión: {mision.nombre}')

    def crear_misiones_mensuales(self):
        """Crear ejemplos de misiones mensuales"""
        self.stdout.write('Creando misiones mensuales...')

        tipo = TipoQuest.objects.get(periodo='mensual')

        misiones = [
            {
                'nombre': 'Desafío del Mes',
                'descripcion': 'Completa 20 entrenamientos este mes',
                'icono': '📆',
                'meta_valor': 20,
                'puntos_recompensa': 300
            },
            {
                'nombre': 'Progreso Constante',
                'descripcion': 'Aumenta el peso en 3 ejercicios diferentes durante el mes',
                'icono': '📈',
                'meta_valor': 3,
                'puntos_recompensa': 250
            },
            {
                'nombre': 'Maestro de la Variedad',
                'descripcion': 'Realiza 10 tipos diferentes de ejercicios este mes',
                'icono': '🔄',
                'meta_valor': 10,
                'puntos_recompensa': 200
            },
            {
                'nombre': 'Desafío de Volumen Mensual',
                'descripcion': 'Alcanza un volumen total de 50,000 kg este mes',
                'icono': '🏋️',
                'meta_valor': 50000,
                'puntos_recompensa': 350
            },
            {
                'nombre': 'Maestro de la Constancia',
                'descripcion': 'No faltes a ningún entrenamiento programado este mes',
                'icono': '✅',
                'meta_valor': 1,
                'puntos_recompensa': 300
            }
        ]

        for mision_data in misiones:
            mision, created = Quest.objects.get_or_create(
                nombre=mision_data['nombre'],
                defaults={
                    'descripcion': mision_data['descripcion'],
                    'tipo': tipo,
                    'meta_valor': mision_data['meta_valor'],
                    'puntos_recompensa': mision_data['puntos_recompensa'],
                    'icono': mision_data['icono']
                }
            )

            if created:
                self.stdout.write(f'  Creada misión: {mision.nombre}')

    def crear_misiones_especiales(self):
        """Crear ejemplos de misiones especiales"""
        self.stdout.write('Creando misiones especiales...')

        tipo = TipoQuest.objects.get(periodo='especial')

        # Obtener fecha actual
        hoy = timezone.now().date()

        misiones = [
            {
                'nombre': 'Desafío de Verano',
                'descripcion': 'Completa 30 entrenamientos durante los meses de verano',
                'icono': '☀️',
                'meta_valor': 30,
                'puntos_recompensa': 500,
                'fecha_inicio_evento': hoy,
                'fecha_fin_evento': hoy.replace(month=hoy.month + 3)  # 3 meses después
            },
            {
                'nombre': 'Maratón de Fitness',
                'descripcion': 'Entrena 7 días consecutivos',
                'icono': '🏃',
                'meta_valor': 7,
                'puntos_recompensa': 300
            },
            {
                'nombre': 'Desafío de Año Nuevo',
                'descripcion': 'Establece y cumple 3 objetivos de fitness para el nuevo año',
                'icono': '🎆',
                'meta_valor': 3,
                'puntos_recompensa': 400,
                'fecha_inicio_evento': hoy.replace(month=1, day=1),  # 1 de enero
                'fecha_fin_evento': hoy.replace(month=1, day=31)  # 31 de enero
            },
            {
                'nombre': 'Transformación Total',
                'descripcion': 'Completa un programa de entrenamiento de 12 semanas sin fallar',
                'icono': '🦋',
                'meta_valor': 1,
                'puntos_recompensa': 1000
            },
            {
                'nombre': 'Desafío en Equipo',
                'descripcion': 'Participa en un desafío grupal y alcanza el objetivo colectivo',
                'icono': '👥',
                'meta_valor': 1,
                'puntos_recompensa': 400
            }
        ]

        for mision_data in misiones:
            defaults = {
                'descripcion': mision_data['descripcion'],
                'tipo': tipo,
                'meta_valor': mision_data['meta_valor'],
                'puntos_recompensa': mision_data['puntos_recompensa'],
                'icono': mision_data['icono']
            }

            # Añadir fechas si existen
            if 'fecha_inicio_evento' in mision_data:
                defaults['fecha_inicio_evento'] = mision_data['fecha_inicio_evento']
            if 'fecha_fin_evento' in mision_data:
                defaults['fecha_fin_evento'] = mision_data['fecha_fin_evento']

            mision, created = Quest.objects.get_or_create(
                nombre=mision_data['nombre'],
                defaults=defaults
            )

            if created:
                self.stdout.write(f'  Creada misión: {mision.nombre}')

    def crear_misiones_progresivas(self):
        """Crear ejemplos de misiones progresivas"""
        self.stdout.write('Creando misiones progresivas...')

        tipo = TipoQuest.objects.get(periodo='progresiva')

        # Serie de fuerza en press de banca
        press_banca = [
            {
                'nombre': 'Principiante en Press de Banca',
                'descripcion': 'Levanta 50kg en press de banca',
                'icono': '🏋️',
                'meta_valor': 50,
                'puntos_recompensa': 100,
                'orden_secuencia': 1,
                'grupo_secuencia': 'press_banca'
            },
            {
                'nombre': 'Intermedio en Press de Banca',
                'descripcion': 'Levanta 80kg en press de banca',
                'icono': '🏋️',
                'meta_valor': 80,
                'puntos_recompensa': 200,
                'orden_secuencia': 2,
                'grupo_secuencia': 'press_banca',
                'requisito_anterior': 'Principiante en Press de Banca'
            },
            {
                'nombre': 'Avanzado en Press de Banca',
                'descripcion': 'Levanta 100kg en press de banca',
                'icono': '🏋️',
                'meta_valor': 100,
                'puntos_recompensa': 300,
                'orden_secuencia': 3,
                'grupo_secuencia': 'press_banca',
                'requisito_anterior': 'Intermedio en Press de Banca'
            },
            {
                'nombre': 'Maestro del Press de Banca',
                'descripcion': 'Levanta 120kg en press de banca',
                'icono': '🏋️',
                'meta_valor': 120,
                'puntos_recompensa': 500,
                'orden_secuencia': 4,
                'grupo_secuencia': 'press_banca',
                'requisito_anterior': 'Avanzado en Press de Banca'
            }
        ]

        # Serie de consistencia
        consistencia = [
            {
                'nombre': 'Iniciando el Hábito',
                'descripcion': 'Entrena 10 días en un mes',
                'icono': '📅',
                'meta_valor': 10,
                'puntos_recompensa': 100,
                'orden_secuencia': 1,
                'grupo_secuencia': 'consistencia'
            },
            {
                'nombre': 'Construyendo Consistencia',
                'descripcion': 'Entrena 15 días en un mes',
                'icono': '📅',
                'meta_valor': 15,
                'puntos_recompensa': 200,
                'orden_secuencia': 2,
                'grupo_secuencia': 'consistencia',
                'requisito_anterior': 'Iniciando el Hábito'
            },
            {
                'nombre': 'Rutina Establecida',
                'descripcion': 'Entrena 20 días en un mes',
                'icono': '📅',
                'meta_valor': 20,
                'puntos_recompensa': 300,
                'orden_secuencia': 3,
                'grupo_secuencia': 'consistencia',
                'requisito_anterior': 'Construyendo Consistencia'
            },
            {
                'nombre': 'Disciplina de Hierro',
                'descripcion': 'Entrena 25 días en un mes',
                'icono': '📅',
                'meta_valor': 25,
                'puntos_recompensa': 500,
                'orden_secuencia': 4,
                'grupo_secuencia': 'consistencia',
                'requisito_anterior': 'Rutina Establecida'
            }
        ]

        # Procesar todas las misiones progresivas
        todas_misiones = press_banca + consistencia

        # Intentar encontrar un ejercicio de press de banca
        ejercicio_press = None
        try:
            ejercicio_press = Ejercicio.objects.filter(nombre__icontains='press').first()
        except:
            self.stdout.write('No se encontró un ejercicio de press de banca')

        for mision_data in todas_misiones:
            defaults = {
                'descripcion': mision_data['descripcion'],
                'tipo': tipo,
                'meta_valor': mision_data['meta_valor'],
                'puntos_recompensa': mision_data['puntos_recompensa'],
                'icono': mision_data['icono'],
                'orden_secuencia': mision_data['orden_secuencia'],
                'grupo_secuencia': mision_data['grupo_secuencia']
            }

            # Añadir requisito anterior si existe
            if 'requisito_anterior' in mision_data:
                defaults['requisito_anterior'] = mision_data['requisito_anterior']

            # Añadir ejercicio para las misiones de press de banca
            if 'press_banca' in mision_data['grupo_secuencia'] and ejercicio_press:
                defaults['ejercicio'] = ejercicio_press

            mision, created = Quest.objects.get_or_create(
                nombre=mision_data['nombre'],
                defaults=defaults
            )

            if created:
                self.stdout.write(f'  Creada misión: {mision.nombre}')

                # Si tiene requisito anterior, establecer la relación
                if 'requisito_anterior' in mision_data:
                    try:
                        mision_anterior = Quest.objects.get(nombre=mision_data['requisito_anterior'])
                        mision.quest_padre = mision_anterior
                        mision.save()
                    except Quest.DoesNotExist:
                        self.stdout.write(
                            f'    ⚠️ No se encontró la misión anterior: {mision_data["requisito_anterior"]}')
