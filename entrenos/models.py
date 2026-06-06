# Archivo: entrenos/models.py - VERSIÓN COMPLETA CON TODOS LOS CAMPOS DE LIFTIN

from django.db import models
from clientes.models import Cliente
from rutinas.models import Rutina
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.utils import timezone
from rutinas.models import EjercicioBase


class GrupoMuscular(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre


class EjercicioRealizado(models.Model):
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='ejercicios_realizados')

    nombre_ejercicio = models.CharField(max_length=100)
    grupo_muscular = models.CharField(max_length=50, blank=True, null=True)

    peso_kg = models.FloatField(default=0)
    series = models.PositiveIntegerField(default=1)
    repeticiones = models.PositiveIntegerField(default=1)
    tempo = models.CharField(max_length=10, blank=True, null=True)  # ej: "3-1-1"
    rpe = models.PositiveIntegerField(blank=True, null=True)  # 1-10
    rir = models.PositiveIntegerField(blank=True, null=True)  # 0-5
    fallo_muscular = models.BooleanField(default=False)

    orden = models.PositiveIntegerField(default=0)
    completado = models.BooleanField(default=True)
    nuevo_record = models.BooleanField(default=False)
    
    # Phase 15: Tracking & Progression Resilience
    is_recovery_load = models.BooleanField(
        default=False,
        help_text="True si este ejercicio se realizó bajo un estado biológico restringido (volume_modifier < 1.0)"
    )
    es_tope_maquina = models.BooleanField(
        default=False,
        help_text="True si el peso recomendado supera el máximo físico de la máquina. Congela progresión de peso y avanza por reps/tempo."
    )

    # Molestia reportada durante el entreno
    molestia_reportada = models.BooleanField(default=False)
    molestia_zona = models.CharField(max_length=100, blank=True)
    molestia_severidad = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="1=Leve, 2=Moderada, 3=Severa/Aguda"
    )
    molestia_descripcion = models.TextField(blank=True)

    es_bloque_principal = models.BooleanField(
        null=True, blank=True,
        help_text="True=bloque principal, False=opcional, None=sesión normal (no esencial).",
    )

    fuente_datos = models.CharField(max_length=20, default='manual')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def volumen(self):
        return self.peso_kg * self.series * self.repeticiones


class EjercicioLiftinDetallado(models.Model):
    """
    Modelo para almacenar los ejercicios específicos de Liftin con todos sus detalles
    """
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE,
                                related_name='ejercicios_liftin_detallados')

    # Información del ejercicio
    nombre_ejercicio = models.CharField(
        max_length=200,
        help_text="Nombre del ejercicio como aparece en Liftin"
    )

    orden_ejercicio = models.PositiveIntegerField(
        default=1,
        help_text="Orden del ejercicio en la rutina"
    )

    # Peso utilizado
    peso_kg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peso utilizado en kg"
    )

    peso_formateado = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Peso como aparece en Liftin (ej: 268.5 kg, PC, 90-100 kg)"
    )

    # Series y repeticiones
    series_realizadas = models.PositiveIntegerField(
        default=1,
        help_text="Número de series realizadas"
    )

    repeticiones_formateado = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Repeticiones como aparecen en Liftin (ej: 3x5-10, 3x10-12)"
    )

    repeticiones_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Repeticiones mínimas por serie"
    )

    repeticiones_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Repeticiones máximas por serie"
    )

    # Estado del ejercicio
    completado = models.BooleanField(
        default=True,
        help_text="Si el ejercicio fue completado exitosamente"
    )

    estado_liftin = models.CharField(
        max_length=20,
        choices=[
            ('completado', '✓ Completado'),
            ('fallado', '✗ Fallado'),
            ('nuevo', 'N Nuevo'),
            ('parcial', '~ Parcial'),
        ],
        default='completado',
        help_text="Estado del ejercicio según Liftin"
    )

    # Notas específicas del ejercicio
    notas_ejercicio = models.TextField(
        null=True,
        blank=True,
        help_text="Notas específicas de este ejercicio"
    )

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        peso_str = self.peso_formateado or f"{self.peso_kg} kg" if self.peso_kg else "Sin peso"
        reps_str = self.repeticiones_formateado or f"{self.repeticiones_min}-{self.repeticiones_max}" if self.repeticiones_min else "Sin reps"
        return f"{self.nombre_ejercicio}: {peso_str}, {reps_str}"

    @property
    def volumen_ejercicio(self):
        """Calcula el volumen aproximado de este ejercicio"""
        if self.peso_kg and self.series_realizadas and self.repeticiones_min:
            # Usar repeticiones promedio si hay rango
            reps_promedio = self.repeticiones_min
            if self.repeticiones_max:
                reps_promedio = (self.repeticiones_min + self.repeticiones_max) / 2

            return self.peso_kg * self.series_realizadas * reps_promedio
        return 0

    class Meta:
        ordering = ['entreno', 'orden_ejercicio']
        verbose_name = "Ejercicio Detallado de Liftin"
        verbose_name_plural = "Ejercicios Detallados de Liftin"


class EjercicioBaseObsoleto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    grupo_muscular = models.CharField(
        max_length=50,
        choices=[
            ('Pecho', 'Pecho'),
            ('Espalda', 'Espalda'),
            ('Piernas', 'Piernas'),
            ('Hombros', 'Hombros'),
            ('Bíceps', 'Bíceps'),
            ('Tríceps', 'Tríceps'),
            ('Glúteos', 'Glúteos'),
            ('Core', 'Core'),
            ('Cardio', 'Cardio'),
            ('Otros', 'Otros'),
        ]
    )
    equipo = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.grupo_muscular})"


# Mantener modelos existentes para compatibilidad
class DetalleEjercicioRealizado(models.Model):
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='detalles_ejercicio')

    ejercicio = models.ForeignKey(EjercicioBase, on_delete=models.CASCADE)
    series = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2)
    completado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.ejercicio.nombre}: {self.series}x{self.repeticiones} - {self.peso_kg} kg"


class SerieRealizada(models.Model):
    TECNICA_CHOICES = [
        ('buena', 'Buena'),
        ('aceptable', 'Aceptable'),
        ('comprometida', 'Comprometida'),
    ]

    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='series')
    ejercicio = models.ForeignKey('rutinas.EjercicioBase', on_delete=models.CASCADE)
    serie_numero = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    completado = models.BooleanField(default=False)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    rpe_real = models.FloatField(null=True, blank=True, help_text="El RPE que el usuario sintió en esta serie")
    tecnica_calidad = models.CharField(
        max_length=15, choices=TECNICA_CHOICES, null=True, blank=True,
        help_text="Calidad de técnica percibida en esta serie"
    )

    def __str__(self):
        return f"{self.ejercicio.nombre}: Serie {self.serie_numero} - {self.repeticiones} reps @ {self.peso_kg} kg"

    class Meta:
        indexes = [
            models.Index(fields=['entreno'], name='serie_entreno_idx'),
        ]


