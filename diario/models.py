from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ========================================
# MODELOS PROSOCHE ACTUALIZADOS - Basados en Notion
# ========================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class ProsocheMes(models.Model):
    """Modelo principal para cada mes de Prosoche"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    mes = models.CharField(max_length=20)  # "Marzo", "Abril", etc.
    año = models.IntegerField()

    # Objetivos del mes (3 principales)
    objetivo_mes_1 = models.TextField(blank=True)
    objetivo_mes_2 = models.TextField(blank=True)
    objetivo_mes_3 = models.TextField(blank=True)

    # Estado de objetivos mensuales
    objetivo_mes_1_completado = models.BooleanField(default=False)
    objetivo_mes_2_completado = models.BooleanField(default=False)
    objetivo_mes_3_completado = models.BooleanField(default=False)

    # Revisión del mes (completar al final)
    logro_principal = models.TextField(blank=True, help_text="Principal logro del mes y cómo lo he celebrado")
    obstaculo_principal = models.TextField(blank=True, help_text="Principal obstáculo del mes y cómo lo he gestionado")
    aprendizaje_principal = models.TextField(blank=True, help_text="Principal aprendizaje del mes")
    momento_felicidad = models.TextField(blank=True, help_text="Principal momento de felicidad")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'mes', 'año')
        ordering = ['-año', '-mes']

    def __str__(self):
        return f"{self.mes} {self.año} - {self.usuario.username}"


class ProsocheSemana(models.Model):
    """Objetivos semanales para cada semana del mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='semanas')
    numero_semana = models.IntegerField(choices=[(i, f'Semana {i}') for i in range(1, 6)])  # 1-5

    # 3 objetivos por semana
    objetivo_1 = models.TextField(blank=True)
    objetivo_2 = models.TextField(blank=True)
    objetivo_3 = models.TextField(blank=True)

    # Estado de objetivos semanales
    objetivo_1_completado = models.BooleanField(default=False)
    objetivo_2_completado = models.BooleanField(default=False)
    objetivo_3_completado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('prosoche_mes', 'numero_semana')
        ordering = ['numero_semana']

    def __str__(self):
        return f"{self.prosoche_mes.mes} {self.prosoche_mes.año} - Semana {self.numero_semana}"


class ProsocheHabito(models.Model):
    """Hábitos a seguir durante el mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='habitos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#00ffff', help_text="Color en formato hex")

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('prosoche_mes', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.prosoche_mes.mes} {self.prosoche_mes.año}"


class ProsocheHabitoDia(models.Model):
    """Seguimiento diario de cada hábito"""
    habito = models.ForeignKey(ProsocheHabito, on_delete=models.CASCADE, related_name='dias_completados')

    dia = models.IntegerField(choices=[(i, i) for i in range(1, 32)])  # 1-31
    completado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('habito', 'dia')
        ordering = ['dia']

    def __str__(self):
        return f"{self.habito.nombre} - Día {self.dia} ({'✓' if self.completado else '○'})"


# ========================================
# EUDAIMONIA - Áreas de la Vida
# ========================================

class AreaVida(models.Model):
    """Área de la vida a evaluar, como Salud Física o Desarrollo Personal."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    icono = models.CharField(max_length=50, blank=True, null=True, help_text="Clase CSS del icono")
    color = models.CharField(max_length=7, default="#00ffff", help_text="Color hexadecimal")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Área de Vida"
        verbose_name_plural = "Áreas de Vida"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Eudaimonia(models.Model):
    """Evaluación de un área de la vida para un usuario."""
    PRIORIDAD_CHOICES = [
        ('alta', 'Prioridad Alta'),
        ('media', 'Prioridad Media'),
        ('baja', 'Prioridad Baja')
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eudaimonia_areas')
    area = models.ForeignKey(AreaVida, on_delete=models.CASCADE)
    prioridad = models.CharField(max_length=5, choices=PRIORIDAD_CHOICES, default='media')
    puntuacion = models.IntegerField(help_text="Puntuación del 1 al 10", default=5)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['usuario', 'area']
        verbose_name = "Eudaimonia"
        verbose_name_plural = "Eudaimonia"

    def __str__(self):
        return f"{self.usuario.username} - {self.area.nombre}"


class TrimestreEudaimonia(models.Model):
    """Seguimiento trimestral de un área de la vida."""
    ESTADO_CHOICES = [
        ('planificado', 'Planificado'),
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado'),
        ('pausado', 'Pausado')
    ]

    eudaimonia = models.ForeignKey(Eudaimonia, on_delete=models.CASCADE, related_name='trimestres')
    trimestre = models.CharField(max_length=20, help_text="Ejemplo: Q1 2025")
    año = models.IntegerField(default=timezone.now().year)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='planificado')
    objetivos = models.TextField(blank=True, null=True)
    plan_accion = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    resultados = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['eudaimonia', 'trimestre', 'año']
        ordering = ['-año', '-trimestre']
        verbose_name = "Trimestre Eudaimonia"
        verbose_name_plural = "Trimestres Eudaimonia"

    def __str__(self):
        return f"{self.eudaimonia.area.nombre} - {self.trimestre} {self.año}"


