from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


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


class TriggerHabito(models.Model):
    """
    Registro de triggers/recaídas para hábitos negativos.
    Permite analizar patrones de recaída y mejorar estrategias.
    """
    EMOCIONES_CHOICES = [
        ('estres', 'Estrés'),
        ('ansiedad', 'Ansiedad'),
        ('aburrimiento', 'Aburrimiento'),
        ('tristeza', 'Tristeza'),
        ('soledad', 'Soledad'),
        ('enojo', 'Enojo'),
        ('frustracion', 'Frustración'),
        ('cansancio', 'Cansancio'),
        ('euforia', 'Euforia'),
        ('otro', 'Otro'),
    ]
    
    habito = models.ForeignKey(
        'ProsocheHabito',
        on_delete=models.CASCADE,
        related_name='triggers',
        help_text="Hábito negativo al que pertenece este trigger"
    )
    
    fecha = models.DateField(default=timezone.now)
    hora = models.TimeField(default=timezone.now)
    
    # Contexto emocional
    emocion_previa = models.CharField(
        max_length=20,
        choices=EMOCIONES_CHOICES,
        verbose_name="Emoción previa",
        help_text="¿Qué emoción sentías antes del impulso?"
    )
    
    # Contexto situacional
    situacion = models.TextField(
        verbose_name="Situación",
        help_text="¿Qué estaba pasando? ¿Dónde estabas?"
    )
    
    personas_presentes = models.TextField(
        blank=True,
        verbose_name="Personas presentes",
        help_text="¿Estabas solo o con alguien?"
    )
    
    # Intensidad y resultado
    intensidad_deseo = models.IntegerField(
        choices=[(i, i) for i in range(1, 11)],
        verbose_name="Intensidad del deseo (1-10)",
        help_text="¿Qué tan fuerte fue el impulso?"
    )
    
    cediste = models.BooleanField(
        verbose_name="¿Cediste?",
        help_text="¿Recaíste o resististe el impulso?"
    )
    
    # Estrategias y aprendizaje
    estrategia_usada = models.TextField(
        blank=True,
        verbose_name="Estrategia usada",
        help_text="¿Qué hiciste para resistir? (si resististe)"
    )
    
    aprendizaje = models.TextField(
        blank=True,
        verbose_name="Aprendizaje",
        help_text="¿Qué aprendiste de esta experiencia?"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha', '-hora']
        verbose_name = "Trigger de Hábito"
        verbose_name_plural = "Triggers de Hábitos"
    
    def __str__(self):
        resultado = "Recaída" if self.cediste else "Resistido"
        return f"{self.habito.nombre} - {self.fecha} ({resultado})"



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
    
    # FASE 1: Campos fundamentales para distinguir hábitos buenos vs malos
    TIPO_CHOICES = [
        ('positivo', 'Hábito a Formar'),
        ('negativo', 'Hábito a Eliminar')
    ]
    tipo_habito = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default='positivo',
        help_text="¿Es un hábito que quieres formar o eliminar?"
    )
    
    # Tracking de objetivos
    objetivo_dias = models.IntegerField(
        default=30,
        help_text="Días objetivo para establecer/eliminar el hábito"
    )
    
    fecha_inicio = models.DateField(
        auto_now_add=True,
        help_text="Fecha en que empezaste a trackear este hábito"
    )
    
    fecha_objetivo = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha objetivo para completar el desafío"
    )
    
    # FASE 2: Atomic Habits - Las 4 Leyes del Cambio de Comportamiento
    # Para hábitos positivos: Make it Obvious, Attractive, Easy, Satisfying
    # Para hábitos negativos: Make it Invisible, Unattractive, Difficult, Unsatisfying
    ley_1_obvio = models.TextField(
        blank=True,
        verbose_name="Ley 1: Hacerlo Obvio/Invisible",
        help_text="¿Cómo harás este hábito obvio (positivo) o invisible (negativo)?"
    )
    
    ley_2_atractivo = models.TextField(
        blank=True,
        verbose_name="Ley 2: Hacerlo Atractivo/No Atractivo",
        help_text="¿Cómo harás este hábito atractivo (positivo) o no atractivo (negativo)?"
    )
    
    ley_3_facil = models.TextField(
        blank=True,
        verbose_name="Ley 3: Hacerlo Fácil/Difícil",
        help_text="¿Cómo harás este hábito fácil (positivo) o difícil (negativo)?"
    )
    
    ley_4_satisfactorio = models.TextField(
        blank=True,
        verbose_name="Ley 4: Hacerlo Satisfactorio/Insatisfactorio",
        help_text="¿Cómo harás este hábito satisfactorio (positivo) o insatisfactorio (negativo)?"
    )
    
    # Habit Loop: Cue → Craving → Response → Reward
    senal_cue = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Señal (Cue)",
        help_text="¿Qué dispara este hábito? Ej: 'Después de despertarme', 'Cuando veo mi teléfono'"
    )
    
    anhelo_craving = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Anhelo (Craving)",
        help_text="¿Qué deseas obtener? Ej: 'Sentirme energizado', 'Reducir ansiedad'"
    )
    
    recompensa_reward = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Recompensa (Reward)",
        help_text="¿Qué obtienes al hacerlo? Ej: 'Endorfinas', 'Sensación de logro'"
    )
    
    # Identity-based habits (hábitos basados en identidad)
    identidad_objetivo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Identidad Objetivo",
        help_text="¿Qué tipo de persona quieres ser? Ej: 'Soy una persona que cuida su salud'"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('prosoche_mes', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.prosoche_mes.mes} {self.prosoche_mes.año}"
    
    def get_dias_completados(self):
        """Obtiene el número de días marcados como completados"""
        return self.dias_completados.filter(completado=True).count()
    
    def get_dias_sin_habito(self):
        """Para hábitos negativos: días SIN hacer el hábito"""
        if self.tipo_habito == 'negativo':
            total_dias = self.dias_completados.count()
            dias_con_habito = self.get_dias_completados()
            return total_dias - dias_con_habito
        return 0
    
    def get_porcentaje_exito(self):
        """Calcula el porcentaje de éxito según el tipo de hábito"""
        if self.objetivo_dias == 0:
            return 0
        if self.tipo_habito == 'negativo':
            dias_sin_habito = self.get_dias_sin_habito()
            return round((dias_sin_habito / self.objetivo_dias) * 100)
        else:
            dias_completados = self.get_dias_completados()
            return round((dias_completados / self.objetivo_dias) * 100)
    
    def get_racha_actual(self):
        """Calcula la racha actual de días consecutivos"""
        dias = self.dias_completados.order_by('-dia')
        if not dias.exists():
            return 0
        if self.tipo_habito == 'negativo':
            racha = 0
            for dia in dias:
                if not dia.completado:
                    racha += 1
                else:
                    break
            return racha
        else:
            racha = 0
            for dia in dias:
                if dia.completado:
                    racha += 1
                else:
                    break
            return racha
    
    def get_mensaje_progreso(self):
        """Genera un mensaje motivacional según el progreso"""
        if self.tipo_habito == 'negativo':
            dias_sin = self.get_dias_sin_habito()
            return f"Llevas {dias_sin} de {self.objetivo_dias} días sin {self.nombre}"
        else:
            dias_con = self.get_dias_completados()
            return f"Has completado {dias_con} de {self.objetivo_dias} días"


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