class Rutina(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Programa(models.Model):
    nombre = models.CharField(max_length=100)
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre


class PlanPersonalizado(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    ejercicio = models.ForeignKey('rutinas.EjercicioBase', on_delete=models.CASCADE)
    rutina = models.ForeignKey('rutinas.Rutina', on_delete=models.CASCADE, null=True, blank=True)
    repeticiones_objetivo = models.PositiveIntegerField(default=10)
    peso_objetivo = models.FloatField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cliente', 'ejercicio', 'rutina')

    def __str__(self):
        return f"{self.cliente} - {self.ejercicio} → {self.repeticiones_objetivo} reps @ {self.peso_objetivo} kg"


class LogroDesbloqueado(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre}"


class EntrenoRealizado(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    rutina = models.ForeignKey('rutinas.Rutina', on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    procesado_gamificacion = models.BooleanField(default=False)

    # Campos adicionales opcionales
    fuente_datos = models.CharField(
        max_length=20,
        choices=[('manual', 'Manual'), ('liftin', 'Liftin')],
        default='manual'
    )
    liftin_workout_id = models.CharField(max_length=100, null=True, blank=True)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    duracion_minutos = models.PositiveIntegerField(null=True, blank=True)
    numero_ejercicios = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Número total de ejercicios realizados"
    )
    puntos_ganados = models.PositiveIntegerField(
        default=0,
        help_text="Puntos ganados por este entrenamiento"
    )
    tiempo_total_formateado = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Duración total en texto (ej: 1:10:23)"
    )

    calorias_quemadas = models.PositiveIntegerField(null=True, blank=True)
    frecuencia_cardiaca_promedio = models.PositiveIntegerField(null=True, blank=True)
    frecuencia_cardiaca_maxima = models.PositiveIntegerField(null=True, blank=True)
    volumen_total_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    nombre_rutina_liftin = models.CharField(max_length=200, null=True, blank=True)
    notas_liftin = models.TextField(null=True, blank=True)
    fecha_importacion = models.DateTimeField(null=True, blank=True)
    puntos_ganados = models.PositiveIntegerField(
        default=0,
        help_text="Puntos ganados por este entrenamiento"
    )
    volumen_total_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Volumen total del entrenamiento en kg"
    )
    records_rotos = models.PositiveIntegerField(
        default=0,
        help_text="Número de récords personales rotos en este entrenamiento"
    )
    energia_pre_sesion = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Energía percibida antes de la sesión (1-10)"
    )

    modo_reducido = models.BooleanField(
        default=False,
        help_text="True si la sesión se realizó en modo esencial (solo bloque principal).",
    )
    principales_planificados = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Nº de ejercicios principales planificados en modo esencial.",
    )
    opcionales_planificados = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Nº de ejercicios opcionales planificados en modo esencial.",
    )

    def calcular_volumen_total(self):
        '''Calcula el volumen total del entrenamiento de todas las fuentes disponibles'''
        total = 0

        # 1. Ejercicios Realizados (Manuales / Importados genéricos)
        for ej in self.ejercicios_realizados.all():
            if ej.completado:
                peso = float(ej.peso_kg or 0)
                series = int(ej.series or 0)
                reps = int(ej.repeticiones or 0)
                total += peso * series * reps

        # 2. Series Realizadas (modelo SerieRealizada, used when logging sets individually)
        for serie in self.series.all():
            peso = float(serie.peso_kg or 0)
            reps = int(serie.repeticiones or 0)
            total += peso * reps

        # 3. Ejercicios Liftin Detallados (Específicos de importación)
        if hasattr(self, 'ejercicios_liftin_detallados'):
            for ej in self.ejercicios_liftin_detallados.all():
                if ej.completado:
                    # Usar propiedad si existe, si no calcular manualmente
                    if hasattr(ej, 'volumen_ejercicio') and ej.volumen_ejercicio:
                        total += float(ej.volumen_ejercicio)
                    else:
                        peso = float(ej.peso_kg or 0)
                        series = int(ej.series_realizadas or 0)
                        # Usar reps min como base conservadora
                        reps = int(ej.repeticiones_min or 0)
                        total += peso * series * reps

        return Decimal(str(total))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Calcular volumen automáticamente si no está establecido o es NULL
        if self.volumen_total_kg is None or self.volumen_total_kg == 0:
            self.volumen_total_kg = self.calcular_volumen_total()
            super().save(update_fields=['volumen_total_kg'])

    @property
    def detalles(self):
        """
        Compatibilidad: permite usar entreno.detalles.all() devolviendo ejercicios_realizados.
        Puedes modificar este método si deseas que devuelva otra cosa.
        """
        return self.ejercicios_realizados.all()

    def __str__(self):
        return f"{self.cliente} - {self.rutina} ({self.fecha})"

    @property
    def duracion_formateada(self):
        if self.tiempo_total_formateado:
            return self.tiempo_total_formateado
        elif self.duracion_minutos is not None:
            horas = self.duracion_minutos // 60
            minutos = self.duracion_minutos % 60
            return f"{horas}h {minutos}m" if horas else f"{minutos}m"
        return "No especificado"

    @property
    def horario_entrenamiento(self):
        if self.hora_inicio and self.hora_fin:
            return f"{self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')}"
        return "No especificado"

    @property
    def volumen_formateado(self):
        if self.volumen_total_kg is not None:
            if self.volumen_total_kg >= 1000:
                return f"{self.volumen_total_kg / 1000:.1f}K KG"
            return f"{self.volumen_total_kg:.0f} KG"
        return "No disponible"

    @property
    def fuente_icono(self):
        return "📱 Liftin" if self.fuente_datos == 'liftin' else "✏️ Manual"

    @property
    def resumen_rutina(self):
        return self.nombre_rutina_liftin or (self.rutina.nombre if self.rutina else "Sin rutina")

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['cliente', 'fecha'], name='entreno_cliente_fecha_idx'),
        ]


