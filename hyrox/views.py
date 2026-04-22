from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from .forms import HyroxObjectiveForm, HyroxSessionNotesForm, UserInjuryForm, DailyRecoveryEntryForm
from .services import HyroxParserService, HyroxCoachService
from .training_engine import HyroxTrainingEngine
from .models import HyroxObjective, HyroxSession, UserInjury, DailyRecoveryEntry

@login_required
def hyrox_dashboard(request):
    cliente = getattr(request.user, 'cliente_perfil', None)
    if not cliente:
        # Si no tiene perfil de cliente, redirigimos (o manejamos el error)
        messages.error(request, "Necesitas configurar tu perfil de cliente primero.")
        return redirect('/') # O_AQUI redirigir a donde sea adecuado
        
    objetivo_activo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
    
    sesiones_completadas = []
    sesiones_planificadas = []
    stats_semana = {
        'fuerza_completadas': 0, 'fuerza_planificadas': 0,
        'carrera_completadas': 0, 'carrera_planificadas': 0,
        'espe_completadas': 0, 'espe_planificadas': 0,
    }
    
    resumen_semanal = None
    readiness_svg_points = None
    
    if objetivo_activo:
        from .models import HyroxReadinessLog
        hoy = timezone.now().date()

        # Phase 6: Registrar el score de Race Readiness solo si no existe aún hoy
        # (evita recalcular en cada recarga; se invalida automáticamente al día siguiente)
        log_hoy = HyroxReadinessLog.objects.filter(objective=objetivo_activo, fecha=hoy).first()
        if log_hoy:
            current_score = log_hoy.score
        else:
            current_score = objetivo_activo.get_race_readiness_score()
            HyroxReadinessLog.objects.create(objective=objetivo_activo, fecha=hoy, score=current_score)

        # Generar puntos SVG para el mini-gráfico (ancho=100, alto=30)
        logs_list = list(HyroxReadinessLog.objects.filter(objective=objetivo_activo).order_by('fecha'))
        svg_points = []
        if len(logs_list) > 1:
            step_x = 100 / (len(logs_list) - 1)
            for i, log in enumerate(logs_list):
                x = i * step_x
                y = 30 - (log.score * 0.3) # 100% -> y=0, 0% -> y=30
                svg_points.append(f"{x},{y}")
        readiness_svg_points = " ".join(svg_points)

        # Auto-ajuste de calendario (reprogramar sesiones perdidas críticas)
        HyroxTrainingEngine.auto_adjust(objetivo_activo)
        
        sesiones_completadas = HyroxSession.objects.filter(objective=objetivo_activo, estado='completado').order_by('-fecha')

        # Sesiones futuras deduplicadas por fecha (evita duplicados del auto_adjust)
        todas_futuras = list(
            HyroxSession.objects.filter(
                objective=objetivo_activo, estado='planificado', fecha__gte=hoy
            ).prefetch_related('activities').order_by('fecha')
        )
        vistas = set()
        todas_futuras_unicas = []
        for s in todas_futuras:
            if s.fecha not in vistas:
                vistas.add(s.fecha)
                todas_futuras_unicas.append(s)

        sesiones_planificadas = todas_futuras_unicas[:3]

        # Agrupar todas las sesiones futuras por semana para el plan timeline
        DIAS_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        TIPO_LABEL = {
            'fuerza': ('Fuerza', 'fa-dumbbell', '#E8341A'),
            'carrera': ('Carrera', 'fa-running', '#1DC8B8'),
            'hyrox_station': ('Estaciones', 'fa-cube', '#F59E0B'),
            'ergometro': ('Cardio', 'fa-bicycle', '#8B5CF6'),
            'cardio_sustituto': ('Cardio Alt.', 'fa-bicycle', '#8B5CF6'),
            'hiit': ('HIIT', 'fa-fire', '#EF4444'),
            'simulacion': ('Simulación', 'fa-flag', '#E8341A'),
        }

        plan_semanas = []
        semana_buf = []
        semana_num_actual = None
        for s in todas_futuras_unicas:
            dias_diff = (s.fecha - hoy).days
            num_semana = dias_diff // 7
            if semana_num_actual is None:
                semana_num_actual = num_semana
            if num_semana != semana_num_actual:
                if semana_buf:
                    plan_semanas.append({'semana_idx': semana_num_actual, 'sesiones': semana_buf})
                semana_buf = []
                semana_num_actual = num_semana

            tipos_act = [a.tipo_actividad for a in s.activities.all()]
            tipo_principal = tipos_act[0] if tipos_act else 'fuerza'
            tipo_info = TIPO_LABEL.get(tipo_principal, ('Entreno', 'fa-bolt', '#888'))

            actividades_resumen = []
            for act in s.activities.all():
                m = act.data_metricas
                if 'distancia_km' in m:
                    ritmo_str = f" · 🎯 {m['ritmo_objetivo']}" if 'ritmo_objetivo' in m else ''
                    actividades_resumen.append(f"{m['distancia_km']} km{ritmo_str}")
                elif 'distancia_m' in m:
                    peso_m = f" @{m['peso_kg']}kg" if 'peso_kg' in m else ''
                    actividades_resumen.append(f"{act.nombre_ejercicio} {m['distancia_m']}m{peso_m}")
                elif 'series' in m:
                    series_list = m['series']
                    reps = series_list[0].get('reps', '?') if series_list else '?'
                    peso = series_list[0].get('peso_kg', '') if series_list else ''
                    peso_str = f" @{peso}kg" if peso else ''
                    actividades_resumen.append(f"{act.nombre_ejercicio} {len(series_list)}×{reps}{peso_str}")
                else:
                    actividades_resumen.append(act.nombre_ejercicio)

            # Comprobar si hay una sesión completada en la misma fecha
            completada_hoy = HyroxSession.objects.filter(
                objective=objetivo_activo, estado='completado', fecha=s.fecha
            ).first() if s.fecha == hoy else None

            semana_buf.append({
                'sesion': s,
                'dia_str': DIAS_ES[s.fecha.weekday()],
                'tipo_label': tipo_info[0],
                'tipo_icon': tipo_info[1],
                'tipo_color': tipo_info[2],
                'actividades_resumen': actividades_resumen[:3],
                'es_hoy': s.fecha == hoy,
                'es_manana': (s.fecha - hoy).days == 1,
                'completada': completada_hoy is not None,
                'sesion_completada': completada_hoy,
            })

        if semana_buf:
            plan_semanas.append({'semana_idx': semana_num_actual, 'sesiones': semana_buf})
        
        # Desglose de la semana actual
        start_of_week = hoy - timezone.timedelta(days=hoy.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=7)
        sesiones_semana = HyroxSession.objects.filter(
            objective=objetivo_activo,
            fecha__gte=start_of_week,
            fecha__lt=end_of_week
        ).prefetch_related('activities')
        
        for s in sesiones_semana:
            tipos = [a.tipo_actividad for a in s.activities.all()]
            
            is_fuerza = 'fuerza' in tipos
            is_carrera = 'carrera' in tipos
            is_espe = any(t in ['hyrox_station', 'ergometro'] for t in tipos)
            
            # Casos bordes: si hay títulos explícitos en caso de que las acties no esten claras
            if not tipos:
                titulo_lower = (s.titulo or '').lower()
                if 'fuerza' in titulo_lower: is_fuerza = True
                if 'carrera' in titulo_lower or 'aeróbico' in titulo_lower: is_carrera = True
                if 'estacion' in titulo_lower or 'específicas' in titulo_lower: is_espe = True
                if 'simulación' in titulo_lower:
                    is_carrera = True
                    is_espe = True

            if is_fuerza:
                stats_semana['fuerza_planificadas'] += 1
                if s.estado == 'completado': stats_semana['fuerza_completadas'] += 1
            if is_carrera:
                stats_semana['carrera_planificadas'] += 1
                if s.estado == 'completado': stats_semana['carrera_completadas'] += 1
            if is_espe:
                stats_semana['espe_planificadas'] += 1
                if s.estado == 'completado': stats_semana['espe_completadas'] += 1

        stats_semana['total_planificadas'] = stats_semana['fuerza_planificadas'] + stats_semana['carrera_planificadas'] + stats_semana['espe_planificadas']
        stats_semana['total_completadas'] = stats_semana['fuerza_completadas'] + stats_semana['carrera_completadas'] + stats_semana['espe_completadas']

        # Phase 6: Resumen Semanal Flash Card (Solo Domingos)
        resumen_semanal = None
        if hoy.weekday() == 6 and stats_semana['total_completadas'] > 0:
            total_rpe = 0
            rpe_count = 0
            volumen_kg = 0
            distancia_km = 0
            
            for s in sesiones_semana:
                if s.estado == 'completado':
                    if s.rpe_global:
                        total_rpe += s.rpe_global
                        rpe_count += 1
                        
                    for act in s.activities.all():
                        if act.tipo_actividad == 'fuerza' and 'series' in act.data_metricas:
                            for serie in act.data_metricas['series']:
                                reps = serie.get('reps', 0)
                                peso = serie.get('peso_kg', 0)
                                if reps and peso:
                                    volumen_kg += (int(reps) * float(peso))
                        elif act.tipo_actividad == 'carrera' and 'distancia_km' in act.data_metricas:
                            try:
                                distancia_km += float(act.data_metricas['distancia_km'])
                            except ValueError:
                                pass
            
            resumen_semanal = {
                'rpe_medio': round(total_rpe / rpe_count, 1) if rpe_count > 0 else 0,
                'volumen_kg': round(volumen_kg),
                'distancia_km': round(distancia_km, 2)
            }

        # Phase 10: Enfoque Mental y Equilibrio Estratégico
        mental_focus = None
        if hoy.weekday() == 0: # Lunes
            mental_focus = "David, esta semana el entrenamiento es tu ancla de disciplina. No es solo fitness, es el orden que estás construyendo."
            
        strength_balance = objetivo_activo.get_strength_balance()
        readiness_breakdown = objetivo_activo.get_readiness_breakdown()
        
        pace_prediction = None
        if objetivo_activo.tiempo_5k_base:
            pace_prediction = f"Basado en tu test de {objetivo_activo.tiempo_5k_base}, proyección recta: recortar 15 seg/km por semana para el sub-25:00."

        # Phase 11: Identidad Consciente y Smart Alerts
        morning_briefing = None
        # Idealmente sería usando la zona horaria del usuario, asumimos hora del servidor por ahora
        if timezone.now().hour <= 11:
            morning_briefing = "Hoy no entrenas para demostrar nada a nadie, entrenas para construir al David que tú quieres ser."
            
        daily_push = objetivo_activo.get_daily_push()
        
        smart_alerts = []
        last_session = objetivo_activo.sessions.filter(estado='completado').order_by('-fecha').first()
        if last_session:
            # Alerta Recuperación (fatiga alta ayer o hoy)
            if last_session.muscle_fatigue_index == 'Alta' and (hoy - last_session.fecha).days <= 1:
                smart_alerts.append("Buen esfuerzo en la sesión pasada. No olvides hidratarte bien hoy para que tus cuádriceps recuperen para lo próximo.")
            
            # Alerta Consistencia (>48h)
            if (hoy - last_session.fecha).days >= 2:
                smart_alerts.append("David, cada sesión es un paso hacia tu nueva identidad y tu casa propia. ¿Ajustamos el entreno de hoy para que encaje en tu tarde?")
        else:
            smart_alerts.append("Es el momento perfecto para arrancar tu primer bloque. La constancia es la clave.")

    competition_progress = None
    macro_data = None
    lesion_activa = None
    ultimo_reporte = None
    
    if objetivo_activo:
        from .services import CompetitionStandardsService, HyroxMacrocycleEngine
        from .models import UserInjury, DailyRecoveryEntry
        competition_progress = CompetitionStandardsService.get_user_standards_progress(request.user.id)
        macro_data = HyroxMacrocycleEngine.get_current_phase(objetivo_activo, return_metadata=True)
        lesion_activa = UserInjury.objects.filter(cliente=cliente, activa=True).first()
        
        sustituciones_activas = []
        sustituciones_dict = {} # <-- Añadimos un diccionario para pasarlo al template de forma fácil
        sustituciones_seen = set()  # Para evitar duplicados
        # PHASE 16: BIO-SAFE UNIFICATION (Dynamic Substitution)
        from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
        from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
        from core.bio_context import BioContextProvider

        bio_data = BioContextProvider.get_current_restrictions(cliente)
        restricted_tags = bio_data.get('tags', set())

        if restricted_tags:
            # Find phase name for SelectorEjercicios
            fase_nombre_temp = 'hipertrofia'
            if objetivo_activo:
                try:
                    # Attempt to extract phase from macrocycle
                    from hyrox.services import HyroxMacrocycleEngine
                    fase_data = HyroxMacrocycleEngine.get_current_phase(objetivo_activo)
                    fase_nombre_temp = fase_data.get('fase', 'hipertrofia').lower()
                except: pass

            safe_replacements_cache = {}

            for plan in sesiones_planificadas:
                plan.is_blocked_by_injury = False
                # We'll use this to show adapted title
                plan.titulo_sustituido = plan.titulo
                
                for act in plan.activities.all():
                    act.display_name = act.nombre_ejercicio # Default
                    ej_name = act.nombre_ejercicio.lower()
                    # 1. Identify risk tags for THIS exercise
                    ej_tags = set()
                    # Generic lookup (very basic, similar to entrenos/views.py)
                    for g_name, g_tipos in EJERCICIOS_DATABASE.items():
                        for cat in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
                            for e in g_tipos.get(cat, []):
                                if isinstance(e, dict) and e.get('nombre', '').lower() in ej_name:
                                    ej_tags.update(e.get('risk_tags', []))
                                    ej_grupo = g_name
                                    break
                            if ej_tags: break
                        if ej_tags: break
                    
                    # 2. Check if blocked
                    if ej_tags.intersection(restricted_tags):
                        plan.is_blocked_by_injury = True
                        act.is_substituted = True
                        
                        # 3. Find replacement
                        if ej_grupo not in safe_replacements_cache:
                            safe_groups = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
                                numero_bloque=1,
                                fase=fase_nombre_temp,
                                cliente=cliente
                            )
                            safe_replacements_cache[ej_grupo] = safe_groups.get(ej_grupo, [])
                        
                        safe_opts = safe_replacements_cache.get(ej_grupo, [])
                        if safe_opts:
                            substitute = safe_opts[0]
                            act.sustituto = substitute.get('nombre', 'Ejercicio Seguro')
                            act.display_name = act.sustituto # Override for template
                            # Mapping icon from mapping if available
                            act.sustituto_icon = 'fa-shield-alt'
                            plan.titulo_sustituido = f"🛡️ Sesión Adaptada: {act.sustituto}"
                    else:
                        act.display_name = act.nombre_ejercicio

    context = {
        'competition_progress': competition_progress,
        'macro_data': macro_data,
        'cliente': cliente,
        'objetivo_activo': objetivo_activo,
        'sesiones': sesiones_completadas,
        'proximas_sesiones': sesiones_planificadas,
        'plan_semanas': plan_semanas if objetivo_activo else [],
        'stats_semana': stats_semana,
        'resumen_semanal': resumen_semanal,
        'readiness_svg_points': readiness_svg_points,
        'mental_focus': mental_focus if objetivo_activo else None,
        'strength_balance': strength_balance if objetivo_activo else None,
        'readiness_breakdown': readiness_breakdown if objetivo_activo else None,
        'pace_prediction': pace_prediction if objetivo_activo else None,
        'morning_briefing': morning_briefing if objetivo_activo else None,
        'daily_push': daily_push if objetivo_activo else None,
        'smart_alerts': smart_alerts if objetivo_activo else [],
        'lesion_activa': lesion_activa,
        'ultimo_reporte': ultimo_reporte,
        'sustituciones_activas': sustituciones_activas if 'sustituciones_activas' in locals() else [],
        'sustituciones_dict': sustituciones_dict if 'sustituciones_dict' in locals() else {},
    }
    return render(request, 'hyrox/dashboard.html', context)

