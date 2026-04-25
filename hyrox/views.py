import logging
from django.shortcuts import render, redirect, get_object_or_404

logger = logging.getLogger(__name__)
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
        PROPOSITO_SESION = {
            'fuerza': 'Construir potencia base y tolerar carga progresiva',
            'carrera': 'Desarrollar motor aeróbico y economía de carrera',
            'cardio_sustituto': 'Cardio de bajo impacto como sustituto de carrera',
            'hyrox_station': 'Técnica en estaciones y adaptación al peso oficial',
            'ergometro': 'Capacidad cardiovascular en ergómetro específico',
            'simulacion': 'Simular la demanda metabólica completa de Hyrox',
            'hiit': 'Potencia anaeróbica y tolerancia al lactato',
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

            proposito = PROPOSITO_SESION.get(tipo_principal, 'Sesión de entrenamiento Hyrox')
            titulo_lower = (s.titulo or '').lower()
            if 'deload' in titulo_lower or 'descarga' in titulo_lower:
                proposito = 'Semana de descarga — reduce la carga para supracompensar'
            elif 'calibraci' in titulo_lower:
                proposito = 'Establecer líneas base de fuerza y capacidad aeróbica'
            elif 'taper' in titulo_lower or 'activaci' in titulo_lower:
                proposito = 'Activación suave precompetición — mantén el ritmo, baja el volumen'

            semana_buf.append({
                'sesion': s,
                'dia_str': DIAS_ES[s.fecha.weekday()],
                'tipo_label': tipo_info[0],
                'tipo_icon': tipo_info[1],
                'tipo_color': tipo_info[2],
                'proposito': proposito,
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
    evolucion_carrera = None

    if objetivo_activo:
        # ── EVOLUCIÓN CARRERA ──────────────────────────────────────
        from .models import HyroxActivity
        runs_qs = (
            HyroxActivity.objects
            .filter(
                sesion__objective=objetivo_activo,
                sesion__estado='completado',
                tipo_actividad__in=['carrera', 'cardio_sustituto'],
            )
            .select_related('sesion')
            .order_by('sesion__fecha')
        )

        pace_objetivo_secs = None
        if objetivo_activo.tiempo_5k_base:
            try:
                parts = str(objetivo_activo.tiempo_5k_base).split(':')
                pace_objetivo_secs = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                pass

        puntos_ritmo = []     # [{fecha, secs, label}]
        km_por_semana = {}    # {iso_week_label: km}
        fc_puntos = []        # [{fecha, fc}]

        for act in runs_qs:
            m = act.data_metricas or {}
            fecha = act.sesion.fecha
            fecha_str = fecha.strftime('%d/%m')
            iso = fecha.isocalendar()
            semana_key = f"S{iso[1]}"

            # Ritmo
            ritmo_str = m.get('ritmo_real') or m.get('ritmo_objetivo')
            if ritmo_str:
                try:
                    p = ritmo_str.split('/')[0].strip()
                    mins, secs = p.split(':')
                    total_secs = int(mins) * 60 + int(secs)
                    puntos_ritmo.append({'fecha': fecha_str, 'secs': total_secs,
                                         'label': p})
                except Exception:
                    pass

            # Km por semana
            try:
                km = float(m.get('distancia_km') or 0)
                km_por_semana[semana_key] = round(km_por_semana.get(semana_key, 0) + km, 2)
            except Exception:
                pass

            # FC media de la sesión
            fc = act.sesion.hr_media
            if fc:
                fc_puntos.append({'fecha': fecha_str, 'fc': fc})

        # Estadísticas globales
        mejor_ritmo = min(puntos_ritmo, key=lambda x: x['secs']) if puntos_ritmo else None
        ultimo_ritmo = puntos_ritmo[-1] if puntos_ritmo else None
        tendencia = None
        if len(puntos_ritmo) >= 3:
            ultimos = [p['secs'] for p in puntos_ritmo[-3:]]
            if ultimos[-1] < ultimos[0]:
                tendencia = 'mejora'
            elif ultimos[-1] > ultimos[0]:
                tendencia = 'empeora'
            else:
                tendencia = 'estable'

        evolucion_carrera = {
            'puntos_ritmo': puntos_ritmo[-12:],   # últimas 12 sesiones
            'km_por_semana': list(km_por_semana.items())[-8:],
            'fc_puntos': fc_puntos[-12:],
            'mejor_ritmo': mejor_ritmo,
            'ultimo_ritmo': ultimo_ritmo,
            'tendencia': tendencia,
            'pace_objetivo_secs': pace_objetivo_secs,
            'total_km': round(sum(km_por_semana.values()), 1),
            'num_sesiones': len(puntos_ritmo),
        }

    # ── EDAD DEL ATLETA ───────────────────────────────────────────────
    edad_atleta = None
    if objetivo_activo and cliente.fecha_nacimiento:
        import datetime as _dt2
        hoy_e = timezone.localdate()
        fn = cliente.fecha_nacimiento
        edad_atleta = hoy_e.year - fn.year - ((hoy_e.month, hoy_e.day) < (fn.month, fn.day))

    # ── SPLITS POR ESTACIÓN ────────────────────────────────────────────
    splits_estaciones = []
    if objetivo_activo:
        import datetime as _dt
        from .models import HyroxActivity
        from .services import HyroxRaceSimulator

        NOMBRE_CANON = {
            'skierg': 'SkiErg', 'ski erg': 'SkiErg',
            'sled push': 'Sled Push',
            'sled pull': 'Sled Pull',
            'burpee broad jump': 'Burpee Broad Jumps', 'burpees broad jump': 'Burpee Broad Jumps',
            'rowing': 'Rowing', 'remo': 'Rowing', 'remo ergometro': 'Rowing',
            'farmer': 'Farmers Carry', 'farmer carry': 'Farmers Carry', "farmer's carry": 'Farmers Carry',
            'sandbag': 'Sandbag Lunges', 'sandbag lunge': 'Sandbag Lunges',
            'wall ball': 'Wall Balls', 'wall balls': 'Wall Balls',
        }
        REFERENCIA = HyroxRaceSimulator.get_tiempos_categoria(objetivo_activo.categoria)

        tiempos_acum = {}       # {canon: [secs, ...]}
        tiempos_por_semana = {} # {canon: {(year, week): [secs, ...]}}

        acts_timer = HyroxActivity.objects.filter(
            sesion__objective=objetivo_activo,
            sesion__estado='completado',
        ).exclude(data_metricas__tiempo_segundos__isnull=True).select_related('sesion')

        for act in acts_timer:
            secs = act.data_metricas.get('tiempo_segundos')
            if not secs or secs <= 0:
                continue
            nombre_lower = (act.nombre_ejercicio or '').lower().strip()
            canon = next((v for k, v in NOMBRE_CANON.items() if k in nombre_lower), None)
            if not canon:
                continue
            secs = int(secs)
            tiempos_acum.setdefault(canon, []).append(secs)
            fecha_s = act.sesion.fecha or timezone.localdate()
            iso_w = fecha_s.isocalendar()[:2]  # (year, week)
            tiempos_por_semana.setdefault(canon, {}).setdefault(iso_w, []).append(secs)

        hoy = timezone.localdate()
        for nombre, ref in sorted(REFERENCIA.items()):
            lista = tiempos_acum.get(nombre, [])
            semanas_dict = tiempos_por_semana.get(nombre, {})

            # Últimas 6 semanas para la tendencia
            tendencia = []
            for w in range(5, -1, -1):
                d = hoy - _dt.timedelta(weeks=w)
                iso = d.isocalendar()[:2]
                vals = semanas_dict.get(iso, [])
                avg = round(sum(vals) / len(vals)) if vals else None
                # progreso = qué % del objetivo cumple (100 = en objetivo, >100 = por encima)
                pct = min(round((ref / avg) * 100), 100) if avg else 0
                tendencia.append({'label': f"S-{w}" if w > 0 else "Esta", 'avg_secs': avg, 'pct': pct})

            if lista:
                promedio = round(sum(lista) / len(lista))
                gap = promedio - ref
                mejor = min(lista)
                pct_ref = min(round((ref / promedio) * 100), 100)
                gap_str = (f"+{gap // 60}:{abs(gap) % 60:02d}" if gap > 0 else f"-{abs(gap) // 60}:{abs(gap) % 60:02d}") if gap != 0 else "0:00"
            else:
                promedio = mejor = gap = pct_ref = None
                gap_str = None

            # Status badge
            if not lista:
                status = 'sin_datos'
            elif pct_ref >= 95:
                status = 'strong'
            elif pct_ref >= 80:
                status = 'good'
            elif pct_ref >= 60:
                status = 'needs_work'
            else:
                status = 'priority'

            splits_estaciones.append({
                'nombre': nombre,
                'promedio_secs': promedio,
                'promedio_str': f"{promedio // 60}:{promedio % 60:02d}" if promedio else None,
                'mejor_secs': mejor,
                'mejor_str': f"{mejor // 60}:{mejor % 60:02d}" if mejor else None,
                'ref_secs': ref,
                'ref_str': f"{ref // 60}:{ref % 60:02d}",
                'gap_secs': gap,
                'gap_str': gap_str,
                'pct_ref': pct_ref or 0,
                'sesiones': len(lista),
                'tendencia': tendencia,
                'tiene_datos': bool(lista),
                'status': status,
            })

    # Race prediction + time-loss analysis
    race_prediction = None
    top_perdidas = []
    if objetivo_activo and splits_estaciones:
        top_perdidas = sorted(
            [s for s in splits_estaciones if s['tiene_datos'] and s['gap_secs'] and s['gap_secs'] > 0],
            key=lambda x: x['gap_secs'],
            reverse=True
        )[:3]

        running_secs = None
        if objetivo_activo.tiempo_5k_base:
            try:
                parts = str(objetivo_activo.tiempo_5k_base).split(':')
                pace_km = int(parts[0]) * 60 + int(parts[1])
                running_secs = pace_km * 8
            except Exception:
                pass

        if running_secs:
            _REF_RUN = {
                'open_men': 2400, 'open_women': 2880,
                'pro_men': 1920, 'pro_women': 2160,
            }
            _run_ref = _REF_RUN.get(objetivo_activo.categoria, 2400)

            total_est = sum(
                s['promedio_secs'] if s['tiene_datos'] else s['ref_secs']
                for s in splits_estaciones
            )
            total_mejor = sum(
                s['mejor_secs'] if (s['tiene_datos'] and s['mejor_secs']) else s['ref_secs']
                for s in splits_estaciones
            )
            total_ref = sum(s['ref_secs'] for s in splits_estaciones)

            total_est += running_secs
            total_mejor += int(running_secs * 0.97)
            total_ref_total = total_ref + _run_ref
            stations_con_datos = sum(1 for s in splits_estaciones if s['tiene_datos'])

            def _fmt_race(s):
                h, rem = divmod(s, 3600)
                m, sec = divmod(rem, 60)
                return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

            mejora_secs = total_est - total_ref_total
            race_prediction = {
                'tiene_datos': stations_con_datos > 0,
                'stations_con_datos': stations_con_datos,
                'total_stations': len(splits_estaciones),
                'estimado_str': _fmt_race(total_est),
                'mejor_str': _fmt_race(total_mejor),
                'ref_str': _fmt_race(total_ref_total),
                'mejora_str': _fmt_race(abs(mejora_secs)),
                'por_encima': mejora_secs > 0,
            }

    # ── STATION WEAKNESS TARGETING ─────────────────────────────────────────────
    estaciones_debiles = []
    if objetivo_activo and splits_estaciones:
        estaciones_debiles = [
            s for s in splits_estaciones
            if s['status'] in ('priority', 'needs_work')
        ]
        estaciones_debiles.sort(key=lambda x: x['pct_ref'])  # peor primero

    # ── FASES TIMELINE ─────────────────────────────────────────────────────────
    fases_timeline = []
    if objetivo_activo and objetivo_activo.fecha_evento:
        import datetime as _dt3
        _hoy_ft = timezone.localdate()
        _days_left = (objetivo_activo.fecha_evento - _hoy_ft).days
        _weeks_total = min(max(1, _days_left // 7), 16)
        # semana 0 = primera semana del plan (en el pasado o hoy)
        for _w in range(_weeks_total):
            _is_taper  = (_weeks_total - _w) <= 2
            _is_deload = (_w % 4 == 3) and not _is_taper
            if _is_taper:
                _fase_lbl, _fase_col = 'Taper', '#1DC8B8'
                _intens = 35
            elif _is_deload:
                _fase_lbl, _fase_col = 'Deload', '#8B5CF6'
                _intens = 45
            elif _w < _weeks_total * 0.25:
                _fase_lbl, _fase_col = 'Base', '#F59E0B'
                _intens = 45 + int((_w / max(_weeks_total-1,1)) * 30)
            elif _w < _weeks_total * 0.6:
                _fase_lbl, _fase_col = 'Potencia', '#E8341A'
                _intens = 60 + int((_w / max(_weeks_total-1,1)) * 20)
            elif _w < _weeks_total * 0.85:
                _fase_lbl, _fase_col = 'Intens.', '#EF4444'
                _intens = 75 + int((_w / max(_weeks_total-1,1)) * 15)
            else:
                _fase_lbl, _fase_col = 'Simul.', '#EF4444'
                _intens = 90
            _es_actual = _w == (_weeks_total - _days_left // 7 - 1) if _days_left < _weeks_total * 7 else False
            fases_timeline.append({
                'semana': _w + 1,
                'fase': _fase_lbl,
                'color': _fase_col,
                'intensidad': min(_intens, 100),
                'es_deload': _is_deload,
                'es_taper': _is_taper,
                'es_actual': (_weeks_total - _w) == (_days_left // 7 + 1),
            })

    # ── MILESTONES ─────────────────────────────────────────────────────────────
    milestones = []
    if objetivo_activo and objetivo_activo.fecha_evento:
        _fe = objetivo_activo.fecha_evento
        _hoy_m = timezone.localdate()
        _semanas = (_fe - _hoy_m).days // 7
        milestones = [
            {
                'semana_desde_hoy': max(0, _semanas - round(_semanas * 0.75)),
                'titulo': 'Test de ritmo 5K',
                'desc': 'Mide tu progreso en carrera y ajusta los ritmos del plan',
                'icono': 'fa-stopwatch',
                'pasado': _semanas <= round(_semanas * 0.25),
            },
            {
                'semana_desde_hoy': max(0, _semanas - round(_semanas * 0.50)),
                'titulo': 'Primera simulación completa',
                'desc': 'Realiza las 8 estaciones seguidas para primera vez',
                'icono': 'fa-flag',
                'pasado': _semanas <= round(_semanas * 0.50),
            },
            {
                'semana_desde_hoy': max(0, _semanas - round(_semanas * 0.25)),
                'titulo': 'Simulación a peso oficial',
                'desc': 'Todas las estaciones al 100% de los pesos de competición',
                'icono': 'fa-medal',
                'pasado': _semanas <= round(_semanas * 0.15),
            },
            {
                'semana_desde_hoy': 0,
                'titulo': 'Race Day',
                'desc': objetivo_activo.fecha_evento.strftime('%d %b %Y'),
                'icono': 'fa-trophy',
                'pasado': False,
            },
        ]

    # ── COACHING CARDS POR ESTACIÓN ───────────────────────────────────────────
    _COACHING = {
        'SkiErg': {
            'tecnica': 'Tira con los brazos Y el core, no solo brazos. Inicia el movimiento desde las caderas, deja que los brazos sigan. Mantén un ritmo de paladas constante (~30 spm). Respira cada 2 paladas.',
            'protocolo': 'El error más común es ir demasiado rápido los primeros 200m. Empieza al 85% y mantén ese ritmo hasta el final.',
            'icono': 'fa-arrows-alt-v',
        },
        'Sled Push': {
            'tecnica': 'Ángulo bajo, espalda recta, empuja desde los talones. Pasos cortos y rápidos, no largos. Mantén las caderas bajas durante todo el recorrido.',
            'protocolo': 'La fuerza de piernas es clave aquí — con tu sentadilla en 60 kg, vamos a subir eso significativamente. Semana final: 100% peso oficial sin pausa.',
            'icono': 'fa-arrow-right',
        },
        'Sled Pull': {
            'tecnica': 'Camina hacia atrás con pasos controlados, cuerda corta entre manos. Tira desde los codos, no las muñecas. Mantén el torso ligeramente inclinado atrás.',
            'protocolo': 'Con tu base de gym, el patrón de tracción va a mejorar rápido. Combina con Farmers Carry para simular la transición de carrera.',
            'icono': 'fa-arrow-left',
        },
        'Burpee Broad Jumps': {
            'tecnica': 'Estrategia clave: ritmo constante y bajo desde el inicio. No saltes al máximo — salta 1.2-1.5 m por rep y mantén ese ritmo. Respira en cada subida.',
            'protocolo': 'Nunca pares completamente, aunque vayas lento. Practica después de carrera para acostumbrarte a la fatiga previa.',
            'icono': 'fa-running',
        },
        'Rowing': {
            'tecnica': 'Secuencia: piernas-cuerpo-brazos en el tirón, brazos-cuerpo-piernas en el regreso. No uses solo brazos. Damper en 4-5, no al máximo.',
            'protocolo': 'Tu 500m row en 2:00-2:15 es tu punto de partida — apunta a mantener ese ritmo en carrera. SPM 24-26.',
            'icono': 'fa-water',
        },
        'Farmers Carry': {
            'tecnica': 'Hombros atrás y abajo, core apretado, pasos cortos y constantes. No te pares — si necesitas, ve más lento pero sin soltar.',
            'protocolo': 'Con tu experiencia de gym y fuerza de grip, esta estación puede ser una de tus mejores. Trabaja 4×50m progresivo.',
            'icono': 'fa-suitcase',
        },
        'Sandbag Lunges': {
            'tecnica': 'Rodilla trasera cerca del suelo, torso erguido, sandbag en el pecho o hombros. Pasos constantes sin pausas largas.',
            'protocolo': 'Con cuádriceps débiles y meniscos con historial, vamos a construir esto muy gradualmente. Prioriza técnica perfecta antes de aumentar peso.',
            'icono': 'fa-dumbbell',
        },
        'Wall Balls': {
            'tecnica': 'Sentadilla profunda, pelota al pecho, explota hacia arriba y lanza en el punto más alto. No esperes la pelota — muévete hacia ella.',
            'protocolo': 'Con 12 reps unbroken ahora, vamos a llegar a sets de 20-25 para la carrera. Meta final: 100 reps sin soltar el balón.',
            'icono': 'fa-circle',
        },
    }

    coaching_estaciones = []
    if objetivo_activo:
        _splits_map = {s['nombre']: s for s in splits_estaciones}
        for nombre, coach in _COACHING.items():
            sp = _splits_map.get(nombre)
            mejora_str = None
            potencial_str = None
            if sp and sp['tiene_datos'] and sp['gap_secs'] and sp['gap_secs'] > 0:
                mejora_str = sp['gap_str']
                potencial_str = f"Con entrenar 2×/semana en esta estación puedes recortar ~{sp['gap_secs'] // 6}s por mes"
            coaching_estaciones.append({
                'nombre': nombre,
                'tecnica': coach['tecnica'],
                'protocolo': coach['protocolo'],
                'icono': coach['icono'],
                'status': sp['status'] if sp else 'sin_datos',
                'pct_ref': sp['pct_ref'] if sp else 0,
                'mejora_str': mejora_str,
                'potencial_str': potencial_str,
                'tiene_datos': sp['tiene_datos'] if sp else False,
            })

    # ── RACE DAY STRATEGY ─────────────────────────────────────────────────────
    race_day_strategy = None
    if objetivo_activo:
        _GRUPOS_RD = [
            {'nombre': 'Arranque', 'estaciones': ['SkiErg', 'Sled Push'],
             'consejo': 'Arranca al 85% — el exceso de ritmo aquí destruye el resto de la carrera.'},
            {'nombre': 'Bloque Central', 'estaciones': ['Sled Pull', 'Burpee Broad Jumps', 'Rowing'],
             'consejo': 'Mantén esfuerzo constante. Es el bloque más largo — gestiona el lactato.'},
            {'nombre': 'Bloque Final', 'estaciones': ['Farmers Carry', 'Sandbag Lunges', 'Wall Balls'],
             'consejo': 'Aquí se gana o se pierde la carrera. Da todo lo que te queda en Wall Balls.'},
        ]
        _splits_map2 = {s['nombre']: s for s in splits_estaciones}
        grupos_rd = []
        for g in _GRUPOS_RD:
            sps = [_splits_map2.get(e) for e in g['estaciones'] if _splits_map2.get(e) and _splits_map2[e]['tiene_datos']]
            avg_pct = round(sum(s['pct_ref'] for s in sps) / len(sps)) if sps else None
            if avg_pct is None:
                color, nivel = '#888', 'Sin datos'
            elif avg_pct >= 85:
                color, nivel = '#1DC8B8', '85-90% esfuerzo — zona fuerte'
            elif avg_pct >= 65:
                color, nivel = '#F59E0B', '80-85% esfuerzo — zona de mejora'
            else:
                color, nivel = '#EF4444', '75-80% — conserva energía aquí'
            grupos_rd.append({**g, 'avg_pct': avg_pct, 'color': color, 'nivel': nivel})

        _ritmo_carrera = None
        if objetivo_activo.tiempo_5k_base:
            try:
                _parts = str(objetivo_activo.tiempo_5k_base).split(':')
                _pace = int(_parts[0]) * 60 + int(_parts[1])
                _ritmo_z3 = _pace * 1.04
                _m, _s = divmod(int(_ritmo_z3), 60)
                _ritmo_carrera = f"{_m}:{_s:02d}/km"
            except Exception:
                pass

        race_day_strategy = {
            'grupos': grupos_rd,
            'ritmo_carrera': _ritmo_carrera,
            'tip_running': 'Corre al ritmo Z3 (+4% sobre tu ritmo 5K). Los 8 segmentos de 1km deben ser iguales.',
            'tip_mental': 'En la estación 6 (Farmers Carry) tu mente cederá antes que el cuerpo. Ese es el momento de acelerar.',
        }

    # ── ÍNDICE DE INTERFERENCIA ───────────────────────────────────────────────
    interferencia_index = []
    if objetivo_activo:
        from .services import InterferenceIndexService
        interferencia_index = InterferenceIndexService.compute_for_objective(objetivo_activo)

    # ── RACE CARD TÁCTICA + MODO COMPETICIÓN ─────────────────────────────────
    race_card = None
    modo_competicion = False
    race_day_briefing = None
    if objetivo_activo and objetivo_activo.tiempo_5k_base:
        from .services import RaceCardService
        race_card = RaceCardService.generate(objetivo_activo, splits_estaciones, interferencia_index)
        if race_card and race_card['es_race_week']:
            modo_competicion = True
            dias = race_card['dias_evento']
            if dias == 0:
                fase_label = 'HOY ES EL DÍA'
                consejos = [
                    'Desayuno familiar 3h antes: arroz, huevo, plátano. Sin experimentos.',
                    'Calentamiento 20 min: trote suave + movilidad de cadera y tobillo.',
                    'Objetivo mental: los primeros 2 km son la carrera dentro de la carrera.',
                    'En el Sled Push: pasos cortos, no pares. Piensa "metro a metro".',
                    'En Wall Balls: series de 10-15, 3 segundos de descanso. Nunca al fallo.',
                ]
            elif dias <= 2:
                fase_label = f'FALTAN {dias} DÍA{"S" if dias > 1 else ""} — ACTIVACIÓN'
                consejos = [
                    'Hoy o mañana: 20-30 min de trote suave + 4 strides de 80m al ritmo de carrera.',
                    'Sin gimnasio, sin pesos, sin fatiga.',
                    'Hidratación activa: 2.5-3L de agua. Reduce el café.',
                    'Visualiza los primeros 3 km y la transición al Sled Push.',
                    'Duerme mínimo 7-8h. Es la sesión de entrenamiento más importante de la semana.',
                ]
            else:
                fase_label = f'FALTAN {dias} DÍAS — TAPER FINAL'
                consejos = [
                    'Máximo 2 sesiones esta semana: una activación suave + un día de movilidad.',
                    'Reduce volumen un 50-60%. Mantén la intensidad en las pocas series que hagas.',
                    'Nada nuevo: misma comida, mismo horario de sueño.',
                    'Repasa mentalmente la Race Card. Los ritmos deben estar memorizados.',
                    'Confia en el trabajo acumulado. El fitness está hecho; solo queda expresarlo.',
                ]
            race_day_briefing = {
                'fase_label': fase_label,
                'consejos': consejos,
                'dias': dias,
            }

    # ── RACE INTELLIGENCE BRIEFING ────────────────────────────────────────────
    race_briefing = None
    if objetivo_activo:
        from .services import HyroxRaceIntelligence
        try:
            race_briefing = HyroxRaceIntelligence.get_race_briefing(
                objetivo_activo,
                interferencia_index=interferencia_index,
                race_card=race_card,
            )
        except Exception:
            logger.exception("[HYROX RaceIntelligence] Error generando race_briefing")
            race_briefing = None

    # ── SESSION OVERRIDE ENGINE ───────────────────────────────────────────────
    sesion_override = None
    if objetivo_activo and race_briefing:
        from .services import HyroxSessionOverrideEngine
        try:
            sesion_override = HyroxSessionOverrideEngine.apply_today_override(
                objetivo_activo, race_briefing
            )
        except Exception:
            logger.exception("[HYROX Override] Error aplicando override automático")
            sesion_override = None

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
        'evolucion_carrera': evolucion_carrera,
        'splits_estaciones': splits_estaciones,
        'splits_categoria': objetivo_activo.get_categoria_display() if objetivo_activo else None,
        'splits_edad': edad_atleta,
        'race_prediction': race_prediction,
        'top_perdidas': top_perdidas,
        'estaciones_debiles': estaciones_debiles,
        'fases_timeline': fases_timeline,
        'milestones': milestones,
        'coaching_estaciones': coaching_estaciones,
        'race_day_strategy': race_day_strategy,
        'sustituciones_activas': sustituciones_activas if 'sustituciones_activas' in locals() else [],
        'sustituciones_dict': sustituciones_dict if 'sustituciones_dict' in locals() else {},
        'interferencia_index': interferencia_index,
        'race_card': race_card,
        'modo_competicion': modo_competicion,
        'race_day_briefing': race_day_briefing,
        'race_briefing': race_briefing,
        'sesion_override': sesion_override,
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

            # Guardar tiempo por ejercicio (wizard timer → data_metricas['tiempo_s'])
            acts_ordered = list(sesion.activities.all().order_by('id'))
            for i, act in enumerate(acts_ordered, 1):
                t_s_raw = request.POST.get(f'act_tiempo_s_{i}')
                if t_s_raw and t_s_raw.strip():
                    t_s = int(t_s_raw)
                    if t_s > 0:
                        m = dict(act.data_metricas or {})
                        m['tiempo_s'] = t_s
                        act.data_metricas = m
                        act.save(update_fields=['data_metricas'])

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

            _STATION_TIPS = {
                'skierg':         "Tira con los brazos Y el core, no solo brazos. Inicia el movimiento desde las caderas, deja que los brazos sigan. Mantén un ritmo de paladas constante (~30 spm). Respira cada 2 paladas. El error más común es ir demasiado rápido los primeros 200m.",
                'sled push':      "Ángulo bajo, espalda recta, empuja desde los talones. Pasos cortos y rápidos, no largos. Mantén las caderas bajas durante todo el recorrido. La fuerza de piernas es clave — con tu sentadilla en 60 kg, vamos a subir eso significativamente.",
                'sled pull':      "Camina hacia atrás con pasos controlados, cuerda corta entre manos. Tira desde los codos, no las muñecas. Mantén el torso ligeramente inclinado atrás. Con tu base de gym, el patrón de tracción va a mejorar rápido.",
                'burpee':         "Este es tu mayor reto. Estrategia clave: ritmo constante y bajo desde el inicio. No saltes al máximo — salta 1.2-1.5 m por rep y mantén ese ritmo. Respira en cada subida. Nunca pares completamente, aunque vayas lento.",
                'rowing':         "Secuencia: piernas-cuerpo-brazos en el tirón, brazos-cuerpo-piernas en el regreso. No uses solo brazos. Tu 500m row en 2:00-2:15 es tu punto de partida — apunta a mantener ese ritmo. Damper en 4-5, no al máximo.",
                'farmers carry':  "Hombros atrás y abajo, core apretado, pasos cortos y constantes. No te pares — si necesitas, ve más lento pero sin soltar. Con tu experiencia de gym y fuerza de grip, esta estación puede ser una de tus mejores.",
                'sandbag':        "Rodilla trasera cerca del suelo, torso erguido, sandbag en el pecho o hombros. Pasos constantes sin pausas largas. Con cuádriceps débiles y meniscos con historial, vamos a construir esto muy gradualmente para proteger las rodillas.",
                'wall ball':      "Sentadilla profunda, pelota al pecho, explota hacia arriba y lanza en el punto más alto. No esperes la pelota — muévete hacia ella. Con 12 reps unbroken ahora, vamos a llegar a sets de 20-25 para la carrera.",
            }

            from hyrox.training_engine import HyroxTrainingEngine as _HTE
            _oficiales_pesos = _HTE.PESOS_OFICIALES.get(
                sesion_planificada.objective.categoria,
                _HTE.PESOS_OFICIALES['open_men']
            )

            # Prepare activities for the context to preserve display_name and is_substituted
            actividades_planificadas = list(sesion_planificada.activities.all())
            for act in actividades_planificadas:
                act.display_name = act.nombre_ejercicio # Default
                m = act.data_metricas or {}
                nombre_lower = act.nombre_ejercicio.lower()
                # Inject station coaching tip into a copy (don't mutate the DB object)
                if not m.get('coach_tip'):
                    m = dict(m)
                    for kw, tip in _STATION_TIPS.items():
                        if kw in nombre_lower:
                            m['coach_tip'] = tip
                            break
                    act.data_metricas = m
                # Build series_processed: unified peso_display handling legacy 'peso' key
                # and injecting official weight for wall balls with no weight data
                _wb_peso = _oficiales_pesos.get('wall_ball') if 'wall ball' in nombre_lower else None
                series_raw = m.get('series') or []
                act.series_processed = []
                for serie in series_raw:
                    s2 = dict(serie)
                    peso = s2.get('peso_kg') or s2.get('peso') or _wb_peso or ''
                    s2['peso_display'] = peso
                    act.series_processed.append(s2)
                
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

        # Detectar AUTO-OVERRIDE y recuperar plan original del snapshot
        es_override = sesion_planificada and '[AUTO-OVERRIDE]' in (sesion_planificada.titulo or '')
        titulo_limpio = sesion_planificada.titulo.replace('[AUTO-OVERRIDE] ', '') if es_override else (sesion_planificada.titulo if sesion_planificada else '')
        plan_original_snapshot = []
        if es_override and sesion_planificada:
            primera_act = sesion_planificada.activities.first()
            if primera_act and primera_act.data_planificado:
                plan_original_snapshot = primera_act.data_planificado.get('plan_original', [])

        form = HyroxSessionNotesForm(initial={'titulo': titulo_limpio})

    return render(request, 'hyrox/registrar_entrenamiento.html', {
        'form': form,
        'objetivo': objetivo,
        'sesion_planificada': sesion_planificada,
        'actividades_planificadas': actividades_planificadas if 'actividades_planificadas' in locals() else sesion_planificada.activities.all() if sesion_planificada else [],
        'lesion_activa': lesion_activa,
        'es_override': es_override if 'es_override' in locals() else False,
        'titulo_limpio': titulo_limpio if 'titulo_limpio' in locals() else '',
        'plan_original_snapshot': plan_original_snapshot if 'plan_original_snapshot' in locals() else [],
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
        import logging as _logging
        _log = _logging.getLogger('hyrox.editar_sesion')

        acts_qs = list(session.activities.all())
        _log.warning(f'[EDIT session={session.id}] activities_count={len(acts_qs)} notas_raw={bool(session.notas_raw)}')

        # Si no hay actividades pero hay notas_raw, re-parsear antes de editar
        if not acts_qs and session.notas_raw:
            from .services import HyroxParserService
            try:
                HyroxParserService.save_parsed_session(session)
                acts_qs = list(session.activities.all())
                _log.warning(f'[EDIT session={session.id}] re-parseado notas_raw, ahora {len(acts_qs)} actividades')
            except Exception as e:
                _log.error(f'[EDIT session={session.id}] ERROR re-parseando: {e}')

        for act in acts_qs:
            if str(act.id) in ids_borrar:
                act.delete()
                continue
            m = dict(act.data_metricas or {})
            ta = act.tipo_actividad or ''
            nombre_lower = (act.nombre_ejercicio or '').lower()
            is_carrera = ta in _CARRERA_TIPOS or 'distancia_km' in m
            is_fuerza = ta == 'fuerza' or 'series' in m
            is_reps_station = any(kw in nombre_lower for kw in _REPS_STATIONS) and ta in _ESTACION_TIPOS

            _log.warning(f'[EDIT act={act.id}] ta={ta!r} is_carrera={is_carrera} is_fuerza={is_fuerza} m_keys={list(m.keys())}')

            if is_carrera:
                km = request.POST.get(f'act_km_{act.id}')
                mins = request.POST.get(f'act_min_{act.id}')
                _log.warning(f'[EDIT act={act.id}] CARRERA km={km!r} mins={mins!r}')
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

            tiempo_s = request.POST.get(f'act_tiempo_s_{act.id}')
            if tiempo_s and tiempo_s.strip():
                m['tiempo_s'] = int(tiempo_s)

            _log.warning(f'[EDIT act={act.id}] GUARDANDO data_metricas={m}')
            act.data_metricas = m
            act.save()
            # Verificar persistencia inmediata
            act.refresh_from_db()
            _log.warning(f'[EDIT act={act.id}] POST-SAVE DB={act.data_metricas}')

        session.estado = 'completado'
        try:
            session.save()
        except Exception as e:
            import traceback as _tb
            _log.error(f'[EDIT session={session.id}] ERROR en session.save(): {e}\n{_tb.format_exc()}')
            # El save de actividades ya se completó — continuar con el redirect
        messages.success(request, "Sesión actualizada. El plan se ha re-adaptado.")
        return redirect('hyrox:dashboard')

    TIPO_ACT_CARRERA = {'carrera', 'cardio_sustituto'}
    TIPO_ACT_ESTACION = {'hyrox_station', 'ergometro', 'isometrico', 'hiit', 'remo', 'skierg', 'bici', 'otro'}
    # Estaciones Hyrox que funcionan por reps+kg, no por distancia
    ESTACIONES_REPS = {'wall ball', 'wall balls', 'burpee broad jump', 'burpees broad jump'}

    # Si no hay actividades pero hay notas_raw, intentar re-parsear
    if session.activities.count() == 0 and session.notas_raw:
        from .services import HyroxParserService
        try:
            HyroxParserService.save_parsed_session(session)
        except Exception:
            pass

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
            'tiempo_s': m.get('tiempo_s', ''),
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

