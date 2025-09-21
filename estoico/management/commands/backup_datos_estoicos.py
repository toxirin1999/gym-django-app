# Django Management Command: backup_datos_estoicos.py
# Ubicación: estoico/management/commands/backup_datos_estoicos.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
import json
import os


class Command(BaseCommand):
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

        parser.add_argument(
            '--directorio',
            type=str,
            default='backups/',
            help='Directorio donde guardar el backup'
        )

        parser.add_argument(
            '--comprimir',
            action='store_true',
            help='Comprimir el archivo de backup con gzip'
        )

        parser.add_argument(
            '--limpiar-antiguos',
            type=int,
            default=0,
            help='Eliminar backups más antiguos que N días'
        )

    def handle(self, *args, **options):
        archivo_salida = options['archivo_salida']
        incluir_usuarios = options['incluir_usuarios']
        directorio = options['directorio']

        # Crear directorio si no existe
        if not os.path.exists(directorio):
            os.makedirs(directorio)

        ruta_completa = os.path.join(directorio, archivo_salida)

        self.stdout.write(f'💾 Creando backup en {ruta_completa}...')

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
            backup_data['logros_usuarios'] = self._backup_logros_usuarios()

        # Guardar archivo
        try:
            with open(ruta_completa, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

            # Mostrar estadísticas del backup
            file_size = os.path.getsize(ruta_completa)
            file_size_mb = file_size / (1024 * 1024)

            self.stdout.write(
                self.style.SUCCESS(f'✅ Backup creado exitosamente: {ruta_completa}')
            )
            self.stdout.write(f'📊 Tamaño del archivo: {file_size_mb:.2f} MB')

            # Mostrar resumen del contenido
            self._mostrar_resumen_backup(backup_data)

            # Comprimir si se solicita
            if options.get('comprimir'):
                self._comprimir_backup(ruta_completa)

            # Limpiar backups antiguos si se solicita
            dias_antiguos = options.get('limpiar_antiguos', 0)
            if dias_antiguos > 0:
                self._limpiar_backups_antiguos(directorio, dias_antiguos)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creando backup: {e}')
            )

    def _backup_contenido_diario(self):
        """Crea backup del contenido diario."""
        try:
            from estoico.models import ContenidoDiario

            contenidos = []
            for contenido in ContenidoDiario.objects.all().order_by('dia'):
                contenido_data = {
                    'dia': contenido.dia,
                    'mes': contenido.mes,
                    'tema': contenido.tema,
                    'cita': contenido.cita,
                    'autor': contenido.autor,
                    'reflexion': contenido.reflexion,
                    'pregunta': contenido.pregunta,
                }

                # Agregar campos adicionales si existen
                if hasattr(contenido, 'fecha_creacion'):
                    contenido_data['fecha_creacion'] = contenido.fecha_creacion
                if hasattr(contenido, 'fecha_actualizacion'):
                    contenido_data['fecha_actualizacion'] = contenido.fecha_actualizacion

                contenidos.append(contenido_data)

            return contenidos

        except ImportError:
            self.stdout.write(
                self.style.WARNING('⚠️ Modelo ContenidoDiario no encontrado')
            )
            return []
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en backup de contenido diario: {e}')
            )
            return []

    def _backup_logros(self):
        """Crea backup de los logros."""
        try:
            from estoico.models import Logro

            logros = []
            for logro in Logro.objects.all().order_by('nombre'):
                logro_data = {
                    'nombre': logro.nombre,
                    'descripcion': logro.descripcion,
                }

                # Agregar campos opcionales si existen
                if hasattr(logro, 'icono'):
                    logro_data['icono'] = logro.icono
                if hasattr(logro, 'criterio_tipo'):
                    logro_data['criterio_tipo'] = logro.criterio_tipo
                if hasattr(logro, 'criterio_valor'):
                    logro_data['criterio_valor'] = logro.criterio_valor
                if hasattr(logro, 'puntos'):
                    logro_data['puntos'] = logro.puntos
                if hasattr(logro, 'categoria'):
                    logro_data['categoria'] = logro.categoria
                if hasattr(logro, 'activo'):
                    logro_data['activo'] = logro.activo

                logros.append(logro_data)

            return logros

        except ImportError:
            self.stdout.write(
                self.style.WARNING('⚠️ Modelo Logro no encontrado')
            )
            return []
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en backup de logros: {e}')
            )
            return []

    def _backup_usuarios(self):
        """Crea backup de usuarios y perfiles."""
        try:
            from django.contrib.auth.models import User

            usuarios = []
            for usuario in User.objects.all().order_by('username'):
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
                    from estoico.models import PerfilEstoico
                    perfil = PerfilEstoico.objects.get(usuario=usuario)

                    perfil_data = {}
                    if hasattr(perfil, 'filosofo_favorito'):
                        perfil_data['filosofo_favorito'] = perfil.filosofo_favorito
                    if hasattr(perfil, 'nivel_dificultad'):
                        perfil_data['nivel_dificultad'] = perfil.nivel_dificultad
                    if hasattr(perfil, 'notificaciones_activas'):
                        perfil_data['notificaciones_activas'] = perfil.notificaciones_activas
                    if hasattr(perfil, 'tema'):
                        perfil_data['tema'] = perfil.tema

                    if perfil_data:
                        usuario_data['perfil_estoico'] = perfil_data

                except (ImportError, Exception):
                    pass

                usuarios.append(usuario_data)

            return usuarios

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en backup de usuarios: {e}')
            )
            return []

    def _backup_reflexiones(self):
        """Crea backup de las reflexiones."""
        try:
            from estoico.models import ReflexionDiaria

            reflexiones = []
            for reflexion in ReflexionDiaria.objects.all().order_by('fecha', 'usuario__username'):
                reflexion_data = {
                    'usuario_username': reflexion.usuario.username,
                    'contenido_dia': reflexion.contenido.dia,
                    'fecha': reflexion.fecha.isoformat(),
                    'reflexion_personal': reflexion.reflexion_personal,
                }

                # Agregar campos opcionales si existen
                if hasattr(reflexion, 'calificacion_dia'):
                    reflexion_data['calificacion_dia'] = reflexion.calificacion_dia
                if hasattr(reflexion, 'marcado_favorito'):
                    reflexion_data['marcado_favorito'] = reflexion.marcado_favorito
                if hasattr(reflexion, 'tiempo_reflexion'):
                    reflexion_data['tiempo_reflexion'] = reflexion.tiempo_reflexion
                if hasattr(reflexion, 'completada'):
                    reflexion_data['completada'] = reflexion.completada
                if hasattr(reflexion, 'fecha_creacion'):
                    reflexion_data['fecha_creacion'] = reflexion.fecha_creacion.isoformat()

                reflexiones.append(reflexion_data)

            return reflexiones

        except ImportError:
            self.stdout.write(
                self.style.WARNING('⚠️ Modelo ReflexionDiaria no encontrado')
            )
            return []
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en backup de reflexiones: {e}')
            )
            return []

    def _backup_logros_usuarios(self):
        """Crea backup de los logros de usuarios."""
        try:
            from estoico.models import LogroUsuario

            logros_usuarios = []
            for logro_usuario in LogroUsuario.objects.all().order_by('fecha_obtenido'):
                logro_data = {
                    'usuario_username': logro_usuario.usuario.username,
                    'logro_nombre': logro_usuario.logro.nombre,
                    'fecha_obtenido': logro_usuario.fecha_obtenido.isoformat(),
                }

                # Agregar campos opcionales si existen
                if hasattr(logro_usuario, 'visto'):
                    logro_data['visto'] = logro_usuario.visto

                logros_usuarios.append(logro_data)

            return logros_usuarios

        except ImportError:
            self.stdout.write(
                self.style.WARNING('⚠️ Modelo LogroUsuario no encontrado')
            )
            return []
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en backup de logros de usuarios: {e}')
            )
            return []

    def _mostrar_resumen_backup(self, backup_data):
        """Muestra un resumen del contenido del backup."""
        self.stdout.write('\n📊 Resumen del backup:')

        # Contenido diario
        contenido_count = len(backup_data.get('contenido_diario', []))
        self.stdout.write(f'  📚 Contenidos diarios: {contenido_count}')

        # Logros
        logros_count = len(backup_data.get('logros', []))
        self.stdout.write(f'  🏆 Logros: {logros_count}')

        # Datos de usuarios (si están incluidos)
        if backup_data.get('incluye_usuarios'):
            usuarios_count = len(backup_data.get('usuarios', []))
            reflexiones_count = len(backup_data.get('reflexiones', []))
            logros_usuarios_count = len(backup_data.get('logros_usuarios', []))

            self.stdout.write(f'  👥 Usuarios: {usuarios_count}')
            self.stdout.write(f'  📝 Reflexiones: {reflexiones_count}')
            self.stdout.write(f'  🎖️ Logros de usuarios: {logros_usuarios_count}')

        self.stdout.write(f'  🕐 Fecha del backup: {backup_data["timestamp"]}')
        self.stdout.write(f'  📋 Versión: {backup_data["version"]}')

    def _comprimir_backup(self, ruta_original):
        """Comprime el archivo de backup."""
        try:
            import gzip
            import shutil

            ruta_comprimida = ruta_original + '.gz'

            with open(ruta_original, 'rb') as f_in:
                with gzip.open(ruta_comprimida, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Eliminar archivo original
            os.remove(ruta_original)

            # Mostrar información de compresión
            size_compressed = os.path.getsize(ruta_comprimida)
            size_compressed_mb = size_compressed / (1024 * 1024)

            self.stdout.write(
                self.style.SUCCESS(f'🗜️ Backup comprimido: {ruta_comprimida}')
            )
            self.stdout.write(f'📊 Tamaño comprimido: {size_compressed_mb:.2f} MB')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error comprimiendo backup: {e}')
            )

    def _limpiar_backups_antiguos(self, directorio, dias_antiguos):
        """Elimina backups más antiguos que el número de días especificado."""
        try:
            from datetime import timedelta

            fecha_limite = timezone.now() - timedelta(days=dias_antiguos)
            archivos_eliminados = 0

            for archivo in os.listdir(directorio):
                if archivo.startswith('backup_estoico_'):
                    ruta_archivo = os.path.join(directorio, archivo)
                    fecha_archivo = datetime.fromtimestamp(
                        os.path.getctime(ruta_archivo)
                    )
                    fecha_archivo = timezone.make_aware(fecha_archivo)

                    if fecha_archivo < fecha_limite:
                        os.remove(ruta_archivo)
                        archivos_eliminados += 1
                        self.stdout.write(f'🗑️ Eliminado: {archivo}')

            if archivos_eliminados > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {archivos_eliminados} backups antiguos eliminados')
                )
            else:
                self.stdout.write('ℹ️ No hay backups antiguos para eliminar')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error limpiando backups antiguos: {e}')
            )
