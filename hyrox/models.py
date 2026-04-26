from django.db import models, transaction
from django.utils import timezone
from clientes.models import Cliente

class HyroxObjective(models.Model):
    CATEGORIA_CHOICES = [
        ('open_men', 'Open Men'),
        ('open_women', 'Open Women'),
        ('pro_men', 'Pro Men'),
        ('pro_women', 'Pro Women'),
        ('doubles_men', 'Doubles Men'),
        ('doubles_women', 'Doubles Women'),
        ('doubles_mixed', 'Doubles Mixed'),
        ('relay', 'Relay'),
    ]
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('completado', 'Completado'),
        ('cancelado', 'Cancelado')
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='hyrox_objectives')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='open_men')
    fecha_evento = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Perfil Atlético Base para escalar el programa
    rm_peso_muerto = models.FloatField(null=True, blank=True, help_text="kg")
    rm_sentadilla = models.FloatField(null=True, blank=True, help_text="kg")
    tiempo_5k_base = models.CharField(max_length=10, blank=True, null=True, help_text="formato MM:SS")
    
    # Contexto del usuario y Health Check (Fase 8)
    NIVEL_CHOICES = [
        ('principiante', 'Principiante (0-1 año)'),
        ('intermedio', 'Intermedio (1-3 años)'),
        ('avanzado', 'Avanzado (+3 años)')
    ]
    nivel_experiencia = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='intermedio', help_text="Experiencia en fuerza/cardio")
    lesiones_previas = models.TextField(blank=True, help_text="Ej: Rodilla derecha, lumbalgia. Dejar en blanco si no hay.")
    material_disponible = models.TextField(blank=True, help_text="Material del que dispone el usuario")
    
    # Disponibilidad Semanal (Fase 14)
    # Ejemplo de estructura: "0,2,4" (0=Lunes, 6=Domingo)
    dias_preferidos = models.CharField(max_length=20, default="0,2,4,6", help_text="Días de la semana preferidos para entrenar (0=Lunes, 6=Domingo)")

    # ── Fisiología para carga objetiva (TRIMP / Karvonen) ────────────────────
    GENERO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino')]
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, default='M',
        help_text="Factor b del TRIMP: M=1.92, F=1.67")
    fc_max_real = models.IntegerField(null=True, blank=True,
        help_text="FC máxima real medida en prueba de esfuerzo (lpm). Vacío = 220-edad.")
    fc_reposo = models.IntegerField(null=True, blank=True, default=60,
        help_text="FC en reposo por la mañana (lpm). Necesario para TRIMP Karvonen.")

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.get_categoria_display()} ({self.fecha_evento})"

    def get_race_readiness_score(self):
        """
        Race Readiness ponderado con tres factores:
          40% Capacidad Técnica  : progreso en estándares oficiales (peso/distancia)
          30% Eficiencia de Esfuerzo: sesiones donde se logra trabajo con RPE < 8
          30% Resistencia Específica: simulacros (fuerza + carrera en la misma sesión)
        """
        from hyrox.services import CompetitionStandardsService

        # ── Factor 1: Capacidad Técnica (40%) ──────────────────────────────
        try:
            progress = CompetitionStandardsService.get_user_standards_progress(
                self.cliente.user_id
            )
            progresos = progress.get('progreso', [])
            if progresos:
                pct_tecnica = sum(p['porcentaje'] for p in progresos) / len(progresos)
            else:
                # Fallback a RM si no hay estándares
                rm_pm = float(self.rm_peso_muerto or 0)
                rm_sq = float(self.rm_sentadilla or 0)
                targets = {
                    'open_men':     {'pm': 140, 'sq': 120},
                    'open_women':   {'pm': 90,  'sq': 70},
                    'pro_men':      {'pm': 180, 'sq': 150},
                    'pro_women':    {'pm': 110, 'sq': 90},
                    'doubles_men':  {'pm': 130, 'sq': 110},
                    'doubles_women':{'pm': 85,  'sq': 65},
                    'doubles_mixed':{'pm': 110, 'sq': 90},
                    'relay':        {'pm': 130, 'sq': 110},
                }
                t = targets.get(self.categoria, targets['open_men'])
                score_pm = min(rm_pm / t['pm'], 1.0) if rm_pm else 0
                score_sq = min(rm_sq / t['sq'], 1.0) if rm_sq else 0
                pct_tecnica = ((score_pm + score_sq) / 2) * 100
        except Exception:
            pct_tecnica = 0.0

        # ── Factor 2: Eficiencia de Esfuerzo (30%) ─────────────────────────
        # Puntuamos las sesiones en zona óptima de esfuerzo (RPE 5-9).
        # RPE < 5 indica trabajo demasiado fácil (sin estímulo), RPE 10 indica fallo extremo.
        # prefetch_related evita el N+1: carga todas las activities en 1 query adicional
        sesiones_completadas = list(self.sessions.filter(estado='completado').prefetch_related('activities'))
        total_sesiones = len(sesiones_completadas)
        sesiones_eficientes = 0
        for s in sesiones_completadas:
            rpe = s.rpe_global
            if rpe and 5 <= rpe <= 9:
                sesiones_eficientes += 1
        if total_sesiones > 0:
            pct_eficiencia = min((sesiones_eficientes / total_sesiones) * 100, 100)
        else:
            pct_eficiencia = 0.0

        # ── Factor 3: Resistencia Específica (30%) ─────────────────────────
        # Simulacros: sesiones que combinan fuerza/estación + carrera. Ponderan por proximidad.
        simulacros_score = 0.0
        import datetime
        from hyrox.services import HyroxMacrocycleEngine
        if not self.fecha_evento:
            return 0.0
        try:
            fecha_obj = self.fecha_evento if isinstance(self.fecha_evento, datetime.date) else datetime.datetime.strptime(str(self.fecha_evento), "%Y-%m-%d").date()
        except Exception:
            return 0.0

        # Llamada única fuera del bucle para evitar 3 queries repetidas por sesión
        inact, dias_run, tiene_credito_futbol, preguntar_bool = HyroxMacrocycleEngine.detect_running_inactivity(self.cliente.user_id)
        hoy_date = datetime.date.today()

        for s in sesiones_completadas:
            # Usar activities.all() aprovecha el prefetch_related (sin query adicional)
            tipos = set(a.tipo_actividad for a in s.activities.all())
            tiene_fuerza = bool(tipos & {'fuerza', 'hyrox_station', 'hiit'})
            tiene_carrera = bool(tipos & {'carrera', 'cardio_sustituto', 'remo', 'skierg', 'bici'})
            if tiene_fuerza and tiene_carrera:
                if s.fecha:
                    dias_al_evento = (fecha_obj - s.fecha).days

                    puntos_base = 0.5
                    if dias_al_evento <= 56: # Fase de Simulación (8 semanas)
                        puntos_base = 2.0
                    elif dias_al_evento <= 77: # Fase Específica (11 semanas)
                        puntos_base = 1.0

                    if inact and (hoy_date - s.fecha).days <= 3:
                        puntos_base *= 1.40

                    simulacros_score += puntos_base
                else:
                    simulacros_score += 0.5

        pct_resistencia = min((simulacros_score / 8.0) * 100, 100)

        # ── Score global ponderado ──────────────────────────────────────────
        score = pct_tecnica * 0.40 + pct_eficiencia * 0.30 + pct_resistencia * 0.30

        # El floor artificial (max(score,25) si pct_tecnica>50) ha sido eliminado:
        # daba falsa sensación de preparación aunque el atleta no corriera ni simulara.

        # ── Penalización por carga acumulada del gym (últimos 5 días) ──────
        # Si el atleta viene de días pesados de gym, su readiness Hyrox baja.
        try:
            from hyrox.training_engine import HyroxTrainingEngine
            gym_load = HyroxTrainingEngine._get_gym_external_load(self.cliente, dias=5)
            if gym_load['fatiga_gym'] == 'Alta':
                score -= 8   # carga de gym muy alta: impacto directo en readiness
            elif gym_load['fatiga_gym'] == 'Media':
                score -= 4   # carga moderada: penalización menor
        except Exception:
            pass

        # ── Readiness Post-Esfuerzo (Phase 16: Molestias Feedback) ──────────
        last_session = max(sesiones_completadas, key=lambda s: s.fecha or datetime.date.min, default=None)
        if last_session and last_session.hubo_molestias:
            score -= 10

        return min(max(int(score), 0), 100)

    def get_strength_balance(self):
        """
        Phase 10: Calcula el ratio de Empuje (Squat) vs Tracción (Deadlift).
        """
        sq = self.rm_sentadilla or 0
        dl = self.rm_peso_muerto

        if not dl:
            return {"ratio": 0, "advice": "Falta registrar Peso Muerto."}

        ratio = (sq / dl) * 100
        
        # Check Modo Preservación
        from hyrox.models import UserInjury
        lesiones_activas = UserInjury.objects.filter(cliente=self.cliente, activa=True)
        is_preservation = False
        lesion_preservation = ""
        for inj in lesiones_activas:
            tags = inj.tags_restringidos or []
            if 'impacto_vertical' in tags or 'carrera' in tags:
                is_preservation = True
                lesion_preservation = inj.zona_afectada
                break

        alerta_inactividad = ""
        from hyrox.services import HyroxMacrocycleEngine
        inactivo_run, dias_run, tiene_credito_futbol, preguntar_bool = HyroxMacrocycleEngine.detect_running_inactivity(self.cliente.user_id)
        
        if is_preservation:
            alerta_inactividad = f"\n⚕️ MODO PRESERVACIÓN ACTIVO (Lesión {lesion_preservation}): Omitir penalizaciones por días sin carrera. Valora positivamente cualquier cardio sustituto para el Readiness."
        elif preguntar_bool:
            alerta_inactividad = "\n⚠️ ELIMINACIÓN DE CASTIGO: No asumas inactividad directamente. En tu saludo debes preguntar TEXTUALMENTE: 'David, no veo carreras esta semana. ¿Has sumado minutos con el fútbol o necesitamos reajustar el bloque?'"
        elif inactivo_run and not tiene_credito_futbol:
            alerta_inactividad = f"\n⚠️ ALERTA DE INACTIVIDAD AERÓBICA: Lleva {dias_run} días sin correr ni compensar con fútbol. DEBES dedicar tu mensaje a recordarle estrictamente que el motor aeróbico es crítico para el 19 de Abril."
        elif inactivo_run and tiene_credito_futbol:
            dias_penalizados = dias_run // 2 # 50% de reducción visual
            alerta_inactividad = f"\n⚠️ ALERTA MITIGADA: Acumula {dias_run} días sin correr, pero gracias al FÚTBOL la penalización se reduce a un equivalente de {dias_penalizados} días. Recuérdale que el fútbol ayuda como mantenimiento, pero no sustituye la especificidad de Hyrox."
        
        insight = ""
        if ratio < 60:
            insight = "Prioridad: Empuje. Tu fuerza de tracción es dominante. Seguimos enfocados en cuádriceps para el Sled Push."
        elif 60 <= ratio < 75:
            insight = "Equilibrio en progreso. Tu transferencia de fuerza a los Wall Balls está mejorando significativamente."
        else:
            insight = "Perfil equilibrado. Ahora el enfoque estratégico cambia a la resistencia bajo fatiga."
            
        return {"ratio": round(float(ratio), 1), "advice": insight + alerta_inactividad}

    def get_readiness_breakdown(self):
        """
        Phase 10: Desglose del Race Readiness en 3 áreas clave.
        Los valores parten de 0 % y crecen con el trabajo real del atleta.
        """
        fuerza = self.get_race_readiness_score()

        # Resistencia: 0 % de base, +6 % por cada sesión de carrera completada (máx 100 %)
        carrera_sessions = self.sessions.filter(
            estado='completado', activities__tipo_actividad='carrera'
        ).distinct().count()
        resistencia = min(carrera_sessions * 6, 100)

        # Potencia: 0 % de base, +12 % por cada sesión de estaciones Hyrox (máx 100 %)
        potencia_sessions = self.sessions.filter(
            estado='completado', activities__tipo_actividad='hyrox_station'
        ).distinct().count()
        potencia = min(potencia_sessions * 12, 100)

        return {
            "fuerza": fuerza,
            "resistencia": resistencia,
            "potencia": potencia
        }

    def get_daily_push(self):
        """
        Phase 11: Push Dinámico
        Genera un mensaje diario personalizado basado en los días restantes al evento y el último RPE.
        """
        from django.utils import timezone
        
        # Check active injury for safety message
        from hyrox.models import UserInjury
        lesion = UserInjury.objects.filter(cliente=self.cliente, activa=True).first()
        if lesion:
            if lesion.fase == 'AGUDA':
                return "Escudo Bio-Safe activo. Tu sesión ha sido blindada para proteger tu recuperación. Prioridad total a la zona lesionada."
            else:
                return "Sesión adaptada por seguridad. Seguimos sumando sin comprometer tu recuperación a largo plazo."

        last_session = self.sessions.filter(estado='completado').order_by('-fecha').first()
        if last_session and last_session.rpe_global and last_session.rpe_global >= 9:
            return "Prioridad hoy: Recuperación estratégica. Tu cuerpo está asimilando el trabajo pesado de ayer."
            
        if self.fecha_evento:
            days_left = (self.fecha_evento - timezone.now().date()).days
            if 0 < days_left < 30:
                return f"Estamos a {days_left} días de la prueba. Cada bloque cuenta para el resultado final."
                
        return "Hoy es un buen día para el orden y la disciplina. ¿Listo para sumar?"