class ReflexionLibre(models.Model):
    """
    Modelo para reflexiones de escritura libre del usuario.
    Puede ser espontánea, guiada por un tema, o de apoyo en momentos difíciles.
    """
    TIPO_CHOICES = [
        ('espontanea', 'Reflexión Espontánea'),
        ('guiada', 'Reflexión Guiada'),
        ('crisis', 'Reflexión de Apoyo'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reflexiones_libres')
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    titulo = models.CharField(max_length=200, blank=True, help_text="Título opcional de la reflexión")
    contenido = models.TextField(help_text="Contenido de la reflexión")
    etiquetas = models.CharField(max_length=500, blank=True,
                                 help_text="Etiquetas separadas por comas (ej: miedo,gratitud,decisión)")

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='espontanea')
    reflexion_guiada = models.ForeignKey('ReflexionGuiadaTema', null=True, blank=True, on_delete=models.SET_NULL,
                                         help_text="Si es una reflexión guiada, referencia al tema")

    # Estado emocional después de escribir (opcional)
    estado_animo_post = models.IntegerField(null=True, blank=True,
                                            help_text="¿Cómo te sientes después de escribir? (1-5)")

    # Metadata
    es_privada = models.BooleanField(default=True, help_text="Si es privada, solo el usuario puede verla")
    favorita = models.BooleanField(default=False, help_text="Marcar como favorita")

    class Meta:
        verbose_name = "Reflexión Libre"
        verbose_name_plural = "Reflexiones Libres"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario.username} - {self.titulo or 'Sin título'} ({self.fecha.strftime('%d/%m/%Y')})"


