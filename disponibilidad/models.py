from django.db import models
from django.utils import timezone

from clientes.models import Cliente


class RegistroDisponibilidad(models.Model):
    """Ver PHASE_NUTRICION_0_CONTRATO.md — modelo mínimo, sin relación con nutricion_app_django."""

    NIVEL_COMPLETA = 'A'
    NIVEL_SUFICIENTE = 'B'
    NIVEL_RECURSO = 'C'
    NIVEL_CHOICES = [
        (NIVEL_COMPLETA, 'Completa'),
        (NIVEL_SUFICIENTE, 'Suficiente'),
        (NIVEL_RECURSO, 'Recurso'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='registros_disponibilidad')
    timestamp = models.DateTimeField(default=timezone.now)
    nivel = models.CharField(max_length=1, choices=NIVEL_CHOICES)
    origen = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.cliente} · {self.get_nivel_display()} · {self.timestamp:%Y-%m-%d %H:%M}"