# ========================================
# ARETÉ - Desarrollo Personal
# ========================================

class EjercicioArete(models.Model):
    """Ejercicio de desarrollo personal."""
    ESTADO_CHOICES = [
        ('sin_completar', 'Sin completar'),
        ('completado', 'Completado'),
        ('a_repetir', 'A repetir')
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ejercicios_arete')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    instrucciones = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='sin_completar')
    fecha_completado = models.DateTimeField(blank=True, null=True)
    reflexiones = models.TextField(blank=True, null=True)
    numero_orden = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ['usuario', 'numero_orden']
        ordering = ['numero_orden']
        verbose_name = "Ejercicio Areté"
        verbose_name_plural = "Ejercicios Areté"

    def __str__(self):
        return f"{self.usuario.username} - {self.nombre}"


# ========================================
# GNOSIS - Gestión de Conocimiento
# ========================================

class Gnosis(models.Model):
    """Contenido de conocimiento (libros, artículos, etc.)."""
    CATEGORIA_CHOICES = [
        ('podcast', 'Podcast'),
        ('video', 'Vídeo'),
        ('libro', 'Libro'),
        ('receta', 'Receta'),
        ('articulo', 'Artículo')
    ]

    ESTADO_CHOICES = [
        ('finalizado', 'Finalizado'),
        ('en_progreso', 'En progreso'),
        ('no_empezado', 'No empezado')
    ]

    PUNTUACION_CHOICES = [
        ('legendario', 'Legendario'),
        ('muy_bueno', 'Muy bueno'),
        ('bueno', 'Bueno'),
        ('regular', 'Regular'),
        ('malo', 'Malo')
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contenido_gnosis')
    titulo = models.CharField(max_length=200)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='no_empezado')
    tematica = models.CharField(max_length=100, blank=True, null=True)
    puntuacion = models.CharField(max_length=10, choices=PUNTUACION_CHOICES, blank=True, null=True)
    autor = models.CharField(max_length=100, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Gnosis"
        verbose_name_plural = "Gnosis"

    def __str__(self):
        return f"{self.titulo} ({self.categoria})"


# ========================================
# VIRES - Salud y Deporte
# ========================================

class EntrenamientoSemanal(models.Model):
    """Planificación de entrenamiento semanal."""
    TIPO_CHOICES = [
        ('pesas', 'Pesas'),
        ('cardio', 'Cardio'),
        ('movilidad', 'Movilidad')
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='entrenamientos_semanales')
    semana_inicio = models.DateField(help_text="Fecha de inicio de la semana")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    lunes = models.TextField(blank=True, null=True)
    martes = models.TextField(blank=True, null=True)
    miercoles = models.TextField(blank=True, null=True)
    jueves = models.TextField(blank=True, null=True)
    viernes = models.TextField(blank=True, null=True)
    sabado = models.TextField(blank=True, null=True)
    domingo = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['usuario', 'semana_inicio', 'tipo']
        ordering = ['-semana_inicio']
        verbose_name = "Entrenamiento Semanal"
        verbose_name_plural = "Entrenamientos Semanales"

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo} - Semana {self.semana_inicio}"


class SeguimientoVires(models.Model):
    """Seguimiento diario de hábitos y medidas corporales."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seguimiento_vires')
    fecha = models.DateField()
    peso = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    grasa_corporal = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    masa_muscular = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    agua_corporal = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    entrenamiento_realizado = models.BooleanField(default=False)
    descripcion_entrenamiento = models.TextField(blank=True, null=True)
    alimentacion_saludable = models.BooleanField(default=False)
    hidratacion_adecuada = models.BooleanField(default=False)
    descanso_suficiente = models.BooleanField(default=False)
    notas = models.TextField(blank=True, null=True)
    horas_sueno = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                      help_text="Horas de sueño de la noche anterior")
    calidad_sueno = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
                                        help_text="Calidad del sueño (1-5)")
    nivel_energia = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
                                        help_text="Nivel de energía general (1-5)")
    nivel_estres = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
                                       help_text="Nivel de estrés percibido (1-5)")
    pasos = models.PositiveIntegerField(null=True, blank=True, help_text="Pasos totales del día")

    class Meta:
        unique_together = ['usuario', 'fecha']
        ordering = ['-fecha']
        verbose_name = "Seguimiento Vires"
        verbose_name_plural = "Seguimientos Vires"

    def __str__(self):
        return f"{self.usuario.username} - {self.fecha}"


# ========================================
# KAIROS - Calendario y Eventos
# ========================================

class EventoKairos(models.Model):
    """Evento en el calendario."""
    TIPO_CHOICES = [
        ('personal', 'Personal'),
        ('trabajo', 'Trabajo'),
        ('salud', 'Salud'),
        ('social', 'Social'),
        ('desarrollo', 'Desarrollo Personal'),
        ('otro', 'Otro')
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eventos_kairos')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='personal')
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(blank=True, null=True)
    todo_el_dia = models.BooleanField(default=False)
    recordatorio = models.BooleanField(default=False)
    minutos_recordatorio = models.PositiveIntegerField(default=15, help_text="Minutos antes del evento")
    completado = models.BooleanField(default=False)
    color = models.CharField(max_length=7, default="#00ffff", help_text="Color hexadecimal")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_inicio']
        verbose_name = "Evento Kairos"
        verbose_name_plural = "Eventos Kairos"

    def __str__(self):
        return f"{self.titulo} - {self.fecha_inicio.strftime('%d/%m/%Y')}"


class PlanificacionDiaria(models.Model):
    """Planificación hora por hora del día."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planificaciones_diarias')
    fecha = models.DateField()
    hora = models.TimeField()
    actividad = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    completado = models.BooleanField(default=False)

    class Meta:
        unique_together = ['usuario', 'fecha', 'hora']
        ordering = ['fecha', 'hora']
        verbose_name = "Planificación Diaria"
        verbose_name_plural = "Planificaciones Diarias"

    def __str__(self):
        return f"{self.fecha} {self.hora} - {self.actividad}"


# ========================================
# MODELOS PROSOCHE ACTUALIZADOS - Basados en Notion
# ========================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ProsocheMes(models.Model):
    """Modelo principal para cada mes de Prosoche"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    mes = models.CharField(max_length=20)  # "Marzo", "Abril", etc.
    año = models.IntegerField()

    # Objetivos del mes (3 principales)
    objetivo_mes_1 = models.TextField(blank=True)
    objetivo_mes_2 = models.TextField(blank=True)
    objetivo_mes_3 = models.TextField(blank=True)

    # Estado de objetivos mensuales
    objetivo_mes_1_completado = models.BooleanField(default=False)
    objetivo_mes_2_completado = models.BooleanField(default=False)
    objetivo_mes_3_completado = models.BooleanField(default=False)

    # Revisión del mes (completar al final)
    logro_principal = models.TextField(blank=True, help_text="Principal logro del mes y cómo lo he celebrado")
    obstaculo_principal = models.TextField(blank=True, help_text="Principal obstáculo del mes y cómo lo he gestionado")
    aprendizaje_principal = models.TextField(blank=True, help_text="Principal aprendizaje del mes")
    momento_felicidad = models.TextField(blank=True, help_text="Principal momento de felicidad")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'mes', 'año')
        ordering = ['-año', '-mes']

    def __str__(self):
        return f"{self.mes} {self.año} - {self.usuario.username}"


class ProsocheSemana(models.Model):
    """Objetivos semanales para cada semana del mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='semanas')
    numero_semana = models.IntegerField(choices=[(i, f'Semana {i}') for i in range(1, 6)])  # 1-5

    # 3 objetivos por semana
    objetivo_1 = models.TextField(blank=True)
    objetivo_2 = models.TextField(blank=True)
    objetivo_3 = models.TextField(blank=True)

    # Estado de objetivos semanales
    objetivo_1_completado = models.BooleanField(default=False)
    objetivo_2_completado = models.BooleanField(default=False)
    objetivo_3_completado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('prosoche_mes', 'numero_semana')
        ordering = ['numero_semana']

    def __str__(self):
        return f"{self.prosoche_mes.mes} {self.prosoche_mes.año} - Semana {self.numero_semana}"


