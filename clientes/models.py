from django.db import models
from django.conf import settings
from rutinas.models import Rutina
from django import forms
from django.utils import timezone
# En tu archivo models.py (o donde tengas tus modelos)
from django.db import models

# from models import Cliente  # Asegúrate de que tu modelo Cliente esté importado

from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class SugerenciaAceptada(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)
    semana_inicio = models.DateField()
    tipo = models.CharField(max_length=20, choices=[
        ('subir', 'Subir carga'),
        ('bajar', 'Bajar carga'),
        ('mantener', 'Mantener carga')
    ])
    aceptada = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_tipo_display()} ({'✅' if self.aceptada else '❌'})"


class MiniReto(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)
    semana_inicio = models.DateField()
    descripcion = models.CharField(max_length=200)
    cumplido = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.descripcion} ({'✅' if self.cumplido else '❌'})"


class EstadoSemanal(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)
    semana_inicio = models.DateField()
    semana_fin = models.DateField()
    promedio_sueno = models.DecimalField(max_digits=4, decimal_places=2)
    promedio_rpe = models.DecimalField(max_digits=4, decimal_places=2)
    humor_dominante = models.CharField(max_length=20, choices=[
        ('verde', '😊 Bien'),
        ('amarillo', '😐 Neutro'),
        ('rojo', '😞 Bajo')
    ])
    mensaje_joi = models.TextField(blank=True)
    sugerencia = models.TextField(blank=True, null=True)  # ← AÑADIDO

    def __str__(self):
        return f"Semana {self.semana_inicio} - {self.semana_fin} ({self.cliente})"


class BitacoraDiaria(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)

    # --- INICIO DE LA CORRECCIÓN ---
    horas_sueno = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    humor = models.CharField(max_length=20, choices=[
        ('verde', '😊 Bien'),
        ('amarillo', '😐 Neutro'),
        ('rojo', '😞 Bajo')
    ], null=True, blank=True)
    rpe = models.PositiveSmallIntegerField(help_text="Esfuerzo percibido (1-10)", null=True, blank=True)
    # --- FIN DE LA CORRECCIÓN ---

    nota_personal = models.TextField(blank=True, null=True)  # Es bueno añadir null=True también a los TextField
    mindfulness_am = models.BooleanField(default=False)
    mindfulness_pm = models.BooleanField(default=False)
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    energia_subjetiva = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Energía subjetiva de 0 a 10")
    dolor_articular = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Dolor articular de 0 a 10")
    autoconciencia = models.TextField(null=True, blank=True, help_text="¿Qué emoción domina (0-10)?")
    descarga_cognitiva = models.TextField(null=True, blank=True, help_text="Escribe 5’ “lo que me preocupa AHORA”")
    rumiacion_baja = models.BooleanField(null=True, blank=True, help_text="¿La rumiación bajó después de escribir?")
    circunferencia_biceps = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    emocion_dia = models.CharField(max_length=100, blank=True, null=True)
    cosas_positivas = models.TextField(blank=True, null=True, help_text="Escribe 3 cosas que funcionaron hoy.")
    aprendizaje = models.TextField(blank=True, null=True)
    quien_quiero_ser = models.TextField(blank=True, null=True,
                                        help_text="Describe qué tipo de persona quieres ser hoy.")
    tareas_dia = models.TextField(blank=True, null=True,
                                  help_text="Escribe hasta 5 tareas importantes para hoy, separadas por saltos de línea.")
    que_puedo_mejorar = models.TextField(blank=True, null=True,
                                         help_text="Reflexiona sobre qué podrías mejorar del día.")
    reflexion_diaria = models.TextField(blank=True, null=True, help_text="Escribe una reflexión libre sobre tu día.")
    limito_socialmente = models.BooleanField(null=True, help_text="¿Respondiste solo, sin iniciar?")
    check_in_energia = models.CharField(max_length=10, choices=[
        ('si', 'Sí, doy más de lo que recibo'),
        ('no', 'No, está equilibrado'),
        ('duda', 'No estoy seguro/a')
    ], blank=True, null=True)

    def __str__(self):
        return f"{self.cliente} - {self.fecha}"

    class Meta:
        indexes = [
            models.Index(fields=['cliente', 'fecha'], name='bitacora_cliente_fecha_idx'),
        ]