# ⭐ MODELO PARA DATOS ESPECÍFICOS DE LIFTIN ⭐
class DatosLiftinDetallados(models.Model):
    """
    Modelo para almacenar datos específicos de Liftin que no encajan
    en la estructura estándar de entrenamientos
    """
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='datos_liftin')

    # Datos de frecuencia cardíaca detallados
    datos_frecuencia_cardiaca = models.JSONField(
        null=True,
        blank=True,
        help_text="Array de datos de frecuencia cardíaca con timestamps"
    )

    # Metadatos de Liftin
    version_liftin = models.CharField(max_length=20, null=True, blank=True)
    dispositivo_origen = models.CharField(max_length=50, null=True, blank=True)

    # Datos de Apple Health/HealthKit
    sincronizado_health = models.BooleanField(default=False)
    health_workout_uuid = models.CharField(max_length=100, null=True, blank=True)

    # Datos adicionales en formato JSON
    metadatos_adicionales = models.JSONField(
        null=True,
        blank=True,
        help_text="Otros datos específicos de Liftin en formato JSON"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Datos Liftin - {self.entreno}"

    class Meta:
        verbose_name = "Datos Detallados de Liftin"
        verbose_name_plural = "Datos Detallados de Liftin"


# Modelo para compatibilidad si es necesario
class EstadoEmocional(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Estado Emocional"
        verbose_name_plural = "Estados Emocionales"


# 🔧 CAMBIO MÍNIMO 1: AGREGAR AL FINAL DE models.py

# ============================================================================
# AGREGAR ESTE CÓDIGO AL FINAL DE TU ARCHIVO entrenos/models.py
# ============================================================================

class EjercicioLiftin(models.Model):
    """
    Modelo simple para guardar ejercicios individuales de Liftin
    """
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='ejercicios_liftin')

    # Información básica del ejercicio
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre del ejercicio (ej: Prensa, Curl Femoral Tumbado)"
    )

    orden = models.PositiveIntegerField(
        default=1,
        help_text="Orden del ejercicio en la rutina"
    )

    # Peso y repeticiones como aparecen en Liftin
    peso_texto = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Peso como aparece en Liftin (ej: 268.5 kg, PC, 90-100 kg)"
    )

    repeticiones_texto = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Repeticiones como aparecen en Liftin (ej: 3x5-10, 3x10-12)"
    )

    # Estado del ejercicio
    estado = models.CharField(
        max_length=20,
        choices=[
            ('completado', '✓ Completado'),
            ('fallado', '✗ Fallado'),
            ('nuevo', 'N Nuevo'),
            ('parcial', '~ Parcial'),
        ],
        default='completado'
    )

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre}: {self.peso_texto}, {self.repeticiones_texto}"

    class Meta:
        ordering = ['entreno', 'orden']
        verbose_name = "Ejercicio de Liftin"
        verbose_name_plural = "Ejercicios de Liftin"


# ============================================================================
# TAMBIÉN AGREGAR ESTA FUNCIÓN HELPER AL FINAL
# ============================================================================

def activar_logros_liftin(entreno):
    """
    Función simple para activar logros basados en datos de Liftin
    """
    from logros.models import LogroDesbloqueado

    cliente = entreno.cliente
    logros_nuevos = []

    # Logro: Primera importación de Liftin
    if not LogroDesbloqueado.objects.filter(
            cliente=cliente,
            nombre="Primera Importación Liftin"
    ).exists():
        logro = LogroDesbloqueado.objects.create(
            cliente=cliente,
            nombre="Primera Importación Liftin",
            descripcion="¡Has importado tu primer entrenamiento desde Liftin!"
        )
        logros_nuevos.append(logro)

    # Logro: Entrenamiento de más de 1 hora
    if entreno.duracion_minutos and entreno.duracion_minutos >= 60:
        if not LogroDesbloqueado.objects.filter(
                cliente=cliente,
                nombre="Entrenamiento Maratón"
        ).exists():
            logro = LogroDesbloqueado.objects.create(
                cliente=cliente,
                nombre="Entrenamiento Maratón",
                descripcion="¡Has completado un entrenamiento de más de 1 hora!"
            )
            logros_nuevos.append(logro)

    # Logro: Más de 300 calorías
    if entreno.calorias_quemadas and entreno.calorias_quemadas >= 300:
        if not LogroDesbloqueado.objects.filter(
                cliente=cliente,
                nombre="Quemador de Calorías"
        ).exists():
            logro = LogroDesbloqueado.objects.create(
                cliente=cliente,
                nombre="Quemador de Calorías",
                descripcion="¡Has quemado más de 300 calorías en un entrenamiento!"
            )
            logros_nuevos.append(logro)

    # Logro: Volumen alto (más de 10K kg)
    if entreno.volumen_total_kg and entreno.volumen_total_kg >= 10000:
        if not LogroDesbloqueado.objects.filter(
                cliente=cliente,
                nombre="Levantador Pesado"
        ).exists():
            logro = LogroDesbloqueado.objects.create(
                cliente=cliente,
                nombre="Levantador Pesado",
                descripcion="¡Has levantado más de 10,000 kg en un entrenamiento!"
            )
            logros_nuevos.append(logro)

    return logros_nuevos


# ============================================================================
# MODELOS DE GAMIFICACIÓN Y TRACKING DE PROGRESO
# ============================================================================

class SesionEntrenamiento(models.Model):
    """
    Resumen detallado de cada sesión de entrenamiento
    Captura todos los datos que se muestran en el modal de finalización
    """
    entreno = models.OneToOneField(
        'EntrenoRealizado',
        on_delete=models.CASCADE,
        related_name='sesion_detalle'
    )

    # Datos de tiempo
    duracion_minutos = models.PositiveIntegerField(
        help_text="Duración total de la sesión en minutos"
    )
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)

    # Datos de series y ejercicios
    series_completadas = models.PositiveIntegerField(default=0)
    series_totales = models.PositiveIntegerField(default=0)
    ejercicios_completados = models.PositiveIntegerField(default=0)
    ejercicios_totales = models.PositiveIntegerField(default=0)

    # Métricas de esfuerzo
    rpe_medio = models.FloatField(
        null=True,
        blank=True,
        help_text="RPE promedio de la sesión (1-10)"
    )
    acwr = models.FloatField(
        null=True,
        blank=True,
        help_text="Ratio ACWR de la sesión"
    )
    volumen_sesion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Volumen total en kg"
    )

    # Logros de la sesión
    nuevos_records = models.PositiveIntegerField(
        default=0,
        help_text="Número de récords personales establecidos"
    )
    logros_desbloqueados = models.ManyToManyField(
        'LogroAutomatico',
        blank=True,
        related_name='sesiones'
    )

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sesión {self.entreno.cliente.nombre} - {self.entreno.fecha}"

    @property
    def porcentaje_completado(self):
        """Porcentaje de series completadas"""
        if self.series_totales > 0:
            return int((self.series_completadas / self.series_totales) * 100)
        return 0

    @property
    def es_sesion_perfecta(self):
        """True si se completaron todas las series"""
        return self.series_completadas == self.series_totales and self.series_totales > 0

    class Meta:
        verbose_name = "Sesión de Entrenamiento"
        verbose_name_plural = "Sesiones de Entrenamiento"
        ordering = ['-fecha_creacion']