@login_required
def crear_objetivo(request):
    cliente = getattr(request.user, 'cliente_perfil', None)
    
    if request.method == 'POST':
        form = HyroxObjectiveForm(request.POST)
        if form.is_valid():
            objetivo = form.save(commit=False)
            objetivo.cliente = cliente
            # Desactivar cualquier objetivo activo previo
            HyroxObjective.objects.filter(cliente=cliente, estado='activo').update(estado='cancelado')
            objetivo.save()
            
            # ¡Generar el plan inteligente de Hyrox!
            HyroxTrainingEngine.generate_training_plan(objetivo)
            
            messages.success(request, "Objetivo Hyrox creado y plan de entrenamiento generado correctamente. ¡A por todas!")
            return redirect('hyrox:dashboard')
    else:
        # Pre-rellenar con los datos que ya tenemos del cliente o del objetivo activo si los hay
        initial_data = {}
        if cliente:
            objetivo_actual = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
            if objetivo_actual:
                initial_data = {
                    'categoria': objetivo_actual.categoria,
                    'fecha_evento': objetivo_actual.fecha_evento,
                    'rm_peso_muerto': objetivo_actual.rm_peso_muerto,
                    'rm_sentadilla': objetivo_actual.rm_sentadilla,
                    'tiempo_5k_base': objetivo_actual.tiempo_5k_base,
                    'nivel_experiencia': objetivo_actual.nivel_experiencia,
                    'lesiones_previas': objetivo_actual.lesiones_previas,
                    'material_disponible': objetivo_actual.material_disponible,
                    'dias_preferidos': objetivo_actual.dias_preferidos
                }
        form = HyroxObjectiveForm(initial=initial_data)
        
    return render(request, 'hyrox/crear_objetivo.html', {'form': form})

