# Script de Migración Inicial para App Estoica
# migracion_inicial_estoica.py

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
            self.style.SUCCESS('🏛️ Iniciando migración de datos estoicos...')
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
                    self.style.SUCCESS('✅ Migración completada exitosamente')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en la migración: {e}')
            )
            raise
    
    def _limpiar_datos_existentes(self):
        """Limpia datos existentes de la app estoica."""
        self.stdout.write('🧹 Limpiando datos existentes...')
        
        from estoico.models import (
            ContenidoDiario, ReflexionDiaria, Logro, LogroUsuario,
            PerfilEstoico, RegistroNotificacion
        )
        
        # Eliminar en orden para respetar foreign keys
        RegistroNotificacion.objects.all().delete()
        LogroUsuario.objects.all().delete()
        ReflexionDiaria.objects.all().delete()
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
                contenido, created = ContenidoDiario.objects.get_or_create(
                    dia_año=dia_data['dia_año'],
                    defaults={
                        'fecha': datetime.strptime(dia_data['fecha'], '%Y-%m-%d').date(),
                        'cita': dia_data['cita'],
                        'autor': dia_data['autor'],
                        'reflexion': dia_data['reflexion'],
                        'pregunta_diario': dia_data['pregunta_diario'],
                        'tema': dia_data.get('tema', ''),
                        'idioma_original': dia_data.get('idioma_original', ''),
                        'contexto_historico': dia_data.get('contexto_historico', ''),
                        'palabras_clave': dia_data.get('palabras_clave', ''),
                        'nivel_dificultad': dia_data.get('nivel_dificultad', 'intermedio')
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
            logro, created = Logro.objects.get_or_create(
                nombre=logro_data['nombre'],
                defaults=logro_data
            )
            
            if created:
                logros_creados += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {logros_creados} logros creados')
        )
    
    def _crear_usuario_demo(self):
        """Crea un usuario de demostración con datos de ejemplo."""
        self.stdout.write('👤 Creando usuario de demostración...')
        
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
        
        # Crear perfil estoico
        perfil, created = PerfilEstoico.objects.get_or_create(
            usuario=usuario_demo,
            defaults={
                'filosofo_favorito': 'marco_aurelio',
                'nivel_dificultad': 'intermedio',
                'notificaciones_activas': True,
                'hora_notificacion': '08:00',
                'frecuencia_notificacion': 'diario',
                'tema': 'claro',
                'tamano_fuente': 'normal'
            }
        )
        
        # Crear reflexiones de ejemplo (últimos 30 días)
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
                    'marcado_favorito': random.choice([True, False, False, False]),  # 25% favoritos
                    'tiempo_reflexion': random.randint(120, 600),  # 2-10 minutos
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
    
    def _generar_reflexion_ejemplo(self, contenido):
        """Genera una reflexión de ejemplo basada en el contenido."""
        reflexiones_ejemplo = [
            f"Esta cita de {contenido.autor} me hace reflexionar sobre la importancia de mantener la calma en situaciones difíciles. En mi vida diaria, puedo aplicar esto cuando me enfrento a desafíos en el trabajo.",
            
            f"Las palabras de {contenido.autor} resuenan profundamente conmigo. Me recuerdan que tengo control sobre mis reacciones, aunque no siempre sobre las circunstancias externas.",
            
            f"Hoy me siento inspirado por esta enseñanza estoica. {contenido.autor} tenía razón al enfatizar la virtud como el bien supremo. Voy a intentar aplicar esto en mis relaciones personales.",
            
            f"Esta reflexión me ayuda a poner las cosas en perspectiva. A menudo me preocupo por cosas que están fuera de mi control, pero {contenido.autor} me recuerda enfocarme en lo que sí puedo cambiar.",
            
            f"Me parece fascinante cómo las enseñanzas de {contenido.autor} siguen siendo relevantes después de tantos siglos. Esta sabiduría antigua tiene mucho que ofrecer a nuestro mundo moderno.",
            
            f"Después de leer esta cita, me doy cuenta de que necesito trabajar más en mi autodisciplina. {contenido.autor} nos muestra que la verdadera libertad viene del autocontrol.",
            
            f"Esta enseñanza me recuerda la importancia de vivir en el presente. A menudo me pierdo en preocupaciones sobre el futuro o lamentos del pasado, pero {contenido.autor} me trae de vuelta al ahora."
        ]
        
        return random.choice(reflexiones_ejemplo)


# Script adicional para verificar integridad de datos
class ComandoVerificarDatos(BaseCommand):
    """
    Comando para verificar la integridad de los datos cargados.
    Uso: python manage.py verificar_datos_estoicos
    """
    
    help = 'Verifica la integridad de los datos estoicos'
    
    def handle(self, *args, **options):
        self.stdout.write('🔍 Verificando integridad de datos...')
        
        self._verificar_contenido_diario()
        self._verificar_logros()
        self._verificar_usuarios()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Verificación completada')
        )
    
    def _verificar_contenido_diario(self):
        """Verifica que el contenido diario esté completo."""
        from estoico.models import ContenidoDiario
        
        total_contenidos = ContenidoDiario.objects.count()
        self.stdout.write(f'📚 Contenidos diarios: {total_contenidos}/366')
        
        if total_contenidos < 366:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Faltan {366 - total_contenidos} contenidos')
            )
        
        # Verificar días faltantes
        dias_existentes = set(
            ContenidoDiario.objects.values_list('dia_año', flat=True)
        )
        dias_faltantes = set(range(1, 367)) - dias_existentes
        
        if dias_faltantes:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Días faltantes: {sorted(list(dias_faltantes))}')
            )
        
        # Verificar campos obligatorios
        contenidos_incompletos = ContenidoDiario.objects.filter(
            cita__isnull=True
        ).count()
        
        if contenidos_incompletos > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ {contenidos_incompletos} contenidos sin cita')
            )
    
    def _verificar_logros(self):
        """Verifica que los logros estén configurados correctamente."""
        from estoico.models import Logro
        
        total_logros = Logro.objects.count()
        self.stdout.write(f'🏆 Logros configurados: {total_logros}')
        
        # Verificar logros por categoría
        categorias = Logro.objects.values_list('categoria', flat=True).distinct()
        for categoria in categorias:
            count = Logro.objects.filter(categoria=categoria).count()
            self.stdout.write(f'  - {categoria}: {count} logros')
        
        # Verificar logros sin criterios
        logros_sin_criterio = Logro.objects.filter(
            criterio_tipo__isnull=True
        ).count()
        
        if logros_sin_criterio > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️ {logros_sin_criterio} logros sin criterio')
            )
    
    def _verificar_usuarios(self):
        """Verifica el estado de los usuarios."""
        from django.contrib.auth.models import User
        from estoico.models import PerfilEstoico, ReflexionDiaria
        
        total_usuarios = User.objects.count()
        usuarios_con_perfil = PerfilEstoico.objects.count()
        usuarios_activos = ReflexionDiaria.objects.values('usuario').distinct().count()
        
        self.stdout.write(f'👥 Usuarios totales: {total_usuarios}')
        self.stdout.write(f'👤 Usuarios con perfil estoico: {usuarios_con_perfil}')
        self.stdout.write(f'✍️ Usuarios con reflexiones: {usuarios_activos}')
        
        if usuarios_con_perfil < total_usuarios:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ {total_usuarios - usuarios_con_perfil} usuarios sin perfil estoico'
                )
            )