class RecordPersonal(models.Model):
    """
    Tracking de récords personales por ejercicio
    """
    TIPO_RECORD_CHOICES = [
        ('peso_maximo', 'Peso Máximo'),
        ('volumen_total', 'Volumen Total'),
        ('reps_maximas', 'Repeticiones Máximas'),
        ('one_rep_max', '1RM Estimado'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='records_personales'
    )
    ejercicio_nombre = models.CharField(
        max_length=200,
        help_text="Nombre del ejercicio"
    )
    tipo_record = models.CharField(
        max_length=20,
        choices=TIPO_RECORD_CHOICES,
        default='peso_maximo'
    )

    # Valor del récord
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor del récord (kg, reps, etc)"
    )

    # Contexto del récord
    fecha_logrado = models.DateField(auto_now_add=True)
    entreno = models.ForeignKey(
        'EntrenoRealizado',
        on_delete=models.CASCADE,
        related_name='records_establecidos'
    )

    # Estado
    superado = models.BooleanField(
        default=False,
        help_text="True si este récord fue superado posteriormente"
    )
    fecha_superado = models.DateField(null=True, blank=True)

    def __str__(self):
        estado = "🏆" if not self.superado else "📊"
        return f"{estado} {self.cliente.nombre} - {self.ejercicio_nombre}: {self.valor} kg ({self.get_tipo_record_display()})"

    class Meta:
        verbose_name = "Récord Personal"
        verbose_name_plural = "Récords Personales"
        ordering = ['-fecha_logrado']
        indexes = [
            models.Index(fields=['cliente', 'ejercicio_nombre', 'tipo_record']),
        ]


class LogroAutomatico(models.Model):
    """
    Sistema de logros predefinidos que se desbloquean automáticamente
    """
    CATEGORIA_CHOICES = [
        ('racha', '🔥 Racha'),
        ('volumen', '💪 Volumen'),
        ('tiempo', '⏱️ Tiempo'),
        ('records', '🏆 Récords'),
        ('perfeccion', '⭐ Perfección'),
        ('especial', '🎯 Especial'),
    ]

    RAREZA_CHOICES = [
        ('comun', 'Común'),
        ('raro', 'Raro'),
        ('epico', 'Épico'),
        ('legendario', 'Legendario'),
    ]

    # Identificación
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text="Código único del logro (ej: racha_7_dias)"
    )
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre del logro (ej: Racha de Fuego 🔥)"
    )
    descripcion = models.TextField(
        help_text="Descripción de cómo desbloquear el logro"
    )
    icono = models.CharField(
        max_length=10,
        default="🏅",
        help_text="Emoji o icono del logro"
    )

    # Clasificación
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='especial'
    )
    rareza = models.CharField(
        max_length=20,
        choices=RAREZA_CHOICES,
        default='comun'
    )

    # Condiciones de desbloqueo (JSON)
    condicion_tipo = models.CharField(
        max_length=50,
        help_text="Tipo de condición (racha_dias, volumen_sesion, etc)"
    )
    condicion_valor = models.JSONField(
        default=dict,
        help_text="Parámetros de la condición en JSON"
    )

    # Recompensas
    puntos_recompensa = models.PositiveIntegerField(
        default=10,
        help_text="Puntos que otorga este logro"
    )

    # Metadatos
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.icono} {self.nombre} ({self.get_rareza_display()})"

    class Meta:
        verbose_name = "Logro Automático"
        verbose_name_plural = "Logros Automáticos"
        ordering = ['rareza', 'nombre']


class ClienteLogroAutomatico(models.Model):
    """
    Relación entre clientes y logros desbloqueados
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='logros_automaticos'
    )
    logro = models.ForeignKey(
        LogroAutomatico,
        on_delete=models.CASCADE,
        related_name='clientes_desbloqueados'
    )
    fecha_desbloqueo = models.DateTimeField(auto_now_add=True)
    sesion = models.ForeignKey(
        'SesionEntrenamiento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logros_obtenidos'
    )

    def __str__(self):
        return f"{self.cliente.nombre} - {self.logro.nombre}"

    class Meta:
        verbose_name = "Logro Desbloqueado"
        verbose_name_plural = "Logros Desbloqueados"
        unique_together = ['cliente', 'logro']
        ordering = ['-fecha_desbloqueo']


class DesafioSemanal(models.Model):
    """
    Desafíos temporales para motivar a los clientes
    """
    OBJETIVO_TIPO_CHOICES = [
        ('sesiones', 'Número de Sesiones'),
        ('volumen', 'Volumen Total (kg)'),
        ('ejercicios', 'Ejercicios Diferentes'),
        ('duracion', 'Tiempo Total (minutos)'),
        ('racha', 'Días Consecutivos'),
    ]

    nombre = models.CharField(
        max_length=100,
        help_text="Nombre del desafío"
    )
    descripcion = models.TextField(
        help_text="Descripción del desafío"
    )
    icono = models.CharField(
        max_length=10,
        default="🎯",
        help_text="Emoji del desafío"
    )

    # Periodo
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    # Objetivo
    objetivo_tipo = models.CharField(
        max_length=20,
        choices=OBJETIVO_TIPO_CHOICES
    )
    objetivo_valor = models.PositiveIntegerField(
        help_text="Valor objetivo a alcanzar"
    )

    # Recompensa
    recompensa_puntos = models.PositiveIntegerField(
        default=50,
        help_text="Puntos que otorga completar el desafío"
    )

    # Estado
    activo = models.BooleanField(default=True)
    global_challenge = models.BooleanField(
        default=True,
        help_text="Si es True, aplica a todos los clientes"
    )

    def __str__(self):
        return f"{self.icono} {self.nombre} ({self.fecha_inicio} - {self.fecha_fin})"

    @property
    def esta_activo(self):
        """Verifica si el desafío está en periodo activo"""
        from django.utils import timezone
        hoy = timezone.now().date()
        return self.activo and self.fecha_inicio <= hoy <= self.fecha_fin

    class Meta:
        verbose_name = "Desafío Semanal"
        verbose_name_plural = "Desafíos Semanales"
        ordering = ['-fecha_inicio']


class ProgresoDesafio(models.Model):
    """
    Tracking del progreso de cada cliente en los desafíos
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='progresos_desafios'
    )
    desafio = models.ForeignKey(
        DesafioSemanal,
        on_delete=models.CASCADE,
        related_name='progresos'
    )

    # Progreso
    progreso_actual = models.PositiveIntegerField(
        default=0,
        help_text="Progreso actual hacia el objetivo"
    )

    # Estado
    completado = models.BooleanField(default=False)
    fecha_completado = models.DateTimeField(null=True, blank=True)

    # Metadatos
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.desafio.nombre}: {self.progreso_actual}/{self.desafio.objetivo_valor}"

    @property
    def porcentaje(self):
        """Porcentaje de completado"""
        if self.desafio.objetivo_valor > 0:
            return min(100, int((self.progreso_actual / self.desafio.objetivo_valor) * 100))
        return 0

    def actualizar_progreso(self, incremento=1):
        """Actualiza el progreso y marca como completado si alcanza el objetivo"""
        self.progreso_actual += incremento

        if self.progreso_actual >= self.desafio.objetivo_valor and not self.completado:
            self.completado = True
            self.fecha_completado = timezone.now()

        self.save()

    class Meta:
        verbose_name = "Progreso de Desafío"
        verbose_name_plural = "Progresos de Desafíos"
        unique_together = ['cliente', 'desafio']
        ordering = ['-ultima_actualizacion']


