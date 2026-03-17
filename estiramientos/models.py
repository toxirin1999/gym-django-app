from django.db import models


class EstiramientoEjercicio(models.Model):
    FASE_CHOICES = [
        ("SUPERIOR", "Tren superior"),
        ("INFERIOR", "Tren inferior"),
        ("COMPLETO", "Cuerpo completo"),
    ]

    nombre = models.CharField(max_length=120)
    fase_recomendada = models.CharField(max_length=12, choices=FASE_CHOICES, blank=True, null=True)
    musculo_objetivo = models.CharField(max_length=120, blank=True, default="")
    descripcion_corta = models.CharField(max_length=220, blank=True, default="")
    imagen = models.ImageField(upload_to="estiramientos/", blank=True, null=True)

    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class EstiramientoPlan(models.Model):
    FASE_CHOICES = EstiramientoEjercicio.FASE_CHOICES

    nombre = models.CharField(max_length=80)  # "Superior", "Inferior", "Completo"
    fase = models.CharField(max_length=12, choices=FASE_CHOICES, unique=True)
    transicion_segundos = models.PositiveIntegerField(default=5)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.fase})"


class EstiramientoPaso(models.Model):
    plan = models.ForeignKey(EstiramientoPlan, on_delete=models.CASCADE, related_name="pasos")
    ejercicio = models.ForeignKey(EstiramientoEjercicio, on_delete=models.PROTECT)
    orden = models.PositiveIntegerField()
    duracion_segundos = models.PositiveIntegerField(default=30)

    class Meta:
        unique_together = ("plan", "orden")
        ordering = ["orden"]

    def __str__(self):
        return f"{self.plan.nombre} #{self.orden} - {self.ejercicio.nombre}"
