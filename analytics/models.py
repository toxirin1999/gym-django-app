# 📊 MODELOS PARA APP ANALYTICS
# Archivo: analytics/models.py

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import json
from datetime import datetime, timedelta
from django.db.models import Sum, Avg, Max, Count


class MetricaRendimiento(models.Model):
    """
    Modelo para almacenar métricas calculadas de rendimiento por día
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    fecha = models.DateField()

    # Métricas básicas (calculadas desde EntrenoRealizado)
    volumen_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    intensidad_promedio = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    carga_entrenamiento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duracion_total = models.IntegerField(default=0)  # minutos
    calorias_totales = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Métricas avanzadas
    indice_fatiga = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    eficiencia_entrenamiento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    densidad_entrenamiento = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Métricas de fuerza
    fuerza_relativa = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    volumen_por_grupo = models.JSONField(default=dict)  # {"pecho": 5000, "piernas": 8000}

    # Métricas cardíacas
    fc_promedio = models.IntegerField(null=True, blank=True)
    fc_maxima = models.IntegerField(null=True, blank=True)

    # Contadores
    entrenamientos_dia = models.IntegerField(default=0)
    ejercicios_totales = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cliente', 'fecha']
        ordering = ['-fecha']
        verbose_name = "Métrica de Rendimiento"
        verbose_name_plural = "Métricas de Rendimiento"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha}"


class AnalisisEjercicio(models.Model):
    """
    Análisis específico por ejercicio y fecha
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    nombre_ejercicio = models.CharField(max_length=200)
    fecha = models.DateField()

    # Métricas del ejercicio (calculadas desde EjercicioLiftinDetallado)
    peso_maximo = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    peso_promedio = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    volumen_ejercicio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    repeticiones_totales = models.IntegerField(default=0)
    series_totales = models.IntegerField(default=0)

    # Análisis de progresión
    progresion_peso = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    progresion_volumen = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %

    # 1RM estimado
    one_rm_estimado = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Estado del ejercicio
    completado_exitosamente = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cliente', 'nombre_ejercicio', 'fecha']
        ordering = ['-fecha', 'nombre_ejercicio']
        verbose_name = "Análisis de Ejercicio"
        verbose_name_plural = "Análisis de Ejercicios"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre_ejercicio} - {self.fecha}"


class TendenciaProgresion(models.Model):
    """
    Tendencias de progresión calculadas por ejercicio
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    nombre_ejercicio = models.CharField(max_length=200)

    # Período de análisis
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    periodo_dias = models.IntegerField(default=90)  # o null=True si prefieres

    tendencia_general = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    peso_maximo = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    sesiones_totales = models.IntegerField(default=0)

    # Tendencia calculada
    tipo_tendencia = models.CharField(max_length=20, choices=[
        ('creciente', 'Creciente'),
        ('decreciente', 'Decreciente'),
        ('estable', 'Estable'),
        ('irregular', 'Irregular')
    ])

    # Métricas de tendencia
    velocidad_progresion = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %/semana
    consistencia = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100%
    confianza = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100%

    # Valores de referencia
    valor_inicial = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    valor_final = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    valor_maximo = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Detección de patrones
    estancamientos_detectados = models.IntegerField(default=0)
    picos_detectados = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cliente', 'nombre_ejercicio', 'fecha_inicio', 'fecha_fin']
        ordering = ['-fecha_fin', 'nombre_ejercicio']
        verbose_name = "Tendencia de Progresión"
        verbose_name_plural = "Tendencias de Progresión"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre_ejercicio} - {self.tipo_tendencia}"


class PrediccionRendimiento(models.Model):
    """
    Predicciones de rendimiento futuro
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    nombre_ejercicio = models.CharField(max_length=200, null=True, blank=True)

    # Tipo de predicción
    tipo_prediccion = models.CharField(max_length=50, choices=[
        ('1rm', '1RM Estimado'),
        ('volumen', 'Volumen Semanal'),
        ('progresion', 'Progresión General'),
        ('peso_objetivo', 'Peso Objetivo'),
        ('tiempo_objetivo', 'Tiempo para Objetivo')
    ])

    # Predicción
    valor_actual = models.DecimalField(max_digits=10, decimal_places=2)
    valor_predicho = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_prediccion = models.DateField()  # Para cuándo es la predicción
    confianza = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100%

    # Metadatos del modelo
    algoritmo_usado = models.CharField(max_length=100)
    parametros = models.JSONField(default=dict)
    datos_entrenamiento = models.IntegerField(default=0)  # Cantidad de datos usados

    # Estado de la predicción
    activa = models.BooleanField(default=True)
    verificada = models.BooleanField(default=False)
    precision_real = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_prediccion', '-created_at']
        verbose_name = "Predicción de Rendimiento"
        verbose_name_plural = "Predicciones de Rendimiento"

    def __str__(self):
        ejercicio = self.nombre_ejercicio or "General"
        return f"{self.cliente.nombre} - {ejercicio} - {self.tipo_prediccion}"