class ReflexionGuiadaTema(models.Model):
    """
    Modelo para temas de reflexiones guiadas.
    Cada tema se activa en una fecha específica y contiene contexto educativo,
    preguntas provocadoras y acciones sugeridas.
    """
    CATEGORIA_CHOICES = [
        ('salud', 'Salud y Bienestar'),
        ('social', 'Causas Sociales'),
        ('filosofia', 'Filosofía y Pensamiento'),
        ('naturaleza', 'Naturaleza y Medio Ambiente'),
        ('personal', 'Desarrollo Personal'),
        ('historia', 'Historia y Cultura'),
    ]

    # Información básica
    titulo = models.CharField(max_length=200, help_text="Título de la reflexión guiada")
    slug = models.SlugField(unique=True, help_text="Identificador único (ej: dia-mundial-ela)")

    # Configuración de activación
    fecha_activacion = models.DateField(help_text="¿Qué día se muestra esta reflexión?")
    es_recurrente = models.BooleanField(default=True, help_text="¿Se repite cada año?")
    activa = models.BooleanField(default=True, help_text="¿Está activa esta reflexión?")

    # Contenido educativo
    contexto = models.TextField(help_text="Explicación breve del tema (2-3 párrafos)")
    cita_filosofica = models.TextField(help_text="Cita relevante de un filósofo o pensador")
    autor_cita = models.CharField(max_length=100, help_text="Autor de la cita")

    # Preguntas guía (mínimo 1, máximo 5)
    pregunta_1 = models.TextField(help_text="Primera pregunta para reflexionar")
    pregunta_2 = models.TextField(blank=True, help_text="Segunda pregunta (opcional)")
    pregunta_3 = models.TextField(blank=True, help_text="Tercera pregunta (opcional)")
    pregunta_4 = models.TextField(blank=True, help_text="Cuarta pregunta (opcional)")
    pregunta_5 = models.TextField(blank=True, help_text="Quinta pregunta (opcional)")

    # Acción sugerida
    accion_sugerida = models.TextField(help_text="Acción concreta que el usuario puede hacer hoy")

    # Metadata
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='personal')
    icono = models.CharField(max_length=50, default='fa-scroll', help_text="Icono Font Awesome")
    color = models.CharField(max_length=7, default='#6c757d', help_text="Color en formato hex (ej: #3498db)")

    # Estadísticas
    veces_completada = models.IntegerField(default=0,
                                           help_text="Número de veces que usuarios han completado esta reflexión")

    # Fechas de creación
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reflexión Guiada (Tema)"
        verbose_name_plural = "Reflexiones Guiadas (Temas)"
        ordering = ['fecha_activacion']

    def __str__(self):
        return f"{self.titulo} ({self.fecha_activacion.strftime('%d/%m')})"

    def get_preguntas(self):
        """Retorna lista de preguntas no vacías"""
        preguntas = []
        for i in range(1, 6):
            pregunta = getattr(self, f'pregunta_{i}', '')
            if pregunta:
                preguntas.append(pregunta)
        return preguntas


# ============================================
# SISTEMA DE VIRTUDES E INSIGNIAS
# ============================================