@login_required
def cancelar_objetivo(request, objective_id):
    """
    Permite al usuario borrar su objetivo actual y todos los entrenamientos asociados para empezar de cero.
    """
    objetivo = get_object_or_404(HyroxObjective, id=objective_id, cliente=getattr(request.user, 'cliente_perfil', None))
    # Un borrado físico limpia completamente la DB para este usuario (On delete cascade borra sesiones/actividades)
    objetivo.delete()
    messages.success(request, "Entrenamientos y objetivo reseteados correctamente. ¡Pizarra limpia para empezar de cero!")
    return redirect('hyrox:dashboard')

@login_required
def regenerar_plan(request, objective_id):
    """Elimina todas las sesiones planificadas futuras y regenera el plan completo."""
    objetivo = get_object_or_404(HyroxObjective, id=objective_id, cliente=request.user.cliente_perfil)
    hoy = timezone.now().date()
    eliminadas = HyroxSession.objects.filter(objective=objetivo, estado='planificado', fecha__gte=hoy).delete()
    HyroxTrainingEngine.generate_training_plan(objetivo)
    messages.success(request, "Plan regenerado correctamente con el nuevo motor de entrenamiento.")
    return redirect('hyrox:dashboard')


@login_required
def registrar_entrenamiento(request, objective_id, session_id=None):
    objetivo = get_object_or_404(HyroxObjective, id=objective_id, cliente=request.user.cliente_perfil)
    hoy = timezone.now().date()

    # Si se pasa un session_id explícito, cargamos esa sesión concreta;
    # si no, buscamos la sesión de hoy (comportamiento previo para el botón "Registrar Entreno")
    if session_id:
        sesion_planificada = get_object_or_404(HyroxSession, id=session_id, objective=objetivo)
    else:
        sesion_planificada = HyroxSession.objects.filter(
            objective=objetivo,
            fecha=hoy,
            estado='planificado'
        ).first()

    from .models import UserInjury
    lesion_activa = UserInjury.objects.filter(cliente=request.user.cliente_perfil, activa=True).first()

    if request.method == 'POST':
        form = HyroxSessionNotesForm(request.POST)
        if form.is_valid():
            if sesion_planificada:
                # Actualizar la sesión planificada existente (no crear una nueva)
                for field, value in form.cleaned_data.items():
                    if field != 'sustituir_material' and hasattr(sesion_planificada, field):
                        setattr(sesion_planificada, field, value)
                sesion = sesion_planificada
            else:
                sesion = form.save(commit=False)
                sesion.objective = objetivo
                sesion.fecha = hoy
            sesion.estado = 'planificado'
            sesion.save()

            # Procesamiento de la IA
            if sesion.notas_raw:
                sustituir_material = form.cleaned_data.get('sustituir_material', False)
                parsed_data = HyroxParserService.parse_workout_text(sesion.notas_raw, sustituir_material=sustituir_material)
                if parsed_data:
                    resultados_save = HyroxParserService.save_parsed_session(sesion, parsed_data)
                    actividades = resultados_save.get('activities', []) if isinstance(resultados_save, dict) else []
                    new_records = resultados_save.get('new_records', []) if isinstance(resultados_save, dict) else []
                    
                    feedback_str = parsed_data.get('feedback', parsed_data.get('Feedback', ''))
                    
                    if actividades:
                        messages.success(request, f"Se han extraído mágicamente {len(actividades)} bloques de tu entrenamiento.")
                        
                        if new_records:
                            for record in new_records:
                                messages.success(request, f"🚀 PB Roto: {record['ejercicio']} estimado ahora es {record['new']}kg.")

                        # Phase 5 & 8: Dynamic UI Feedback Flash Generation
                        if sustituir_material and feedback_str:
                             messages.info(request, f"🤖 Auto-Ajuste de Equivalencia: {feedback_str}")
                        elif feedback_str:
                             messages.info(request, f"🧠 Entrenador IA: {feedback_str}")

                    else:
                        messages.success(request, "Sesión guardada. No se detectaron ejercicios estructurados en el texto.")
                else:
                    messages.warning(request, "No se pudieron extraer ejercicios del texto. Revisa el formato.")
            else:
                messages.success(request, "Datos de la sesión guardados sin procesamiento IA.")
                actividades = sesion.activities.all()

            # --- CHECK BIO-SAFETY: VALIDACIÓN DE LESIONES ---
            # UserInjury ya está importado al inicio de la función
            bloqueado_por_bio_safety = False
            
            if lesion_activa and lesion_activa.tags_restringidos and actividades:
                nombres_ejercicios_raw = [a.nombre_ejercicio.lower() for a in actividades]
                mapping_inverso = {
                    'carrera': 'impacto_vertical', 'run': 'impacto_vertical', 'running': 'impacto_vertical',
                    'prensa': 'estabilidad_gemelo', 'squat': 'estabilidad_gemelo', 'hack squat': 'estabilidad_gemelo', 'sentadilla': 'estabilidad_gemelo',
                    'wall ball': 'flexion_rodilla_profunda', 'wall balls': 'flexion_rodilla_profunda',
                    'sled push': 'empuje_pierna', 'empuje trineo': 'empuje_pierna',
                    'salto': 'flexion_plantar', 'saltos': 'flexion_plantar', 'box jump': 'flexion_plantar', 'broad jumps': 'flexion_plantar',
                    'burpee': 'empuje_hombro', 'burpees': 'empuje_hombro', 'press': 'empuje_hombro',
                    'dominada': 'traccion_superior', 'pull-up': 'traccion_superior', 'muscle up': 'traccion_superior',
                    'flexion': 'empuje_horizontal', 'push up': 'empuje_horizontal', 'push-ups': 'empuje_horizontal',
                    'peso muerto': 'lumbar_carga', 'deadlift': 'lumbar_carga',
                    'sandbag lunge': 'rotacion_tronco', 'lunges': 'rotacion_tronco'
                }
                
                tags_detectados = set()
                for nombre in nombres_ejercicios_raw:
                    for key, tag in mapping_inverso.items():
                        if key in nombre:
                            tags_detectados.add(tag)
                            
                tags_violados = [tag for tag in tags_detectados if tag in lesion_activa.tags_restringidos]
                
                if tags_violados:
                    if lesion_activa.fase == 'AGUDA':
                        msg = f"⚠️ Cuidado David, este movimiento compromete tu recuperación. Has realizado ejercicios incompatibles con tu lesión en fase AGUDA ({', '.join(tags_violados)})."
                    else:
                        msg = f"🛑 Check-in bloqueado por seguridad biológica. Has realizado ejercicios incompatibles con tu lesión en fase {lesion_activa.get_fase_display()} ({', '.join(tags_violados)})."
                    
                    bloqueado_por_bio_safety = True
                    sesion.estado = 'planificado' # Revert check-in
                    sesion.save()
                    messages.error(request, msg)

            if not bloqueado_por_bio_safety:
                sesion.estado = 'completado'
                sesion.save()
                
                # Phase 8 & 9 & 14: Bucle de Feedback Continuo Post-Procesamiento.
                # 1. Ajuste de volumen inmediato por Energía Pre-Entreno
                HyroxTrainingEngine.scale_volume_by_energy(sesion)
                
                # 2. Evaluamos la sesión completada (RPE, Volumen) y ajustamos la(s) siguiente(s)
                alertas = HyroxTrainingEngine.apply_continuous_adaptation(sesion)
                if alertas:
                     for alerta in alertas:
                          messages.info(request, f"⚡ {alerta}")
                
            return redirect('hyrox:dashboard')
    else:
        # Phase 16: Bio-Safe Dynamic Substitution for Registration
        from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
        from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
        from core.bio_context import BioContextProvider

        cliente = request.user.cliente_perfil
        bio_data = BioContextProvider.get_current_restrictions(cliente)
        restricted_tags = bio_data.get('tags', set())

        if sesion_planificada:
            safe_replacements_cache = {}
            fase_nombre_temp = 'hipertrofia'
            try:
                from hyrox.services import HyroxMacrocycleEngine
                fase_data = HyroxMacrocycleEngine.get_current_phase(objetivo)
                fase_nombre_temp = fase_data.get('fase', 'hipertrofia').lower()
            except: pass

            # Prepare activities for the context to preserve display_name and is_substituted
            actividades_planificadas = list(sesion_planificada.activities.all())
            for act in actividades_planificadas:
                act.display_name = act.nombre_ejercicio # Default
                
                # Check for Bio-Safe issues
                ej_name = act.nombre_ejercicio.lower()
                ej_tags = set()
                ej_grupo = None
                for g_name, g_tipos in EJERCICIOS_DATABASE.items():
                    for cat in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
                        for e in g_tipos.get(cat, []):
                            if isinstance(e, dict) and e.get('nombre', '').lower() in ej_name:
                                ej_tags.update(e.get('risk_tags', []))
                                ej_grupo = g_name
                                break
                        if ej_tags: break
                    if ej_tags: break
                
                if ej_tags.intersection(restricted_tags) and ej_grupo:
                    if ej_grupo not in safe_replacements_cache:
                        safe_groups = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
                            numero_bloque=1,
                            fase=fase_nombre_temp,
                            cliente=cliente
                        )
                        safe_replacements_cache[ej_grupo] = safe_groups.get(ej_grupo, [])
                    
                    safe_opts = safe_replacements_cache.get(ej_grupo, [])
                    if safe_opts:
                        act.display_name = safe_opts[0].get('nombre', act.nombre_ejercicio)
                        act.is_substituted = True

        form = HyroxSessionNotesForm(initial={'titulo': sesion_planificada.titulo if sesion_planificada else ""})
        
    return render(request, 'hyrox/registrar_entrenamiento.html', {
        'form': form, 
        'objetivo': objetivo,
        'sesion_planificada': sesion_planificada,
        'actividades_planificadas': actividades_planificadas if 'actividades_planificadas' in locals() else sesion_planificada.activities.all() if sesion_planificada else [],
        'lesion_activa': lesion_activa
    })

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@login_required
def registrar_entrenamiento_ia(request, session_id):
    """
    Endpoint AJAX para procesar el log en texto plano usando la IA sin recargar la página.
    """
    if request.method == 'POST':
        sesion = get_object_or_404(HyroxSession, id=session_id, objective__cliente=getattr(request.user, 'cliente_perfil', None))
        texto_usuario = request.POST.get('notas_raw')
        usa_equivalencias = request.POST.get('sustituir_material') == 'true' or request.POST.get('sustituir_material') == 'on'

        # Guardamos el raw text
        sesion.notas_raw = texto_usuario
        sesion.save()

        # 1. Llamamos al servicio de Gemini
        parsed_data = HyroxParserService.parse_workout_text(texto_usuario, usa_equivalencias)
        
        if parsed_data:
            # Vaciamos actividades viejas si existieran para evitar duplicados en reprocesos
            sesion.activities.all().delete()
            
            # 2. Creamos las actividades y se guarda el feedback (eso lo hace el parser / create_activities)
            HyroxParserService.create_activities_from_parsed_data(sesion, parsed_data)
            
            # --- CHECK BIO-SAFETY: VALIDACIÓN DE LESIONES ---
            from .models import UserInjury
            lesion_activa = UserInjury.objects.filter(cliente=getattr(request.user, 'cliente_perfil', None), activa=True).first()
            actividades = sesion.activities.all()
            bloqueado_por_bio_safety = False
            
            if lesion_activa and lesion_activa.tags_restringidos and actividades:
                nombres_ejercicios_raw = [a.nombre_ejercicio.lower() for a in actividades]
                mapping_inverso = {
                    'carrera': 'impacto_vertical', 'run': 'impacto_vertical', 'running': 'impacto_vertical',
                    'prensa': 'estabilidad_gemelo', 'squat': 'estabilidad_gemelo', 'hack squat': 'estabilidad_gemelo', 'sentadilla': 'estabilidad_gemelo',
                    'wall ball': 'flexion_rodilla_profunda', 'wall balls': 'flexion_rodilla_profunda',
                    'sled push': 'empuje_pierna', 'empuje trineo': 'empuje_pierna',
                    'salto': 'flexion_plantar', 'saltos': 'flexion_plantar', 'box jump': 'flexion_plantar', 'broad jumps': 'flexion_plantar',
                    'burpee': 'empuje_hombro', 'burpees': 'empuje_hombro', 'press': 'empuje_hombro',
                    'dominada': 'traccion_superior', 'pull-up': 'traccion_superior', 'muscle up': 'traccion_superior',
                    'flexion': 'empuje_horizontal', 'push up': 'empuje_horizontal', 'push-ups': 'empuje_horizontal',
                    'peso muerto': 'lumbar_carga', 'deadlift': 'lumbar_carga',
                    'sandbag lunge': 'rotacion_tronco', 'lunges': 'rotacion_tronco'
                }
                
                tags_detectados = set()
                for nombre in nombres_ejercicios_raw:
                    for key, tag in mapping_inverso.items():
                        if key in nombre:
                            tags_detectados.add(tag)
                            
                tags_violados = [tag for tag in tags_detectados if tag in lesion_activa.tags_restringidos]
                
                if tags_violados:
                    bloqueado_por_bio_safety = True
                    sesion.estado = 'planificado' # Revert check-in
                    sesion.save()
                    return JsonResponse({
                        'status': 'error',
                        'message': f"🛑 Check-in bloqueado por seguridad biológica. Has realizado ejercicios incompatibles con tu lesión en fase {lesion_activa.get_fase_display()}. Realiza la alternativa adaptada."
                    })

            sesion.estado = 'completado'
            # Save final to trigger any post_save signals (like the one we just made)
            sesion.save()
            
            # Formatear la respuesta JSON
            feedback = parsed_data.get('feedback', '')
            score = sesion.ai_evaluation_score if sesion.ai_evaluation_score else parsed_data.get('ai_evaluation_score', None)
            
            # 3. Lógica de Visualización Estratégica
            obj = sesion.objective
            
            return JsonResponse({
                'status': 'success',
                'feedback': feedback,
                'score': score,
                'objective_data': {
                    'strength_balance': obj.get_strength_balance(),
                    'readiness_breakdown': obj.get_readiness_breakdown()
                }
            })
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def procesar_con_ia(request, session_id):
    """Procesa retroactivamente las notas_raw de una sesión con Gemini."""
    from .models import HyroxSession
    from .services import HyroxParserService
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    
    if request.method == 'POST':
        session = get_object_or_404(
            HyroxSession,
            id=session_id,
            objective__cliente__user=request.user
        )
        
        if not session.notas_raw:
            messages.warning(request, "Esta sesión no tiene texto en bruto para procesar.")
            return redirect('hyrox:dashboard')
        
        parsed_data = HyroxParserService.parse_workout_text(session.notas_raw)
        
        if parsed_data:
            result = HyroxParserService.save_parsed_session(session, parsed_data)
            if result and result.get('activities'):
                session.parsed_by_ia = True
                session.save()
                count = len(result.get('activities', []))
                messages.success(request, f"✅ ¡Procesado con IA! Se han encontrado {count} actividades en este entrenamiento.")
            else:
                messages.warning(request, "La IA procesó el texto pero no encontró actividades para guardar. Revisa que el texto incluya ejercicios.")
        else:
            messages.error(request, "No se pudo conectar con la API de Gemini. Espera un minuto e inténtalo de nuevo.")
    
    return redirect('hyrox:dashboard')

