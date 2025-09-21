from django.apps import apps
from django.db import models


# Modelo para asignar un programa a un cliente
class Asignacion(models.Model):
    # Usa 'app_name.ModelName' para referenciar modelos de otras apps
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    programa = models.ForeignKey('Programa', on_delete=models.CASCADE)

    def __str__(self):
        return f"Asignación de '{self.programa.nombre}' a {self.cliente}"


class Programa(models.Model):
    nombre = models.CharField(max_length=100)
    icono = models.CharField(max_length=100, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    fecha_creacion = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class EjercicioEnRutina(models.Model):
    rutina = models.ForeignKey('Rutina', on_delete=models.CASCADE, related_name='ejercicios_asignados')
    ejercicio = models.ForeignKey('EjercicioBase', on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(default=0)

    series_default = models.PositiveIntegerField(default=3)
    repeticiones_default = models.PositiveIntegerField(default=10)
    peso_default = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = ('rutina', 'ejercicio')
        ordering = ['orden']

    def __str__(self):
        return f"{self.rutina.nombre} - {self.ejercicio.nombre}"


class EjercicioBase(models.Model):
    # Este es el modelo CORRECTO. No se toca.
    nombre = models.CharField(max_length=100, unique=True)  # <-- Es buena práctica añadir unique=True
    grupo_muscular = models.CharField(max_length=100)
    equipo = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nombre


class Rutina(models.Model):
    programa = models.ForeignKey('Programa', on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=100)

    ejercicios = models.ManyToManyField(EjercicioBase, through='RutinaEjercicio')

    orden = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nombre


class RutinaEjercicio(models.Model):
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE)

    ejercicio = models.ForeignKey(EjercicioBase, on_delete=models.CASCADE)

    series = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.ejercicio.nombre} en rutina '{self.rutina.nombre}'"
