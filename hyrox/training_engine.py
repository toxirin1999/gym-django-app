import logging
from datetime import timedelta
from django.utils import timezone
from .models import HyroxObjective, HyroxSession, HyroxActivity

logger = logging.getLogger(__name__)

class HyroxTrainingEngine:
    """
    Motor inteligente para generar y adaptar planes de entrenamiento Hyrox.
    """

    @staticmethod
    def generate_training_plan(objective: HyroxObjective):
        """
        Genera el plan de entrenamiento estructurado hasta la fecha del evento.
        Se basa en la categoría y los baselines del usuario.
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
        if weeks_until_event > 16:
            weeks_to_plan = 16
        else:
            # Mínimo 1 semana: si el evento es esta semana o ya pasó,
            # generamos al menos las próximas sesiones de mantenimiento.
            weeks_to_plan = max(1, weeks_until_event)

        # Determinar volumen semanal base por categoría
        sessions_per_week = 4
        if 'pro' in objective.categoria:
            sessions_per_week = 5
        elif 'doubles' in objective.categoria:
            sessions_per_week = 4

        # Buscar tags de lesiones activos (Recovery Mode / Sustituciones)
        from .models import UserInjury
        lesiones_activas = UserInjury.objects.filter(cliente=objective.cliente, activa=True)
        restricted_tags = set()
        for inj in lesiones_activas:
            if inj.tags_restringidos:
                restricted_tags.update(inj.tags_restringidos)

        current_date = today

        # Fase 1: Acumulación (Base)
        # Fase 2: Intensificación (Específico)
        # Fase 3: Peak/Tapering (Afinamiento)

        for week in range(weeks_to_plan):
            is_taper = (weeks_to_plan - week) <= 2
            
            # Phase 8: Protocolo de Arranque en Frío
            is_cold_start = (not objective.rm_sentadilla or not objective.rm_peso_muerto) and week == 0
            template_fuerza = 'calibracion' if is_cold_start else 'fuerza_metcon'
            titulo_fuerza = f"Semana {week+1}: Calibración de Datos Base" if is_cold_start else (f"Semana {week+1}: Fuerza y Potencia Base" if not is_taper else f"Semana {week+1}: Fuerza de Activación (Tapering)")

            # Parsear días preferidos si existen, sino fallback a [Lunes, Miércoles, Viernes, Domingo] o similar.
            dias_pref = getattr(objective, 'dias_preferidos', '0,2,4,6')
            try:
                dias_semana_asignables = [int(p) for p in dias_pref.split(',')]
            except:
                dias_semana_asignables = [0, 2, 4, 6]

            # Deduplicar y validar rango 0-6
            seen = set()
            dias_semana_asignables = [
                d for d in dias_semana_asignables
                if isinstance(d, int) and 0 <= d <= 6 and not (d in seen or seen.add(d))
            ]

            # Si el array preferido no tiene suficientes días, llenamos con los restantes
            sessions_per_week_capped = min(sessions_per_week, 7)
            for i in range(7):
                if len(dias_semana_asignables) >= sessions_per_week_capped:
                    break
                if i not in dias_semana_asignables:
                    dias_semana_asignables.append(i)

            dias_asignados = sorted(dias_semana_asignables[:sessions_per_week_capped])

            # Iterar asignando a los días de la semana
            try:
                dia_fuerza = dias_asignados[0]
                dia_cardio = dias_asignados[1]
                dia_espe = dias_asignados[2]
                dia_simul = dias_asignados[3] if sessions_per_week >= 4 else dias_asignados[2]
            except IndexError:
                # Recurso de seguridad
                dia_fuerza, dia_cardio, dia_espe, dia_simul = 0, 2, 4, 6

            # Día 1: Fuerza + Metcon Corto
            HyroxTrainingEngine._create_session(
                objective=objective,
                fecha=current_date + timedelta(days=(week * 7) + dia_fuerza),
                titulo=titulo_fuerza,
                template=template_fuerza,
                is_taper=is_taper,
                restricted_tags=restricted_tags
            )

            # Día 2: Carrera Continua o Series
            HyroxTrainingEngine._create_session(
                objective=objective,
                fecha=current_date + timedelta(days=(week * 7) + dia_cardio),
                titulo=f"Semana {week+1}: Motor Aeróbico (Carrera)" if not is_taper else f"Semana {week+1}: Trote Regenerativo",
                template='cardio',
                is_taper=is_taper,
                restricted_tags=restricted_tags
            )

            # Día 3: Estaciones Específicas Hyrox
            if dia_espe != dia_cardio: # Evitar duplicar
                HyroxTrainingEngine._create_session(
                    objective=objective,
                    fecha=current_date + timedelta(days=(week * 7) + dia_espe),
                    titulo=f"Semana {week+1}: Estaciones Hyrox Específicas" if not is_taper else f"Semana {week+1}: Repaso Técnico Estaciones",
                    template='hyrox_stations',
                    is_taper=is_taper,
                    restricted_tags=restricted_tags
                )

            if sessions_per_week >= 4 and dia_simul not in [dia_fuerza, dia_cardio, dia_espe]:
                # Día 4: Simulación Larga
                HyroxTrainingEngine._create_session(
                    objective=objective,
                    fecha=current_date + timedelta(days=(week * 7) + dia_simul),
                    titulo=f"Semana {week+1}: Simulación de Carrera" if not is_taper else f"Semana {week+1}: Descanso Activo",
                    template='simulacion',
                    is_taper=is_taper,
                    restricted_tags=restricted_tags
                )

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
        
        # Buscar sesiones que no se hicieron esta semana y quedaron atrás
        sesiones_pasadas = HyroxSession.objects.filter(
            objective=objective,
            estado='planificado',
            fecha__lt=hoy,
            fecha__gte=start_of_week
        ).prefetch_related('activities').order_by('fecha')
        
        for sesion in sesiones_pasadas:
            # Check si es crítica (carrera, simulación o específicamente para Relay)
            is_critica = False
            titulo_lower = (sesion.titulo or '').lower()
            if 'carrera' in titulo_lower or 'simulación' in titulo_lower:
                is_critica = True
            else:
                # Comprobamos por el tipo de actividades internas
                actividades = [a.tipo_actividad for a in sesion.activities.all()]
                if 'carrera' in actividades:
                    is_critica = True
                    
            # Validamos lógica de Relay (En relevos, la carrera y fuerza explosiva (Sled) son críticas)
            if objective.categoria == 'relay' and not is_critica:
                if 'fuerza' in titulo_lower or 'hyrox_station' in [a.tipo_actividad for a in sesion.activities.all()]:
                    is_critica = True
            
            if is_critica:
                # Si es crítica la movemos a HOY, y empujamos todo lo de hoy en adelante 1 día
                sesiones_futuras = HyroxSession.objects.filter(
                    objective=objective,
                    estado='planificado',
                    fecha__gte=hoy
                ).order_by('-fecha') # Order by -fecha para evitar superposiciones al desplazar
                
                for sf in sesiones_futuras:
                    sf.fecha = sf.fecha + timedelta(days=1)
                    sf.save()
                    
                sesion.fecha = hoy
                sesion.save()
                logger.info(f"Auto-Ajuste: Sesión crítica '{sesion.titulo}' reprogramada para hoy {hoy}")
            else:
                # Si no es crítica (ej. fuerza base extra), se asume como pérdida para no saturar
                sesion.estado = 'saltado'
                sesion.save()
                logger.info(f"Auto-Ajuste: Sesión accesoria '{sesion.titulo}' marcada como saltada.")

    @staticmethod
    def apply_continuous_adaptation(sesion_completada: HyroxSession):
        """
        Phase 8 & 9: Bucle de Feedback Continuo Avanzado.
        Retorna una lista de strings con los mensajes de alertas para el UI.
        """
        mensajes_ui = []
        rpe = sesion_completada.rpe_global
        hr_max = sesion_completada.hr_maxima or 0
        
        if not rpe:
            return mensajes_ui

        from datetime import timedelta
        
        # --- TRIGGER 1: SOBREESFUERZO (RPE >= 9 O HR_Max > 185) ---
        if rpe >= 9 or hr_max > 185:
            target_date = sesion_completada.fecha + timedelta(days=2)
            sesion_48h = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='planificado',
                fecha=target_date
            ).first()
            
            if sesion_48h:
                is_mutated = False
                for act in sesion_48h.activities.all():
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
                    sesion_48h.titulo = (sesion_48h.titulo or 'Entrenamiento') + ' (Recuperación Activa)'
                    sesion_48h.save()
                    mensajes_ui.append(f"David, hoy has llegado al límite. He suavizado un 20% la sesión del {target_date.strftime('%d/%m')} para optimizar tu recuperación tras el esfuerzo de hoy.")

        # --- TRIGGER 2: ESTANCAMIENTO (2 Sesiones seguidas < 5) ---
        if rpe <= 5:
            tipos_actual = set([a.tipo_actividad for a in sesion_completada.activities.all()])
            prev_sesion = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='completado',
                fecha__lt=sesion_completada.fecha
            ).order_by('-fecha').first()
            
            if prev_sesion and prev_sesion.rpe_global and prev_sesion.rpe_global <= 5:
                tipos_prev = set([a.tipo_actividad for a in prev_sesion.activities.all()])
                common_types = tipos_actual.intersection(tipos_prev)
                
                if common_types:
                    # Encontrar la PRÓXIMA sesión que tenga alguna de estas actividades
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
                                    act.data_metricas['notas'] = notas_actuales + " | 🔄 Ajuste Estancamiento: +10% Carga."
                                    act.save()
                                    
                            if is_mutated:
                                mensajes_ui.append(f"He detectado carga baja persistente en {tipo.capitalize()}. He incrementado un 10% la intensidad de tu sesión del {next_sesion.fecha.strftime('%d/%m')}.")

        # --- TRIGGER 3 (FASE 14): ENERGIA CRITICA CONSECUTIVA ---
        if sesion_completada.nivel_energia_pre is not None and sesion_completada.nivel_energia_pre < 3:
            prev_sesion = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='completado',
                fecha__lt=sesion_completada.fecha
            ).order_by('-fecha').first()
            if prev_sesion and prev_sesion.nivel_energia_pre is not None and prev_sesion.nivel_energia_pre < 3:
                # Dos días seguidos con energía por el suelo. Se inserta DESCANSO.
                proxima = HyroxSession.objects.filter(
                    objective=sesion_completada.objective,
                    estado='planificado',
                    fecha__gt=sesion_completada.fecha
                ).order_by('fecha').first()
                if proxima:
                    proxima.titulo = "Día de Descanso / Salud (Autorregulado)"
                    proxima.activities.all().delete()
                    import django.utils.timezone as tz
                    proxima.fecha_actualizacion = tz.now() # Trigger
                    proxima.save()
                    mensajes_ui.append(f"🛑 Cuidado: Has reportado baja energía dos sesiones seguidas. He cancelado tu próxima sesión ({proxima.fecha.strftime('%d/%m')}) para priorizar tu salud y evitar sobre-entrenamiento.")

        return mensajes_ui

    @staticmethod
    def scale_volume_by_energy(sesion: HyroxSession):
        """
        Phase 14: Escala el volumen de la sesión según el nivel de energía pre-entreno reportado.
        Si la energía es baja (< 5), se reduce el volumen un 30%.
        Si la energía es alta (> 8), se mantiene, pero se sugiere aumentar intensidad.
        """
        if sesion.nivel_energia_pre is None:
            return False

        is_mutated = False
        energia = sesion.nivel_energia_pre

        if energia < 5:
            ajuste_notas = "📉 Ajuste por Energía Baja (70% Volumen)"
            for act in sesion.activities.all():
                mutated_act = False
                if 'series' in act.data_metricas:
                    for serie in act.data_metricas['series']:
                        if 'reps' in serie:
                            serie['reps'] = max(1, round(int(serie['reps']) * 0.7))
                            mutated_act = True
                        # Podría reducir el peso en lugar de reps o ambas. Vamos por las reps/volumen general.
                        if 'peso_kg' in serie:
                            serie['peso_kg'] = max(1, round(float(serie['peso_kg']) * 0.85)) # Bajamos un 15% peso tmb
                            mutated_act = True
                if 'distancia_km' in act.data_metricas:
                    act.data_metricas['distancia_km'] = round(float(act.data_metricas['distancia_km']) * 0.7, 1)
                    mutated_act = True
                
                if mutated_act:
                    notas_actuales = act.data_metricas.get('notas', '')
                    # Evitar duplicar la nota si ya se escaló
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

    @staticmethod
    def _create_session(objective, fecha, titulo, template, is_taper=False, restricted_tags=None):
        """
        Crea la sesión y sus actividades planificadas basadas en el template
        y escaladas a los RM del usuario, aplicando sustituciones por lesiones.
        """
        # Chequear si ya existe una sesión para evitar duplicados en la regeneración
        if HyroxSession.objects.filter(objective=objective, fecha=fecha).exists():
            return

        restricted_tags = restricted_tags or set()
        sesion = HyroxSession.objects.create(
            objective=objective,
            fecha=fecha,
            titulo=titulo,
            estado='planificado'
        )

        rm_squat = objective.rm_sentadilla or 60.0
        rm_deadlift = objective.rm_peso_muerto or 80.0

        if template == 'calibracion':
            # Phase 8: Sesión Diagnóstico sin pesos estáticos.
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='fuerza',
                nombre_ejercicio='Sentadilla Trasera (Back Squat) [TEST]',
                data_metricas={
                    "planificado": True,
                    "notas": "Hoy vamos a descubrir tu nivel. Haz 3 series de 10 repeticiones. Elige un peso que sientas que podrías hacer 2 o 3 repeticiones más pero decides parar (RPE 7-8). Al terminar, registra el peso exacto en las notas de resultado.",
                    "series": [{"reps": 10} for _ in range(3)]
                }
            )
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='fuerza',
                nombre_ejercicio='Peso Muerto (Deadlift) [TEST]',
                data_metricas={
                    "planificado": True,
                    "notas": "Haz 3 series de 8 reps (RPE 7-8). No busques un máximo hoy, busca un peso técnico que demande esfuerzo pero vayas cómodo.",
                    "series": [{"reps": 8} for _ in range(3)]
                }
            )

        elif template == 'fuerza_metcon':
            # Phase 5: Calibrador de Imbalances (Backend)
            imbalance_type = None
            if rm_deadlift > (rm_squat * 1.5):
                imbalance_type = 'weak_squat'
            elif rm_squat > (rm_deadlift * 1.2):
                imbalance_type = 'weak_deadlift'

            if not is_taper:
                # Phase 7: Sobrecarga Progresiva Dinámica
                dias_para_evento = (objective.fecha_evento - fecha).days
                
                # Determinación de la fase: > 30 días es Base, < 30 es Potencia/Peak
                if dias_para_evento > 30:
                    porcentaje_rm = 0.70
                    reps_obj = 10
                    series_obj = 4
                    fase_nombre = "Fase de Base"
                    rpe_target = 8
                else:
                    porcentaje_rm = 0.85
                    reps_obj = 5
                    series_obj = 4
                    fase_nombre = "Fase de Potencia"
                    rpe_target = 9
                    
                # Aplicamos calibrador de imbalances (Fase 5) sobre la carga dinámica
                if imbalance_type == 'weak_squat':
                    peso_trabajo = rm_squat * porcentaje_rm
                    ejercicio = 'Prensa de Piernas / Hack Squat (Foco Cuádriceps)'
                    notas = f'Ajuste Imbalance: Déficit de cuádriceps. Prioridad Empuje.'
                elif imbalance_type == 'weak_deadlift':
                    peso_trabajo = rm_deadlift * porcentaje_rm
                    ejercicio = 'Peso Muerto Rumano / Hip Thrust'
                    notas = f'Ajuste Imbalance: Déficit cadena posterior. Prioridad Tracción.'
                else:
                    peso_trabajo = rm_squat * porcentaje_rm
                    ejercicio = 'Sentadilla Trasera'
                    notas = f'Equilibrio estructural OK.'

                # --- Sustitución Bio-Segura ---
                # Verificar tags de tren inferior
                restricciones_pierna = {'impacto_vertical', 'flexion_rodilla_profunda', 'empuje_pierna', 'flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo'}
                if restricted_tags and any(tag in restricted_tags for tag in restricciones_pierna):
                    ejercicio = 'Press Militar Sentado / Remo con Mancuerna (Tren Superior)'
                    peso_trabajo = 0  # No aplicamos base RMs de pierna
                    notas = f'⛔ {notas} -> Modificado a Tren Superior por restricciones biomecánicas (Lesión activa).'

                # Phase 7: Generación de "Coach Tips" basados en perfil
                edad = getattr(objective.cliente, 'edad', 35) # Asumimos 35 por defecto si no hay edad explícita, en este MVP
                coach_tip = f"David, estamos en {fase_nombre}. Hoy buscamos un RPE {rpe_target}, guarda {'2' if rpe_target==8 else '1'} reps en reserva. "
                if edad >= 45:
                    coach_tip += f"⚠️ Ajuste por edad (+40): Calentamiento articular estricto de 10 min antes de la primera serie efectiva a {round(peso_trabajo)}kg. Cuida las rodillas en la excéntrica (2s de bajada)."
                elif edad <= 25:
                    coach_tip += f"🚀 Máxima explosividad concéntrica aprovechando tu recuperación de SNC."

                # Phase 8: Metadatos de Ejecución (Tempo y Descanso)
                if fase_nombre == "Fase de Base":
                    tempo_str = "3-0-1-0" # Lentos y controlados para hipertrofia y adaptación
                    descanso_str = "90 seg"
                else:
                    tempo_str = "2-0-X-0" # Más explosivos en concéntrica, máxima potencia
                    descanso_str = "120-180 seg"

                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='fuerza',
                    nombre_ejercicio=ejercicio,
                    data_metricas={
                        "planificado": True,
                        "notas": notas,
                        "coach_tip": coach_tip,
                        "tempo": tempo_str,
                        "descanso": descanso_str,
                        "series": [{"reps": reps_obj, "peso_kg": round(peso_trabajo)} for _ in range(series_obj)]
                    }
                )
            else:
                peso_squat = rm_squat * 0.50
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='fuerza',
                    nombre_ejercicio='Sentadilla Trasera (Activación)',
                    data_metricas={
                        "planificado": True,
                        "series": [{"reps": 5, "peso_kg": round(peso_squat)} for _ in range(3)]
                    }
                )

        elif template == 'cardio':
            is_sub = 'impacto_vertical' in restricted_tags or 'carrera' in restricted_tags
            
            if not is_taper:
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='cardio_sustituto' if is_sub else 'carrera',
                    nombre_ejercicio='SkiErg / Remo Z2' if is_sub else 'Carrera Continua Z2',
                    data_metricas={
                        "planificado": True, 
                        "distancia_km": 6.0, 
                        "notas": "Sustitución metabólica por lesión. Mantener Z2" if is_sub else "Mantener pulsaciones bajas (Z2)"
                    }
                )
            else:
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='cardio_sustituto' if is_sub else 'carrera',
                    nombre_ejercicio='Bici Suave' if is_sub else 'Trote Ligero',
                    data_metricas={
                        "planificado": True, 
                        "distancia_km": 3.0, 
                        "notas": "Protegiendo impacto por lesión" if is_sub else "Solo para mover las piernas"
                    }
                )

        elif template == 'hyrox_stations':
            peso_sled = 100 if 'pro' not in objective.categoria.lower() else 150
            if is_taper:
                peso_sled = peso_sled // 2
                
            # Filter Station Exercises based on Risk Tags
            estaciones = [
                {'nombre': 'Sled Push', 'distancia_m': 50, 'peso_kg': peso_sled, 'tags': ['empuje_pierna', 'carga_distal_pierna']},
                {'nombre': 'Wall Balls', 'series': [{"reps": 20}, {"reps": 20}, {"reps": 20}], 'tags': ['impacto_vertical', 'flexion_rodilla_profunda']},
                {'nombre': 'Burpees Broad Jump', 'distancia_m': 80, 'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'triple_extension_explosiva']},
                {'nombre': 'Sandbag Lunges', 'distancia_m': 80, 'peso_kg': 20, 'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'estabilidad_tobillo']}
            ]
            
            for est in estaciones:
                # Si el ejercicio tiene tags que chocan con las restricciones del usuario, saltamos
                if restricted_tags and any(tag in restricted_tags for tag in est.get('tags', [])):
                    logger.info(f"Bio-Safe: Saltando {est['nombre']} por restricciones biomecánicas.")
                    continue
                    
                nombre = est.pop('nombre')
                est.pop('tags', None)
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='hyrox_station',
                    nombre_ejercicio=nombre,
                    data_metricas={"planificado": True, **est}
                )

        elif template == 'simulacion':
            if not is_taper:
                is_sub = 'impacto_vertical' in restricted_tags or 'carrera' in restricted_tags
                notas_sim = "1km Remo/Ski + 50m Sled Push + 1km Remo/Ski + 50m Sled Pull + 1km Remo/Ski + 50 Empujes" if is_sub else "1km Run + 50m Sled Push + 1km Run + 50m Sled Pull + 1km Run + 50 Wallballs"
                
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='otro',
                    nombre_ejercicio='Simulación Mini-Hyrox' + (' (Adaptado)' if is_sub else ''),
                    data_metricas={
                        "planificado": True, 
                        "notas": notas_sim
                    }
                )

        return sesion
