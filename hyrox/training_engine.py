import logging
from datetime import timedelta
from django.utils import timezone
from .models import HyroxObjective, HyroxSession, HyroxActivity

logger = logging.getLogger(__name__)

# Parámetros de volumen por nivel de experiencia
_VOLUMEN_POR_NIVEL = {
    'principiante': {'series': 3, 'reps_factor': 0.85},
    'intermedio':   {'series': 4, 'reps_factor': 1.00},
    'avanzado':     {'series': 5, 'reps_factor': 1.10},
}


class HyroxTrainingEngine:
    """
    Motor inteligente para generar y adaptar planes de entrenamiento Hyrox.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE PROGRESIÓN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calcular_porcentaje_rm(week, weeks_to_plan, is_deload, is_taper):
        """
        Progresión lineal de carga del 65 % al 85 % a lo largo del macrociclo.
        Semanas de deload bajan al 60 %; tapering al 50 %.
        """
        if is_taper:
            return 0.50
        if is_deload:
            return 0.60
        if weeks_to_plan <= 1:
            return 0.70
        progreso = week / max(weeks_to_plan - 1, 1)
        return round(0.65 + (progreso * 0.20), 3)

    @staticmethod
    def _calcular_ritmos_carrera(tiempo_5k_str):
        """
        Calcula ritmos Z2 y tempo a partir del tiempo 5K en formato MM:SS.
        Devuelve None si el campo está vacío o tiene formato incorrecto.
        """
        if not tiempo_5k_str:
            return None
        try:
            partes = tiempo_5k_str.strip().split(':')
            total_segundos = int(partes[0]) * 60 + int(partes[1])
            ritmo_5k = total_segundos / 5  # segundos por km

            def fmt(sec):
                m, s = divmod(int(sec), 60)
                return f"{m}:{s:02d}/km"

            return {
                'ritmo_5k':    fmt(ritmo_5k),
                'ritmo_z2':    fmt(ritmo_5k * 1.30),   # 30 % más lento — zona aeróbica baja
                'ritmo_tempo': fmt(ritmo_5k * 1.08),   # 8 % más lento — umbral láctico
            }
        except Exception:
            return None

    @staticmethod
    def _distancia_carrera(nivel, week, weeks_to_plan, is_deload, is_taper):
        """
        Distancia base de carrera progresiva según nivel y semana del macrociclo.
        Principiante: 4→8 km  |  Intermedio: 5→10 km  |  Avanzado: 6→14 km
        """
        bases   = {'principiante': 4.0, 'intermedio': 5.0, 'avanzado': 6.0}
        maximos = {'principiante': 8.0, 'intermedio': 10.0, 'avanzado': 14.0}
        base    = bases.get(nivel, 5.0)
        maximo  = maximos.get(nivel, 10.0)

        if weeks_to_plan > 1:
            progreso  = week / max(weeks_to_plan - 1, 1)
            distancia = base + (progreso * (maximo - base))
        else:
            distancia = base

        if is_deload:
            distancia *= 0.60
        if is_taper:
            distancia = base * 0.50

        return round(distancia, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # GENERACIÓN DEL PLAN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_training_plan(objective: HyroxObjective):
        """
        Genera el plan de entrenamiento estructurado hasta la fecha del evento.
        Se basa en la categoría, baselines del usuario y nivel de experiencia.
        Incluye semanas de deload cada 4 semanas y progresión lineal de carga.
        """
        if not objective.fecha_evento:
            logger.warning("No se puede generar plan sin fecha de evento.")
            return

        today = timezone.now().date()
        days_until_event = (objective.fecha_evento - today).days

        if days_until_event < 0:
            logger.warning("La fecha del evento ya ha pasado.")
            return

        weeks_until_event = days_until_event // 7
        weeks_to_plan = min(max(1, weeks_until_event), 16)

        # Volumen semanal base por categoría
        sessions_per_week = 5 if 'pro' in objective.categoria else 4

        # Tags de lesiones activas para Bio-Safe substitution
        from .models import UserInjury
        lesiones_activas = UserInjury.objects.filter(cliente=objective.cliente, activa=True)
        restricted_tags = set()
        for inj in lesiones_activas:
            if inj.tags_restringidos:
                restricted_tags.update(inj.tags_restringidos)

        current_date = today

        for week in range(weeks_to_plan):
            is_taper  = (weeks_to_plan - week) <= 2
            is_deload = (week % 4 == 3) and not is_taper  # Semana 4ª, 8ª, 12ª

            # Protocolo de Arranque en Frío
            is_cold_start   = (not objective.rm_sentadilla or not objective.rm_peso_muerto) and week == 0
            template_fuerza = 'calibracion' if is_cold_start else 'fuerza_metcon'

            if is_cold_start:
                titulo_fuerza = f"Semana {week+1}: Calibración de Datos Base"
            elif is_deload:
                titulo_fuerza = f"Semana {week+1}: Semana de Descarga (Deload)"
            elif is_taper:
                titulo_fuerza = f"Semana {week+1}: Fuerza de Activación (Tapering)"
            else:
                titulo_fuerza = f"Semana {week+1}: Fuerza y Potencia Base"

            # Días preferidos del usuario
            dias_pref = getattr(objective, 'dias_preferidos', '0,2,4,6') or '0,2,4,6'
            try:
                dias_semana_asignables = [int(p) for p in dias_pref.split(',')]
            except Exception:
                dias_semana_asignables = [0, 2, 4, 6]

            # Deduplicar y validar rango 0-6
            seen = set()
            dias_semana_asignables = [
                d for d in dias_semana_asignables
                if isinstance(d, int) and 0 <= d <= 6 and not (d in seen or seen.add(d))
            ]

            sessions_per_week_capped = min(sessions_per_week, 7)
            for i in range(7):
                if len(dias_semana_asignables) >= sessions_per_week_capped:
                    break
                if i not in dias_semana_asignables:
                    dias_semana_asignables.append(i)

            dias_asignados = sorted(dias_semana_asignables[:sessions_per_week_capped])

            try:
                dia_fuerza = dias_asignados[0]
                dia_cardio = dias_asignados[1]
                dia_espe   = dias_asignados[2]
                dia_simul  = dias_asignados[3] if sessions_per_week >= 4 else dias_asignados[2]
            except IndexError:
                dia_fuerza, dia_cardio, dia_espe, dia_simul = 0, 2, 4, 6

            shared = dict(
                objective=objective,
                is_taper=is_taper,
                is_deload=is_deload,
                week=week,
                weeks_to_plan=weeks_to_plan,
                restricted_tags=restricted_tags,
            )

            # Día 1: Fuerza + MetCon
            HyroxTrainingEngine._create_session(
                fecha=current_date + timedelta(days=(week * 7) + dia_fuerza),
                titulo=titulo_fuerza,
                template=template_fuerza,
                **shared
            )

            # Día 2: Motor aeróbico
            titulo_cardio = (
                f"Semana {week+1}: Descarga Aeróbica" if is_deload
                else f"Semana {week+1}: Trote Regenerativo" if is_taper
                else f"Semana {week+1}: Motor Aeróbico (Carrera)"
            )
            HyroxTrainingEngine._create_session(
                fecha=current_date + timedelta(days=(week * 7) + dia_cardio),
                titulo=titulo_cardio,
                template='cardio',
                **shared
            )

            # Día 3: Estaciones específicas Hyrox
            if dia_espe != dia_cardio:
                titulo_espe = (
                    f"Semana {week+1}: Técnica Reducida (Deload)" if is_deload
                    else f"Semana {week+1}: Repaso Técnico Estaciones" if is_taper
                    else f"Semana {week+1}: Estaciones Hyrox Específicas"
                )
                HyroxTrainingEngine._create_session(
                    fecha=current_date + timedelta(days=(week * 7) + dia_espe),
                    titulo=titulo_espe,
                    template='hyrox_stations',
                    **shared
                )

            # Día 4: Simulación de carrera
            if sessions_per_week >= 4 and dia_simul not in [dia_fuerza, dia_cardio, dia_espe]:
                titulo_simul = (
                    f"Semana {week+1}: Descanso Activo" if (is_taper or is_deload)
                    else f"Semana {week+1}: Simulación de Carrera"
                )
                HyroxTrainingEngine._create_session(
                    fecha=current_date + timedelta(days=(week * 7) + dia_simul),
                    titulo=titulo_simul,
                    template='simulacion',
                    **shared
                )

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO-AJUSTE DE SESIONES SALTADAS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def auto_adjust(objective: HyroxObjective):
        """
        Detecta sesiones de la semana actual retrasadas (>24h).
        Si la sesión saltada contiene carrera, la reprograma a hoy
        y empuja el resto de sesiones futuras para no perder el estímulo aeróbico clave.
        """
        if objective.estado != 'activo':
            return

        hoy = timezone.now().date()
        start_of_week = hoy - timedelta(days=hoy.weekday())

        sesiones_pasadas = HyroxSession.objects.filter(
            objective=objective,
            estado='planificado',
            fecha__lt=hoy,
            fecha__gte=start_of_week
        ).prefetch_related('activities').order_by('fecha')

        for sesion in sesiones_pasadas:
            is_critica   = False
            titulo_lower = (sesion.titulo or '').lower()
            if 'carrera' in titulo_lower or 'simulación' in titulo_lower:
                is_critica = True
            else:
                actividades = [a.tipo_actividad for a in sesion.activities.all()]
                if 'carrera' in actividades:
                    is_critica = True

            if objective.categoria == 'relay' and not is_critica:
                if 'fuerza' in titulo_lower or 'hyrox_station' in [a.tipo_actividad for a in sesion.activities.all()]:
                    is_critica = True

            if is_critica:
                sesiones_futuras = HyroxSession.objects.filter(
                    objective=objective,
                    estado='planificado',
                    fecha__gte=hoy
                ).order_by('-fecha')

                for sf in sesiones_futuras:
                    sf.fecha = sf.fecha + timedelta(days=1)
                    sf.save()

                sesion.fecha = hoy
                sesion.save()
                logger.info(f"Auto-Ajuste: Sesión crítica '{sesion.titulo}' reprogramada para hoy {hoy}")
            else:
                sesion.estado = 'saltado'
                sesion.save()
                logger.info(f"Auto-Ajuste: Sesión accesoria '{sesion.titulo}' marcada como saltada.")

    # ─────────────────────────────────────────────────────────────────────────
    # ADAPTACIÓN CONTINUA POST-SESIÓN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def apply_continuous_adaptation(sesion_completada: HyroxSession):
        """
        Phase 8 & 9: Bucle de Feedback Continuo Avanzado.
        Retorna una lista de strings con los mensajes de alertas para el UI.
        """
        mensajes_ui = []
        rpe    = sesion_completada.rpe_global
        hr_max = sesion_completada.hr_maxima or 0
        nombre = sesion_completada.objective.cliente.nombre

        if not rpe:
            return mensajes_ui

        # --- TRIGGER 1: SOBREESFUERZO (RPE >= 9 O HR_Max > 185) ---
        if rpe >= 9 or hr_max > 185:
            target_date = sesion_completada.fecha + timedelta(days=2)
            # Ventana ±1 día: robustez ante calendarios con huecos
            sesion_sig = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='planificado',
                fecha__gte=target_date - timedelta(days=1),
                fecha__lte=target_date + timedelta(days=1),
            ).order_by('fecha').first()

            if sesion_sig:
                is_mutated = False
                for act in sesion_sig.activities.all():
                    mutated_act = False
                    if 'series' in act.data_metricas:
                        for serie in act.data_metricas['series']:
                            if 'reps' in serie:
                                serie['reps'] = max(1, round(int(serie['reps']) * 0.8))
                                mutated_act = True
                            if 'peso_kg' in serie:
                                serie['peso_kg'] = round(float(serie['peso_kg']) * 0.8)
                                mutated_act = True
                    if 'distancia_km' in act.data_metricas:
                        act.data_metricas['distancia_km'] = round(float(act.data_metricas['distancia_km']) * 0.8, 1)
                        if act.tipo_actividad == 'carrera':
                            notes = act.data_metricas.get('notas', '')
                            act.data_metricas['notas'] = notes + " (Trote suave por recuperación)"
                        mutated_act = True

                    if mutated_act:
                        act.save()
                        is_mutated = True

                if is_mutated:
                    sesion_sig.titulo = (sesion_sig.titulo or 'Entrenamiento') + ' (Recuperación Activa)'
                    sesion_sig.save()
                    mensajes_ui.append(
                        f"{nombre}, hoy has llegado al límite. He suavizado un 20 % la sesión del "
                        f"{sesion_sig.fecha.strftime('%d/%m')} para optimizar tu recuperación."
                    )

        # --- TRIGGER 2: ESTANCAMIENTO (2 sesiones seguidas RPE <= 5) ---
        if rpe <= 5:
            tipos_actual = set(a.tipo_actividad for a in sesion_completada.activities.all())
            prev_sesion = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='completado',
                fecha__lt=sesion_completada.fecha
            ).order_by('-fecha').first()

            if prev_sesion and prev_sesion.rpe_global and prev_sesion.rpe_global <= 5:
                tipos_prev   = set(a.tipo_actividad for a in prev_sesion.activities.all())
                common_types = tipos_actual.intersection(tipos_prev)

                if common_types:
                    for tipo in common_types:
                        next_sesion = HyroxSession.objects.filter(
                            objective=sesion_completada.objective,
                            estado='planificado',
                            fecha__gt=sesion_completada.fecha,
                            activities__tipo_actividad=tipo
                        ).order_by('fecha').first()

                        if next_sesion:
                            is_mutated = False
                            for act in next_sesion.activities.filter(tipo_actividad=tipo):
                                if 'series' in act.data_metricas:
                                    for serie in act.data_metricas['series']:
                                        if 'peso_kg' in serie:
                                            serie['peso_kg'] = round(float(serie['peso_kg']) * 1.1)
                                            is_mutated = True
                                if is_mutated:
                                    notas_actuales = act.data_metricas.get('notas', '')
                                    act.data_metricas['notas'] = notas_actuales + " | 🔄 Ajuste Estancamiento: +10 % Carga."
                                    act.save()

                            if is_mutated:
                                mensajes_ui.append(
                                    f"He detectado carga baja persistente en {tipo.capitalize()}. "
                                    f"He incrementado un 10 % la intensidad de tu sesión del {next_sesion.fecha.strftime('%d/%m')}."
                                )

        # --- TRIGGER 3: ENERGÍA CRÍTICA CONSECUTIVA ---
        if sesion_completada.nivel_energia_pre is not None and sesion_completada.nivel_energia_pre < 3:
            prev_sesion = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='completado',
                fecha__lt=sesion_completada.fecha
            ).order_by('-fecha').first()
            if prev_sesion and prev_sesion.nivel_energia_pre is not None and prev_sesion.nivel_energia_pre < 3:
                proxima = HyroxSession.objects.filter(
                    objective=sesion_completada.objective,
                    estado='planificado',
                    fecha__gt=sesion_completada.fecha
                ).order_by('fecha').first()
                if proxima:
                    proxima.titulo = "Día de Descanso / Salud (Autorregulado)"
                    proxima.activities.all().delete()
                    import django.utils.timezone as tz
                    proxima.fecha_actualizacion = tz.now()
                    proxima.save()
                    mensajes_ui.append(
                        f"🛑 Cuidado: Has reportado baja energía dos sesiones seguidas. "
                        f"He cancelado tu próxima sesión ({proxima.fecha.strftime('%d/%m')}) "
                        f"para priorizar tu salud y evitar sobre-entrenamiento."
                    )

        return mensajes_ui

    # ─────────────────────────────────────────────────────────────────────────
    # ESCALA DE VOLUMEN POR ENERGÍA PRE-ENTRENO
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def scale_volume_by_energy(sesion: HyroxSession):
        """
        Phase 14: Escala el volumen de la sesión según el nivel de energía pre-entreno reportado.
        Si la energía es baja (< 5), se reduce el volumen un 30 %.
        Si la energía es alta (> 8), se mantiene pero se sugiere aumentar intensidad.
        """
        if sesion.nivel_energia_pre is None:
            return False

        is_mutated = False
        energia    = sesion.nivel_energia_pre

        if energia < 5:
            ajuste_notas = "📉 Ajuste por Energía Baja (70 % Volumen)"
            for act in sesion.activities.all():
                mutated_act = False
                if 'series' in act.data_metricas:
                    for serie in act.data_metricas['series']:
                        if 'reps' in serie:
                            serie['reps'] = max(1, round(int(serie['reps']) * 0.7))
                            mutated_act = True
                        if 'peso_kg' in serie:
                            serie['peso_kg'] = max(1, round(float(serie['peso_kg']) * 0.85))
                            mutated_act = True
                if 'distancia_km' in act.data_metricas:
                    act.data_metricas['distancia_km'] = round(float(act.data_metricas['distancia_km']) * 0.7, 1)
                    mutated_act = True

                if mutated_act:
                    notas_actuales = act.data_metricas.get('notas', '')
                    if "Ajuste por Energía" not in notas_actuales:
                        act.data_metricas['notas'] = f"{notas_actuales} | {ajuste_notas}".strip(" |")
                    act.save()
                    is_mutated = True

        elif energia > 8:
            ajuste_notas = "🔥 Energía Óptima: Considera subir el ritmo o carga en la última serie."
            for act in sesion.activities.all():
                notas_actuales = act.data_metricas.get('notas', '')
                if "Energía Óptima" not in notas_actuales:
                    act.data_metricas['notas'] = f"{notas_actuales} | {ajuste_notas}".strip(" |")
                    act.save()
                    is_mutated = True

        return is_mutated

    # ─────────────────────────────────────────────────────────────────────────
    # CREACIÓN DE SESIÓN INDIVIDUAL
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _create_session(
        objective, fecha, titulo, template,
        is_taper=False, is_deload=False,
        week=0, weeks_to_plan=1,
        restricted_tags=None
    ):
        """
        Crea la sesión y sus actividades planificadas basadas en el template,
        escaladas a los RM del usuario, nivel de experiencia y semana del macrociclo.
        """
        if HyroxSession.objects.filter(objective=objective, fecha=fecha).exists():
            return

        restricted_tags = restricted_tags or set()
        nivel           = getattr(objective, 'nivel_experiencia', 'intermedio') or 'intermedio'
        nombre_cliente  = objective.cliente.nombre
        vol             = _VOLUMEN_POR_NIVEL.get(nivel, _VOLUMEN_POR_NIVEL['intermedio'])

        sesion = HyroxSession.objects.create(
            objective=objective,
            fecha=fecha,
            titulo=titulo,
            estado='planificado'
        )

        rm_squat    = objective.rm_sentadilla  or 60.0
        rm_deadlift = objective.rm_peso_muerto or 80.0

        # ── CALIBRACIÓN ──────────────────────────────────────────────────────
        if template == 'calibracion':
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='fuerza',
                nombre_ejercicio='Sentadilla Trasera (Back Squat) [TEST]',
                data_metricas={
                    "planificado": True,
                    "notas": (
                        "Hoy vamos a descubrir tu nivel. Haz 3 series de 10 repeticiones. "
                        "Elige un peso que sientas que podrías hacer 2 o 3 reps más pero decides parar (RPE 7-8). "
                        "Al terminar, registra el peso exacto en las notas de resultado."
                    ),
                    "series": [{"reps": 10} for _ in range(3)]
                }
            )
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='fuerza',
                nombre_ejercicio='Peso Muerto (Deadlift) [TEST]',
                data_metricas={
                    "planificado": True,
                    "notas": (
                        "Haz 3 series de 8 reps (RPE 7-8). No busques un máximo hoy, "
                        "busca un peso técnico que demande esfuerzo pero vayas cómodo."
                    ),
                    "series": [{"reps": 8} for _ in range(3)]
                }
            )

        # ── FUERZA + METCON ───────────────────────────────────────────────────
        elif template == 'fuerza_metcon':
            # Detectar imbalance muscular
            imbalance_type = None
            if rm_deadlift > (rm_squat * 1.5):
                imbalance_type = 'weak_squat'
            elif rm_squat > (rm_deadlift * 1.2):
                imbalance_type = 'weak_deadlift'

            # Progresión lineal de % RM semana a semana
            porcentaje_rm = HyroxTrainingEngine._calcular_porcentaje_rm(week, weeks_to_plan, is_deload, is_taper)

            # Parámetros de series/reps/fase según % RM actual
            if is_taper:
                series_obj   = 3
                reps_obj     = 5
                fase_nombre  = "Tapering"
                rpe_target   = 6
                tempo_str    = "2-0-X-0"
                descanso_str = "120 seg"
            elif is_deload:
                series_obj   = max(vol['series'] - 1, 2)
                reps_obj     = round(8 * vol['reps_factor'])
                fase_nombre  = "Deload"
                rpe_target   = 6
                tempo_str    = "3-0-1-0"
                descanso_str = "90 seg"
            elif porcentaje_rm < 0.75:
                series_obj   = vol['series']
                reps_obj     = round(10 * vol['reps_factor'])
                fase_nombre  = "Fase de Base"
                rpe_target   = 7
                tempo_str    = "3-0-1-0"
                descanso_str = "90 seg"
            elif porcentaje_rm < 0.82:
                series_obj   = vol['series']
                reps_obj     = round(7 * vol['reps_factor'])
                fase_nombre  = "Fase de Intensificación"
                rpe_target   = 8
                tempo_str    = "2-1-1-0"
                descanso_str = "120 seg"
            else:
                series_obj   = vol['series']
                reps_obj     = round(5 * vol['reps_factor'])
                fase_nombre  = "Fase de Potencia"
                rpe_target   = 9
                tempo_str    = "2-0-X-0"
                descanso_str = "120-180 seg"

            # Selección de ejercicio base según imbalance
            if imbalance_type == 'weak_squat':
                ejercicio = 'Prensa de Piernas / Hack Squat (Foco Cuádriceps)'
                peso_base = rm_squat
                notas_ej  = 'Ajuste Imbalance: Déficit de cuádriceps. Prioridad Empuje.'
            elif imbalance_type == 'weak_deadlift':
                ejercicio = 'Peso Muerto Rumano / Hip Thrust'
                peso_base = rm_deadlift
                notas_ej  = 'Ajuste Imbalance: Déficit cadena posterior. Prioridad Tracción.'
            else:
                ejercicio = 'Sentadilla Trasera'
                peso_base = rm_squat
                notas_ej  = 'Equilibrio estructural OK.'

            peso_trabajo = peso_base * porcentaje_rm

            # Sustitución Bio-Segura por lesión de tren inferior
            restricciones_pierna = {
                'impacto_vertical', 'flexion_rodilla_profunda', 'empuje_pierna',
                'flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo'
            }
            if restricted_tags and any(tag in restricted_tags for tag in restricciones_pierna):
                ejercicio    = 'Press Militar Sentado / Remo con Mancuerna (Tren Superior)'
                peso_trabajo = 0
                notas_ej     = f'⛔ {notas_ej} -> Modificado a Tren Superior por restricciones biomecánicas (Lesión activa).'

            # Sustitución por material disponible (sin barra → mancuernas)
            material  = (objective.material_disponible or '').lower()
            sin_barra = any(k in material for k in ['sin barra', 'no barra', 'mancuerna', 'dumbbell', 'casa', 'sin material'])
            if sin_barra and 'Sentadilla Trasera' in ejercicio:
                ejercicio = 'Sentadilla con Mancuernas / Goblet Squat'
                notas_ej  = notas_ej + ' (Adaptado a mancuernas por material disponible.)'

            # Coach tip personalizado
            edad         = getattr(objective.cliente, 'edad', 35) or 35
            reserva_reps = '2' if rpe_target <= 8 else '1'
            coach_tip    = (
                f"{nombre_cliente}, estamos en {fase_nombre} ({round(porcentaje_rm * 100)} % RM). "
                f"Hoy buscamos RPE {rpe_target}, guarda {reserva_reps} rep en reserva. "
            )
            if edad >= 45:
                coach_tip += (
                    f"⚠️ Ajuste (+40): Calentamiento articular estricto de 10 min antes de la primera serie "
                    f"efectiva a {round(peso_trabajo)} kg. Cuida la excéntrica (2 s de bajada)."
                )
            elif edad <= 25:
                coach_tip += "🚀 Máxima explosividad concéntrica aprovechando tu recuperación de SNC."

            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='fuerza',
                nombre_ejercicio=ejercicio,
                data_metricas={
                    "planificado":    True,
                    "notas":          notas_ej,
                    "coach_tip":      coach_tip,
                    "tempo":          tempo_str,
                    "descanso":       descanso_str,
                    "porcentaje_rm":  round(porcentaje_rm * 100),
                    "series": [
                        {"reps": reps_obj, "peso_kg": round(peso_trabajo)}
                        for _ in range(series_obj)
                    ]
                }
            )

        # ── CARDIO ────────────────────────────────────────────────────────────
        elif template == 'cardio':
            is_sub    = 'impacto_vertical' in restricted_tags or 'carrera' in restricted_tags
            distancia = HyroxTrainingEngine._distancia_carrera(nivel, week, weeks_to_plan, is_deload, is_taper)
            ritmos    = HyroxTrainingEngine._calcular_ritmos_carrera(objective.tiempo_5k_base or '')

            if ritmos:
                nota_ritmo    = f"Ritmo objetivo Z2: {ritmos['ritmo_z2']}. Referencia tempo: {ritmos['ritmo_tempo']}."
                ritmo_guardar = ritmos['ritmo_z2']
            else:
                nota_ritmo    = "Mantener pulsaciones bajas (Z2, ~65-75 % FC máx). Sin tiempo 5K registrado."
                ritmo_guardar = None

            metricas = {
                "planificado":  True,
                "distancia_km": distancia if not is_sub else round(distancia * 0.8, 1),
                "notas":        (
                    f"Sustitución metabólica por lesión. {nota_ritmo}" if is_sub
                    else nota_ritmo
                ),
            }
            if ritmo_guardar:
                metricas["ritmo_objetivo"] = ritmo_guardar

            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='cardio_sustituto' if is_sub else 'carrera',
                nombre_ejercicio=(
                    'Bici Suave' if (is_sub and is_taper)
                    else 'SkiErg / Remo Z2' if is_sub
                    else 'Trote Ligero' if is_taper
                    else 'Carrera Continua Z2'
                ),
                data_metricas=metricas
            )

        # ── ESTACIONES HYROX ──────────────────────────────────────────────────
        elif template == 'hyrox_stations':
            peso_sled_base = 100 if 'pro' not in objective.categoria.lower() else 150

            # Escalar por fase y nivel
            if is_taper:
                peso_sled = peso_sled_base // 2
            elif is_deload:
                peso_sled = round(peso_sled_base * 0.60)
            else:
                peso_sled = peso_sled_base

            if nivel == 'principiante':
                peso_sled = round(peso_sled * 0.70)
            elif nivel == 'avanzado':
                peso_sled = round(peso_sled * 1.10)

            # Wall Balls reps por nivel
            wb_reps = {'principiante': 12, 'intermedio': 20, 'avanzado': 25}.get(nivel, 20)
            if is_deload or is_taper:
                wb_reps = max(8, round(wb_reps * 0.60))

            estaciones = [
                {
                    'nombre': 'Sled Push',
                    'distancia_m': 50, 'peso_kg': peso_sled,
                    'tags': ['empuje_pierna', 'carga_distal_pierna']
                },
                {
                    'nombre': 'Wall Balls',
                    'series': [{"reps": wb_reps}, {"reps": wb_reps}, {"reps": wb_reps}],
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda']
                },
                {
                    'nombre': 'Burpees Broad Jump',
                    'distancia_m': 80,
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'triple_extension_explosiva']
                },
                {
                    'nombre': 'Sandbag Lunges',
                    'distancia_m': 80, 'peso_kg': 20,
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'estabilidad_tobillo']
                },
            ]

            for est in estaciones:
                if restricted_tags and any(tag in restricted_tags for tag in est.get('tags', [])):
                    logger.info(f"Bio-Safe: Saltando {est['nombre']} por restricciones biomecánicas.")
                    continue

                nombre_est = est.pop('nombre')
                est.pop('tags', None)
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='hyrox_station',
                    nombre_ejercicio=nombre_est,
                    data_metricas={"planificado": True, **est}
                )

        # ── SIMULACIÓN ────────────────────────────────────────────────────────
        elif template == 'simulacion':
            if not is_taper and not is_deload:
                is_sub     = 'impacto_vertical' in restricted_tags or 'carrera' in restricted_tags
                peso_sled  = 100 if 'pro' not in objective.categoria.lower() else 150
                if nivel == 'principiante':
                    peso_sled = round(peso_sled * 0.70)

                # Tramos de carrera proporcionales a la semana del macrociclo
                dist_carrera = HyroxTrainingEngine._distancia_carrera(nivel, week, weeks_to_plan, False, False)
                dist_tramo   = round(min(dist_carrera * 0.35, 2.0), 1)

                segmentos = [
                    {
                        'tipo': 'cardio_sustituto' if is_sub else 'carrera',
                        'nombre': f"{'Remo / SkiErg' if is_sub else 'Carrera'} Tramo 1",
                        'metricas': {"planificado": True, "distancia_km": dist_tramo},
                    },
                    {
                        'tipo': 'hyrox_station',
                        'nombre': 'Sled Push',
                        'metricas': {"planificado": True, "distancia_m": 50, "peso_kg": peso_sled},
                        'tags': ['empuje_pierna'],
                    },
                    {
                        'tipo': 'cardio_sustituto' if is_sub else 'carrera',
                        'nombre': f"{'Remo / SkiErg' if is_sub else 'Carrera'} Tramo 2",
                        'metricas': {"planificado": True, "distancia_km": dist_tramo},
                    },
                    {
                        'tipo': 'hyrox_station',
                        'nombre': 'Sled Pull',
                        'metricas': {"planificado": True, "distancia_m": 25, "peso_kg": round(peso_sled * 0.60)},
                    },
                    {
                        'tipo': 'cardio_sustituto' if is_sub else 'carrera',
                        'nombre': f"{'Remo / SkiErg' if is_sub else 'Carrera'} Tramo 3",
                        'metricas': {"planificado": True, "distancia_km": dist_tramo},
                    },
                    {
                        'tipo': 'hyrox_station',
                        'nombre': 'Wall Balls',
                        'metricas': {"planificado": True, "series": [{"reps": 15}]},
                        'tags': ['impacto_vertical'],
                    },
                ]

                for seg in segmentos:
                    tags_seg = seg.pop('tags', [])
                    if restricted_tags and any(t in restricted_tags for t in tags_seg):
                        logger.info(f"Bio-Safe Simulación: Saltando {seg['nombre']}.")
                        continue
                    HyroxActivity.objects.create(
                        sesion=sesion,
                        tipo_actividad=seg['tipo'],
                        nombre_ejercicio=seg['nombre'] + (' (Adaptado)' if is_sub and seg['tipo'] != 'hyrox_station' else ''),
                        data_metricas=seg['metricas']
                    )

        return sesion