# ============================================================================
# HUB CENTRAL DE ACTIVIDAD — FASE 1 DEL PLAN DE UNIFICACIÓN
# ============================================================================

class ActividadRealizada(models.Model):
    """
    Modelo hub que unifica TODAS las actividades físicas del atleta en una
    línea temporal única. Cada registro representa una sesión de cualquier tipo:
    gimnasio, hyrox, fútbol, remo, etc.

    Relaciones opcionales (solo una estará presente por registro):
    - entreno_gym → EntrenoRealizado (sesión de fuerza/musculación)
    - sesion_hyrox → HyroxSession (sesión de hyrox planificada)

    Este hub es la fuente única de verdad para:
    - Timeline unificado del atleta
    - Cálculo de ACWR multi-modalidad (Fase 3)
    - Conexión con el diario emocional (Fase 4)
    """

    TIPO_CHOICES = [
        ('gym', 'Gimnasio / Fuerza'),
        ('hyrox', 'Sesión Hyrox'),
        ('carrera', 'Carrera / Running'),
        ('ciclismo', 'Ciclismo'),
        ('remo', 'Remo / Ergómetro'),
        ('futbol', 'Fútbol'),
        ('natacion', 'Natación'),
        ('yoga', 'Yoga / Movilidad'),
        ('estiramientos', 'Estiramientos'),
        ('otro', 'Otra Actividad'),
    ]

    FUENTE_CHOICES = [
        ('manual', 'Registro manual'),
        ('liftin', 'Importado de Liftin'),
        ('hyrox_engine', 'Motor Hyrox'),
        ('strava', 'Importado de Strava'),
        ('auto', 'Generado automáticamente'),
    ]

    # ── Quién ──────────────────────────────────────────────────────────────────
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='actividades_realizadas',
        db_index=True,
    )

    # ── Qué ────────────────────────────────────────────────────────────────────
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='gym')
    titulo = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nombre libre de la sesión (ej: 'Pierna A', 'Hyrox Semana 3')"
    )

    # ── Cuándo ─────────────────────────────────────────────────────────────────
    fecha = models.DateField(db_index=True)          # fecha planificada del entreno
    fecha_realizado = models.DateField(              # fecha en que realmente se ejecutó
        null=True, blank=True, db_index=True,
        help_text="Fecha real de ejecución. Si es null, se asume igual a 'fecha'."
    )
    hora_inicio = models.TimeField(null=True, blank=True)

    # ── Métricas universales ────────────────────────────────────────────────────
    duracion_minutos = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Duración total de la sesión en minutos"
    )
    volumen_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Volumen total en kg (peso × series × reps). Null para cardio puro."
    )
    distancia_metros = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Distancia recorrida en metros (para cardio/running)"
    )
    carga_ua = models.FloatField(
        null=True, blank=True,
        help_text="Carga en Unidades Arbitrarias = RPE × duración_minutos (para ACWR)"
    )
    rpe_medio = models.FloatField(
        null=True, blank=True,
        help_text="RPE medio de la sesión (escala 1-10)"
    )
    calorias = models.PositiveIntegerField(null=True, blank=True)
    hr_media = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="FC media de la sesión en lpm (fuente: Strava / dispositivo)"
    )
    hr_maxima = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="FC máxima de la sesión en lpm (fuente: Strava / dispositivo)"
    )

    # ── Punteros a modelos existentes (uno o ninguno) ───────────────────────────
    entreno_gym = models.OneToOneField(
        'EntrenoRealizado',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hub_actividad',
        help_text="Enlace al EntrenoRealizado para sesiones de gimnasio"
    )
    sesion_hyrox = models.OneToOneField(
        'hyrox.HyroxSession',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hub_actividad',
        help_text="Enlace a HyroxSession para sesiones del motor hyrox"
    )

    # ── Metadatos ────────────────────────────────────────────────────────────
    fuente = models.CharField(max_length=20, choices=FUENTE_CHOICES, default='manual')
    notas = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Actividad Realizada"
        verbose_name_plural = "Actividades Realizadas"
        ordering = ['-fecha', '-hora_inicio']
        indexes = [
            models.Index(fields=['cliente', 'fecha'], name='actividad_cliente_fecha_idx'),
            models.Index(fields=['cliente', 'tipo'], name='actividad_cliente_tipo_idx'),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.cliente.nombre} ({self.fecha})"

    def calcular_carga_ua(self):
        """
        Calcula la Carga en Unidades Arbitrarias (RPE × duración).
        Este valor es la base del cálculo ACWR multi-modalidad.
        """
        if self.rpe_medio and self.duracion_minutos:
            return round(self.rpe_medio * self.duracion_minutos, 1)
        return None

    def save(self, *args, **kwargs):
        # Auto-calcular carga UA si tenemos RPE y duración
        if self.carga_ua is None:
            self.carga_ua = self.calcular_carga_ua()
        super().save(*args, **kwargs)