class Virtud(models.Model):
    """
    Modelo para las 4 virtudes cardinales estoicas de cada usuario.
    Cada virtud tiene puntos y niveles que se van desbloqueando.
    """
    TIPO_CHOICES = [
        ('sabiduria', 'Sabiduría (Sophia)'),
        ('coraje', 'Coraje (Andreia)'),
        ('justicia', 'Justicia (Dikaiosyne)'),
        ('templanza', 'Templanza (Sophrosyne)'),
    ]

    NIVEL_CHOICES = [
        ('aprendiz', 'Aprendiz'),
        ('practicante', 'Practicante'),
        ('adepto', 'Adepto'),
        ('maestro', 'Maestro'),
        ('sabio', 'Sabio'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='virtudes')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    # Progreso
    puntos = models.IntegerField(default=0, help_text="Puntos acumulados en esta virtud")
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='aprendiz')

    # Fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_nivel = models.DateTimeField(auto_now_add=True, help_text="Fecha en que alcanzó el nivel actual")

    class Meta:
        verbose_name = "Virtud"
        verbose_name_plural = "Virtudes"
        unique_together = ['usuario', 'tipo']

    def __str__(self):
        return f"{self.usuario.username} - {self.get_tipo_display()} ({self.nivel})"

    def calcular_nivel(self):
        """Calcula el nivel basándose en los puntos acumulados"""
        if self.puntos < 50:
            return 'aprendiz'
        elif self.puntos < 150:
            return 'practicante'
        elif self.puntos < 300:
            return 'adepto'
        elif self.puntos < 500:
            return 'maestro'
        else:
            return 'sabio'

    def actualizar_nivel(self):
        """Actualiza el nivel si los puntos lo permiten"""
        nivel_anterior = self.nivel
        nivel_nuevo = self.calcular_nivel()

        if nivel_nuevo != nivel_anterior:
            self.nivel = nivel_nuevo
            self.fecha_ultimo_nivel = timezone.now()
            self.save()
            return True  # Indica que hubo cambio de nivel
        return False

    def porcentaje_progreso(self):
        """Calcula el porcentaje de progreso hacia el siguiente nivel"""
        umbrales = {
            'aprendiz': (0, 50),
            'practicante': (50, 150),
            'adepto': (150, 300),
            'maestro': (300, 500),
            'sabio': (500, 1000),
        }

        min_puntos, max_puntos = umbrales.get(self.nivel, (0, 50))

        if self.puntos >= max_puntos:
            return 100

        rango = max_puntos - min_puntos
        progreso = self.puntos - min_puntos
        return int((progreso / rango) * 100)


class Insignia(models.Model):
    """
    Modelo para definir insignias que los usuarios pueden desbloquear.
    Cada insignia está asociada a una virtud y tiene criterios específicos.
    """
    VIRTUD_CHOICES = [
        ('sabiduria', 'Sabiduría'),
        ('coraje', 'Coraje'),
        ('justicia', 'Justicia'),
        ('templanza', 'Templanza'),
        ('general', 'General'),
    ]

    # Información básica
    codigo = models.CharField(max_length=50, unique=True, help_text="Código único de la insignia (ej: racha_7_dias)")
    nombre = models.CharField(max_length=100, help_text="Nombre de la insignia")
    descripcion = models.TextField(help_text="Descripción de lo que representa")

    # Asociación
    virtud_asociada = models.CharField(max_length=20, choices=VIRTUD_CHOICES, default='general')

    # Visual
    icono = models.CharField(max_length=50, default='fa-trophy', help_text="Icono Font Awesome")
    color = models.CharField(max_length=7, default='#FFD700', help_text="Color en formato hex")

    # Criterios
    criterio_logro = models.TextField(help_text="Descripción de cómo se obtiene esta insignia")
    puntos_virtud = models.IntegerField(default=0, help_text="Puntos de virtud que otorga al desbloquear")

    # Metadata
    es_secreta = models.BooleanField(default=False, help_text="Si es secreta, no se muestra hasta desbloquearla")
    orden = models.IntegerField(default=0, help_text="Orden de visualización")
    activa = models.BooleanField(default=True)

    # Estadísticas
    veces_desbloqueada = models.IntegerField(default=0, help_text="Cuántos usuarios la han desbloqueado")

    class Meta:
        verbose_name = "Insignia"
        verbose_name_plural = "Insignias"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_virtud_asociada_display()})"


