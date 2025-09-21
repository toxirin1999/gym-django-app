# Django Management Command: cargar_datos_estoicos.py
# Ubicación: estoico/management/commands/cargar_datos_estoicos.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
import json
import os
from datetime import datetime, timedelta
from django.utils import timezone


class Command(BaseCommand):
    """
    Comando para cargar datos iniciales de la app estoica.
    Uso: python manage.py cargar_datos_estoicos
    """

    help = 'Carga datos iniciales para la aplicación estoica'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo-contenido',
            type=str,
            default='contenido_estoico_completo_366_dias.json',
            help='Archivo JSON con el contenido de 366 días'
        )

        parser.add_argument(
            '--crear-logros',
            action='store_true',
            help='Crear logros predefinidos'
        )

        parser.add_argument(
            '--crear-usuario-demo',
            action='store_true',
            help='Crear usuario de demostración con datos de ejemplo'
        )

        parser.add_argument(
            '--limpiar-datos',
            action='store_true',
            help='Limpiar datos existentes antes de cargar'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏛️ Iniciando carga de datos estoicos...')
        )

        try:
            with transaction.atomic():
                if options['limpiar_datos']:
                    self._limpiar_datos_existentes()

                # Cargar contenido diario
                archivo_contenido = options['archivo_contenido']
                if os.path.exists(archivo_contenido):
                    self._cargar_contenido_diario(archivo_contenido)
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Archivo {archivo_contenido} no encontrado')
                    )

                # Crear logros
                if options['crear_logros']:
                    self._crear_logros_predefinidos()

                # Crear usuario demo
                if options['crear_usuario_demo']:
                    self._crear_usuario_demo()

                self.stdout.write(
                    self.style.SUCCESS('✅ Carga de datos completada exitosamente')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en la carga de datos: {e}')
            )
            raise

    def _limpiar_datos_existentes(self):
        """Limpia datos existentes de la app estoica."""
        self.stdout.write('🧹 Limpiando datos existentes...')

        from estoico.models import (
            ContenidoDiario, ReflexionDiaria, Logro, LogroUsuario,
            PerfilEstoico, RegistroNotificacion, EstadisticaUsuario
        )

        # Eliminar en orden para respetar foreign keys
        RegistroNotificacion.objects.all().delete()
        LogroUsuario.objects.all().delete()
        ReflexionDiaria.objects.all().delete()
        EstadisticaUsuario.objects.all().delete()
        PerfilEstoico.objects.all().delete()
        Logro.objects.all().delete()
        ContenidoDiario.objects.all().delete()

        self.stdout.write('✅ Datos limpiados')

    def _cargar_contenido_diario(self, archivo_path):
        """Carga el contenido diario desde el archivo JSON."""
        self.stdout.write(f'📚 Cargando contenido desde {archivo_path}...')

        from estoico.models import ContenidoDiario

        try:
            with open(archivo_path, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            contenidos_creados = 0

            # Verificar estructura del JSON
            if 'contenido_366_dias' in datos:
                contenido_dias = datos['contenido_366_dias']
            elif isinstance(datos, list):
                contenido_dias = datos
            else:
                raise ValueError("Formato de archivo JSON no reconocido")

            for dia_data in contenido_dias:
                # Mapear campos del JSON a los campos del modelo existente
                # Según el error: dia, mes, tema, cita, autor, reflexion, pregunta

                contenido, created = ContenidoDiario.objects.get_or_create(
                    dia=dia_data.get('dia_año', dia_data.get('dia', 1)),  # Usar dia_año o dia
                    defaults={
                        'mes': dia_data.get('mes', 'Enero'),
                        'tema': dia_data.get('tema', 'Sabiduría General'),
                        'cita': dia_data.get('cita', ''),
                        'autor': dia_data.get('autor', 'Filósofo Estoico'),
                        'reflexion': dia_data.get('reflexion', ''),
                        'pregunta': dia_data.get('pregunta_diario', dia_data.get('pregunta', ''))
                    }
                )

                if created:
                    contenidos_creados += 1

            self.stdout.write(
                self.style.SUCCESS(f'✅ {contenidos_creados} contenidos diarios cargados')
            )

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'❌ Archivo {archivo_path} no encontrado')
            )
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error decodificando JSON: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error cargando contenido: {e}')
            )

    def _crear_logros_predefinidos(self):
        """Crea los logros predefinidos del sistema."""
        self.stdout.write('🏆 Creando logros predefinidos...')

        from estoico.models import Logro

        logros_data = [
            # Logros de Inicio
            {
                'nombre': 'Primer Paso',
                'descripcion': 'Completa tu primera reflexión diaria',
                'icono': '🌱',
                'criterio_tipo': 'reflexiones_completadas',
                'criterio_valor': 1,
                'puntos': 10,
                'categoria': 'inicio'
            },
            {
                'nombre': 'Semana Sabia',
                'descripcion': 'Reflexiona durante 7 días consecutivos',
                'icono': '📅',
                'criterio_tipo': 'racha_dias',
                'criterio_valor': 7,
                'puntos': 50,
                'categoria': 'racha'
            },
            {
                'nombre': 'Mes Estoico',
                'descripcion': 'Mantén una racha de 30 días',
                'icono': '🗓️',
                'criterio_tipo': 'racha_dias',
                'criterio_valor': 30,
                'puntos': 200,
                'categoria': 'racha'
            },

            # Logros de Calidad
            {
                'nombre': 'Perfeccionista',
                'descripcion': 'Obtén 10 calificaciones de 5 estrellas',
                'icono': '⭐',
                'criterio_tipo': 'calificaciones_5_estrellas',
                'criterio_valor': 10,
                'puntos': 100,
                'categoria': 'calidad'
            },
            {
                'nombre': 'Excelencia Constante',
                'descripcion': 'Mantén un promedio de 4+ estrellas en 30 días',
                'icono': '🌟',
                'criterio_tipo': 'promedio_alto_30_dias',
                'criterio_valor': 4,
                'puntos': 150,
                'categoria': 'calidad'
            },

            # Logros de Cantidad
            {
                'nombre': 'Centurión',
                'descripcion': 'Completa 100 reflexiones',
                'icono': '💯',
                'criterio_tipo': 'reflexiones_completadas',
                'criterio_valor': 100,
                'puntos': 300,
                'categoria': 'cantidad'
            },
            {
                'nombre': 'Filósofo Dedicado',
                'descripcion': 'Completa 365 reflexiones',
                'icono': '🎓',
                'criterio_tipo': 'reflexiones_completadas',
                'criterio_valor': 365,
                'puntos': 1000,
                'categoria': 'cantidad'
            },

            # Logros de Exploración
            {
                'nombre': 'Explorador de Sabiduría',
                'descripcion': 'Reflexiona con citas de los 3 filósofos principales',
                'icono': '🗺️',
                'criterio_tipo': 'filosofos_diferentes',
                'criterio_valor': 3,
                'puntos': 75,
                'categoria': 'exploracion'
            },
            {
                'nombre': 'Coleccionista de Favoritos',
                'descripcion': 'Marca 25 reflexiones como favoritas',
                'icono': '❤️',
                'criterio_tipo': 'favoritos_marcados',
                'criterio_valor': 25,
                'puntos': 80,
                'categoria': 'exploracion'
            },

            # Logros Especiales
            {
                'nombre': 'Madrugador Estoico',
                'descripcion': 'Reflexiona antes de las 7 AM durante 10 días',
                'icono': '🌅',
                'criterio_tipo': 'reflexiones_temprano',
                'criterio_valor': 10,
                'puntos': 120,
                'categoria': 'especial'
            },
            {
                'nombre': 'Búho Sabio',
                'descripcion': 'Reflexiona después de las 10 PM durante 10 días',
                'icono': '🦉',
                'criterio_tipo': 'reflexiones_tarde',
                'criterio_valor': 10,
                'puntos': 120,
                'categoria': 'especial'
            },
            {
                'nombre': 'Guerrero de Fin de Semana',
                'descripcion': 'Reflexiona todos los fines de semana durante un mes',
                'icono': '⚔️',
                'criterio_tipo': 'fines_semana_consecutivos',
                'criterio_valor': 8,
                'puntos': 100,
                'categoria': 'especial'
            },

            # Logros de Maestría
            {
                'nombre': 'Discípulo de Marco Aurelio',
                'descripcion': 'Completa 50 reflexiones con citas de Marco Aurelio',
                'icono': '👑',
                'criterio_tipo': 'reflexiones_marco_aurelio',
                'criterio_valor': 50,
                'puntos': 200,
                'categoria': 'maestria'
            },
            {
                'nombre': 'Seguidor de Séneca',
                'descripcion': 'Completa 50 reflexiones con citas de Séneca',
                'icono': '📜',
                'criterio_tipo': 'reflexiones_seneca',
                'criterio_valor': 50,
                'puntos': 200,
                'categoria': 'maestria'
            },
            {
                'nombre': 'Alumno de Epicteto',
                'descripcion': 'Completa 50 reflexiones con citas de Epicteto',
                'icono': '🕊️',
                'criterio_tipo': 'reflexiones_epicteto',
                'criterio_valor': 50,
                'puntos': 200,
                'categoria': 'maestria'
            },

            # Logros Épicos
            {
                'nombre': 'Emperador Filósofo',
                'descripcion': 'Mantén una racha de 100 días',
                'icono': '🏛️',
                'criterio_tipo': 'racha_dias',
                'criterio_valor': 100,
                'puntos': 500,
                'categoria': 'epico'
            },
            {
                'nombre': 'Maestro Estoico',
                'descripcion': 'Alcanza 1000 días de reflexión total',
                'icono': '🧙‍♂️',
                'criterio_tipo': 'reflexiones_completadas',
                'criterio_valor': 1000,
                'puntos': 2000,
                'categoria': 'epico'
            },
            {
                'nombre': 'Leyenda Viviente',
                'descripcion': 'Mantén una racha de 365 días',
                'icono': '🌟',
                'criterio_tipo': 'racha_dias',
                'criterio_valor': 365,
                'puntos': 3000,
                'categoria': 'epico'
            }
        ]

        logros_creados = 0

        for logro_data in logros_data:
            # Verificar si el modelo Logro tiene estos campos
            try:
                logro, created = Logro.objects.get_or_create(
                    nombre=logro_data['nombre'],
                    defaults={
                        'descripcion': logro_data['descripcion'],
                        'icono': logro_data['icono'],
                        'puntos': logro_data['puntos'],
                        # Solo agregar campos que existan en el modelo
                        **{k: v for k, v in logro_data.items()
                           if k in ['criterio_tipo', 'criterio_valor', 'categoria']
                           and hasattr(Logro, k)}
                    }
                )

                if created:
                    logros_creados += 1
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ No se pudo crear logro {logro_data["nombre"]}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'✅ {logros_creados} logros creados')
        )

    def _crear_usuario_demo(self):
        """Crea un usuario de demostración con datos de ejemplo."""
        self.stdout.write('👤 Creando usuario de demostración...')

        try:
            from estoico.models import PerfilEstoico, ReflexionDiaria, ContenidoDiario
            from django.contrib.auth.models import User
            import random

            # Crear usuario demo
            usuario_demo, created = User.objects.get_or_create(
                username='demo_estoico',
                defaults={
                    'email': 'demo@estoico.app',
                    'first_name': 'Usuario',
                    'last_name': 'Demo',
                    'is_active': True
                }
            )

            if created:
                usuario_demo.set_password('demo123')
                usuario_demo.save()

            # Crear perfil estoico si el modelo existe
            try:
                perfil, created = PerfilEstoico.objects.get_or_create(
                    usuario=usuario_demo,
                    defaults={
                        'filosofo_favorito': 'marco_aurelio',
                        'nivel_dificultad': 'intermedio',
                        'notificaciones_activas': True,
                        'tema': 'claro'
                    }
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ No se pudo crear perfil estoico: {e}')
                )

            # Crear reflexiones de ejemplo si los modelos existen
            try:
                contenidos = list(ContenidoDiario.objects.all()[:30])
                fecha_inicio = timezone.now().date() - timedelta(days=29)

                reflexiones_creadas = 0

                for i, contenido in enumerate(contenidos):
                    fecha_reflexion = fecha_inicio + timedelta(days=i)

                    # Crear reflexión con datos aleatorios realistas
                    reflexion, created = ReflexionDiaria.objects.get_or_create(
                        usuario=usuario_demo,
                        contenido=contenido,
                        fecha=fecha_reflexion,
                        defaults={
                            'reflexion_personal': self._generar_reflexion_ejemplo(contenido),
                            'calificacion_dia': random.randint(3, 5),
                            'completada': True
                        }
                    )

                    if created:
                        reflexiones_creadas += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Usuario demo creado con {reflexiones_creadas} reflexiones de ejemplo'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ No se pudieron crear reflexiones de ejemplo: {e}')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creando usuario demo: {e}')
            )

    def _generar_reflexion_ejemplo(self, contenido):
        """Genera una reflexión de ejemplo basada en el contenido."""
        reflexiones_ejemplo = [
            f"Esta cita de {contenido.autor} me hace reflexionar sobre la importancia de mantener la calma en situaciones difíciles. En mi vida diaria, puedo aplicar esto cuando me enfrento a desafíos en el trabajo.",

            f"Las palabras de {contenido.autor} resuenan profundamente conmigo. Me recuerdan que tengo control sobre mis reacciones, aunque no siempre sobre las circunstancias externas.",

            f"Hoy me siento inspirado por esta enseñanza estoica. {contenido.autor} tenía razón al enfatizar la virtud como el bien supremo. Voy a intentar aplicar esto en mis relaciones personales.",

            f"Esta reflexión me ayuda a poner las cosas en perspectiva. A menudo me preocupo por cosas que están fuera de mi control, pero {contenido.autor} me recuerda enfocarme en lo que sí puedo cambiar.",

            f"Me parece fascinante cómo las enseñanzas de {contenido.autor} siguen siendo relevantes después de tantos siglos. Esta sabiduría antigua tiene mucho que ofrecer a nuestro mundo moderno."
        ]

        import random
        return random.choice(reflexiones_ejemplo)