class ProsocheDiario(models.Model):
    """Entrada completa del diario diario con todos los campos de Notion"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE)
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


class ProsocheHabito(models.Model):
    """Hábitos a seguir durante el mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='habitos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#00ffff', help_text="Color en formato hex")

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('prosoche_mes', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.prosoche_mes.mes} {self.prosoche_mes.año}"


class ProsocheHabitoDia(models.Model):
    """Seguimiento diario de cada hábito"""
    habito = models.ForeignKey(ProsocheHabito, on_delete=models.CASCADE, related_name='dias_completados')

    dia = models.IntegerField(choices=[(i, i) for i in range(1, 32)])  # 1-31
    completado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('habito', 'dia')
        ordering = ['dia']

    def __str__(self):
        return f"{self.habito.nombre} - Día {self.dia} ({'✓' if self.completado else '○'})"


# ========================================
# MODELOS PROSOCHE ACTUALIZADOS - Basados en Notion
# ========================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ProsocheMes(models.Model):
    """Modelo principal para cada mes de Prosoche"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    mes = models.CharField(max_length=20)  # "Marzo", "Abril", etc.
    año = models.IntegerField()

    # Objetivos del mes (3 principales)
    objetivo_mes_1 = models.TextField(blank=True)
    objetivo_mes_2 = models.TextField(blank=True)
    objetivo_mes_3 = models.TextField(blank=True)

    # Estado de objetivos mensuales
    objetivo_mes_1_completado = models.BooleanField(default=False)
    objetivo_mes_2_completado = models.BooleanField(default=False)
    objetivo_mes_3_completado = models.BooleanField(default=False)

    # Revisión del mes (completar al final)
    logro_principal = models.TextField(blank=True, help_text="Principal logro del mes y cómo lo he celebrado")
    obstaculo_principal = models.TextField(blank=True, help_text="Principal obstáculo del mes y cómo lo he gestionado")
    aprendizaje_principal = models.TextField(blank=True, help_text="Principal aprendizaje del mes")
    momento_felicidad = models.TextField(blank=True, help_text="Principal momento de felicidad")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'mes', 'año')
        ordering = ['-año', '-mes']

    def __str__(self):
        return f"{self.mes} {self.año} - {self.usuario.username}"


class ProsocheSemana(models.Model):
    """Objetivos semanales para cada semana del mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='semanas')
    numero_semana = models.IntegerField(choices=[(i, f'Semana {i}') for i in range(1, 6)])  # 1-5

    # 3 objetivos por semana
    objetivo_1 = models.TextField(blank=True)
    objetivo_2 = models.TextField(blank=True)
    objetivo_3 = models.TextField(blank=True)

    # Estado de objetivos semanales
    objetivo_1_completado = models.BooleanField(default=False)
    objetivo_2_completado = models.BooleanField(default=False)
    objetivo_3_completado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('prosoche_mes', 'numero_semana')
        ordering = ['numero_semana']

    def __str__(self):
        return f"{self.prosoche_mes.mes} {self.prosoche_mes.año} - Semana {self.numero_semana}"


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


