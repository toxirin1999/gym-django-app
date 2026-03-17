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