class GymDecisionLog(models.Model):
    ACCION_CHOICES = [
        ('subir_peso', 'Subir peso'),
        ('subir_reps', 'Subir repeticiones'),
        ('mantener', 'Mantener'),
        ('bajar_peso', 'Reducir peso'),
        ('deload', 'Descarga'),
        ('cambiar_variante', 'Cambiar variante'),
    ]
    RESULTADO_CHOICES = [
        ('validada', 'Validada'),
        ('fallida', 'Fallida'),
        ('neutra', 'Neutra'),
    ]
    CONFIANZA_CHOICES = [
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='gym_decision_logs')
    ejercicio = models.CharField(max_length=120)

    peso_anterior = models.FloatField(null=True, blank=True)
    reps_anteriores = models.PositiveIntegerField(null=True, blank=True)
    rpe_anterior = models.FloatField(null=True, blank=True)

    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    valor_cambio = models.FloatField(null=True, blank=True)
    motivo = models.TextField()

    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, null=True, blank=True)
    notas_resultado = models.TextField(null=True, blank=True)

    confianza = models.CharField(max_length=20, choices=CONFIANZA_CHOICES, default='media')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_evaluacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Decisión de Progresión"
        verbose_name_plural = "Decisiones de Progresión"
        indexes = [
            models.Index(fields=['cliente', 'ejercicio'], name='decision_cliente_ejercicio_idx'),
        ]

    def __str__(self):
        return f"{self.ejercicio} → {self.accion} ({self.fecha_creacion.date()})"

    @property
    def accion_label(self):
        return dict(self.ACCION_CHOICES).get(self.accion, self.accion)

    @property
    def resultado_label(self):
        return dict(self.RESULTADO_CHOICES).get(self.resultado, '') if self.resultado else 'Pendiente'

    @property
    def peso_sugerido(self):
        """Peso concreto recomendado para la próxima sesión (kg), o None si no aplica."""
        if not self.peso_anterior or not self.valor_cambio:
            return None
        if self.accion == 'subir_peso':
            raw = float(self.peso_anterior) * (1 + float(self.valor_cambio) / 100)
        elif self.accion in ('bajar_peso', 'deload'):
            raw = float(self.peso_anterior) * (1 - float(self.valor_cambio) / 100)
        else:
            return None
        # Redondear al múltiplo de 2.5 kg más cercano (disco estándar)
        return round(round(raw / 2.5) * 2.5, 1)


class GymAdaptationProfile(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='gym_adaptation_profiles')
    ejercicio = models.CharField(max_length=120)

    incremento_peso_pct = models.FloatField(default=5.0, help_text="% de incremento preferido")
    reduccion_peso_pct = models.FloatField(default=10.0, help_text="% de reducción preferida")

    decisiones_totales = models.IntegerField(default=0)
    decisiones_validadas = models.IntegerField(default=0)
    decisiones_fallidas = models.IntegerField(default=0)

    confianza = models.CharField(max_length=20, default='baja')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('cliente', 'ejercicio')]
        verbose_name = "Perfil de Adaptación"
        verbose_name_plural = "Perfiles de Adaptación"

    def __str__(self):
        return f"{self.cliente} — {self.ejercicio}"

    @property
    def precision(self):
        if self.decisiones_totales == 0:
            return 0
        return round((self.decisiones_validadas / self.decisiones_totales) * 100)


class SesionProgramada(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_COMPLETADA = "completada"
    ESTADO_SALTADA_USUARIO = "saltada_usuario"
    ESTADO_OMITIDA_SISTEMA = "omitida_sistema"
    ESTADO_CANCELADA_LESION = "cancelada_lesion"

    PRIORIDAD_ALTA = "alta"
    PRIORIDAD_NORMAL = "normal"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_COMPLETADA, "Completada"),
        (ESTADO_SALTADA_USUARIO, "Saltada por usuario"),
        (ESTADO_OMITIDA_SISTEMA, "Omitida por sistema"),
        (ESTADO_CANCELADA_LESION, "Cancelada por lesión"),
    ]

    PRIORIDADES = [
        (PRIORIDAD_ALTA, "Alta"),
        (PRIORIDAD_NORMAL, "Normal"),
    ]

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE,
        related_name="sesiones_programadas",
    )

    fecha_prevista = models.DateField(db_index=True)
    fecha_realizada = models.DateField(null=True, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
        db_index=True,
    )

    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDADES,
        default=PRIORIDAD_ALTA,
    )

    nombre_sesion = models.CharField(max_length=200, blank=True)
    bloque_nombre = models.CharField(max_length=100, blank=True)
    dia_numero = models.PositiveSmallIntegerField(null=True, blank=True)

    pospuesta_hasta = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="Si está presente, la sesión no se muestra como pendiente hasta esa fecha.",
    )

    entreno_realizado = models.ForeignKey(
        "entrenos.EntrenoRealizado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sesiones_programadas",
    )

    motivo_estado = models.TextField(blank=True)

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha_prevista", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "fecha_prevista"],
                name="unique_sesion_cliente_fecha",
            )
        ]
        indexes = [
            models.Index(fields=["cliente", "estado", "fecha_prevista"]),
        ]

    def __str__(self):
        return f"{self.cliente} - {self.fecha_prevista} - {self.nombre_sesion} - {self.estado}"


class SugerenciaPlan(models.Model):
    """
    Phase 10B — Records user responses to plan suggestions.

    CONTRACT:
    - Created lazily when a suggestion is first displayed.
    - A ignored suggestion respects cooldown_hasta before reappearing.
    - An accepted/applied suggestion does NOT auto-modify the plan.
    - Never shows the same suggestion twice within the cooldown window.
    """
    ESTADO_PENDIENTE  = 'pendiente'
    ESTADO_ACEPTADA   = 'aceptada'
    ESTADO_IGNORADA   = 'ignorada'
    ESTADO_APLICADA   = 'aplicada'
    ESTADO_DESCARTADA = 'descartada'

    ESTADOS = [
        ('pendiente',  'Pendiente'),
        ('aceptada',   'Aceptada'),
        ('ignorada',   'Ignorada por ahora'),
        ('aplicada',   'Aplicada'),
        ('descartada', 'Descartada'),
    ]

    COOLDOWN_DIAS = 7  # days before an ignored suggestion reappears

    cliente       = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='sugerencias_plan')
    patron        = models.CharField(max_length=60, db_index=True)  # e.g. 'carga_alta_sostenida'
    texto         = models.TextField()
    estado        = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE, db_index=True)
    cooldown_hasta = models.DateField(null=True, blank=True, db_index=True)
    fecha_generada = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_generada']
        indexes = [
            models.Index(fields=['cliente', 'patron', 'estado']),
        ]

    def __str__(self):
        return f"{self.cliente} — {self.patron} ({self.estado})"


