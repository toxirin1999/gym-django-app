from django.db import models
from django.contrib.auth.models import User


class RecuerdoEmocional(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()
    contexto = models.TextField(blank=True, null=True)  # ej: “desmotivación”, “post-entreno”, etc.

    def __str__(self):
        return f"{self.user.username} - {self.fecha.date()} - {self.contexto or 'sin contexto'}"


class EstadoEmocional(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    emocion = models.CharField(max_length=50)
    nota = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.emocion} ({self.fecha})"


class Entrenamiento(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    tipo = models.CharField(max_length=100)
    duracion = models.IntegerField()
    intensidad = models.CharField(max_length=50)
    completado = models.BooleanField(default=True)

    # 🧠 Nuevo campo
    recomendacion_joi = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.tipo} ({self.fecha})"


class Logro(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    desbloqueado = models.BooleanField(default=False)
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.user.username} ({'✔️' if self.desbloqueado else '❌'})"


class EventoLogro(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre_logro = models.CharField(max_length=100)
    icono = models.CharField(max_length=10, default="🏅")
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.icono} {self.nombre_logro} ({self.user.username} - {self.fecha})"


class MotivacionUsuario(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    motivo = models.TextField()

    def __str__(self):
        return f"{self.user.username} — {self.fecha}"


class MensajeJOI(models.Model):
    TRIGGER_CHOICES = [
        ('entreno_completado',          'Entreno completado'),
        ('apertura_manana',             'Apertura matutina'),
        ('ausencia_detectada',          'Ausencia sin lesión'),
        ('carga_anomala',               'Carga anómala ACWR'),
        ('pr_roto',                     'Récord personal'),
        ('lesion_activa',               'Lesión activa'),
        ('fin_bloque',                  'Fin de bloque'),
        ('hyrox_sesion_completada',     'Hyrox — sesión completada'),
        ('hyrox_readiness_bajo',        'Hyrox — readiness bajo'),
        ('hyrox_readiness_alto',        'Hyrox — readiness alto'),
        ('hyrox_cuenta_regresiva',      'Hyrox — cuenta regresiva'),
        ('hyrox_simulacion_completada', 'Hyrox — simulación completada'),
        ('hyrox_ausencia',              'Hyrox — ausencia detectada'),
        ('decision_plan',               'Decisión del plan — intervención'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mensajes_joi')
    trigger     = models.CharField(max_length=40, choices=TRIGGER_CHOICES)
    mensaje     = models.TextField()
    contexto    = models.JSONField(default=dict)   # datos que usó JOI para generar el mensaje
    leido       = models.BooleanField(default=False)
    creado_en   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"JOI → {self.user.username} [{self.trigger}] {self.creado_en.date()}"
