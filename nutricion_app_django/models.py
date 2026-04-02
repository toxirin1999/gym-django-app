from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# ─────────────────────────────────────────────────────────────
# MÓDULO ORIGINAL (pirámide nutricional educativa) — sin tocar
# ─────────────────────────────────────────────────────────────

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    edad = models.IntegerField()
    sexo = models.CharField(max_length=10, choices=[("Masculino", "Masculino"), ("Femenino", "Femenino")])
    peso = models.FloatField()
    altura = models.IntegerField()
    nivel_actividad = models.CharField(max_length=50, choices=[
        ("Sedentario", "Sedentario"),
        ("Ligeramente activo", "Ligeramente activo"),
        ("Activo", "Activo"),
        ("Muy activo", "Muy activo")
    ])
    objetivo = models.CharField(max_length=50, choices=[
        ("Pérdida de grasa", "Pérdida de grasa"),
        ("Mantenimiento", "Mantenimiento"),
        ("Ganancia muscular", "Ganancia muscular")
    ])
    experiencia = models.CharField(max_length=50, choices=[
        ("Novato", "Novato"),
        ("Intermedio", "Intermedio"),
        ("Avanzado", "Avanzado")
    ], default="Intermedio")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def get_niveles_completados(self):
        return self.progresonivel_set.filter(completado=True).count()

    def get_ultimo_calculo_nivel1(self):
        return self.calculonivel1_set.order_by('-fecha_calculo').first()

    def get_ultimo_calculo_nivel2(self):
        return self.calculonivel2_set.order_by('-fecha_calculo').first()

    def get_progreso_piramide(self):
        progreso_guardado = {p.nivel: p for p in self.progresonivel_set.all()}
        lista_progreso = []
        for nivel in range(1, 6):
            progreso_obj = progreso_guardado.get(nivel)
            lista_progreso.append({
                'nivel': nivel,
                'completado': progreso_obj.completado if progreso_obj else False,
                'fecha': progreso_obj.fecha_completado if progreso_obj else None,
            })
        return lista_progreso

    def get_proximo_paso(self):
        progreso = self.get_progreso_piramide()
        if not progreso[0]['completado']:
            return "Configura tu balance energético para establecer tus calorías objetivo."
        elif not progreso[1]['completado']:
            return "Define tus macronutrientes para optimizar tu composición corporal."
        elif not progreso[2]['completado']:
            return "Aprende sobre micronutrientes e hidratación para tu salud general."
        elif not progreso[3]['completado']:
            return "Optimiza el timing de tus comidas para mejorar tu rendimiento."
        elif not progreso[4]['completado']:
            return "Considera qué suplementos pueden beneficiarte."
        else:
            return "¡Felicidades! Has completado toda la pirámide. Mantén la consistencia."

    def __str__(self):
        return self.user.username


