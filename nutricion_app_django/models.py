from django.db import models
from django.contrib.auth.models import User


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
        """Calcula y devuelve el número de niveles de la pirámide completados."""
        # 'progresonivel_set' es la forma en que Django accede a la relación inversa
        # desde UserProfile hacia ProgresoNivel.
        return self.progresonivel_set.filter(completado=True).count()

    def get_ultimo_calculo_nivel1(self):
        """Devuelve el último cálculo del Nivel 1, o None si no existe."""
        # 'calculonivel1_set' es la relación inversa.
        return self.calculonivel1_set.order_by('-fecha_calculo').first()

    def get_ultimo_calculo_nivel2(self):
        """Devuelve el último cálculo del Nivel 2, o None si no existe."""
        return self.calculonivel2_set.order_by('-fecha_calculo').first()

    def get_progreso_piramide(self):
        """
        Devuelve una lista con el estado de cada nivel de la pirámide.
        Esto es perfecto para iterar en la plantilla.
        """
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
        """Determina cuál es el siguiente paso lógico para el usuario."""
        progreso = self.get_progreso_piramide()
        if not progreso[0]['completado']:
            return "Configura tu balance energético para establecer tus calorías objetivo."
        elif not progreso[1]['completado']:
            return "Define tus macronutrientes para optimizar tu composición corporal."
        elif not progreso[2]['completado']:
            return "Aprende sobre micronutrientes y hidratación para tu salud general."
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
