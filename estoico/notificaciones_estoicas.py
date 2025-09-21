# Sistema de Notificaciones para App Estoica
# notificaciones_estoicas.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import json
import requests
from typing import List, Dict, Optional
import logging

# Configurar logging
logger = logging.getLogger(__name__)

class NotificacionesEstoicas:
    """
    Sistema completo de notificaciones para la app estoica.
    Maneja recordatorios diarios, notificaciones de logros y mensajes motivacionales.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'PUSH_NOTIFICATION_URL', None)
        self.api_key = getattr(settings, 'PUSH_NOTIFICATION_KEY', None)
        
    def enviar_recordatorio_diario(self, usuario_id: int) -> bool:
        """
        Envía recordatorio diario para reflexionar.
        """
        try:
            from .models import PerfilEstoico, ContenidoDiario
            
            perfil = PerfilEstoico.objects.get(usuario_id=usuario_id)
            
            if not perfil.notificaciones_activas:
                return False
                
            # Verificar si ya reflexionó hoy
            hoy = timezone.now().date()
            dia_año = hoy.timetuple().tm_yday
            
            from .models import ReflexionDiaria
            ya_reflexiono = ReflexionDiaria.objects.filter(
                usuario_id=usuario_id,
                fecha=hoy
            ).exists()
            
            if ya_reflexiono:
                return False  # Ya reflexionó hoy
                
            # Obtener contenido del día
            contenido = ContenidoDiario.objects.filter(dia_año=dia_año).first()
            
            if not contenido:
                return False
                
            # Preparar mensaje personalizado
            mensaje = self._generar_mensaje_recordatorio(perfil, contenido)
            
            # Enviar notificación
            return self._enviar_notificacion_push(
                usuario_id=usuario_id,
                titulo="🏛️ Momento de Reflexión",
                mensaje=mensaje,
                tipo="recordatorio_diario",
                datos_extra={
                    'dia_año': dia_año,
                    'autor': contenido.autor,
                    'tema': contenido.tema
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio diario a usuario {usuario_id}: {e}")
            return False
    
    def enviar_notificacion_logro(self, usuario_id: int, logro_id: int) -> bool:
        """
        Envía notificación cuando se desbloquea un logro.
        """
        try:
            from .models import Logro, LogroUsuario
            
            logro_usuario = LogroUsuario.objects.get(
                usuario_id=usuario_id,
                logro_id=logro_id
            )
            
            logro = logro_usuario.logro
            
            mensaje = f"¡Felicitaciones! Has desbloqueado: {logro.nombre}"
            
            return self._enviar_notificacion_push(
                usuario_id=usuario_id,
                titulo="🏆 ¡Nuevo Logro!",
                mensaje=mensaje,
                tipo="logro_desbloqueado",
                datos_extra={
                    'logro_id': logro_id,
                    'logro_nombre': logro.nombre,
                    'logro_descripcion': logro.descripcion
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificación de logro: {e}")
            return False
    
    def enviar_recordatorio_racha(self, usuario_id: int, dias_racha: int) -> bool:
        """
        Envía recordatorio especial para mantener la racha.
        """
        try:
            if dias_racha < 3:  # Solo para rachas significativas
                return False
                
            mensajes_racha = {
                3: "¡3 días consecutivos! Estás construyendo un hábito sólido 💪",
                7: "¡Una semana completa! Tu disciplina estoica está floreciendo 🌱",
                14: "¡Dos semanas! Como decía Marco Aurelio: 'La disciplina es libertad' 🗽",
                30: "¡Un mes entero! Has demostrado verdadera virtud estoica 👑",
                60: "¡Dos meses! Tu perseverancia sería admirada por Epicteto 🕊️",
                90: "¡Tres meses! Como Séneca: 'Cada día es un paso hacia la sabiduría' 📚",
                180: "¡Medio año! Tu dedicación es verdaderamente filosófica 🏛️",
                365: "¡Un año completo! Has alcanzado la maestría estoica 🎯"
            }
            
            mensaje = mensajes_racha.get(
                dias_racha, 
                f"¡{dias_racha} días consecutivos! Tu constancia es admirable 🔥"
            )
            
            return self._enviar_notificacion_push(
                usuario_id=usuario_id,
                titulo="🔥 ¡Racha Increíble!",
                mensaje=mensaje,
                tipo="racha_especial",
                datos_extra={
                    'dias_racha': dias_racha
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio de racha: {e}")
            return False
    
    def enviar_cita_inspiracional(self, usuario_id: int) -> bool:
        """
        Envía una cita inspiracional aleatoria.
        """
        try:
            from .models import ContenidoDiario, PerfilEstoico
            import random
            
            perfil = PerfilEstoico.objects.get(usuario_id=usuario_id)
            
            # Filtrar por filósofo favorito si está configurado
            queryset = ContenidoDiario.objects.all()
            if perfil.filosofo_favorito and perfil.filosofo_favorito != 'todos':
                queryset = queryset.filter(autor__icontains=perfil.filosofo_favorito.replace('_', ' '))
            
            contenido = queryset.order_by('?').first()
            
            if not contenido:
                return False
            
            mensaje = f'"{contenido.cita}" - {contenido.autor}'
            
            return self._enviar_notificacion_push(
                usuario_id=usuario_id,
                titulo="💭 Sabiduría Estoica",
                mensaje=mensaje,
                tipo="cita_inspiracional",
                datos_extra={
                    'autor': contenido.autor,
                    'tema': contenido.tema
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando cita inspiracional: {e}")
            return False
    
    def programar_notificaciones_usuario(self, usuario_id: int) -> bool:
        """
        Programa todas las notificaciones para un usuario según sus preferencias.
        """
        try:
            from .models import PerfilEstoico
            from celery import current_app
            
            perfil = PerfilEstoico.objects.get(usuario_id=usuario_id)
            
            if not perfil.notificaciones_activas:
                return False
            
            # Cancelar tareas programadas existentes
            self._cancelar_notificaciones_programadas(usuario_id)
            
            # Programar recordatorio diario
            if perfil.frecuencia_notificacion == 'diario':
                self._programar_recordatorio_diario(usuario_id, perfil.hora_notificacion)
            elif perfil.frecuencia_notificacion == 'dias_laborales':
                self._programar_recordatorio_laborales(usuario_id, perfil.hora_notificacion)
            
            # Programar notificaciones de logros (siempre activas)
            if perfil.notificaciones_logros:
                self._programar_verificacion_logros(usuario_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error programando notificaciones para usuario {usuario_id}: {e}")
            return False
    
    def _generar_mensaje_recordatorio(self, perfil, contenido) -> str:
        """
        Genera un mensaje personalizado para el recordatorio diario.
        """
        mensajes_base = [
            "Es momento de reflexionar con sabiduría estoica",
            "Tu crecimiento personal te espera",
            "Dedica unos minutos a la contemplación filosófica",
            "La sabiduría antigua tiene algo que enseñarte hoy",
            "Tu viaje hacia la virtud continúa"
        ]
        
        # Personalizar según filósofo favorito
        if perfil.filosofo_favorito == 'marco_aurelio':
            mensajes_base.extend([
                "Como emperador-filósofo, Marco Aurelio te invita a reflexionar",
                "Lidera tu día con sabiduría imperial"
            ])
        elif perfil.filosofo_favorito == 'seneca':
            mensajes_base.extend([
                "Séneca tiene una carta moral para ti hoy",
                "La sabiduría práctica de Séneca te aguarda"
            ])
        elif perfil.filosofo_favorito == 'epicteto':
            mensajes_base.extend([
                "Epicteto te recuerda: lo que depende de ti está en tus manos",
                "La libertad interior comienza con tu reflexión"
            ])
        
        import random
        mensaje_base = random.choice(mensajes_base)
        
        # Agregar información del tema del día
        if contenido.tema:
            mensaje_base += f" | Tema de hoy: {contenido.tema}"
        
        return mensaje_base
    
    def _enviar_notificacion_push(self, usuario_id: int, titulo: str, mensaje: str, 
                                 tipo: str, datos_extra: Dict = None) -> bool:
        """
        Envía notificación push real al dispositivo del usuario.
        """
        try:
            # Obtener tokens de dispositivo del usuario
            tokens = self._obtener_tokens_dispositivo(usuario_id)
            
            if not tokens:
                logger.warning(f"No hay tokens de dispositivo para usuario {usuario_id}")
                return False
            
            # Preparar payload de notificación
            payload = {
                'registration_ids': tokens,
                'notification': {
                    'title': titulo,
                    'body': mensaje,
                    'icon': '/static/estoico/img/logos/logo_estoico_principal.png',
                    'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                },
                'data': {
                    'tipo': tipo,
                    'usuario_id': str(usuario_id),
                    'timestamp': timezone.now().isoformat(),
                    **(datos_extra or {})
                }
            }
            
            # Enviar via FCM (Firebase Cloud Messaging)
            if self.api_key:
                headers = {
                    'Authorization': f'key={self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    'https://fcm.googleapis.com/fcm/send',
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"Notificación enviada exitosamente a usuario {usuario_id}")
                    
                    # Guardar registro de notificación
                    self._guardar_registro_notificacion(usuario_id, titulo, mensaje, tipo)
                    return True
                else:
                    logger.error(f"Error enviando notificación: {response.status_code} - {response.text}")
                    return False
            else:
                # Modo desarrollo - solo log
                logger.info(f"[DEV] Notificación para usuario {usuario_id}: {titulo} - {mensaje}")
                return True
                
        except Exception as e:
            logger.error(f"Error en _enviar_notificacion_push: {e}")
            return False
    
    def _obtener_tokens_dispositivo(self, usuario_id: int) -> List[str]:
        """
        Obtiene los tokens de dispositivo registrados para el usuario.
        """
        try:
            from .models import DispositivoUsuario
            
            dispositivos = DispositivoUsuario.objects.filter(
                usuario_id=usuario_id,
                activo=True
            ).values_list('token_fcm', flat=True)
            
            return list(dispositivos)
            
        except Exception as e:
            logger.error(f"Error obteniendo tokens de dispositivo: {e}")
            return []
    
    def _guardar_registro_notificacion(self, usuario_id: int, titulo: str, 
                                     mensaje: str, tipo: str) -> None:
        """
        Guarda un registro de la notificación enviada.
        """
        try:
            from .models import RegistroNotificacion
            
            RegistroNotificacion.objects.create(
                usuario_id=usuario_id,
                titulo=titulo,
                mensaje=mensaje,
                tipo=tipo,
                enviada=True,
                fecha_envio=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error guardando registro de notificación: {e}")
    
    def _programar_recordatorio_diario(self, usuario_id: int, hora: str) -> None:
        """
        Programa recordatorio diario usando Celery.
        """
        try:
            from celery import current_app
            from datetime import time
            
            # Convertir hora string a objeto time
            hora_obj = datetime.strptime(hora, '%H:%M').time()
            
            # Programar tarea recurrente
            current_app.send_task(
                'estoico.tasks.enviar_recordatorio_diario',
                args=[usuario_id],
                eta=timezone.now().replace(
                    hour=hora_obj.hour,
                    minute=hora_obj.minute,
                    second=0,
                    microsecond=0
                )
            )
            
        except Exception as e:
            logger.error(f"Error programando recordatorio diario: {e}")
    
    def _cancelar_notificaciones_programadas(self, usuario_id: int) -> None:
        """
        Cancela todas las notificaciones programadas para un usuario.
        """
        try:
            from .models import TareaProgramada
            
            # Marcar tareas como canceladas
            TareaProgramada.objects.filter(
                usuario_id=usuario_id,
                activa=True
            ).update(activa=False)
            
        except Exception as e:
            logger.error(f"Error cancelando notificaciones programadas: {e}")


class ComandoNotificaciones(BaseCommand):
    """
    Comando de Django para enviar notificaciones programadas.
    Uso: python manage.py enviar_notificaciones
    """
    
    help = 'Envía notificaciones programadas a los usuarios'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['recordatorios', 'logros', 'rachas', 'inspiracional'],
            help='Tipo de notificaciones a enviar'
        )
        
        parser.add_argument(
            '--usuario',
            type=int,
            help='ID de usuario específico'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular envío sin enviar notificaciones reales'
        )
    
    def handle(self, *args, **options):
        notificaciones = NotificacionesEstoicas()
        
        tipo = options.get('tipo')
        usuario_id = options.get('usuario')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Modo simulación - no se enviarán notificaciones reales')
            )
        
        if usuario_id:
            # Enviar a usuario específico
            self._procesar_usuario(notificaciones, usuario_id, tipo, dry_run)
        else:
            # Enviar a todos los usuarios activos
            self._procesar_todos_usuarios(notificaciones, tipo, dry_run)
    
    def _procesar_usuario(self, notificaciones, usuario_id, tipo, dry_run):
        """Procesa notificaciones para un usuario específico."""
        try:
            if not dry_run:
                if tipo == 'recordatorios' or not tipo:
                    resultado = notificaciones.enviar_recordatorio_diario(usuario_id)
                    self.stdout.write(f"Recordatorio usuario {usuario_id}: {'✓' if resultado else '✗'}")
                
                if tipo == 'inspiracional' or not tipo:
                    resultado = notificaciones.enviar_cita_inspiracional(usuario_id)
                    self.stdout.write(f"Cita inspiracional usuario {usuario_id}: {'✓' if resultado else '✗'}")
            else:
                self.stdout.write(f"[SIMULACIÓN] Procesaría usuario {usuario_id}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error procesando usuario {usuario_id}: {e}")
            )
    
    def _procesar_todos_usuarios(self, notificaciones, tipo, dry_run):
        """Procesa notificaciones para todos los usuarios activos."""
        try:
            from django.contrib.auth.models import User
            from .models import PerfilEstoico
            
            # Obtener usuarios con notificaciones activas
            usuarios_activos = User.objects.filter(
                perfilestoico__notificaciones_activas=True
            ).values_list('id', flat=True)
            
            total_usuarios = len(usuarios_activos)
            self.stdout.write(f"Procesando {total_usuarios} usuarios...")
            
            exitosos = 0
            errores = 0
            
            for usuario_id in usuarios_activos:
                try:
                    if not dry_run:
                        if tipo == 'recordatorios' or not tipo:
                            if notificaciones.enviar_recordatorio_diario(usuario_id):
                                exitosos += 1
                            else:
                                errores += 1
                    else:
                        exitosos += 1
                        
                except Exception as e:
                    errores += 1
                    logger.error(f"Error procesando usuario {usuario_id}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Procesamiento completado: {exitosos} exitosos, {errores} errores"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error en procesamiento masivo: {e}")
            )


# Tareas de Celery para notificaciones asíncronas
from celery import shared_task

@shared_task
def enviar_recordatorio_diario_task(usuario_id):
    """Tarea asíncrona para enviar recordatorio diario."""
    notificaciones = NotificacionesEstoicas()
    return notificaciones.enviar_recordatorio_diario(usuario_id)

@shared_task
def enviar_notificacion_logro_task(usuario_id, logro_id):
    """Tarea asíncrona para enviar notificación de logro."""
    notificaciones = NotificacionesEstoicas()
    return notificaciones.enviar_notificacion_logro(usuario_id, logro_id)

@shared_task
def verificar_logros_usuario_task(usuario_id):
    """Tarea asíncrona para verificar y otorgar logros."""
    try:
        from .utils import verificar_logros_usuario
        logros_nuevos = verificar_logros_usuario(usuario_id)
        
        # Enviar notificaciones para logros nuevos
        notificaciones = NotificacionesEstoicas()
        for logro_id in logros_nuevos:
            notificaciones.enviar_notificacion_logro(usuario_id, logro_id)
        
        return len(logros_nuevos)
        
    except Exception as e:
        logger.error(f"Error verificando logros para usuario {usuario_id}: {e}")
        return 0

@shared_task
def limpiar_notificaciones_antiguas():
    """Tarea para limpiar registros de notificaciones antiguos."""
    try:
        from .models import RegistroNotificacion
        from datetime import timedelta
        
        fecha_limite = timezone.now() - timedelta(days=90)
        
        eliminados = RegistroNotificacion.objects.filter(
            fecha_envio__lt=fecha_limite
        ).delete()[0]
        
        logger.info(f"Eliminados {eliminados} registros de notificaciones antiguos")
        return eliminados
        
    except Exception as e:
        logger.error(f"Error limpiando notificaciones antiguas: {e}")
        return 0

@shared_task
def enviar_resumen_semanal_task(usuario_id):
    """Tarea para enviar resumen semanal de progreso."""
    try:
        from .models import ReflexionDiaria, PerfilEstoico
        from datetime import timedelta
        
        # Obtener estadísticas de la semana
        hace_semana = timezone.now().date() - timedelta(days=7)
        
        reflexiones_semana = ReflexionDiaria.objects.filter(
            usuario_id=usuario_id,
            fecha__gte=hace_semana
        ).count()
        
        if reflexiones_semana == 0:
            return False
        
        promedio_calificacion = ReflexionDiaria.objects.filter(
            usuario_id=usuario_id,
            fecha__gte=hace_semana,
            calificacion_dia__isnull=False
        ).aggregate(
            promedio=models.Avg('calificacion_dia')
        )['promedio'] or 0
        
        # Enviar resumen
        notificaciones = NotificacionesEstoicas()
        mensaje = f"Esta semana reflexionaste {reflexiones_semana} días con un promedio de {promedio_calificacion:.1f} estrellas. ¡Sigue así!"
        
        return notificaciones._enviar_notificacion_push(
            usuario_id=usuario_id,
            titulo="📊 Resumen Semanal",
            mensaje=mensaje,
            tipo="resumen_semanal",
            datos_extra={
                'dias_activos': reflexiones_semana,
                'promedio_calificacion': round(promedio_calificacion, 1)
            }
        )
        
    except Exception as e:
        logger.error(f"Error enviando resumen semanal a usuario {usuario_id}: {e}")
        return False

