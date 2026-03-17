

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
        ProsocheHabito,
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