class HyroxSession(models.Model):
    ESTADO_CHOICES = [
        ('planificado', 'Planificado'),
        ('completado', 'Completado'),
        ('saltado', 'Saltado')
    ]
    
    objective = models.ForeignKey(HyroxObjective, on_delete=models.CASCADE, related_name='sessions')
    fecha = models.DateField(default=timezone.now)
    titulo = models.CharField(max_length=200, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='planificado')
    
    # Check de Energía Previo
    nivel_energia_pre = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Energía reportada por el usuario hoy (1-10)")
    
    # Métricas Globales de la Sesión
    tiempo_total_minutos = models.IntegerField(null=True, blank=True)
    hr_media = models.IntegerField(null=True, blank=True, help_text="Frecuencia Cardíaca Media (lpm)")
    hr_maxima = models.IntegerField(null=True, blank=True, help_text="Frecuencia Cardíaca Máxima (lpm)")
    rpe_global = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Escala de Esfuerzo Percibido 1-10")

    # ── Carga objetiva (TRIMP / CTL / ATL / TSB) ────────────────────────────
    trimp = models.FloatField(null=True, blank=True,
        help_text="Training Impulse (Banister): carga objetiva de la sesión")
    zona_cardiaca_predominante = models.CharField(max_length=5, null=True, blank=True,
        help_text="Zona cardíaca predominante de la sesión: Z1-Z5")
    ctl = models.FloatField(null=True, blank=True,
        help_text="Chronic Training Load: fitness acumulado (42 días, exponential decay)")
    atl = models.FloatField(null=True, blank=True,
        help_text="Acute Training Load: fatiga acumulada (7 días, exponential decay)")
    tsb = models.FloatField(null=True, blank=True,
        help_text="Training Stress Balance: CTL - ATL (positivo=fresco, negativo=fatigado)")

    # Texto en crudo pegado por el usuario (sobre el que actuará Gemini)
    notas_raw = models.TextField(blank=True, null=True, help_text="Texto libre pegado por el usuario del entrenamiento")
    parsed_by_ia = models.BooleanField(default=False, help_text="True si ya fue procesado por el parser de IA")
    # Phase 15: Clinical Tracking
    hubo_molestias = models.BooleanField(default=False, help_text="¿Hubo molestias en la lesión durante el entrenamiento?")
    
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    # Cumplimiento real vs. plan (0.0 – 1.0)
    cumplimiento_ratio = models.FloatField(
        null=True, blank=True,
        help_text="0-1: qué % del volumen/distancia planificado completó el usuario"
    )

    # Phase 8: Historial Inteligente y Analytics Acumulado
    ai_evaluation_score = models.IntegerField(null=True, blank=True, help_text="Valor 1-100 calculado por IA basado en cumplimiento vs plan")
    muscle_fatigue_index = models.CharField(max_length=20, null=True, blank=True, choices=[('Baja', 'Baja'), ('Media', 'Media'), ('Alta', 'Alta')], help_text="Estimación de fatiga calculada por IA resumiendo el RPE/Volumen")
    fatiga_updated_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo se inyectó la fatiga por última vez (para Fatigue Decay)")

    def save(self, *args, **kwargs):
        # Lógica de cambio de título según energía pre-entreno (Fase 14)
        if self.nivel_energia_pre is not None and self.nivel_energia_pre < 4:
            if not self.titulo or 'Recuperación Activa' not in self.titulo:
                self.titulo = 'Recuperación Activa / Movilidad'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sesión {self.fecha} - {self.objective.cliente.nombre}"