class ObjetivoCliente(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='objetivos')
    medida = models.CharField(max_length=20, choices=[
        ('peso', 'Peso (kg)'),
        ('grasa', 'Grasa corporal (%)'),
        ('cintura', 'Cintura (cm)'),
    ])
    valor = models.FloatField()
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('cliente', 'medida')

    def __str__(self):
        return f"{self.cliente.nombre} - {self.get_medida_display()}: {self.valor}"


class RevisionProgreso(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='revisiones')
    fecha = models.DateField(auto_now_add=True)
    peso_corporal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grasa_corporal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cintura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pecho = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    biceps = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    muslos = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    hombro = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cuello = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    antebrazos = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    caderas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    gemelos = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['fecha']

    def check_alerts(self):
        alertas = []
        if self.grasa_corporal and self.grasa_corporal > 30:
            alertas.append("Grasa corporal alta")
        if self.peso_corporal and self.peso_corporal < 50:
            alertas.append("Peso corporal muy bajo")
        return alertas if alertas else None

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha}"


# Archivo: clientes/models.py

from django.db import models
from django.conf import settings  # Es una buena práctica importar settings


class Cliente(models.Model):
    # --- Tus campos existentes ---
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cliente_perfil',
                                null=True, blank=True)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    genero = models.CharField(max_length=10, choices=[('M', 'Masculino'), ('F', 'Femenino')], blank=True)
    programa = models.ForeignKey('rutinas.Programa', on_delete=models.SET_NULL, null=True, blank=True)
    rutina_actual = models.ForeignKey('rutinas.Rutina', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_registro = models.DateField(auto_now_add=True)
    membresia_activa = models.BooleanField(default=True)
    fecha_vencimiento_membresia = models.DateField(null=True, blank=True)
    proximo_registro_peso = models.DateField(null=True, blank=True)

    # Campos físicos
    peso_corporal = models.FloatField(null=True, blank=True, help_text="kg")
    grasa_corporal = models.FloatField(null=True, blank=True, help_text="%")
    cintura = models.FloatField(null=True, blank=True, help_text="cm")
    pecho = models.FloatField(null=True, blank=True, help_text="cm")
    hombro = models.FloatField(null=True, blank=True, help_text="cm")
    cuello = models.FloatField(null=True, blank=True, help_text="cm")
    biceps = models.FloatField(null=True, blank=True, help_text="cm")
    antebrazos = models.FloatField(null=True, blank=True, help_text="cm")
    caderas = models.FloatField(null=True, blank=True, help_text="cm")
    muslos = models.FloatField(null=True, blank=True, help_text="cm")
    gemelos = models.FloatField(null=True, blank=True, help_text="cm")
    entrenos_perfectos = models.PositiveIntegerField(default=0)
    # NIVEL 1: ADHERENCIA
    dias_disponibles = models.IntegerField(
        default=4,
        help_text="Días por semana disponibles para entrenar"
    )
    tiempo_por_sesion = models.IntegerField(
        default=90,
        help_text="Minutos disponibles por sesión"
    )
    ejercicios_preferidos = models.JSONField(
        default=list,
        help_text="Lista de ejercicios que le gustan al cliente"
    )
    ejercicios_evitar = models.JSONField(
        default=list,
        help_text="Lista de ejercicios que el cliente no puede/quiere hacer"
    )
    flexibilidad_horario = models.BooleanField(
        default=True,
        help_text="¿Puede cambiar horarios si es necesario?"
    )
    perfil_nutricion = models.OneToOneField(
        'nutricion_app_django.UserProfile',  # Usamos string para evitar importación circular
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_asociado',
        verbose_name="Perfil de Nutrición"
    )
    # ============ AUTORREGULACIÓN ============
    nivel_estres = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Nivel de estrés actual (1-10)"
    )
    calidad_sueño = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Calidad del sueño (1-10)"
    )
    nivel_energia = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Nivel de energía general (1-10)"
    )

    # ============ DATOS TÉCNICOS ============
    one_rm_data = models.JSONField(
        default=dict,
        help_text="Datos de 1RM por ejercicio: {'sentadilla': 100, 'press_banca': 80}"
    )
    historial_volumen = models.JSONField(
        default=dict,
        help_text="Series por semana históricas por grupo muscular"
    )
    # Foto (usamos tu campo 'foto' existente y le añadimos un default)
    foto = models.ImageField(upload_to='clientes_fotos/', null=True, blank=True, default='clientes_fotos/default.png')
    experiencia_años = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Años de experiencia entrenando de forma consistente.",
        verbose_name="Años de experiencia"
    )
    # Campo para el objetivo principal del cliente (NUEVO)
    OBJETIVO_CHOICES = [
        ('hipertrofia', 'Hipertrofia Muscular'),
        ('fuerza', 'Ganancia de Fuerza'),
        ('perdida_peso', 'Pérdida de Peso'),
        ('resistencia', 'Mejora de Resistencia'),
        ('general', 'Salud General'),
    ]
    objetivo_principal = models.CharField(
        max_length=50,
        choices=OBJETIVO_CHOICES,
        default='general',
        help_text="El objetivo principal del cliente para personalizar su experiencia."
    )
    # ============================================================================
    # NIVEL 1: ADHERENCIA (Base fundamental del sistema Helms)
    # ============================================================================

    dias_disponibles = models.IntegerField(
        default=4,
        validators=[MinValueValidator(2), MaxValueValidator(7)],
        help_text="Días reales por semana que puede entrenar (2-7)",
        verbose_name="Días disponibles por semana"
    )

    tiempo_por_sesion = models.IntegerField(
        default=90,
        validators=[MinValueValidator(30), MaxValueValidator(180)],
        help_text="Minutos reales disponibles por sesión (30-180)",
        verbose_name="Tiempo por sesión (minutos)"
    )

    ejercicios_preferidos = models.JSONField(
        default=list,
        help_text="Ejercicios que disfruta hacer - mejora adherencia",
        verbose_name="Ejercicios preferidos"
    )

    ejercicios_evitar = models.JSONField(
        default=list,
        help_text="Ejercicios que no puede/quiere hacer - lesiones, limitaciones",
        verbose_name="Ejercicios a evitar"
    )

    flexibilidad_horario = models.BooleanField(
        default=True,
        help_text="¿Puede cambiar horarios si surge un imprevisto?",
        verbose_name="Flexibilidad de horario"
    )

    # ============================================================================
    # AUTORREGULACIÓN (Adaptación inteligente del programa)
    # ============================================================================

    nivel_estres = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Nivel de estrés actual (1=muy bajo, 10=muy alto)",
        verbose_name="Nivel de estrés"
    )

    calidad_sueño = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Calidad del sueño (1=muy mala, 10=excelente)",
        verbose_name="Calidad del sueño"
    )

    nivel_energia = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Nivel de energía general (1=muy bajo, 10=muy alto)",
        verbose_name="Nivel de energía"
    )

    # ============================================================================
    # DATOS TÉCNICOS AVANZADOS
    # ============================================================================

    one_rm_data = models.JSONField(
        default=dict,
        help_text="1RM por ejercicio: {'sentadilla': 100, 'press_banca': 80, 'peso_muerto': 120}",
        verbose_name="Datos de 1RM"
    )

    historial_volumen = models.JSONField(
        default=dict,
        help_text="Series por semana por grupo muscular: {'pecho': 16, 'espalda': 18, 'piernas': 20}",
        verbose_name="Historial de volumen"
    )

    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================

    def get_nivel_experiencia(self):
        """Determina el nivel según años de experiencia"""
        if self.experiencia_años < 1:
            return 'principiante'
        elif self.experiencia_años < 3:
            return 'intermedio'
        else:
            return 'avanzado'

    def get_factor_recuperacion(self):
        """Calcula factor de recuperación basado en autorregulación"""
        # Promedio de estrés (invertido), sueño y energía
        estres_invertido = 11 - self.nivel_estres
        promedio = (estres_invertido + self.calidad_sueño + self.nivel_energia) / 3
        return promedio / 10  # Factor entre 0.1 y 1.0

    def necesita_descarga(self):
        """Determina si necesita una semana de descarga"""
        factor_recuperacion = self.get_factor_recuperacion()
        return factor_recuperacion < 0.6  # Si está por debajo del 60%

    def get_ejercicios_permitidos(self):
        """Lista de ejercicios que puede hacer (excluyendo los que evita)"""
        todos_ejercicios = [
            'sentadilla', 'press_banca', 'peso_muerto', 'press_militar',
            'remo_con_barra', 'dominadas', 'fondos', 'curl_biceps',
            'extension_triceps', 'elevaciones_laterales', 'peso_muerto_rumano'
        ]
        return [ej for ej in todos_ejercicios if ej not in self.ejercicios_evitar]

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return f"{self.nombre} - {self.get_nivel_experiencia().title()}"


