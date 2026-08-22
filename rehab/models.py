from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from clientes.models import Cliente


class ProtocoloRehab(models.Model):
    slug = models.CharField(max_length=100)
    version = models.IntegerField()
    nombre = models.CharField(max_length=150)
    zona = models.CharField(max_length=100)
    descripcion = models.TextField()
    fuente_referencia = models.TextField()
    criterios_alta = models.JSONField(default=dict)
    advertencias = models.TextField()
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('slug', 'version')

    def __str__(self):
        return f"{self.nombre} v{self.version}"


class FaseProtocolo(models.Model):
    protocolo = models.ForeignKey(ProtocoloRehab, on_delete=models.CASCADE, related_name='fases')
    orden = models.PositiveIntegerField()
    slug = models.CharField(max_length=100)
    nombre = models.CharField(max_length=150)
    objetivo = models.TextField()
    duracion_minima_dias = models.PositiveIntegerField()
    duracion_tipica_dias = models.PositiveIntegerField()
    reglas_avance = models.JSONField(default=dict)
    reglas_retroceso = models.JSONField(default=dict)
    descripcion = models.TextField()

    def __str__(self):
        return f"{self.protocolo.nombre} · {self.nombre}"


def validar_risk_tags(value):
    if not isinstance(value, list) or not value or any(
        not isinstance(tag, str) or not tag.strip() or tag != tag.strip().lower()
        for tag in value
    ):
        raise ValidationError('risk_tags debe ser una lista no vacía de tokens normalizados.')
    if len(value) != len(set(value)):
        raise ValidationError('risk_tags no admite duplicados.')


class ContratoRiesgoGymFaseRehab(models.Model):
    """Contrato declarativo publicado. Fase 6.7A no lo ejecuta sobre Gym."""

    ACTION_CHOICES = [('sostener', 'Sostener')]
    SCOPE_CHOICES = [('matching_exercises', 'Ejercicios coincidentes')]
    RED_FLAG_ACTION_CHOICES = [('proteger', 'Proteger')]

    fase = models.ForeignKey(FaseProtocolo, on_delete=models.PROTECT, related_name='contratos_riesgo_gym')
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    schema_version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    risk_tags = models.JSONField(validators=[validar_risk_tags])
    pain_hold_min = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    freshness_days = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1)])
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='sostener')
    scope = models.CharField(max_length=30, choices=SCOPE_CHOICES, default='matching_exercises')
    red_flag_action = models.CharField(max_length=20, choices=RED_FLAG_ACTION_CHOICES, default='proteger')
    activo = models.BooleanField(default=True)
    vigente_desde = models.DateTimeField(default=timezone.now)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fase', 'version'], name='rehab_contrato_fase_version_unico'),
        ]

    def clean(self):
        super().clean()
        if self.activo and self.fase_id:
            conflict = type(self).objects.filter(fase_id=self.fase_id, activo=True)
            if self.pk:
                conflict = conflict.exclude(pk=self.pk)
            if conflict.exists():
                raise ValidationError({'activo': 'Solo puede existir un contrato activo por fase.'})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.fase_id:
                FaseProtocolo.objects.select_for_update().get(pk=self.fase_id)
            if self.pk and type(self).objects.filter(pk=self.pk).exists():
                persisted = type(self).objects.get(pk=self.pk)
                editable = ('fase_id', 'version', 'schema_version', 'risk_tags', 'pain_hold_min',
                            'freshness_days', 'action', 'scope', 'red_flag_action', 'activo',
                            'vigente_desde')
                if any(getattr(self, field) != getattr(persisted, field) for field in editable):
                    raise ValidationError('Un contrato publicado es inmutable; publique una sucesora.')
            self.full_clean()
            return super().save(*args, **kwargs)


class EjercicioRehab(models.Model):
    TIPO_CONTRACCION_CHOICES = [
        ('isometrico', 'Isométrico'),
        ('isotonico_lento', 'Isotónico lento'),
        ('pliometrico', 'Pliométrico'),
        ('movilidad', 'Movilidad'),
    ]

    nombre = models.CharField(max_length=150)
    slug = models.CharField(max_length=150, unique=True)
    tipo_contraccion = models.CharField(max_length=20, choices=TIPO_CONTRACCION_CHOICES)
    descripcion_ejecucion = models.TextField()
    equipo = models.CharField(max_length=150, blank=True)
    nombre_equivalente_gym = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return self.nombre