class HyroxActivity(models.Model):
    TIPO_CHOICES = [
        ('fuerza', 'Fuerza / Musculación'),
        ('carrera', 'Carrera / Running'),
        ('ergometro', 'Ergómetro (Remo, SkiErg)'),
        ('isometrico', 'Isométricos (Wall Sit, Plancha)'),
        ('hyrox_station', 'Estación Específica Hyrox (Sled, Sandbag, etc.)'),
        ('cardio_sustituto', 'Cardio Sustituto (Fútbol, Ciclismo, etc.)'),
        ('hiit', 'HIIT / Interválico'),
        ('remo', 'Remo (Rowing Machine)'),
        ('skierg', 'SkiErg'),
        ('bici', 'Bicicleta / Ciclismo'),
        ('otro', 'Otro / Mixto'),
    ]
    
    sesion = models.ForeignKey(HyroxSession, on_delete=models.CASCADE, related_name='activities')
    tipo_actividad = models.CharField(max_length=25, choices=TIPO_CHOICES, default='fuerza')
    nombre_ejercicio = models.CharField(max_length=150)
    
    # Diccionario flexible para guardar los datos métricos exactos que extrae la IA basándose en el tipo_actividad
    data_metricas = models.JSONField(
        default=dict,
        help_text="JSON flexible con series, kg, tiempos, ritmos o FC extrados del texto libre"
    )
    # Snapshot de lo que estaba planificado antes de registrar lo real
    data_planificado = models.JSONField(
        null=True, blank=True,
        help_text="Copia de data_metricas planificado antes de sobrescribir con lo real"
    )

    @property
    def get_icon_class(self):
        nombre = self.nombre_ejercicio.lower()
        if 'ski' in nombre: return 'fa-skiing text-cyan-400'
        if 'sled push' in nombre: return 'fa-truck-loading text-orange-500'
        if 'sled pull' in nombre: return 'fa-grip-lines text-orange-400'
        if 'burpee' in nombre: return 'fa-person-running text-green-500'
        if 'remo' in nombre or 'row' in nombre: return 'fa-water text-blue-400'
        if 'farmer' in nombre or 'granjero' in nombre: return 'fa-suitcase text-amber-500'
        if 'sandbag' in nombre or 'zancada' in nombre: return 'fa-walking text-yellow-600'
        if 'wall ball' in nombre: return 'fa-bullseye text-red-500'
        
        if self.tipo_actividad == 'carrera': return 'fa-running text-pink-500'
        if self.tipo_actividad == 'fuerza': return 'fa-dumbbell text-cyan-500'
        return 'fa-cube text-purple-500'

    def __str__(self):
        return f"Bloque {self.get_tipo_actividad_display()} - {self.nombre_ejercicio} ({self.sesion})"