class IntervencionPlan(models.Model):
    """
    Phase 10C — Temporary plan policy created when the user accepts a suggestion.

    CONTRACT:
    - Created when SugerenciaPlan.estado transitions to 'aceptada'.
    - Active while estado='activa' and fecha_inicio <= today <= fecha_fin.
    - evaluar_permiso_progresion reads this FIRST, overriding pattern detection.
    - Does NOT modify the annual plan or PlanificadorHelms.
    - Expires automatically at end of the current week (Sunday).
    - Safe types only: 'no_subir_cargas' and 'reducir_accesorios'.
    """
    TIPO_NO_SUBIR   = 'no_subir_cargas'
    TIPO_REDUCIR    = 'reducir_accesorios'
    TIPO_MANTENER   = 'mantener_estructura'  # records acceptance, no-op on freno

    # Phase 18 — Distribution interventions (2-week window)
    TIPO_REDISTRIB_DIA     = 'redistrib_dia_frecuente'
    TIPO_REDISTRIB_DIAS    = 'redistrib_dias_menores'
    TIPO_REDISTRIB_PIERNA  = 'redistrib_pierna_futbol'
    TIPO_REDISTRIB_LIGERO  = 'redistrib_aligerar_dia'

    # Phase 37 — Hypothesis experiment: watch a signal for 14 days (no load change)
    TIPO_VIGILAR_SENAL     = 'vigilar_senal'

    TIPOS = [
        ('no_subir_cargas',          'No subir cargas'),
        ('reducir_accesorios',       'Reducir accesorios'),
        ('mantener_estructura',      'Mantener estructura'),
        ('redistrib_dia_frecuente',  'Redistribuir día con muchas caídas'),
        ('redistrib_dias_menores',   'Probar semana con menos días'),
        ('redistrib_pierna_futbol',  'Separar pierna de fútbol'),
        ('redistrib_aligerar_dia',   'Aligerar día con versiones esenciales'),
        ('vigilar_senal',            'Observar señal durante 2 semanas'),
    ]

    ESTADO_ACTIVA   = 'activa'
    ESTADO_EXPIRADA = 'expirada'
    ESTADO_CANCELADA = 'cancelada'

    ESTADOS = [
        ('activa',    'Activa'),
        ('expirada',  'Expirada'),
        ('cancelada', 'Cancelada'),
    ]

    cliente         = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='intervenciones_plan')
    sugerencia      = models.ForeignKey(SugerenciaPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='intervenciones')
    tipo            = models.CharField(max_length=30, choices=TIPOS, db_index=True)
    origen_patron   = models.CharField(max_length=60, blank=True)
    fecha_inicio    = models.DateField(db_index=True)
    fecha_fin       = models.DateField(db_index=True)
    estado          = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_ACTIVA, db_index=True)
    creada_en       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']
        indexes = [
            models.Index(fields=['cliente', 'estado', 'fecha_fin']),
        ]

    def __str__(self):
        return f"{self.cliente} — {self.tipo} ({self.fecha_inicio} → {self.fecha_fin})"


class PreferenciaPlanAprendida(models.Model):
    """
    Phase 22 — A soft plan preference learned from repeated favorable probes.

    CONTRACT:
    - Created only when the SAME probe type was favorable ≥ 2 times AND user consented.
    - Represents an inclination, not a rule. The motor may respect it when possible.
    - NEVER silently reprograms the plan. Always visible to the user.
    - Reversible: user can suspend or revoke at any time.
    - Does NOT write to ManualDavid automatically.

    Hierarchy: Preferencia > IntervencionPlan activa > patrón inferido.
    """
    TIPO_EVITAR_PIERNA_FUTBOL = 'evitar_pierna_tras_futbol'
    TIPO_EVITAR_DIA            = 'evitar_dia_frecuente'
    TIPO_MENOS_DIAS            = 'preferir_menos_dias'
    TIPO_ALIGERAR_DIA          = 'aligerar_dia_concreto'

    TIPOS = [
        ('evitar_pierna_tras_futbol', 'Evitar pierna cerca del fútbol'),
        ('evitar_dia_frecuente',      'Evitar sesión principal en día problemático'),
        ('preferir_menos_dias',       'Preferir estructura real de menos días'),
        ('aligerar_dia_concreto',     'Aligerar accesorios en un día concreto'),
    ]

    ESTADO_ACTIVA    = 'activa'
    ESTADO_SUSPENDIDA = 'suspendida'
    ESTADO_REVOCADA  = 'revocada'

    ESTADOS = [
        ('activa',     'Activa'),
        ('suspendida', 'Suspendida'),
        ('revocada',   'Revocada'),
    ]

    cliente              = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='preferencias_plan')
    tipo                 = models.CharField(max_length=40, choices=TIPOS, db_index=True)
    estado               = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_ACTIVA, db_index=True)
    evidencia_count      = models.PositiveSmallIntegerField(default=2, help_text="Number of favorable probes that originated this preference.")
    origen_patron        = models.CharField(max_length=60, blank=True, help_text="e.g. 'redistrib_pierna_futbol'")
    descripcion          = models.TextField(blank=True, help_text="Human-readable description shown to the user.")
    fecha_inicio         = models.DateField()
    ultima_confirmacion  = models.DateField()
    metadata             = models.JSONField(default=dict, blank=True, help_text="Extra info: e.g. {dia: 'lunes', umbral_horas: 48}")

    class Meta:
        ordering = ['-fecha_inicio']
        unique_together = [('cliente', 'tipo', 'estado')]

    def __str__(self):
        return f"{self.cliente} — {self.tipo} ({self.estado})"


