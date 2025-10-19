# ========================================
# MODELO PROSOCHE DIARIO COMPLETO - Basado en Notion
# ========================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ProsocheDiario(models.Model):
    """Entrada completa del diario diario con todos los campos de Notion"""
    prosoche_mes = models.ForeignKey('ProsocheMes', on_delete=models.CASCADE, related_name='entradas_diario')
    fecha = models.DateField()
    
    # Campos básicos
    etiquetas = models.CharField(max_length=200, blank=True, help_text="Etiquetas separadas por comas")
    estado_animo = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], 
        default=3, 
        help_text="Estado de ánimo (1-5)"
    )
    
    # Journaling Mañana
    persona_quiero_ser = models.TextField(
        blank=True, 
        help_text="¿Qué clase de persona quiero ser hoy?"
    )
    
    # Tareas del día (JSON field para flexibilidad)
    tareas_dia = models.JSONField(
        default=list, 
        blank=True,
        help_text="Lista de tareas del día con estado de completado"
    )
    
    # Gratitud (5 puntos)
    gratitud_1 = models.CharField(max_length=200, blank=True)
    gratitud_2 = models.CharField(max_length=200, blank=True)
    gratitud_3 = models.CharField(max_length=200, blank=True)
    gratitud_4 = models.CharField(max_length=200, blank=True)
    gratitud_5 = models.CharField(max_length=200, blank=True)
    
    # Journaling Noche
    podcast_libro_dia = models.TextField(
        blank=True,
        help_text="Podcast o libro del día"
    )
    
    felicidad = models.TextField(
        blank=True,
        help_text="¿Qué me ha hecho feliz hoy?"
    )
    
    que_ha_ido_bien = models.TextField(
        blank=True,
        help_text="¿Qué ha ido bien?"
    )
    
    que_puedo_mejorar = models.TextField(
        blank=True,
        help_text="¿Qué puedo mejorar?"
    )
    
    reflexiones_dia = models.TextField(
        blank=True,
        help_text="Reflexiones del día"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('prosoche_mes', 'fecha')
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.fecha} - {self.prosoche_mes.usuario.username}"
    
    def get_tareas_completadas(self):
        """Obtener número de tareas completadas"""
        if not self.tareas_dia:
            return 0
        return sum(1 for tarea in self.tareas_dia if tarea.get('completada', False))
    
    def get_total_tareas(self):
        """Obtener número total de tareas"""
        return len(self.tareas_dia) if self.tareas_dia else 0
    
    def get_gratitud_items(self):
        """Obtener lista de items de gratitud no vacíos"""
        items = []
        for i in range(1, 6):
            item = getattr(self, f'gratitud_{i}', '')
            if item.strip():
                items.append(item)
        return items
    
    def get_porcentaje_completado(self):
        """Calcular porcentaje de campos completados"""
        campos_importantes = [
            self.persona_quiero_ser,
            self.felicidad,
            self.que_ha_ido_bien,
            self.que_puedo_mejorar,
            self.reflexiones_dia
        ]
        
        completados = sum(1 for campo in campos_importantes if campo.strip())
        total = len(campos_importantes)
        
        # Agregar gratitud (al menos 3 items)
        gratitud_items = len(self.get_gratitud_items())
        if gratitud_items >= 3:
            completados += 1
        total += 1
        
        # Agregar tareas (al menos 1 tarea)
        if self.get_total_tareas() > 0:
            completados += 1
        total += 1
        
        return round((completados / total) * 100) if total > 0 else 0
