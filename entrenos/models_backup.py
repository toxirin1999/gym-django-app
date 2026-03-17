from django.db import models
from clientes.models import Cliente
from rutinas.models import Ejercicio, Rutina
from django.db import models
from django.contrib.auth.models import User
from clientes.models import Cliente
from rutinas.models import Ejercicio, Rutina


class EntrenoRealizado(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    procesado_gamificacion = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.rutina.nombre} ({self.fecha})"


class DetalleEjercicioRealizado(models.Model):
    entreno = models.ForeignKey(EntrenoRealizado, on_delete=models.CASCADE, related_name='detalles')
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.CASCADE)
    series = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2)
    completado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.ejercicio.nombre}: {self.series}x{self.repeticiones} - {self.peso_kg} kg"


class Rutina(models.Model):
    nombre = models.CharField(max_length=100)


class Programa(models.Model):
    nombre = models.CharField(max_length=100)
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE)


class SerieRealizada(models.Model):
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='series')
    ejercicio = models.ForeignKey('rutinas.Ejercicio', on_delete=models.CASCADE)
    serie_numero = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    completado = models.BooleanField(default=False)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True,
                                  blank=True)  # <-- Añade null=True, blank=True


class PlanPersonalizado(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    ejercicio = models.ForeignKey('rutinas.Ejercicio', on_delete=models.CASCADE)
    rutina = models.ForeignKey('rutinas.Rutina', on_delete=models.CASCADE, null=True, blank=True)
    repeticiones_objetivo = models.PositiveIntegerField(default=10)
    peso_objetivo = models.FloatField(default=0)

    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cliente', 'ejercicio', 'rutina')  # evita duplicados

    def __str__(self):
        return f"{self.cliente} - {self.ejercicio} → {self.repeticiones_objetivo} reps @ {self.peso_objetivo} kg"


class LogroDesbloqueado(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"


class EstadoEmocional(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=100)
    emoji = models.CharField(max_length=5)
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.emoji} {self.descripcion} - {self.cliente.nombre}"