class GymDecisionTrace(models.Model):
    """
    Phase 32 — Memoria de decisiones del plan.

    Stores a structured trace of why the motor made a specific decision on a given day.
    One trace per (cliente, fecha) — updated in place if the decision changes.

    CONTRACT:
    - Saved asynchronously (after the panel response) to avoid latency.
    - Never stores absolute/identity/diagnostic language (enforced by Phase 31 audit).
    - Does NOT replace GymDecisionLog (which records load decisions per exercise).
      This records the DAILY PANEL DECISION: why today looks like it does.
    - explicacion_senales mirrors construir_explicacion_decision().senales_activas.
    """
    cliente             = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='decision_traces')
    fecha               = models.DateField(db_index=True)
    sesion_programada   = models.ForeignKey('entrenos.SesionProgramada', null=True, blank=True, on_delete=models.SET_NULL)

    decision_estado     = models.CharField(max_length=50)   # entrenar / recuperar / posponer / descanso
    causa_principal     = models.CharField(max_length=80, blank=True)

    # Raw signals from _obtener_contexto_fisico and decision dict
    senales_motor       = models.JSONField(default=dict)

    # Signals visible/hidden in the panel
    capas_visibles      = models.JSONField(default=list)    # ['lesion_aviso', 'preferencia_aplicada', ...]
    capas_suprimidas    = models.JSONField(default=list)    # ['distribucion_aviso'] when preference wins

    # Human-readable signal list from construir_explicacion_decision
    explicacion_senales = models.JSONField(default=list)

    # Active influencers at the time of the decision
    preferencias_activas    = models.JSONField(default=list)    # [tipo_str, ...]
    intervenciones_activas  = models.JSONField(default=list)    # [tipo_str, ...]
    lesion_contexto         = models.JSONField(default=dict)    # {zona, fase, es_bloqueante, ejercicios}

    creado_en   = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-creado_en']
        unique_together = [('cliente', 'fecha')]
        indexes = [models.Index(fields=['cliente', 'fecha'])]

    def __str__(self):
        return f"{self.cliente} — {self.fecha} — {self.decision_estado} ({self.causa_principal})"

    def get_explicacion_humana(self) -> str:
        """Returns a single-sentence human-readable explanation of this decision."""
        if self.explicacion_senales:
            lineas = '. '.join(s.rstrip('.') for s in self.explicacion_senales[:3])
            return f"{lineas}."
        _CAUSA_TEXTO = {
            'lesion':          'Descanso recomendado — lesión activa en ese momento.',
            'fatiga':          'Descanso recomendado — fatiga acumulada elevada.',
            'acwr_alto':       'Descanso recomendado — carga aguda/crónica fuera de rango seguro.',
            'readiness_bajo':  'Recuperación recomendada — readiness bajo.',
            'pospuesto_usuario': 'El usuario indicó que ese día no podía entrenar.',
            'sesion_hoy':      'Sesión del plan ejecutada sin adaptaciones.',
            'pendiente':       'Sesión pendiente de días anteriores.',
            'descanso_plan':   'Día de descanso según el plan.',
        }
        causa = self.causa_principal or ''
        if causa in _CAUSA_TEXTO:
            return _CAUSA_TEXTO[causa]
        if self.decision_estado == 'recuperar':
            return 'Recuperación recomendada por el motor.'
        if self.decision_estado == 'descanso':
            return 'Día de descanso.'
        return 'Sesión del plan.'


class GymDecisionTraceEvaluation(models.Model):
    """
    Phase 34 — Seguimiento posterior de decisiones.

    Reviews observable signals after a decision to detect whether it seemed to
    release margin, was neutral, or missed a prior signal.

    CONTRACT:
    - Does NOT evaluate whether the motor was right.
    - Does NOT score the motor or punish the user.
    - Does NOT claim strong causality.
    - Language: "parece", "puede", "señal", "provisionalmente".
    - Runs automatically 2+ days after the decision (auto-evaluated).
    - One evaluation per trace (OneToOne).
    """
    LIBERO_MARGEN     = 'libero_margen'
    NEUTRO            = 'neutral'
    SENAL_NO_CAPTADA  = 'senal_no_captada'
    INSUFICIENTE      = 'datos_insuficientes'

    RESULTADOS = [
        ('libero_margen',      'Pareció liberar margen'),
        ('neutral',            'Sin señal clara posterior'),
        ('senal_no_captada',   'Quizá faltó captar una señal previa'),
        ('datos_insuficientes','Datos posteriores insuficientes'),
    ]

    trace               = models.OneToOneField(
        GymDecisionTrace, on_delete=models.CASCADE, related_name='evaluacion',
    )
    resultado           = models.CharField(max_length=50, choices=RESULTADOS)
    resumen             = models.TextField(blank=True)
    senales_posteriores = models.JSONField(default=dict)
    creado_en           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.trace} → {self.resultado}"


class PausaEntrenamiento(models.Model):
    """Phase Continuidad 1.3 — registro de una pausa de entrenamiento.

    "La pausa no es deuda". Se persiste SOLO cuando la pausa es significativa
    (nivel >= clara, ≥6 días sin gym), no por cada hueco de 2 días. El motivo lo
    declara el usuario una sola vez; la app nunca lo inventa. Es la fuente única
    del motivo para que JOI y el resto de la app lo consuman vía core.continuidad.

    Regla madre: la duración manda la prudencia física; el motivo modula la
    narrativa. desconocido (no contestó) ≠ prefiero_no_decirlo (contestó que no).
    """
    MOTIVO_DESCONOCIDO = 'desconocido'
    MOTIVO_CHOICES = [
        (MOTIVO_DESCONOCIDO,    'Desconocido'),
        ('enfermedad',          'Enfermedad'),
        ('molestia_lesion',     'Molestia / lesión'),
        ('vacaciones_viaje',    'Vacaciones / viaje'),
        ('trabajo_no_pude',     'Trabajo / no pude'),
        ('descanso_decidido',   'Descanso decidido'),
        ('otro',                'Otro'),
        ('prefiero_no_decirlo', 'Prefiero no decirlo'),
    ]
    NIVEL_CHOICES = [
        ('clara',         'Pausa clara'),
        ('larga',         'Pausa larga'),
        ('recalibracion', 'Recalibración'),
    ]

    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='pausas_entrenamiento',
        db_index=True,
    )
    fecha_inicio = models.DateField(help_text="Primer día de la pausa (último gym + 1).")
    fecha_fin = models.DateField(null=True, blank=True, help_text="Día en que se retomó. Null = pausa abierta.")
    dias_sin_gym = models.PositiveIntegerField(default=0)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES)
    motivo = models.CharField(max_length=40, choices=MOTIVO_CHOICES, default=MOTIVO_DESCONOCIDO)
    motivo_preguntado = models.BooleanField(default=False)
    motivo_respondido = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_inicio']
        indexes = [models.Index(fields=['cliente', 'fecha_fin'])]

    def __str__(self):
        estado = 'abierta' if self.fecha_fin is None else f'cerrada {self.fecha_fin}'
        return f"Pausa {self.cliente_id} {self.nivel} ({estado})"