class PrescripcionEjercicio(models.Model):
    fase = models.ForeignKey(FaseProtocolo, on_delete=models.CASCADE, related_name='prescripciones')
    ejercicio = models.ForeignKey(EjercicioRehab, on_delete=models.CASCADE)
    orden = models.PositiveIntegerField()
    series = models.PositiveIntegerField()
    frecuencia_semanal = models.PositiveIntegerField()
    parametros = models.JSONField(default=dict)
    notas = models.TextField(blank=True)

    def __str__(self):
        return f"{self.fase} · {self.ejercicio.nombre}"


class EpisodioRehab(models.Model):
    LATERALIDAD_CHOICES = [
        ('izquierda', 'Izquierda'),
        ('derecha', 'Derecha'),
        ('bilateral', 'Bilateral'),
    ]
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('PAUSADO', 'Pausado'),
        ('ALTA', 'Alta'),
        ('ABANDONADO', 'Abandonado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='episodios_rehab')
    protocolo = models.ForeignKey(ProtocoloRehab, on_delete=models.CASCADE, related_name='episodios')
    protocolo_version = models.IntegerField()
    fase_actual = models.ForeignKey(
        FaseProtocolo, on_delete=models.SET_NULL, null=True, blank=True, related_name='episodios_en_curso'
    )
    lateralidad = models.CharField(max_length=20, choices=LATERALIDAD_CHOICES)
    fecha_inicio = models.DateField()
    fase_actual_desde = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')
    dolor_basal_inicial = models.PositiveSmallIntegerField()
    notas = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'protocolo'],
                condition=Q(estado='ACTIVO'),
                name='un_episodio_activo_por_protocolo',
            ),
        ]

    def __str__(self):
        return f"{self.cliente} · {self.protocolo.nombre} ({self.estado})"


class RegistroDiarioRehab(models.Model):
    episodio = models.ForeignKey(EpisodioRehab, on_delete=models.CASCADE, related_name='registros_diarios')
    fecha = models.DateField()
    dolor_manana = models.PositiveSmallIntegerField()
    rigidez_manana = models.PositiveSmallIntegerField()
    bandera_roja = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    class Meta:
        unique_together = ('episodio', 'fecha')

    def __str__(self):
        return f"{self.episodio} · {self.fecha}"


class SesionRehab(models.Model):
    ESTADO_CHOICES = [
        ('COMPLETADA', 'Completada'),
        ('PARCIAL', 'Parcial'),
        ('OMITIDA', 'Omitida'),
    ]

    episodio = models.ForeignKey(EpisodioRehab, on_delete=models.CASCADE, related_name='sesiones')
    fase = models.ForeignKey(FaseProtocolo, on_delete=models.CASCADE, related_name='sesiones')
    fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    dolor_durante = models.PositiveSmallIntegerField()
    dolor_post_24h = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_min = models.PositiveIntegerField(null=True, blank=True)
    prescripcion_snapshot = models.JSONField(default=dict)
    notas = models.TextField(blank=True)

    def __str__(self):
        return f"{self.episodio} · {self.fecha} ({self.estado})"


class EjercicioSesionRehab(models.Model):
    sesion = models.ForeignKey(SesionRehab, on_delete=models.CASCADE, related_name='ejercicios')
    prescripcion = models.ForeignKey(PrescripcionEjercicio, on_delete=models.CASCADE)
    series_completadas = models.PositiveIntegerField()
    carga_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    dolor_ejercicio = models.PositiveSmallIntegerField(null=True, blank=True)
    completado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sesion} · {self.prescripcion.ejercicio.nombre}"


class TransicionFase(models.Model):
    DIRECCION_CHOICES = [
        ('INICIO', 'Inicio'),
        ('AVANCE', 'Avance'),
        ('RETROCESO', 'Retroceso'),
        ('ALTA', 'Alta'),
    ]

    episodio = models.ForeignKey(EpisodioRehab, on_delete=models.CASCADE, related_name='transiciones')
    fase_desde = models.ForeignKey(
        FaseProtocolo, on_delete=models.SET_NULL, null=True, blank=True, related_name='transiciones_salida'
    )
    fase_hasta = models.ForeignKey(FaseProtocolo, on_delete=models.CASCADE, related_name='transiciones_entrada')
    fecha = models.DateField()
    direccion = models.CharField(max_length=20, choices=DIRECCION_CHOICES)
    motivo = models.CharField(max_length=100)
    automatica = models.BooleanField()
    evidencia = models.JSONField(default=dict)
    confirmada_por_usuario = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.episodio} · {self.direccion} → {self.fase_hasta.nombre}"