# Phase 6: Analytics Visuales - Histórico de Race Readiness
class HyroxReadinessLog(models.Model):
    objective = models.ForeignKey(HyroxObjective, on_delete=models.CASCADE, related_name='readiness_logs')
    fecha = models.DateField(auto_now_add=True)
    score = models.IntegerField()

    # Biometría matutina diaria
    fc_reposo = models.IntegerField(
        null=True, blank=True,
        help_text="FC de reposo al despertar (lpm) — indicador clave de recuperación"
    )
    horas_sueno = models.FloatField(
        null=True, blank=True,
        help_text="Horas de sueño la noche anterior"
    )
    calidad_sueno = models.IntegerField(
        null=True, blank=True,
        help_text="Calidad subjetiva del sueño (1-10)"
    )

    class Meta:
        ordering = ['fecha']
        unique_together = ('objective', 'fecha')

    def __str__(self):
        return f"{self.objective.cliente.nombre} - {self.score}% ({self.fecha})"


# ==============================================================================
# SISTEMA DE GESTIÓN DE LESIONES Y RECUPERACIÓN (RECOVERY MODE)
# ==============================================================================

class UserInjury(models.Model):
    """
    Modelo maestro de lesiones. Define la patología activa, su fase y las
    etiquetas de riesgo (riesgo_biomecánico) que deben ser bloqueadas en Hyrox.
    """
    class Fase(models.TextChoices):
        AGUDA = 'AGUDA', 'Fase Aguda (Alta inflamación, reposo relativo)'
        SUB_AGUDA = 'SUB_AGUDA', 'Fase Sub-aguda (Movilidad sin dolor, carga parcial)'
        RETORNO = 'RETORNO', 'Fase de Retorno (Fuerza excéntrica, carga progresiva)'
        RECUPERADO = 'RECUPERADO', 'Recuperado (Alta médica, sin restricciones)'

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='lesiones_hyrox')
    zona_afectada = models.CharField(max_length=100, help_text="Ej: Gemelo derecho, Rodilla izquierda")
    fase = models.CharField(max_length=20, choices=Fase.choices, default=Fase.AGUDA)
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_resolucion = models.DateField(null=True, blank=True)
    gravedad = models.IntegerField(default=5, help_text="Del 1 al 10")
    activa = models.BooleanField(default=True)
    
    tags_restringidos = models.JSONField(
        default=list, 
        blank=True,
        help_text="Lista de Risk Tags prohibidos (ej. 'impacto_vertical', 'triple_extension_explosiva')"
    )
    notas_medicas = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Trigger de Invalidez: Si la lesión está activa (o es nueva), invalidar plan futuro
        if self.activa:
            self.invalidate_future_sessions()

    def invalidate_future_sessions(self):
        """
        Elimina TODAS las sesiones planificadas a partir de hoy y regenera el plan
        completo aplicando los nuevos filtros de riesgo de la lesión activa.
        Las sesiones ya completadas no se tocan.
        """
        from .models import HyroxSession, HyroxObjective
        from .training_engine import HyroxTrainingEngine
        hoy = timezone.now().date()

        with transaction.atomic():
            # Borramos TODAS las sesiones de Hyrox planificadas a partir de hoy
            HyroxSession.objects.filter(
                objective__cliente=self.cliente,
                fecha__gte=hoy,
                estado='planificado'
            ).delete()

            # Regeneramos el plan para rellenar los huecos filtrados
            obj_activo = HyroxObjective.objects.filter(cliente=self.cliente, estado='activo').first()
            if obj_activo:
                HyroxTrainingEngine.generate_training_plan(obj_activo)
        
    def __str__(self):
        estado = "ACTIVA" if self.activa else "RESUELTA"
        return f"{self.zona_afectada} ({self.fase}) - {estado}"

    class Meta:
        verbose_name = "Registro de Lesión"
        verbose_name_plural = "Registros de Lesiones"
        ordering = ['-activa', '-fecha_inicio']