class CalculoNivel1(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    calorias_mantenimiento = models.FloatField()
    calorias_objetivo = models.FloatField()
    factor_actividad = models.FloatField()
    deficit_superavit_porcentaje = models.FloatField()
    metodo_calculo = models.CharField(max_length=50)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nivel 1 para {self.user_profile.user.username} - {self.calorias_objetivo} kcal"


class CalculoNivel2(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    proteina_gramos = models.FloatField()
    grasa_gramos = models.FloatField()
    carbohidratos_gramos = models.FloatField()
    proteina_calorias = models.FloatField()
    grasa_calorias = models.FloatField()
    carbohidratos_calorias = models.FloatField()
    proteina_porcentaje = models.FloatField()
    grasa_porcentaje = models.FloatField()
    carbohidratos_porcentaje = models.FloatField()
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nivel 2 para {self.user_profile.user.username}"


class ProgresoNivel(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    nivel = models.IntegerField()
    completado = models.BooleanField(default=False)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    datos_json = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ("user_profile", "nivel")

    def __str__(self):
        return f"Progreso Nivel {self.nivel} para {self.user_profile.user.username}"


class SeguimientoPeso(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    peso = models.FloatField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Peso de {self.user_profile.user.username} - {self.peso} kg ({self.fecha_registro.date()})"


class ConfiguracionNivel3(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    agua_litros = models.FloatField(null=True, blank=True)
    frutas_porciones = models.IntegerField(null=True, blank=True)
    verduras_porciones = models.IntegerField(null=True, blank=True)
    suplementos_recomendados = models.TextField(null=True, blank=True)
    fecha_configuracion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nivel 3 para {self.user_profile.user.username}"


class ConfiguracionNivel4(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    comidas_por_dia = models.IntegerField(null=True, blank=True)
    timing_pre_entreno = models.TextField(null=True, blank=True)
    timing_post_entreno = models.TextField(null=True, blank=True)
    distribucion_macros = models.TextField(null=True, blank=True)
    refeeds_configurados = models.BooleanField(default=False)
    fecha_configuracion = models.DateTimeField(auto_now_add=True)

    def get_timing_pre_entreno_display(self):
        opciones = {
            "carbohidratos": "Carbohidratos principalmente",
            "proteina_carbohidratos": "Proteína + Carbohidratos",
            "comida_completa": "Comida completa normal",
            "ayunas": "Entrenar en ayunas",
        }
        return opciones.get(self.timing_pre_entreno, self.timing_pre_entreno)

    def get_timing_post_entreno_display(self):
        opciones = {
            "proteina_carbohidratos": "Proteína + Carbohidratos",
            "solo_proteina": "Solo proteína",
            "comida_completa": "Comida completa normal",
            "no_prioritario": "No es una prioridad",
        }
        return opciones.get(self.timing_post_entreno, self.timing_post_entreno)

    def get_distribucion_macros_display(self):
        opciones = {
            "uniforme": "Distribución uniforme",
            "post_entreno": "Mayor cantidad post-entrenamiento",
            "extremos": "Mayor cantidad en desayuno y cena",
            "flexible": "Flexible según preferencias",
        }
        return opciones.get(self.distribucion_macros, self.distribucion_macros)

    def __str__(self):
        return f"Nivel 4 para {self.user_profile.user.username}"


class ConfiguracionNivel5(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    creatina = models.BooleanField(default=False)
    proteina_polvo = models.BooleanField(default=False)
    multivitaminico = models.BooleanField(default=False)
    omega3 = models.BooleanField(default=False)
    vitamina_d = models.BooleanField(default=False)
    otros_suplementos = models.TextField(null=True, blank=True)
    fecha_configuracion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nivel 5 para {self.user_profile.user.username}"


# ─────────────────────────────────────────────────────────────
# MÓDULO CIENTÍFICO V2 — Sistema de Bloques + PAS
# ─────────────────────────────────────────────────────────────

class PerfilNutricional(models.Model):
    """
    Datos base del atleta. Se configura una vez en el onboarding.
    Navy Method para composición corporal.
    """
    FASE_CHOICES = [
        ('definicion',   'Definición'),
        ('volumen',      'Volumen'),
        ('peak_week',    'Peak Week'),
        ('mantenimiento','Mantenimiento'),
    ]

    cliente = models.OneToOneField(
        'clientes.Cliente',
        on_delete=models.CASCADE,
        related_name='perfil_nutricional'
    )
    altura_cm = models.FloatField(help_text="Altura en cm")
    fase = models.CharField(max_length=15, choices=FASE_CHOICES, default='mantenimiento')

    # Calculados automáticamente (Navy Method)
    grasa_corporal_pct = models.FloatField(editable=False)
    masa_magra_kg      = models.FloatField(editable=False)

    # Safety locks — nunca bajar de estos valores
    safety_proteina_min_g_kg = models.FloatField(
        default=1.8,
        help_text="g proteína mínimos por kg de masa magra"
    )
    safety_grasa_min_g_kg = models.FloatField(
        default=1.2,
        help_text="g grasa mínimos por kg de peso total"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def _calcular_navy(self):
        import math
        c = self.cliente
        try:
            if c.genero == 'M':
                return (
                    495 / (1.0324 - 0.19077 * math.log10(c.cintura - c.cuello)
                           + 0.15456 * math.log10(self.altura_cm)) - 450
                )
            else:
                return (
                    495 / (1.29579 - 0.35004 * math.log10(c.cintura + c.caderas - c.cuello)
                           + 0.22100 * math.log10(self.altura_cm)) - 450
                )
        except (TypeError, ValueError):
            return 20.0

    def _get_peso_actual(self):
        from clientes.models import PesoDiario
        ultimo = (
            PesoDiario.objects
            .filter(cliente=self.cliente)
            .order_by('-fecha')
            .values_list('peso_kg', flat=True)
            .first()
        )
        if ultimo:
            return float(ultimo)
        self.cliente.refresh_from_db(fields=['peso_corporal'])
        return float(self.cliente.peso_corporal or 0)

    def save(self, *args, **kwargs):
        self.grasa_corporal_pct = self._calcular_navy()
        peso = self._get_peso_actual()
        self.masa_magra_kg = peso * (1 - self.grasa_corporal_pct / 100)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Perfil nutricional — {self.cliente.nombre} ({self.get_fase_display()})"

    class Meta:
        verbose_name = "Perfil Nutricional"
        verbose_name_plural = "Perfiles Nutricionales"


class TargetNutricionalDiario(models.Model):
    """
    Prescripción diaria en bloques Zone.
    1 bloque P = 7g proteína | 1 bloque C = 9g carbos | 1 bloque G = 3g grasa
    """
    TIPO_SESION = [
        ('gym',      'Sesión de Gym'),
        ('hyrox',    'Sesión de Hyrox'),
        ('descanso', 'Día de Descanso'),
    ]

    cliente     = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE,
                                    related_name='targets_nutricionales')
    fecha       = models.DateField()
    tipo_sesion = models.CharField(max_length=10, choices=TIPO_SESION, default='descanso')

    # Bloques del día (calculados por el motor)
    bloques_proteina = models.IntegerField(help_text="1 bloque = 7g proteína")
    bloques_carbos   = models.IntegerField(help_text="1 bloque = 9g carbos netos")
    bloques_grasas   = models.IntegerField(help_text="1 bloque = 3g grasa")
    bloques_verduras = models.IntegerField(default=3, help_text="Bloques fijos de verduras")

    # Gramos de referencia calculados (internos, para el PAS)
    proteina_g_ref = models.IntegerField(default=0)
    carbos_g_ref   = models.IntegerField(default=0)
    grasas_g_ref   = models.IntegerField(default=0)

    # Distribución por comida (JSON): {'desayuno': {'P':1,'C':2,'G':1}, ...}
    distribucion_comidas = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['cliente', 'fecha']
        verbose_name = "Target Nutricional Diario"
        verbose_name_plural = "Targets Nutricionales Diarios"

    def __str__(self):
        return f"{self.cliente.nombre} — {self.fecha} ({self.get_tipo_sesion_display()})"

    @property
    def bloques_totales(self):
        return self.bloques_proteina + self.bloques_carbos + self.bloques_grasas


class CheckNutricionalDiario(models.Model):
    """
    Check-in diario. Biofeedback + cumplimiento de bloques.
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE,
                                related_name='checks_nutricionales')
    fecha   = models.DateField()

    # Cumplimiento de bloques
    bloques_proteina_cumplidos = models.BooleanField(null=True, blank=True)
    bloques_carbos_cumplidos   = models.BooleanField(null=True, blank=True)
    bloques_grasas_cumplidos   = models.BooleanField(null=True, blank=True)
    verduras_cumplidas         = models.BooleanField(null=True, blank=True)
    hidratacion_ok             = models.BooleanField(null=True, blank=True)

    # Biofeedback
    fatiga_percibida   = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Fatiga percibida (1=ninguna, 10=agotamiento total)"
    )
    calidad_sueno      = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Calidad del sueño (1=pésima, 10=perfecta)"
    )
    energia_entreno    = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Energía durante el entreno (1-5)"
    )
    hambre_excesiva    = models.BooleanField(null=True, blank=True)

    # Porcentaje de cumplimiento del día (0-100), calculado al guardar
    cumplimiento_pct   = models.FloatField(default=0.0)

    class Meta:
        unique_together = ['cliente', 'fecha']
        verbose_name = "Check Nutricional Diario"
        verbose_name_plural = "Checks Nutricionales Diarios"

    def calcular_cumplimiento(self):
        """Calcula el % de ítems binarios confirmados como True."""
        campos = [
            self.bloques_proteina_cumplidos,
            self.bloques_carbos_cumplidos,
            self.bloques_grasas_cumplidos,
            self.verduras_cumplidas,
            self.hidratacion_ok,
        ]
        respondidos = [c for c in campos if c is not None]
        if not respondidos:
            return 0.0
        cumplidos = sum(1 for c in respondidos if c is True)
        return round(cumplidos / len(respondidos) * 100, 1)

    def save(self, *args, **kwargs):
        self.cumplimiento_pct = self.calcular_cumplimiento()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente.nombre} — Check {self.fecha} ({self.cumplimiento_pct}%)"


class RegistroBloques(models.Model):
    """
    Lo que el usuario realmente comió en cada toma del día.
    Permite el cálculo de cumplimiento real.
    """
    COMIDA_CHOICES = [
        ('desayuno',  'Desayuno'),
        ('almuerzo',  'Almuerzo'),
        ('cena',      'Cena'),
        ('snack',     'Snack'),
        ('pre',       'Pre-entreno'),
        ('post',      'Post-entreno'),
    ]

    cliente  = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE,
                                 related_name='registros_bloques')
    fecha    = models.DateField()
    comida   = models.CharField(max_length=10, choices=COMIDA_CHOICES)

    bloques_proteina = models.FloatField(default=0)
    bloques_carbos   = models.FloatField(default=0)
    bloques_grasas   = models.FloatField(default=0)

    # Comodín: el usuario marca bloques sin especificar alimento
    es_comodin  = models.BooleanField(default=False)
    nota_comodin = models.CharField(max_length=200, blank=True)

    # Alimentos seleccionados (JSON): [{"id": "pollo", "cantidad_g": 120, "P":4,"C":0,"G":0}]
    alimentos_json = models.JSONField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'comida']
        verbose_name = "Registro de Bloques"
        verbose_name_plural = "Registros de Bloques"

    def __str__(self):
        return f"{self.cliente.nombre} — {self.fecha} {self.get_comida_display()}"


class InformeOptimizacion(models.Model):
    """
    Informe semanal generado por el PAS (Protocolo de Ajuste Semanal).
    Se genera cada lunes.
    """
    ESCENARIO_CHOICES = [
        ('A', 'Óptimo — mantener'),
        ('B', 'Estancado — ajustar bloques'),
        ('C', 'Fatiga/caída — Refeed'),
        ('D', 'Sobreingesta — auditoría'),
        ('X', 'Datos insuficientes'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de revisión'),
        ('aceptado',  'Ajuste aceptado'),
        ('rechazado', 'Semana atípica — sin ajuste'),
    ]

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE,
                                related_name='informes_optimizacion')
    semana  = models.DateField(help_text="Lunes de la semana analizada")

    # Datos de entrada
    media_peso_anterior  = models.FloatField(null=True, blank=True)
    media_peso_nueva     = models.FloatField(null=True, blank=True)
    cumplimiento_semana_pct = models.FloatField(default=0.0)
    fatiga_media         = models.FloatField(null=True, blank=True)
    rendimiento_gym_delta_pct   = models.FloatField(null=True, blank=True,
                                                    help_text="% cambio en volumen total gym")
    rendimiento_hyrox_delta_pct = models.FloatField(null=True, blank=True,
                                                    help_text="% cambio en tiempo/ritmo Hyrox")

    # Diagnóstico
    escenario   = models.CharField(max_length=2, choices=ESCENARIO_CHOICES, default='X')
    alerta_honestidad = models.BooleanField(default=False,
                                            help_text="True si los datos son contradictorios")

    # Ajuste propuesto
    ajuste_bloques_proteina = models.IntegerField(default=0)
    ajuste_bloques_carbos   = models.IntegerField(default=0)
    ajuste_bloques_grasas   = models.IntegerField(default=0)
    ajuste_aplica_a         = models.CharField(
        max_length=20, default='todos',
        help_text="gym | hyrox | descanso | todos — a qué tipo de día aplica"
    )

    # Mensaje legible generado por el algoritmo
    justificacion = models.TextField()

    # Safety lock activado
    safety_lock_activado = models.BooleanField(default=False)
    diet_break_sugerido  = models.BooleanField(default=False)

    # Acción del usuario
    estado         = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='pendiente')
    razon_rechazo  = models.CharField(max_length=200, blank=True)

    creado_en      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cliente', 'semana']
        ordering = ['-semana']
        verbose_name = "Informe de Optimización"
        verbose_name_plural = "Informes de Optimización"

    def __str__(self):
        return f"{self.cliente.nombre} — Semana {self.semana} [{self.get_escenario_display()}]"

    @property
    def delta_peso(self):
        if self.media_peso_anterior and self.media_peso_nueva:
            return round(self.media_peso_nueva - self.media_peso_anterior, 2)
        return None

    @property
    def delta_peso_pct(self):
        if self.media_peso_anterior and self.media_peso_anterior > 0:
            return round((self.delta_peso / self.media_peso_anterior) * 100, 2)
        return None


class AjusteNutricional(models.Model):
    """
    Log histórico de cada ajuste aplicado. Auditoría y transparencia.
    """
    MOTIVO = [
        ('sin_progreso',    'Sin progreso en 2 semanas'),
        ('progreso_rapido', 'Progreso demasiado rápido'),
        ('fatiga_alta',     'Fatiga elevada detectada'),
        ('refeed',          'Refeed técnico'),
        ('diet_break',      'Diet Break obligatorio'),
        ('inicio',          'Configuración inicial'),
    ]

    cliente  = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE,
                                 related_name='ajustes_nutricionales')
    fecha    = models.DateField(auto_now_add=True)
    motivo   = models.CharField(max_length=20, choices=MOTIVO)

    proteina_anterior = models.IntegerField()
    proteina_nuevo    = models.IntegerField()
    carbos_anterior   = models.IntegerField()
    carbos_nuevo      = models.IntegerField()
    grasas_anterior   = models.IntegerField(default=0)
    grasas_nuevo      = models.IntegerField(default=0)

    aplica_a      = models.CharField(max_length=20, default='todos')
    mensaje_usuario = models.TextField()

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Ajuste Nutricional"
        verbose_name_plural = "Ajustes Nutricionales"

    def __str__(self):
        return f"{self.cliente.nombre} — {self.get_motivo_display()} ({self.fecha})"