@login_required
@login_required
def editar_sesion_hyrox(request, session_id):
    from .models import HyroxActivity

    session = get_object_or_404(
        HyroxSession,
        id=session_id,
        objective__cliente__user=request.user,
    )

    if request.method == 'POST':
        # Campos de sesión
        rpe = request.POST.get('rpe_global')
        if rpe: session.rpe_global = int(rpe)
        tiempo = request.POST.get('tiempo_total_minutos')
        if tiempo: session.tiempo_total_minutos = int(tiempo)
        hr_med = request.POST.get('hr_media')
        if hr_med: session.hr_media = int(hr_med)
        hr_max = request.POST.get('hr_maxima')
        if hr_max: session.hr_maxima = int(hr_max)

        # Procesar actividades directamente (sin re-parseo)
        _CARRERA_TIPOS = {'carrera', 'cardio_sustituto'}
        _ESTACION_TIPOS = {'hyrox_station', 'ergometro', 'isometrico', 'hiit', 'remo', 'skierg', 'bici', 'otro'}
        _REPS_STATIONS = {'wall ball', 'wall balls', 'burpee broad jump', 'burpees broad jump'}
        ids_borrar = set(request.POST.getlist('act_delete'))
        for act in session.activities.all():
            if str(act.id) in ids_borrar:
                act.delete()
                continue
            m = dict(act.data_metricas or {})
            ta = act.tipo_actividad or ''
            nombre_lower = (act.nombre_ejercicio or '').lower()
            is_carrera = ta in _CARRERA_TIPOS or 'distancia_km' in m
            is_fuerza = ta == 'fuerza' or 'series' in m
            is_reps_station = any(kw in nombre_lower for kw in _REPS_STATIONS) and ta in _ESTACION_TIPOS
            if is_carrera:
                km = request.POST.get(f'act_km_{act.id}')
                mins = request.POST.get(f'act_min_{act.id}')
                if km: m['distancia_km'] = float(km)
                if mins and km and float(km) > 0 and float(mins) > 0:
                    secs = round((float(mins) * 60) / float(km))
                    m['ritmo_real'] = f"{secs // 60}:{str(secs % 60).zfill(2)}/km"
                    m['tiempo_minutos'] = float(mins)
            elif is_fuerza:
                series = m.get('series') or []
                for i, serie in enumerate(series):
                    reps = request.POST.get(f'act_reps_{act.id}_{i}')
                    kg = request.POST.get(f'act_kg_serie_{act.id}_{i}')
                    if reps: serie['reps'] = int(reps)
                    if kg: serie['peso_kg'] = float(kg); serie['peso'] = float(kg)
                m['series'] = series
            elif is_reps_station:
                reps = request.POST.get(f'act_reps_total_{act.id}')
                kg = request.POST.get(f'act_kg_{act.id}')
                if reps:
                    peso = float(kg) if kg else None
                    m['series'] = [{'reps': int(reps), 'peso_kg': peso}] if peso else [{'reps': int(reps)}]
                if kg: m['peso_kg'] = float(kg)
            else:
                # estacion por distancia u otro
                distm = request.POST.get(f'act_distm_{act.id}')
                kg = request.POST.get(f'act_kg_{act.id}')
                if distm: m['distancia_m'] = float(distm)
                if kg: m['peso_kg'] = float(kg)
            act.data_metricas = m
            act.save()

        session.estado = 'completado'
        session.save()
        messages.success(request, "Sesión actualizada. El plan se ha re-adaptado.")
        return redirect('hyrox:dashboard')

    TIPO_ACT_CARRERA = {'carrera', 'cardio_sustituto'}
    TIPO_ACT_ESTACION = {'hyrox_station', 'ergometro', 'isometrico', 'hiit', 'remo', 'skierg', 'bici', 'otro'}
    # Estaciones Hyrox que funcionan por reps+kg, no por distancia
    ESTACIONES_REPS = {'wall ball', 'wall balls', 'burpee broad jump', 'burpees broad jump'}

    actividades_ctx = []
    for act in session.activities.all():
        m = act.data_metricas or {}
        ta = act.tipo_actividad or ''
        nombre_lower = (act.nombre_ejercicio or '').lower()
        es_reps_station = any(kw in nombre_lower for kw in ESTACIONES_REPS)

        if ta in TIPO_ACT_CARRERA or m.get('distancia_km'):
            tipo = 'carrera'
        elif m.get('series'):
            # Si ya tiene series guardadas, editar como fuerza independientemente del tipo
            tipo = 'fuerza'
        elif ta == 'fuerza':
            tipo = 'fuerza'
        elif ta in TIPO_ACT_ESTACION and m.get('distancia_m') is not None:
            tipo = 'estacion'
        elif ta in TIPO_ACT_ESTACION and es_reps_station:
            # Wall Balls y similares: reps + kg, aunque aún no tengan datos guardados
            tipo = 'reps_kg'
        elif ta in TIPO_ACT_ESTACION:
            tipo = 'estacion'
        elif m.get('peso_kg') is not None:
            tipo = 'estacion'
        else:
            tipo = 'otro'

        series = m.get('series') or []
        # Para reps_kg sin series guardadas, crear una fila vacía para que el usuario rellene
        reps_total = m.get('reps_total', '')
        if tipo == 'reps_kg' and series:
            # Consolidar todas las series en total reps
            reps_total = sum(int(s.get('reps', 0)) for s in series)

        actividades_ctx.append({
            'id': act.id,
            'nombre': act.nombre_ejercicio or act.get_tipo_actividad_display(),
            'tipo': tipo,
            'tipo_actividad': ta,
            'km': m['distancia_km'] if 'distancia_km' in m else '',
            'tiempo_min': m['tiempo_minutos'] if 'tiempo_minutos' in m else '',
            'distm': m['distancia_m'] if 'distancia_m' in m else '',
            'kg': m['peso_kg'] if 'peso_kg' in m else '',
            'series': series,
            'reps_total': reps_total,
        })

    return render(request, 'hyrox/editar_sesion.html', {
        'session': session,
        'actividades': actividades_ctx,
    })