class DailyRecoveryEntry(models.Model):
    """
    Tracking diario fisiológico. Alimenta el motor de transición de fase (Upgrade/Downgrade).
    """
    lesion = models.ForeignKey(UserInjury, on_delete=models.CASCADE, related_name='registros_diarios')
    fecha = models.DateField(default=timezone.now)
    dolor_reposo = models.IntegerField(default=0, help_text="0-10: Dolor sin hacer nada")
    dolor_movimiento = models.IntegerField(default=0, help_text="0-10: Dolor al caminar o rango articular")
    inflamacion_percibida = models.IntegerField(default=1, help_text="1-10: 1=Sin hinchazón, 10=Inflamación severa")
    rango_movimiento = models.IntegerField(default=5, help_text="1-10: 1=Muy limitado, 10=Rango completo normal")
    
    notas_usuario = models.TextField(blank=True, null=True, help_text="¿Tomaste AINEs hoy? ¿Aplicaste hielo?")

    def __str__(self):
        return f"DRE: {self.fecha} - Dolor M: {self.dolor_movimiento}/10"

    class Meta:
        verbose_name = "Registro Diario de Recuperación"
        verbose_name_plural = "Registros Diarios de Recuperación"
        ordering = ['-fecha']
        unique_together = ['lesion', 'fecha']  # Solo un registro por lesión por día