class Medida(models.Model):
    nombre = models.CharField(max_length=100)
    valor = models.FloatField(null=True, blank=True)
    unidad = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.nombre}: {self.valor} {self.unidad}"


class PlanNutricional(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='planes_nutricionales')
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    edad = models.IntegerField()
    genero = models.CharField(max_length=1)  # 'M' o 'F'
    altura_cm = models.DecimalField(max_digits=5, decimal_places=2)
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2)
    nivel_actividad = models.CharField(max_length=20)
    objetivo = models.CharField(max_length=20)

    calorias_estimadas = models.DecimalField(max_digits=7, decimal_places=2)
    gramos_proteinas = models.DecimalField(max_digits=7, decimal_places=2)
    gramos_grasas = models.DecimalField(max_digits=7, decimal_places=2)
    gramos_carbohidratos = models.DecimalField(max_digits=7, decimal_places=2)

    plan_generado_texto = models.TextField()  # Para guardar el texto completo del plan de la IA

    # Puedes añadir más campos para el plan detallado si la IA lo genera estructurado
    # desayuno = models.TextField(blank=True, null=True)
    # almuerzo = models.TextField(blank=True, null=True)
    # cena = models.TextField(blank=True, null=True)
    # snacks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Plan nutricional para {self.cliente.nombre} - {self.objetivo} ({self.fecha_generacion.strftime('%Y-%m-%d')})"