# Script para backup de datos
class ComandoBackupDatos(BaseCommand):
    """
    Comando para crear backup de todos los datos estoicos.
    Uso: python manage.py backup_datos_estoicos
    """
    
    help = 'Crea backup de todos los datos estoicos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo-salida',
            type=str,
            default=f'backup_estoico_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            help='Nombre del archivo de backup'
        )
        
        parser.add_argument(
            '--incluir-usuarios',
            action='store_true',
            help='Incluir datos de usuarios en el backup'
        )
    
    def handle(self, *args, **options):
        archivo_salida = options['archivo_salida']
        incluir_usuarios = options['incluir_usuarios']
        
        self.stdout.write(f'💾 Creando backup en {archivo_salida}...')
        
        backup_data = {
            'timestamp': timezone.now().isoformat(),
            'version': '1.0',
            'incluye_usuarios': incluir_usuarios
        }
        
        # Backup de contenido diario
        backup_data['contenido_diario'] = self._backup_contenido_diario()
        
        # Backup de logros
        backup_data['logros'] = self._backup_logros()
        
        # Backup de usuarios (opcional)
        if incluir_usuarios:
            backup_data['usuarios'] = self._backup_usuarios()
            backup_data['reflexiones'] = self._backup_reflexiones()
        
        # Guardar archivo
        try:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Backup creado exitosamente: {archivo_salida}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creando backup: {e}')
            )
    
    def _backup_contenido_diario(self):
        """Crea backup del contenido diario."""
        from estoico.models import ContenidoDiario
        
        contenidos = []
        for contenido in ContenidoDiario.objects.all():
            contenidos.append({
                'dia_año': contenido.dia_año,
                'fecha': contenido.fecha.isoformat(),
                'cita': contenido.cita,
                'autor': contenido.autor,
                'reflexion': contenido.reflexion,
                'pregunta_diario': contenido.pregunta_diario,
                'tema': contenido.tema,
                'idioma_original': contenido.idioma_original,
                'contexto_historico': contenido.contexto_historico,
                'palabras_clave': contenido.palabras_clave,
                'nivel_dificultad': contenido.nivel_dificultad
            })
        
        return contenidos
    
    def _backup_logros(self):
        """Crea backup de los logros."""
        from estoico.models import Logro
        
        logros = []
        for logro in Logro.objects.all():
            logros.append({
                'nombre': logro.nombre,
                'descripcion': logro.descripcion,
                'icono': logro.icono,
                'criterio_tipo': logro.criterio_tipo,
                'criterio_valor': logro.criterio_valor,
                'puntos': logro.puntos,
                'categoria': logro.categoria,
                'activo': logro.activo
            })
        
        return logros
    
    def _backup_usuarios(self):
        """Crea backup de usuarios y perfiles."""
        from django.contrib.auth.models import User
        from estoico.models import PerfilEstoico
        
        usuarios = []
        for usuario in User.objects.all():
            usuario_data = {
                'username': usuario.username,
                'email': usuario.email,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'date_joined': usuario.date_joined.isoformat(),
                'is_active': usuario.is_active
            }
            
            # Agregar perfil estoico si existe
            try:
                perfil = PerfilEstoico.objects.get(usuario=usuario)
                usuario_data['perfil_estoico'] = {
                    'filosofo_favorito': perfil.filosofo_favorito,
                    'nivel_dificultad': perfil.nivel_dificultad,
                    'notificaciones_activas': perfil.notificaciones_activas,
                    'hora_notificacion': perfil.hora_notificacion.strftime('%H:%M'),
                    'frecuencia_notificacion': perfil.frecuencia_notificacion,
                    'tema': perfil.tema,
                    'tamano_fuente': perfil.tamano_fuente
                }
            except PerfilEstoico.DoesNotExist:
                pass
            
            usuarios.append(usuario_data)
        
        return usuarios
    
    def _backup_reflexiones(self):
        """Crea backup de las reflexiones."""
        from estoico.models import ReflexionDiaria
        
        reflexiones = []
        for reflexion in ReflexionDiaria.objects.all():
            reflexiones.append({
                'usuario_username': reflexion.usuario.username,
                'contenido_dia_año': reflexion.contenido.dia_año,
                'fecha': reflexion.fecha.isoformat(),
                'reflexion_personal': reflexion.reflexion_personal,
                'calificacion_dia': reflexion.calificacion_dia,
                'marcado_favorito': reflexion.marcado_favorito,
                'tiempo_reflexion': reflexion.tiempo_reflexion,
                'completada': reflexion.completada,
                'fecha_creacion': reflexion.fecha_creacion.isoformat()
            })
        
        return reflexiones