# Phase 12: Recovery Test Log
class RecoveryTestLog(models.Model):
    lesion = models.ForeignKey(UserInjury, on_delete=models.CASCADE, related_name='recovery_tests')
    fecha = models.DateTimeField(auto_now_add=True)
    dolor_movimiento = models.PositiveSmallIntegerField(help_text="Dolor del 0 al 10")
    inflamacion_percibida = models.PositiveSmallIntegerField(help_text="Inflamación percibida del 0 al 10")
    confianza_atleta = models.PositiveSmallIntegerField(help_text="Confianza del atleta del 0 al 10")
    es_apto = models.BooleanField(default=False)

    def evaluate(self):
        return self.dolor_movimiento <= 1 and self.inflamacion_percibida == 0 and self.confianza_atleta >= 8
        
    def save(self, *args, **kwargs):
        self.es_apto = self.evaluate()
        super().save(*args, **kwargs)

    def __str__(self):
        estado = "Apto" if self.es_apto else "No Apto"
        return f"Test {self.fecha.strftime('%Y-%m-%d')} - {self.lesion.zona_afectada} - {estado}"


# ── Strava Integration ────────────────────────────────────────────────────────

class StravaToken(models.Model):
    """OAuth2 tokens per athlete. One per cliente."""
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='strava_token')
    athlete_id = models.BigIntegerField(unique=True)
    access_token = models.CharField(max_length=200)
    refresh_token = models.CharField(max_length=200)
    expires_at = models.DateTimeField()

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Strava token — {self.cliente}"


