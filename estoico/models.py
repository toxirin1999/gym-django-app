from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import json


class ContenidoDiario(models.Model):
    """
    Modelo para almacenar el contenido estoico de cada día del año
    """
    dia = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(366)],
        unique=True,
        help_text="Día del año (1-366)"
    )
    mes = models.CharField(max_length=20)
    tema = models.CharField(max_length=100)
    cita = models.TextField()
    autor = models.CharField(max_length=50)
    reflexion = models.TextField()
    pregunta = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contenido Diario"
        verbose_name_plural = "Contenidos Diarios"
        ordering = ['dia']

    def __str__(self):
        return f"Día {self.dia} - {self.tema}"


class PerfilEstoico(models.Model):
    """
    Perfil estoico del usuario con configuraciones y estadísticas
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_estoico')
    fecha_inicio = models.DateField(default=timezone.now)
    dias_consecutivos = models.PositiveIntegerField(default=0)
    total_reflexiones = models.PositiveIntegerField(default=0)
    notificaciones_activas = models.BooleanField(default=True)
    hora_notificacion = models.TimeField(default='08:00')
    filosofo_favorito = models.CharField(
        max_length=50,
        choices=[
            ('marco_aurelio', 'Marco Aurelio'),
            ('seneca', 'Séneca'),
            ('epicteto', 'Epicteto'),
            ('musonio_rufo', 'Musonio Rufo'),
            ('zenon', 'Zenón de Citio'),
        ],
        default='marco_aurelio'
    )
    tema_favorito = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Perfil Estoico"
        verbose_name_plural = "Perfiles Estoicos"

    def __str__(self):
        return f"Perfil estoico de {self.usuario.username}"


class ReflexionDiaria(models.Model):
    """
    Reflexiones diarias del usuario basadas en el contenido estoico
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reflexiones_estoicas')
    contenido_dia = models.ForeignKey(ContenidoDiario, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    reflexion_personal = models.TextField(
        help_text="Respuesta del usuario a la pregunta del día"
    )
    calificacion_dia = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Calificación del día (1-5 estrellas)"
    )
    tiempo_reflexion = models.PositiveIntegerField(
        default=0,
        help_text="Tiempo en segundos dedicado a la reflexión"
    )
    marcado_favorito = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reflexión Diaria"
        verbose_name_plural = "Reflexiones Diarias"
        unique_together = ['usuario', 'fecha']
        ordering = ['-fecha']

    def __str__(self):
        return f"Reflexión de {self.usuario.username} - {self.fecha}"


class LogroEstoico(models.Model):
    """
    Sistema de logros para motivar la práctica estoica
    """
    TIPOS_LOGRO = [
        ('dias_consecutivos', 'Días Consecutivos'),
        ('total_reflexiones', 'Total de Reflexiones'),
        ('tema_completado', 'Tema Completado'),
        ('filosofo_explorado', 'Filósofo Explorado'),
        ('calidad_reflexion', 'Calidad de Reflexión'),
    ]

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPOS_LOGRO)
    criterio_valor = models.PositiveIntegerField(
        help_text="Valor necesario para desbloquear el logro"
    )
    icono = models.CharField(max_length=50, default='🏆')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Logro Estoico"
        verbose_name_plural = "Logros Estoicos"

    def __str__(self):
        return self.nombre


class LogroUsuario(models.Model):
    """
    Logros desbloqueados por cada usuario
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logros_estoicos')
    logro = models.ForeignKey(LogroEstoico, on_delete=models.CASCADE)
    fecha_obtenido = models.DateTimeField(auto_now_add=True)
    visto = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Logro de Usuario"
        verbose_name_plural = "Logros de Usuarios"
        unique_together = ['usuario', 'logro']

    def __str__(self):
        return f"{self.usuario.username} - {self.logro.nombre}"


class EstadisticaUsuario(models.Model):
    """
    Estadísticas detalladas del progreso del usuario
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estadisticas_estoicas')
    dias_activos = models.PositiveIntegerField(default=0)
    racha_actual = models.PositiveIntegerField(default=0)
    racha_maxima = models.PositiveIntegerField(default=0)
    promedio_calificacion = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00
    )
    tiempo_total_reflexion = models.PositiveIntegerField(default=0)  # en segundos
    temas_completados = models.JSONField(default=list)
    filosofos_explorados = models.JSONField(default=list)
    fecha_ultima_actividad = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Estadística de Usuario"
        verbose_name_plural = "Estadísticas de Usuarios"

    def __str__(self):
        return f"Estadísticas de {self.usuario.username}"

    def actualizar_racha(self):
        """Actualiza la racha actual del usuario"""
        hoy = timezone.now().date()
        if self.fecha_ultima_actividad:
            if self.fecha_ultima_actividad == hoy - timezone.timedelta(days=1):
                self.racha_actual += 1
            elif self.fecha_ultima_actividad != hoy:
                self.racha_actual = 1
        else:
            self.racha_actual = 1

        if self.racha_actual > self.racha_maxima:
            self.racha_maxima = self.racha_actual

        self.fecha_ultima_actividad = hoy
        self.save()


class ConfiguracionNotificacion(models.Model):
    """
    Configuración personalizada de notificaciones
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='config_notificaciones_estoicas')
    notificacion_matutina = models.BooleanField(default=True)
    hora_matutina = models.TimeField(default='08:00')
    notificacion_vespertina = models.BooleanField(default=True)
    hora_vespertina = models.TimeField(default='20:00')
    recordatorio_reflexion = models.BooleanField(default=True)
    frecuencia_recordatorio = models.PositiveSmallIntegerField(
        default=2,
        help_text="Horas entre recordatorios"
    )
    dias_semana = models.JSONField(
        default=list,
        help_text="Días de la semana activos (0=Lunes, 6=Domingo)"
    )

    class Meta:
        verbose_name = "Configuración de Notificación"
        verbose_name_plural = "Configuraciones de Notificaciones"

    def __str__(self):
        return f"Notificaciones de {self.usuario.username}"
