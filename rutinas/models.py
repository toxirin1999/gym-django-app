from django.apps import apps
from django.db import models


class Asignacion(models.Model):
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
    TIPO_PROGRESION_CHOICES = [
        ('peso_reps', 'Peso + repeticiones'),
        ('progresion_reps', 'Solo repeticiones'),
        ('progresion_tiempo', 'Tiempo'),
        ('progresion_distancia', 'Distancia / metros'),
        ('peso_corporal_lastre', 'Peso corporal + lastre'),
        ('progresion_variante', 'Variante de dificultad'),
    ]

    nombre = models.CharField(max_length=100, unique=True)
    grupo_muscular = models.CharField(max_length=100)
    equipo = models.CharField(max_length=100, blank=True, null=True)

    # Etiquetas de riesgo biomecánico
    risk_tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tokens de riesgo, ej: 'impacto_vertical', 'triple_extension_explosiva'"
    )

    # Tipo de progresión — define cómo se mide y progresa este ejercicio
    tipo_progresion = models.CharField(
        max_length=25,
        choices=TIPO_PROGRESION_CHOICES,
        default='peso_reps',
        help_text="Define cómo se mide la progresión de este ejercicio"
    )

    def __str__(self):
        return self.nombre

    @property
    def usa_peso(self):
        """True si el ejercicio se registra con peso externo."""
        return self.tipo_progresion in ('peso_reps', 'peso_corporal_lastre')

    @property
    def usa_tiempo(self):
        return self.tipo_progresion == 'progresion_tiempo'

    @property
    def usa_distancia(self):
        return self.tipo_progresion == 'progresion_distancia'


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