from django.db import models
from django.conf import settings  # Necesario para settings.AUTH_USER_MODEL


# from django.contrib.auth.models import User # También podrías importar User directamente

# ... tus otras clases de modelo (DietaAsignada, ObjetivoCliente, RevisionProgreso, Cliente, Medida, PlanNutricional) ...

# AÑADE ESTA CLASE UserProfile SI ES TU INTENCIÓN TENERLA
class UserProfile(models.Model):
    # Relación uno a uno con el modelo de usuario de Django
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_profile')

    # Añade aquí otros campos específicos del perfil de usuario si los tienes
    # Por ejemplo:
    # avatar = models.ImageField(upload_to='user_avatars/', null=True, blank=True)
    # bio = models.TextField(blank=True)

    def __str__(self):
        return self.user.username


# Modelos para el control de peso y evolución (inspirado en HappyScale)

class PesoDiario(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='registros_peso')
    fecha = models.DateField(auto_now_add=True, unique=True)  # Se registra una vez al día
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "Peso Diario"
        verbose_name_plural = "Pesos Diarios"
        ordering = ['-fecha']
        unique_together = ('cliente', 'fecha')  # Asegura que un cliente solo tenga un registro por día

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha}: {self.peso_kg} kg"


class ObjetivoPeso(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='objetivos_peso')
    peso_objetivo_kg = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_inicio = models.DateField(auto_now_add=True)
    fecha_fin = models.DateField(null=True, blank=True)
    alcanzado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Objetivo de Peso"
        verbose_name_plural = "Objetivos de Peso"
        ordering = ['-fecha_inicio']

    def __str__(self):
        estado = "(Alcanzado)" if self.alcanzado else ""
        return f"{self.cliente.nombre} - Objetivo: {self.peso_objetivo_kg} kg {estado}"


class FaseCliente(models.Model):
    FASE_CHOICES = [
        ('volumen', 'Hipertrofia (Volumen)'),
        ('definicion', 'Definición (Corte)'),
        ('mantenimiento', 'Mantenimiento'),
        ('descarga', 'Descarga (Deload)'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='fases')
    fase = models.CharField(max_length=20, choices=FASE_CHOICES)
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = "Fase del Cliente"
        verbose_name_plural = "Fases del Cliente"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.get_fase_display()} ({self.fecha_inicio})"