class RecomendacionEntrenamiento(models.Model):
    """
    Recomendaciones generadas por el sistema de análisis
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)

    # Tipo de recomendación
    tipo = models.CharField(max_length=50, choices=[
        ('ejercicio', 'Nuevo Ejercicio'),
        ('intensidad', 'Ajuste de Intensidad'),
        ('volumen', 'Ajuste de Volumen'),
        ('descanso', 'Tiempo de Descanso'),
        ('frecuencia', 'Frecuencia de Entrenamiento'),
        ('tecnica', 'Mejora de Técnica'),
        ('variacion', 'Variación de Rutina'),
        ('recuperacion', 'Recuperación'),
        ('nutricion', 'Apoyo Nutricional')
    ])

    # Contenido de la recomendación
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    prioridad = models.IntegerField(default=2, choices=[
        (1, 'Alta'),
        (2, 'Media'),
        (3, 'Baja')
    ])

    # Datos de soporte
    metricas_base = models.JSONField(default=dict)
    impacto_esperado = models.CharField(max_length=100)
    ejercicio_relacionado = models.CharField(max_length=200, null=True, blank=True)

    # Estado de la recomendación
    aplicada = models.BooleanField(default=False)
    fecha_aplicacion = models.DateTimeField(null=True, blank=True)
    efectividad = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback_usuario = models.TextField(null=True, blank=True)

    # Vigencia
    expires_at = models.DateTimeField()  # Fecha de expiración

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['prioridad', '-created_at']
        verbose_name = "Recomendación de Entrenamiento"
        verbose_name_plural = "Recomendaciones de Entrenamiento"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.titulo}"

    @property
    def esta_vigente(self):
        return datetime.now() <= self.expires_at

    def marcar_como_aplicada(self):
        self.aplicada = True
        self.fecha_aplicacion = datetime.now()
        self.save()


class ComparativaRendimiento(models.Model):
    """
    Comparativas de rendimiento con diferentes referencias
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)

    # Tipo de comparativa
    tipo_comparativa = models.CharField(max_length=50, choices=[
        ('temporal', 'Temporal (períodos)'),
        ('poblacion', 'Con Población'),
        ('objetivo', 'Con Objetivo'),
        ('ejercicios', 'Entre Ejercicios')
    ])

    # Período de análisis
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    # Métricas comparadas
    metrica_principal = models.CharField(max_length=50)
    valor_cliente = models.DecimalField(max_digits=10, decimal_places=2)
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)

    # Resultados de la comparativa
    percentil = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    clasificacion = models.CharField(max_length=20, choices=[
        ('excepcional', 'Excepcional'),
        ('muy_bueno', 'Muy Bueno'),
        ('bueno', 'Bueno'),
        ('promedio', 'Promedio'),
        ('por_debajo', 'Por Debajo del Promedio'),
        ('necesita_mejora', 'Necesita Mejora')
    ])

    # Análisis detallado
    diferencia_absoluta = models.DecimalField(max_digits=10, decimal_places=2)
    diferencia_porcentual = models.DecimalField(max_digits=5, decimal_places=2)
    significancia = models.CharField(max_length=20, choices=[
        ('muy_significativa', 'Muy Significativa'),
        ('significativa', 'Significativa'),
        ('moderada', 'Moderada'),
        ('no_significativa', 'No Significativa')
    ])

    # Metadatos
    poblacion_referencia = models.CharField(max_length=100, null=True, blank=True)
    tamaño_muestra = models.IntegerField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Comparativa de Rendimiento"
        verbose_name_plural = "Comparativas de Rendimiento"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.tipo_comparativa} - {self.metrica_principal}"


class CacheAnalisis(models.Model):
    """
    Cache para análisis complejos que requieren mucho procesamiento
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)

    # Identificación del cache
    tipo_analisis = models.CharField(max_length=100)
    parametros_hash = models.CharField(max_length=64)  # Hash MD5 de los parámetros

    # Datos cacheados
    resultado = models.JSONField()

    # Metadatos
    tiempo_calculo = models.DecimalField(max_digits=8, decimal_places=3)  # segundos
    datos_utilizados = models.IntegerField()  # Cantidad de registros procesados

    # Vigencia
    expires_at = models.DateTimeField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cliente', 'tipo_analisis', 'parametros_hash']
        ordering = ['-created_at']
        verbose_name = "Cache de Análisis"
        verbose_name_plural = "Caches de Análisis"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.tipo_analisis}"

    @property
    def esta_vigente(self):
        return datetime.now() <= self.expires_at


# analytics/models.py
from django.db import models
from clientes.models import Cliente  # Asegúrate de importar Cliente
from django.utils import timezone


# ... tus otros modelos (MetricaRendimiento, etc.)

class MetaRendimiento(models.Model):
    """
    Representa una meta que un cliente se establece para un ejercicio específico.
    """
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='metas')
    nombre_ejercicio = models.CharField(max_length=100)
    fecha_objetivo = models.DateField()
    valor_objetivo = models.DecimalField(max_digits=7, decimal_places=2)  # Ej: 100.00 kg
    creada_en = models.DateTimeField(auto_now_add=True)
    alcanzada = models.BooleanField(default=False)

    def __str__(self):
        return f"Meta de {self.cliente.nombre}: {self.nombre_ejercicio} - {self.valor_objetivo}kg para {self.fecha_objetivo}"

    class Meta:
        ordering = ['-fecha_objetivo']


class AnotacionEntrenamiento(models.Model):
    """
    Representa un evento o nota importante en una fecha específica para un cliente.
    """
    TIPO_ANOTACION = [
        ('PR', 'Récord Personal'),
        ('INICIO', 'Inicio de Programa'),
        ('FIN', 'Fin de Programa'),
        ('LESION', 'Lesión o Molestia'),
        ('DESCANSO', 'Semana de Descarga'),
        ('EVENTO', 'Evento o Competición'),
        ('OTRO', 'Otro'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='anotaciones')
    fecha = models.DateField()
    tipo = models.CharField(max_length=10, choices=TIPO_ANOTACION, default='OTRO')
    descripcion = models.CharField(max_length=255)
    ejercicio_asociado = models.CharField(max_length=100, blank=True, null=True,
                                          help_text="Opcional: asociar a un ejercicio específico")
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anotación de {self.cliente.nombre} en {self.fecha}: {self.get_tipo_display()}"

    class Meta:
        ordering = ['-fecha']
