from django.db import models
from django.contrib.auth.models import User


class RecuerdoEmocional(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()
    contexto = models.TextField(blank=True, null=True)  # ej: “desmotivación”, “post-entreno”, etc.

    def __str__(self):
        return f"{self.user.username} - {self.fecha.date()} - {self.contexto or 'sin contexto'}"


class EstadoEmocional(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    emocion = models.CharField(max_length=50)
    nota = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.emocion} ({self.fecha})"


class Entrenamiento(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    tipo = models.CharField(max_length=100)
    duracion = models.IntegerField()
    intensidad = models.CharField(max_length=50)
    completado = models.BooleanField(default=True)

    # 🧠 Nuevo campo
    recomendacion_joi = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.tipo} ({self.fecha})"


class Logro(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    desbloqueado = models.BooleanField(default=False)
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.user.username} ({'✔️' if self.desbloqueado else '❌'})"


class EventoLogro(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre_logro = models.CharField(max_length=100)
    icono = models.CharField(max_length=10, default="🏅")
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.icono} {self.nombre_logro} ({self.user.username} - {self.fecha})"


class MotivacionUsuario(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    motivo = models.TextField()

    def __str__(self):
        return f"{self.user.username} — {self.fecha}"


class MensajeJOI(models.Model):
    TRIGGER_CHOICES = [
        ('entreno_completado',          'Entreno completado'),
        ('apertura_manana',             'Apertura matutina'),
        ('ausencia_detectada',          'Ausencia sin lesión'),
        ('carga_anomala',               'Carga anómala ACWR'),
        ('pr_roto',                     'Récord personal'),
        ('lesion_activa',               'Lesión activa'),
        ('fin_bloque',                  'Fin de bloque'),
        ('hyrox_sesion_completada',     'Hyrox — sesión completada'),
        ('hyrox_readiness_bajo',        'Hyrox — readiness bajo'),
        ('hyrox_readiness_alto',        'Hyrox — readiness alto'),
        ('hyrox_cuenta_regresiva',      'Hyrox — cuenta regresiva'),
        ('hyrox_simulacion_completada', 'Hyrox — simulación completada'),
        ('hyrox_ausencia',              'Hyrox — ausencia detectada'),
        ('decision_plan',               'Decisión del plan — intervención'),
        ('resumen_semanal',             'Resumen semanal — qué aprendió el plan'),
        ('hyrox_estancamiento_estacion', 'Hyrox — estancamiento por estación'),
        ('hyrox_deload_automatico',      'Hyrox — deload automático por TSB'),
        ('rpe_calibracion',             'Calibración RPE personal'),
        ('sintesis_joi',                'Síntesis autónoma — JOI en su propio tiempo'),
        ('poda_manual',                 'Poda mensual del Manual de David'),
        ('dialogo_respondido',          'Respuesta a diálogo de narrativa'),
        ('lectura_plan',                'Lectura del plan — estado de las rutinas'),
    ]

    FEEDBACK_CHOICES = [
        ('clavado',    'Lo has clavado'),
        ('equivocado', 'Te has equivocado'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mensajes_joi')
    trigger     = models.CharField(max_length=40, choices=TRIGGER_CHOICES)
    mensaje     = models.TextField()
    contexto    = models.JSONField(default=dict)   # datos que usó JOI para generar el mensaje
    leido       = models.BooleanField(default=False)
    feedback    = models.CharField(max_length=20, choices=FEEDBACK_CHOICES, null=True, blank=True)
    creado_en   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"JOI → {self.user.username} [{self.trigger}] {self.creado_en.date()}"


class ManualDavid(models.Model):
    """
    Lo que JOI ha aprendido sobre cómo leer al usuario.
    Se actualiza cuando el usuario corrige una interpretación errónea.
    Se poda mensualmente: el usuario decide qué sigue siendo verdad.
    """
    ORIGEN_CHOICES = [
        ('feedback_error',   'Corrección de interpretación'),
        ('patron_detectado', 'Patrón deducido por JOI'),
    ]

    TIPO_CHOICES = [
        ('dato_usuario',  'Dato del usuario'),
        ('preferencia',   'Preferencia'),
        ('patron',        'Patrón'),
        ('hipotesis',     'Hipótesis'),
        ('limite',        'Límite'),
        ('contradiccion', 'Contradicción'),
    ]

    ESTADO_CHOICES = [
        ('activa',     'Activa'),
        ('debilitada', 'Debilitada'),
        ('cuestionada','Cuestionada'),
        ('descartada', 'Descartada'),
    ]

    user               = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_david')
    entrada            = models.TextField(help_text="Lo que JOI aprendió, en una frase.")
    origen             = models.CharField(max_length=20, choices=ORIGEN_CHOICES)
    tipo               = models.CharField(max_length=20, choices=TIPO_CHOICES, default='hipotesis')
    confianza          = models.FloatField(default=0.7, help_text="0.0–1.0. Decae con tiempo; se refuerza con evidencia.")
    estado             = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='activa')
    hipotesis_contraria = models.TextField(
        blank=True, null=True,
        help_text="Interpretación alternativa que compite con esta hipótesis.",
    )
    activa             = models.BooleanField(default=True)
    fuente_mensaje     = models.ForeignKey(
        'MensajeJOI', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='entradas_manual',
    )
    creado_en          = models.DateTimeField(auto_now_add=True)
    ultima_evidencia   = models.DateField(null=True, blank=True)
    notas_revision     = models.TextField(
        null=True, blank=True,
        help_text="Razón del último cambio de confianza/estado, registrada por JOI.",
    )

    class Meta:
        ordering = ['creado_en']

    def __str__(self):
        tag = 'activa' if self.activa else 'podada'
        return f"Manual [{self.tipo}/{self.estado}] {self.user.username}: {self.entrada[:60]} ({tag})"


class NarrativaActiva(models.Model):
    """
    Postura interpretativa actual de JOI sobre el usuario.
    Una sola entrada por usuario. Tres capas con velocidades de actualización distintas:
    - capa_corta:  estado reciente (días/semana). Se actualiza en cada revisión significativa.
    - capa_media:  trayectoria de semanas. Solo si capa_corta lleva ≥14 días con patrón estable.
    - capa_larga:  identidad y patrones profundos. Solo si capa_media estable ≥28 días o por diálogo.
    `texto` es la versión renderizada combinada de las tres, para prompts y UI.
    """
    ESTADO_CHOICES = [
        ('borrador',   'Borrador'),
        ('activa',     'Activa'),
        ('cuestionada','Cuestionada'),
        ('congelada',  'Congelada'),
        ('descartada', 'Descartada'),
    ]

    user                   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='narrativa_joi')
    # Capa de renderizado combinado (para prompts y display)
    texto                  = models.TextField(
        blank=True, default='',
        help_text="Renderizado combinado de las tres capas. No editar directamente.",
    )
    # Tres capas temporales
    capa_corta             = models.TextField(null=True, blank=True,
                                              help_text="Estado reciente (días/semana).")
    capa_media             = models.TextField(null=True, blank=True,
                                              help_text="Trayectoria de semanas.")
    capa_larga             = models.TextField(null=True, blank=True,
                                              help_text="Identidad y patrones profundos.")
    # Timestamps de actualización por capa (para reglas de promoción)
    capa_corta_actualizada = models.DateField(null=True, blank=True)
    capa_media_actualizada = models.DateField(null=True, blank=True)
    capa_larga_actualizada = models.DateField(null=True, blank=True)
    # Meta
    estado                 = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='borrador')
    confianza              = models.FloatField(default=0.5)
    version                = models.PositiveIntegerField(default=1)
    ultima_revision_manual = models.DateTimeField(null=True, blank=True)
    creado_en              = models.DateTimeField(auto_now_add=True)
    actualizado_en         = models.DateTimeField(auto_now=True)

    def render_texto(self) -> str:
        """Combina las capas disponibles en un texto fluido para prompts y UI."""
        parts = [c for c in [self.capa_larga, self.capa_media, self.capa_corta] if c]
        return ' '.join(parts)

    def __str__(self):
        capas = sum(1 for c in [self.capa_corta, self.capa_media, self.capa_larga] if c)
        return f"Narrativa JOI [{self.estado}] {self.user.username} v{self.version} ({capas}/3 capas)"


class DialogoNarrativa(models.Model):
    """
    El usuario responde a un fragmento de la NarrativaActiva.
    No es feedback binario — es co-interpretación.

    El usuario aporta significado. JOI calcula impacto (tipos_detectados,
    delta_confianza_calculado) en el siguiente ciclo (≥4h después).
    La respuesta visible —si existe— llega como MensajeJOI, no como confirmación inmediata.
    """
    CAPA_CHOICES = [
        ('corto',   'Corto plazo — ahora mismo'),
        ('medio',   'Medio plazo — esta fase'),
        ('largo',   'Largo plazo — patrón profundo'),
        ('general', 'General'),
    ]

    TIPO_CHOICES = [
        ('matiz',            'Matiz'),
        ('contradiccion',    'Contradicción'),
        ('actualizacion',    'Actualización'),
        ('desfase_temporal', 'Desfase temporal'),
        ('ampliacion',       'Ampliación'),
    ]

    user                      = models.ForeignKey(User, on_delete=models.CASCADE,
                                                   related_name='dialogos_narrativa')
    narrativa                 = models.ForeignKey(NarrativaActiva, on_delete=models.CASCADE,
                                                   related_name='dialogos')
    texto_usuario             = models.TextField(help_text="Lo que el usuario escribió. Significado, no estructura.")
    capa_afectada             = models.CharField(max_length=10, choices=CAPA_CHOICES, default='general')
    tipos_detectados          = models.JSONField(default=list,
                                                  help_text="Lista de tipos detectados por JOI al procesar.")
    delta_confianza_calculado = models.FloatField(default=0.0,
                                                   help_text="Calculado por JOI. No fijado por el usuario.")
    procesado                 = models.BooleanField(default=False)
    procesado_en              = models.DateTimeField(null=True, blank=True)
    creado_en                 = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en']

    def __str__(self):
        estado = 'procesado' if self.procesado else 'pendiente'
        return f"Diálogo [{estado}] {self.user.username}: {self.texto_usuario[:60]}"