class ProsocheHabito(models.Model):
    """Hábitos a seguir durante el mes"""
    prosoche_mes = models.ForeignKey(ProsocheMes, on_delete=models.CASCADE, related_name='habitos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#00ffff', help_text="Color en formato hex")

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('prosoche_mes', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.prosoche_mes.mes} {self.prosoche_mes.año}"


class ProsocheHabitoDia(models.Model):
    """Seguimiento diario de cada hábito"""
    habito = models.ForeignKey(ProsocheHabito, on_delete=models.CASCADE, related_name='dias_completados')

    dia = models.IntegerField(choices=[(i, i) for i in range(1, 32)])  # 1-31
    completado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('habito', 'dia')
        ordering = ['dia']

    def __str__(self):
        return f"{self.habito.nombre} - Día {self.dia} ({'✓' if self.completado else '○'})"


# diario/models.py

class RevisionSemanal(models.Model):
    semana = models.OneToOneField(ProsocheSemana, on_delete=models.CASCADE, related_name='revision')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    logro_principal = models.TextField(blank=True, help_text="El mayor logro de la semana.")
    obstaculo_principal = models.TextField(blank=True, help_text="El mayor desafío enfrentado.")
    aprendizaje_principal = models.TextField(blank=True, help_text="El aprendizaje más importante.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Revisión de la semana {self.semana.numero_semana} para {self.usuario.username}"


class PersonaImportante(models.Model):
    """Representa a una persona importante en la vida del usuario."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)

    TIPO_RELACION_CHOICES = [
        ('familia', 'Familia'),
        ('pareja', 'Pareja'),
        ('amigo', 'Amigo/a'),
        ('mentor', 'Mentor/a'),
        ('colega', 'Colega de Trabajo'),
        ('otro', 'Otro'),
    ]
    tipo_relacion = models.CharField(max_length=20, choices=TIPO_RELACION_CHOICES, default='amigo')
    salud_relacion = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)],
                                         help_text="Salud percibida de la relación (1=Mala, 5=Excelente)")
    notas = models.TextField(blank=True, help_text="Notas generales sobre esta persona o relación.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_relacion_display()}) - {self.usuario.username}"


class Interaccion(models.Model):
    """Representa una interacción significativa con una o más personas."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    personas = models.ManyToManyField(PersonaImportante, blank=True)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(help_text="Describe la interacción. ¿Qué pasó?")
    mi_sentir = models.TextField(blank=True, help_text="¿Cómo me sentí durante y después?")
    aprendizaje = models.TextField(blank=True, help_text="¿Qué aprendí sobre mí mismo o sobre los demás?")
    fecha = models.DateField(default=timezone.now)

    TIPO_INTERACCION_CHOICES = [
        ('positiva', 'Positiva'),
        ('negativa', 'Negativa'),
        ('neutra', 'Neutra'),
        ('conflicto', 'Conflicto'),
        ('apoyo', 'Apoyo Recibido/Dado'),
    ]
    tipo_interaccion = models.CharField(max_length=20, choices=TIPO_INTERACCION_CHOICES, default='neutra')

    def __str__(self):
        return f"Interacción '{self.titulo}' el {self.fecha} - {self.usuario.username}"
