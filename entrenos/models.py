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

    # Molestia reportada durante el entreno
    molestia_reportada = models.BooleanField(default=False)
    molestia_zona = models.CharField(max_length=100, blank=True)
    molestia_severidad = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="1=Leve, 2=Moderada, 3=Severa/Aguda"
    )
    molestia_descripcion = models.TextField(blank=True)

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
    entreno = models.ForeignKey('EntrenoRealizado', on_delete=models.CASCADE, related_name='series')
    ejercicio = models.ForeignKey('rutinas.EjercicioBase', on_delete=models.CASCADE)
    serie_numero = models.PositiveIntegerField()
    repeticiones = models.PositiveIntegerField()
    completado = models.BooleanField(default=False)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    rpe_real = models.FloatField(null=True, blank=True, help_text="El RPE que el usuario sintió en esta serie")

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