class InsigniaUsuario(models.Model):
    """
    Modelo de relación entre usuarios e insignias desbloqueadas.
    Registra cuándo se obtuvo cada insignia y si el usuario ya la vio.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='insignias_desbloqueadas')
    insignia = models.ForeignKey(Insignia, on_delete=models.CASCADE, related_name='usuarios_que_la_tienen')

    # Fechas
    fecha_obtencion = models.DateTimeField(auto_now_add=True)

    # Estado
    vista = models.BooleanField(default=False, help_text="¿El usuario ya vio la notificación de desbloqueo?")
    favorita = models.BooleanField(default=False, help_text="¿El usuario la marcó como favorita?")

    class Meta:
        verbose_name = "Insignia de Usuario"
        verbose_name_plural = "Insignias de Usuarios"
        unique_together = ['usuario', 'insignia']
        ordering = ['-fecha_obtencion']

    def __str__(self):
        return f"{self.usuario.username} - {self.insignia.nombre}"


# ============================================
# MODELO PARA RACHA DE ESCRITURA
# ============================================

class RachaEscritura(models.Model):
    """
    Modelo para trackear la racha de días consecutivos escribiendo.
    Se actualiza automáticamente cada vez que el usuario escribe.
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='racha_escritura')

    # Racha actual
    dias_consecutivos = models.IntegerField(default=0, help_text="Días consecutivos escribiendo")
    fecha_ultima_entrada = models.DateField(null=True, blank=True, help_text="Última fecha en que escribió")

    # Racha más larga
    racha_maxima = models.IntegerField(default=0, help_text="Racha más larga alcanzada")
    fecha_racha_maxima = models.DateField(null=True, blank=True, help_text="Fecha en que alcanzó la racha máxima")

    # Estadísticas
    total_dias_escritos = models.IntegerField(default=0,
                                              help_text="Total de días que ha escrito (no necesariamente consecutivos)")

    class Meta:
        verbose_name = "Racha de Escritura"
        verbose_name_plural = "Rachas de Escritura"

    def __str__(self):
        return f"{self.usuario.username} - {self.dias_consecutivos} días consecutivos"

    def actualizar_racha(self, fecha_entrada):
        """
        Actualiza la racha basándose en la fecha de una nueva entrada.
        Retorna True si se rompió una racha o se alcanzó un hito.
        """
        hoy = fecha_entrada.date() if hasattr(fecha_entrada, 'date') else fecha_entrada

        # Si es la primera entrada
        if not self.fecha_ultima_entrada:
            self.dias_consecutivos = 1
            self.fecha_ultima_entrada = hoy
            self.total_dias_escritos = 1
            self.save()
            return False

        # Calcular días desde la última entrada
        dias_diferencia = (hoy - self.fecha_ultima_entrada).days

        # Si escribió hoy (mismo día), no hacer nada
        if dias_diferencia == 0:
            return False

        # Si escribió ayer (racha continúa)
        elif dias_diferencia == 1:
            self.dias_consecutivos += 1
            self.fecha_ultima_entrada = hoy
            self.total_dias_escritos += 1

            # Verificar si alcanzó nueva racha máxima
            if self.dias_consecutivos > self.racha_maxima:
                self.racha_maxima = self.dias_consecutivos
                self.fecha_racha_maxima = hoy

            self.save()
            return True  # Indica que la racha creció

        # Si pasaron más de 1 día (racha se rompe)
        else:
            self.dias_consecutivos = 1
            self.fecha_ultima_entrada = hoy
            self.total_dias_escritos += 1
            self.save()
            return False  # Racha rota


# ============================================
# SEÑALES PARA CREAR VIRTUDES AUTOMÁTICAMENTE
# ============================================


@receiver(post_save, sender=User)
def crear_virtudes_usuario(sender, instance, created, **kwargs):
    """
    Cuando se crea un nuevo usuario, automáticamente se crean sus 4 virtudes
    y su racha de escritura.
    """
    if created:
        # Crear las 4 virtudes
        for tipo, _ in Virtud.TIPO_CHOICES:
            Virtud.objects.create(usuario=instance, tipo=tipo)

        # Crear racha de escritura
        RachaEscritura.objects.create(usuario=instance)