@login_required
def borrar_entrenamiento(request, session_id):
    if request.method == 'POST':
        from .models import HyroxSession
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        # Obtenemos la sesión verificando que pertenezca al usuario activo
        session = get_object_or_404(
            HyroxSession, 
            id=session_id, 
            objective__cliente__user=request.user
        )
        session.delete()
        messages.success(request, "Entrenamiento eliminado correctamente.")
        
    return redirect('hyrox:dashboard')

import json
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class CoachInteractionView(View):
    """
    Punto de entrada único para el chat del dashboard.
    Contacta al HyroxCoachService para decidir si es registro o charla.
    """
    def post(self, request, *args, **kwargs):
        try:
            # Parsear datos de entrada (Soporta JSON o form-data)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                session_id = data.get('session_id')
                user_input = data.get('user_input')
            else:
                session_id = request.POST.get('session_id')
                user_input = request.POST.get('user_input')

            if not user_input:
                return JsonResponse({'status': 'error', 'message': 'No se proporcionó ningún texto.'}, status=400)

            # Obtener sesión actual (Si session_id es proporcionado)
            session = None
            if session_id:
                session = get_object_or_404(
                    HyroxSession, 
                    id=session_id, 
                    objective__cliente__user=request.user
                )

            # Llamada al nuevo HyroxCoachService
            from .services import HyroxCoachService
            
            # Phase Z: Extraer contexto e identificar intención primero para ver si necesitamos sesión ad-hoc
            contexto = HyroxCoachService._obtener_contexto_atleta(request.user.id)
            if not contexto:
                return JsonResponse({'status': 'error', 'message': "No tienes un objetivo Hyrox activo."}, status=400)
                
            intencion = HyroxCoachService._clasificar_intencion(user_input, contexto)
            
            # Si quiere registrar entreno pero no mandó sesión, buscamos la de hoy o la creamos
            if intencion == "registro" and not session:
                from django.utils import timezone
                from .models import HyroxObjective
                hoy = timezone.now().date()
                objetivo_activo = HyroxObjective.objects.filter(cliente__user=request.user, estado='activo').first()
                if objetivo_activo:
                    # Buscar la planificada de hoy si existe
                    session = HyroxSession.objects.filter(objective=objetivo_activo, fecha=hoy, estado='planificado').first()
                    if not session:
                        # Crear Ad Hoc
                        session = HyroxSession.objects.create(
                            objective=objetivo_activo,
                            titulo='Entrenamiento Libre IA',
                            fecha=hoy,
                            estado='planificado', # temporal, se completará abajo
                            tipo_fase='hibrido',
                            score_dificultad=5
                        )

            resultado = HyroxCoachService.procesar_mensaje(
                user_id=request.user.id,
                texto_usuario=user_input,
                session=session
            )

            if resultado.get("tipo") == "error":
                return JsonResponse({'status': 'error', 'message': resultado.get("mensaje")}, status=400)

            # Formar respuesta base
            response_data = {
                'status': 'success',
                'tipo': resultado.get('tipo'),
                'coach_message': resultado.get('mensaje'),
            }

            # Si es registro y tenemos una sesión, actualizamos estados y extraemos datos enriquecidos
            if resultado.get('tipo') == 'registro' and session:
                # Marcar sesión como completada y guardar notas brutas
                session.estado = 'completado'
                session.notas_raw = user_input
                
                # El servicio guarda feedback_ia y score internamente en la sesión
                # Aseguramos el guardado
                session.save()
                
                # Recopilar métricas actualizadas del objetivo para enriquecer la UI
                objetivo = session.objective
                response_data['new_readiness_score'] = objetivo.get_race_readiness_score()
                response_data['strength_balance'] = objetivo.get_strength_balance()
                
                # Devolver la lista de actividades recién creadas
                actividades = session.activities.all()
                actividades_lista = []
                for act in actividades:
                    actividades_lista.append({
                        'tipo': act.get_tipo_actividad_display(),
                        'nombre': act.nombre_ejercicio,
                        'metricas': act.data_metricas
                    })
                response_data['updated_activities'] = actividades_lista
                
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class GetGreetingView(View):
    """
    Endpoint de carga inicial para el chatbot del dashboard.
    Devuelve un saludo proactivo y el estado actual de los indicadores.
    """
    def get(self, request, *args, **kwargs):
        try:
            from .services import HyroxCoachService
            mensaje = HyroxCoachService.get_proactive_greeting(request.user.id)
            
            # Recuperar KPIs para inicializar el UI si es necesario
            objetivo = HyroxObjective.objects.filter(cliente__user=request.user, estado='activo').first()
            
            readiness = objetivo.get_race_readiness_score() if objetivo else 0
            balance = objetivo.get_strength_balance() if objetivo else None
            
            return JsonResponse({
                'status': 'success',
                'greeting': mensaje,
                'readiness_score': readiness,
                'strength_balance': balance
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def reportar_lesion(request):
    cliente = getattr(request.user, 'cliente_perfil', None)
    if not cliente:
        messages.error(request, "Necesitas un perfil de cliente para reportar una lesión.")
        return redirect('hyrox:dashboard')
        
    if request.method == 'POST':
        form = UserInjuryForm(request.POST)
        if form.is_valid():
            lesion = form.save(commit=False)
            lesion.cliente = cliente
            lesion.activa = True
            
            # La fase se recoge del formulario ahora ('AGUDA' por defecto)
            lesion.fase = form.cleaned_data.get('fase', 'AGUDA')
            lesion.tags_restringidos = form.cleaned_data.get('tags_seleccionados', [])
            lesion.save()

            # Invalidar el plan Helms en sesión para que se regenere con las nuevas restricciones
            from django.core.cache import cache
            cache.set(f"bio_needs_regen_{cliente.id}", True, timeout=3600)
            request.session.pop(f'plan_anual_{cliente.id}', None)
            request.session.pop(f'plan_anual_v2_{cliente.id}', None)
            request.session.modified = True

            # Bio-Purge: Limpiar sesiones Hyrox futuras para forzar re-evaluación
            from core.bio_context import BioContextProvider
            BioContextProvider.force_clean_future_workouts(cliente)
            
            bloqueos_str = ""
            if lesion.tags_restringidos:
                bloqueos = []
                mapping = {
                    'impacto_vertical': '🏃 Carrera ➡️ <b>SkiErg</b>',
                    'carga_distal_pierna': '🦵 Prensa ➡️ <b>Tren Superior (Press/Remo)</b>',
                    'estabilidad_gemelo': '🦵 Prensa ➡️ <b>Tren Superior (Press/Remo)</b>',
                    'flexion_rodilla_profunda': '🎯 Wall Balls ➡️ <b>Press Hombro Sentado</b>',
                    'empuje_pierna': '🛷 Sled Push ➡️ <b>Assault Bike (Solo brazos)</b>',
                    'flexion_plantar': '🦘 Saltos ➡️ <b>Remo</b>',
                    'empuje_hombro': '🏋️ Burpees/Press ➡️ <b>Sled Pull</b>',
                    'traccion_superior': '🧗 Dominadas ➡️ <b>Peso Muerto (Carga ligera)</b>',
                    'empuje_horizontal': '💪 Flexiones ➡️ <b>Plancha Isométrica</b>',
                    'lumbar_carga': '🏋️‍♂️ Peso Muerto ➡️ <b>Hip Thrust</b>',
                    'rotacion_tronco': '🎒 Sandbag Lunges ➡️ <b>Sentadilla Búlgara</b>',
                }
                for tag in lesion.tags_restringidos:
                    if tag in mapping:
                        bloqueos.append(mapping[tag])
                
                if bloqueos:
                    bloqueos_str = "<br><br><b>❌ Protección Activa en Hyrox Engine:</b><br>" + "<br>".join(bloqueos[:3])
            
            messages.success(request, mark_safe(f"Lesión registrada en fase {lesion.get_fase_display()}. Hemos inyectado las restricciones.{bloqueos_str}"))
            return redirect('hyrox:dashboard')
    else:
        form = UserInjuryForm()
        
    return render(request, 'hyrox/reportar_lesion.html', {'form': form})

@login_required
def reportar_recuperacion(request, lesion_id):
    from .models import UserInjury
    lesion = get_object_or_404(UserInjury, id=lesion_id, cliente=request.user.cliente_perfil)
    
    if request.method == 'POST':
        form = DailyRecoveryEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.lesion = lesion
            entry.save()
            
            # Evaluar si hay cambio de fase (InjuryPhaseManager)
            from .services import InjuryPhaseManager
            InjuryPhaseManager.evaluate_phase_transition(lesion)
            
            # Bio-Purge: Limpiar sesiones futuras para adaptar a la nueva recuperación/fase
            from core.bio_context import BioContextProvider
            BioContextProvider.force_clean_future_workouts(lesion.cliente)
            
            messages.success(request, "Reporte diario guardado. El Coach ha actualizado tus restricciones.")
            return redirect('hyrox:dashboard')
    else:
        # Pre-poblar la fecha con hoy
        from django.utils import timezone
        form = DailyRecoveryEntryForm(initial={'fecha': timezone.now().date()})
        
    return render(request, 'hyrox/reportar_recuperacion.html', {'form': form, 'lesion': lesion})

@login_required
def marcar_lesion_recuperada(request, lesion_id):
    from .models import UserInjury
    lesion = get_object_or_404(UserInjury, id=lesion_id, cliente=request.user.cliente_perfil)
    
    if request.method == 'POST':
        from django.utils import timezone
        lesion.fase = UserInjury.Fase.RECUPERADO
        lesion.activa = False
        lesion.fecha_resolucion = timezone.now().date()
        lesion.save()

        # Invalidar plan Helms para que se regenere sin las restricciones
        from django.core.cache import cache
        cache.set(f"bio_needs_regen_{lesion.cliente.id}", True, timeout=3600)
        request.session.pop(f'plan_anual_{lesion.cliente.id}', None)
        request.session.pop(f'plan_anual_v2_{lesion.cliente.id}', None)
        request.session.modified = True

        # Bio-Purge: Limpiar sesiones Hyrox futuras para eliminar restricciones
        from core.bio_context import BioContextProvider
        BioContextProvider.force_clean_future_workouts(lesion.cliente)
        
        messages.success(request, "¡Enhorabuena! Has marcado la lesión como recuperada. Ya no hay restricciones.")

    next_url = request.POST.get('next') or request.GET.get('next') or 'hyrox:dashboard'
    try:
        return redirect(next_url)
    except Exception:
        return redirect('hyrox:dashboard')


# Phase 12: Return to Play - Recovery Test
@login_required
def test_recuperacion(request, lesion_id):
    from .models import UserInjury
    from .forms import RecoveryTestForm
    from core.bio_context import BioContextProvider

    lesion = get_object_or_404(UserInjury, id=lesion_id, cliente=request.user.cliente_perfil)

    # ── Phase 14: 48h block on failed test due to pain (dolor_movimiento > 1) ──
    from django.utils import timezone
    from datetime import timedelta
    
    ultimo_test_fallido = lesion.recovery_tests.filter(
        es_apto=False, 
        dolor_movimiento__gt=1
    ).order_by('-fecha').first()
    
    if ultimo_test_fallido:
        tiempo_desde_test = timezone.now() - ultimo_test_fallido.fecha
        if tiempo_desde_test < timedelta(hours=48):
            horas_restantes = 48 - (tiempo_desde_test.total_seconds() // 3600)
            messages.error(
                request, 
                f"Acceso denegado: Detectamos dolor al movimiento en tu último test. Por seguridad biomecánica, debes esperar {int(horas_restantes)} horas antes de volver a intentarlo."
            )
            return redirect('hyrox:dashboard')

    if request.method == 'POST':
        form = RecoveryTestForm(request.POST)
        if form.is_valid():
            test_log = form.save(commit=False)
            test_log.lesion = lesion
            test_log.save() # self.evaluate() is called in save()

            if test_log.es_apto:
                # 1. Update injury to RECUPERADO
                from django.utils import timezone
                lesion.fase = UserInjury.Fase.RECUPERADO
                lesion.activa = False
                lesion.fecha_resolucion = timezone.now().date()
                lesion.save()

                # 2. Force bio-purge of future restricted sessions
                BioContextProvider.force_clean_future_workouts(lesion.cliente)

                # 3. Inject successful test into session for UI Feedback
                request.session['recovery_test_passed'] = True
                
                messages.success(request, "🛡️ Validación superada. Tu planificador ha restaurado los ejercicios de fuerza máxima (Sentadillas/Prensa) en tu rutina.")
                return redirect('hyrox:dashboard')
            else:
                if test_log.dolor_movimiento > 1:
                    messages.error(request, "Las métricas de dolor superan el límite de seguridad (Dolor al movimiento > 1). El sistema deniega el acceso a los ejercicios de Cadena Cerrada por otras 48 horas.")
                else:
                    messages.error(request, "Las métricas no alcanzan el umbral de seguridad (Confianza < 8 o Inflamación > 0). El sistema mantiene las restricciones por precaución.")
                return redirect('hyrox:dashboard')
    else:
        form = RecoveryTestForm()

    return render(request, 'hyrox/test_recuperacion.html', {'form': form, 'lesion': lesion})