class StravaActivityRaw(models.Model):
    """Incoming Strava activity, staged before user confirms."""
    ESTADO_CHOICES = [
        ('pending',  'Pendiente de revisión'),
        ('merged',   'Fusionado con sesión existente'),
        ('created',  'Nueva sesión creada'),
        ('ignored',  'Ignorado por el usuario'),
    ]

    TIPO_STRAVA_MAP = {
        'Run':            'carrera',
        'Walk':           'cardio_sustituto',
        'Hike':           'cardio_sustituto',
        'Ride':           'bici',
        'VirtualRide':    'bici',
        'Rowing':         'remo',
        'WeightTraining': 'fuerza',
        'Workout':        'otro',
        'Soccer':         'cardio_sustituto',
        'Football':       'cardio_sustituto',
        'EBikeRide':      'bici',
        'Swim':           'cardio_sustituto',
        'Yoga':           'otro',
    }

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='strava_activities')
    strava_id = models.BigIntegerField(unique=True)
    fecha_actividad = models.DateField()
    tipo_strava = models.CharField(max_length=50, blank=True)
    nombre_strava = models.CharField(max_length=200, blank=True)
    duracion_segundos = models.IntegerField(default=0)
    hr_media = models.IntegerField(null=True, blank=True)
    hr_maxima = models.IntegerField(null=True, blank=True)
    distancia_metros = models.FloatField(null=True, blank=True)
    raw_json = models.JSONField()
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='pending')
    hyrox_session = models.ForeignKey(
        'HyroxSession', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='strava_sources'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_actividad']
        verbose_name = "Actividad Strava"
        verbose_name_plural = "Actividades Strava"

    def tipo_hyrox(self):
        return self.TIPO_STRAVA_MAP.get(self.tipo_strava, 'otro')

    def duracion_minutos(self):
        return round(self.duracion_segundos / 60, 1)

    def __str__(self):
        return f"Strava #{self.strava_id} — {self.tipo_strava} {self.fecha_actividad}"

