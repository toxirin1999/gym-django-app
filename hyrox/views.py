import logging
from django.shortcuts import render, redirect, get_object_or_404

logger = logging.getLogger(__name__)


def _checkin_hoy(cliente):
    """Returns today's BitacoraDiaria if morning check-in was done, else None."""
    try:
        from datetime import date
        from clientes.models import BitacoraDiaria
        return BitacoraDiaria.objects.filter(
            cliente=cliente, fecha=date.today(), fc_reposo__isnull=False
        ).first()
    except Exception:
        return None
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from .forms import HyroxObjectiveForm, HyroxSessionNotesForm, UserInjuryForm, DailyRecoveryEntryForm
from .services import HyroxParserService, HyroxCoachService
from .training_engine import HyroxTrainingEngine
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import HyroxObjective, HyroxSession, HyroxActivity, UserInjury, DailyRecoveryEntry

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
    current_score = 0
    _recovery_delta = 0
    _gym_nota = None

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

            # Cruzar con BitacoraDiaria del día para ajustar por recuperación real
            _bitacora_fields = {}
            _recovery_delta = 0
            try:
                from clientes.models import BitacoraDiaria
                from datetime import timedelta
                _bitacora = BitacoraDiaria.objects.filter(
                    cliente=objetivo_activo.cliente,
                    fecha__gte=hoy - timedelta(days=1),
                ).order_by('-fecha').first()
                if _bitacora:
                    cal = _bitacora.calidad_sueno    # 0-100
                    hrs = float(_bitacora.horas_sueno or 0)
                    ene = _bitacora.energia_subjetiva  # 0-10
                    hrv_hoy = _bitacora.hrv_ms

                    # Penalización sueño calidad
                    if cal is not None:
                        if cal < 40:   _recovery_delta -= 10
                        elif cal < 60: _recovery_delta -= 5

                    # Penalización horas
                    if hrs > 0:
                        if hrs < 5:   _recovery_delta -= 10
                        elif hrs < 6: _recovery_delta -= 5
                        elif hrs < 7: _recovery_delta -= 2

                    # Penalización energía
                    if ene is not None:
                        if ene < 4:   _recovery_delta -= 8
                        elif ene < 6: _recovery_delta -= 3

                    # HRV: comparar con baseline personal (últimos 30 días)
                    if hrv_hoy:
                        _hrv_historial = list(
                            BitacoraDiaria.objects
                            .filter(
                                cliente=objetivo_activo.cliente,
                                hrv_ms__isnull=False,
                                fecha__gte=hoy - timedelta(days=30),
                                fecha__lt=hoy,
                            )
                            .values_list('hrv_ms', flat=True)
                        )
                        if len(_hrv_historial) >= 5:
                            _hrv_baseline = sum(_hrv_historial) / len(_hrv_historial)
                            _hrv_ratio = hrv_hoy / _hrv_baseline
                            if _hrv_ratio < 0.80:
                                _recovery_delta -= 10   # caída significativa
                            elif _hrv_ratio < 0.90:
                                _recovery_delta -= 5    # caída leve
                            elif _hrv_ratio > 1.10:
                                _recovery_delta += 3    # recuperación óptima

                    _bitacora_fields = {
                        'calidad_sueno': cal,
                        'horas_sueno': hrs if hrs > 0 else None,
                    }
            except Exception:
                pass

            # Cruzar con sesiones de gym (entrenos app) — últimas 48h
            _gym_delta = 0
            _gym_nota = None
            try:
                from entrenos.models import EntrenoRealizado
                from datetime import timedelta as _td
                _LEGS_KW = {'pierna', 'cuadricep', 'isquio', 'gluteo', 'gemelo',
                            'soleo', 'femoral', 'posterior'}
                _entrenos_recientes = (
                    EntrenoRealizado.objects
                    .filter(
                        cliente=objetivo_activo.cliente,
                        fecha__gte=hoy - _td(days=2),
                    )
                    .prefetch_related('ejercicios_realizados', 'sesion_detalle')
                )
                for _e in _entrenos_recientes:
                    _rpe = None
                    try:
                        _rpe = _e.sesion_detalle.rpe_medio
                    except Exception:
                        pass
                    _vol = float(_e.volumen_total_kg or 0)

                    # Detectar tren inferior
                    _grupos = {
                        (ej.grupo_muscular or '').lower()
                        for ej in _e.ejercicios_realizados.all()
                    }
                    _es_pierna = any(
                        any(kw in g for kw in _LEGS_KW) for g in _grupos
                    )

                    _carga_alta = (_rpe and _rpe >= 7) or _vol >= 5000
                    if _es_pierna and _carga_alta:
                        _gym_delta -= 10
                        _gym_nota = f'Piernas intensas ({_e.fecha})'
                    elif _carga_alta:
                        _gym_delta -= 5
                        _gym_nota = _gym_nota or f'Gym intenso ({_e.fecha})'
                    elif _es_pierna:
                        _gym_delta -= 4
                        _gym_nota = _gym_nota or f'Trabajo de piernas ({_e.fecha})'

                _gym_delta = max(_gym_delta, -12)  # cap gym
            except Exception:
                pass

            _recovery_delta = max(_recovery_delta + _gym_delta, -25)  # cap total
            current_score = max(0, min(100, round(current_score + _recovery_delta)))
            HyroxReadinessLog.objects.create(
                objective=objetivo_activo,
                fecha=hoy,
                score=current_score,
                **_bitacora_fields,
            )

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
        
        sesiones_completadas = list(HyroxSession.objects.filter(objective=objetivo_activo, estado='completado').order_by('-fecha'))

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
                    plan_semanas.append({
                        'semana_idx': semana_num_actual,
                        'numero': semana_num_actual + 1,
                        'fase': '',
                        'sesiones': semana_buf,
                        'dias': semana_buf,
                        'completadas': sum(1 for d in semana_buf if d.get('completada')),
                    })
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
            plan_semanas.append({
                'semana_idx': semana_num_actual,
                'numero': semana_num_actual + 1,
                'fase': '',
                'sesiones': semana_buf,
                'dias': semana_buf,
                'completadas': sum(1 for d in semana_buf if d.get('completada')),
            })
        
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

        stats_semana['total_planificadas'] = len(list(sesiones_semana))
        stats_semana['total_completadas'] = sum(1 for s in sesiones_semana if s.estado == 'completado')

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
            objetivo_carrera = objetivo_activo.objetivo_tiempo_carrera or None
            if objetivo_carrera:
                pace_prediction = (
                    f"5K actual: {objetivo_activo.tiempo_5k_base} · "
                    f"Objetivo carrera: {objetivo_carrera}. "
                    f"Recorta 10–15 seg/km cada semana con Z2 y series hasta alcanzar el ritmo objetivo."
                )
            else:
                pace_prediction = (
                    f"5K actual: {objetivo_activo.tiempo_5k_base}. "
                    f"Añade tu tiempo objetivo en Editar objetivo para ver la proyección de mejora."
                )

        # Phase 11: Identidad Consciente y Smart Alerts
        morning_briefing = None
        # Idealmente sería usando la zona horaria del usuario, asumimos hora del servidor por ahora
        if timezone.now().hour <= 11:
            morning_briefing = "Hoy no entrenas para demostrar nada a nadie, entrenas para construir al David que tú quieres ser."
            
        daily_push = objetivo_activo.get_daily_push()

        from .training_engine import WeeklySummaryEngine
        resumen_semanal = WeeklySummaryEngine.get_summary(objetivo_activo)

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
            .exclude(sesion__titulo__icontains='caminata')
            .exclude(nombre_ejercicio__icontains='caminata')
            .select_related('sesion')
            .order_by('sesion__fecha')
        )

        def _parse_5k_to_pace(raw):
            """
            Convierte tiempo_5k_base a segundos/km.
            Si MM >= 10 asume tiempo total de 5K (ej. "25:00" = 5:00/km).
            Si MM < 10 asume ritmo por km (ej. "5:00" = 5:00/km).
            """
            try:
                parts = str(raw).split(':')
                if len(parts) == 3:
                    total = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    return total // 5
                mm = int(parts[0])
                ss = int(parts[1])
                total = mm * 60 + ss
                return total // 5 if mm >= 10 else total
            except Exception:
                return None

        pace_objetivo_secs = None
        if objetivo_activo.tiempo_5k_base:
            pace_objetivo_secs = _parse_5k_to_pace(objetivo_activo.tiempo_5k_base)

        puntos_ritmo = []     # [{fecha, secs, label}]
        km_por_semana = {}    # {iso_week_label: km}
        fc_puntos = []        # [{fecha, fc}]
        total_runs = 0

        for act in runs_qs:
            total_runs += 1
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
        if len(puntos_ritmo) >= 5:
            ultimos = [p['secs'] for p in puntos_ritmo[-5:]]
            media_primera = sum(ultimos[:2]) / 2
            media_ultima = sum(ultimos[-2:]) / 2
            delta = media_primera - media_ultima  # positivo = mejora (menor ritmo = más rápido)
            if delta > 10:
                tendencia = 'mejora'
            elif delta < -10:
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
            'num_sesiones': total_runs,
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
    splits_ref_label = 'Open'
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
        _cat_efectiva = objetivo_activo.categoria
        if HyroxRaceSimulator.TIEMPOS_POR_CATEGORIA.get(_cat_efectiva) is None:
            _cat_efectiva = 'open_women' if 'women' in _cat_efectiva else 'open_men'
        _CAT_LABEL = {
            'open_men': 'Open Masc.', 'open_women': 'Open Fem.',
            'pro_men': 'Pro Masc.', 'pro_women': 'Pro Fem.',
        }
        splits_ref_label = _CAT_LABEL.get(_cat_efectiva, 'Open')

        tiempos_acum = {}       # {canon: [secs, ...]}
        tiempos_por_semana = {} # {canon: {(year, week): [secs, ...]}}
        tiempos_por_mes = {}    # {canon: {(year, month): [secs, ...]}}
        rpes_acum = {}          # {canon: [rpe, ...]}

        from django.db.models import Q as _Q
        _STATION_TIPOS = ('hyrox_station', 'ergometro', 'skierg', 'remo')
        acts_timer = HyroxActivity.objects.filter(
            sesion__objective=objetivo_activo,
            sesion__estado='completado',
            tipo_actividad__in=_STATION_TIPOS,
        ).filter(
            _Q(data_metricas__tiempo_segundos__isnull=False) |
            _Q(data_metricas__tiempo_s__isnull=False)
        ).select_related('sesion').order_by('sesion__fecha', 'sesion__id')

        # También recogemos actividades con RPE aunque no tengan tiempo
        acts_rpe = HyroxActivity.objects.filter(
            sesion__objective=objetivo_activo,
            sesion__estado='completado',
            tipo_actividad__in=_STATION_TIPOS,
            data_metricas__rpe__isnull=False,
        ).values('nombre_ejercicio', 'data_metricas__rpe')

        for ar in acts_rpe:
            nombre_lower = (ar['nombre_ejercicio'] or '').lower().strip()
            canon = next((v for k, v in NOMBRE_CANON.items() if k in nombre_lower), None)
            if canon and ar['data_metricas__rpe']:
                rpes_acum.setdefault(canon, []).append(int(ar['data_metricas__rpe']))

        for act in acts_timer:
            secs = act.data_metricas.get('tiempo_segundos') or act.data_metricas.get('tiempo_s')
            if not secs or secs <= 0:
                continue
            nombre_lower = (act.nombre_ejercicio or '').lower().strip()
            canon = next((v for k, v in NOMBRE_CANON.items() if k in nombre_lower), None)
            if not canon:
                continue
            secs = int(secs)
            tiempos_acum.setdefault(canon, []).append(secs)
            fecha_s = act.sesion.fecha or timezone.localdate()
            iso_w = fecha_s.isocalendar()[:2]
            tiempos_por_semana.setdefault(canon, {}).setdefault(iso_w, []).append(secs)
            mes_key = (fecha_s.year, fecha_s.month)
            tiempos_por_mes.setdefault(canon, {}).setdefault(mes_key, []).append(secs)

        hoy = timezone.localdate()
        _mes_actual = (hoy.year, hoy.month)
        _mes_ant = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)

        for nombre, ref in sorted(REFERENCIA.items()):
            lista = tiempos_acum.get(nombre, [])
            semanas_dict = tiempos_por_semana.get(nombre, {})
            meses_dict = tiempos_por_mes.get(nombre, {})

            # Últimas 6 semanas para la tendencia
            tendencia = []
            for w in range(5, -1, -1):
                d = hoy - _dt.timedelta(weeks=w)
                iso = d.isocalendar()[:2]
                vals = semanas_dict.get(iso, [])
                avg = round(sum(vals) / len(vals)) if vals else None
                # progreso = qué % del objetivo cumple (100 = en objetivo, >100 = por encima)
                pct = min(round((ref / avg) * 100), 100) if avg else None
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

            # Comparativa mensual
            _vals_mes_act = meses_dict.get(_mes_actual, [])
            _vals_mes_ant = meses_dict.get(_mes_ant, [])
            mejora_mes_pct = None
            if _vals_mes_act and _vals_mes_ant:
                _avg_act = sum(_vals_mes_act) / len(_vals_mes_act)
                _avg_ant = sum(_vals_mes_ant) / len(_vals_mes_ant)
                if _avg_ant > 0:
                    mejora_mes_pct = round((_avg_ant - _avg_act) / _avg_ant * 100, 1)

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

            rpes = rpes_acum.get(nombre, [])
            rpe_medio_station = round(sum(rpes) / len(rpes), 1) if rpes else None

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
                'mejora_mes_pct': mejora_mes_pct,
                'rpe_medio': rpe_medio_station,
                'rpe_sesiones': len(rpes),
            })

    # ── DETECCIÓN DE ESTANCAMIENTO ────────────────────────────────────────────
    if objetivo_activo and tiempos_acum:
        from .training_engine import StagnationEngine
        _stagnation = StagnationEngine.check(tiempos_acum)
        for sp in splits_estaciones:
            st = _stagnation.get(sp['nombre'], {})
            sp['estancada'] = st.get('estancada', False)
            sp['stagnation_sugerencia'] = st.get('sugerencia') if st.get('estancada') else None

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
            _pace = _parse_5k_to_pace(objetivo_activo.tiempo_5k_base)
            if _pace:
                running_secs = _pace * 8

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
            # Mejor caso: usa el mejor ritmo real si existe, pero nunca peor que el estimado
            _mejor_pace = (evolucion_carrera.get('mejor_ritmo') or {}).get('secs') if evolucion_carrera else None
            if _mejor_pace:
                total_mejor += min(int(_mejor_pace * 8), int(running_secs * 0.97))
            else:
                total_mejor += int(running_secs * 0.97)
            total_mejor = min(total_mejor, total_est)  # mejor siempre ≤ estimado
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

    # ── POST-SESSION DIAGNOSIS (datos + percepción) ───────────────────────────
    post_session_diagnosis = None
    if objetivo_activo:
        from django.utils import timezone as _tz
        from .models import HyroxSession as _HS
        from .diagnostic_engine import HyroxDiagnosticEngine as _DX
        _hoy = _tz.localdate()
        _sesion_hoy = (
            _HS.objects
            .filter(objective=objetivo_activo, estado='completado', fecha=_hoy)
            .prefetch_related('activities')
            .order_by('-fecha_actualizacion')
            .first()
        )
        if _sesion_hoy and _sesion_hoy.station_feedback:
            try:
                post_session_diagnosis = _DX.evaluate_session(_sesion_hoy)
            except Exception:
                logger.exception("[HYROX] Error en DiagnosticEngine")

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
        import datetime as _dt
        _fe = objetivo_activo.fecha_evento
        _hoy_m = timezone.localdate()
        _dias_restantes = (_fe - _hoy_m).days
        _semanas_restantes = _dias_restantes // 7

        # Use fecha_creacion to anchor milestones at fixed % of total plan duration
        _fecha_inicio = objetivo_activo.fecha_creacion.date() if hasattr(objetivo_activo.fecha_creacion, 'date') else objetivo_activo.fecha_creacion
        _total_dias = (_fe - _fecha_inicio).days
        _total_semanas = max(_total_dias // 7, 1)

        def _milestone_entry(pct, titulo, desc, icono, entreno, tipo_hito):
            """Build a milestone dict anchored at pct% of total plan duration."""
            dias_desde_inicio = int(_total_dias * pct)
            fecha_hito = _fecha_inicio + _dt.timedelta(days=dias_desde_inicio)
            semanas_desde_hoy = (fecha_hito - _hoy_m).days // 7
            pasado = fecha_hito < _hoy_m
            esta_semana = not pasado and 0 <= semanas_desde_hoy <= 1
            return {
                'semana_desde_hoy': semanas_desde_hoy,
                'fecha': fecha_hito.strftime('%-d %b %Y'),
                'titulo': titulo,
                'desc': desc,
                'icono': icono,
                'pasado': pasado,
                'esta_semana': esta_semana,
                'tipo_hito': tipo_hito,
                'entreno': entreno if esta_semana else None,
            }

        milestones = [
            _milestone_entry(
                pct=0.25,
                titulo='Test de ritmo 5K',
                desc='Mide tu progreso en carrera y ajusta los ritmos del plan',
                icono='fa-stopwatch',
                tipo_hito='test_5k',
                entreno={
                    'nombre': 'Test 5K',
                    'pasos': [
                        '10 min de calentamiento a ritmo suave',
                        'Corre 5K al máximo esfuerzo sostenible — registra el tiempo',
                        '5 min de vuelta a la calma',
                        'El tiempo se actualiza automáticamente en tu perfil atlético',
                    ],
                    'color': 'var(--accent)',
                },
            ),
            _milestone_entry(
                pct=0.50,
                titulo='Primera simulación completa',
                desc='Realiza las 8 estaciones seguidas por primera vez',
                icono='fa-flag',
                tipo_hito='sim_completa',
                entreno={
                    'nombre': 'Simulación 8 estaciones (70%)',
                    'pasos': [
                        '1 km de carrera suave de entrada',
                        'SkiErg 1000m → carrera 1km → Sled Push 50m → carrera 1km',
                        'Sled Pull 50m → carrera 1km → Burpee Broad Jumps 80m → carrera 1km',
                        'Rowing 1000m → carrera 1km → Farmers Carry 200m → carrera 1km',
                        'Sandbag Lunges 100m → carrera 1km → Wall Balls 100 reps',
                        'Pesos al 70% del oficial — foco en ritmo y transiciones',
                    ],
                    'color': 'var(--ok)',
                },
            ),
            _milestone_entry(
                pct=0.75,
                titulo='Simulación a peso oficial',
                desc='Todas las estaciones al 100% de los pesos de competición',
                icono='fa-medal',
                tipo_hito='sim_peso_oficial',
                entreno={
                    'nombre': 'Simulación Race Day (100%)',
                    'pasos': [
                        '1 km de carrera — ritmo de competición',
                        'Las 8 estaciones completas con pesos oficiales de tu categoría',
                        '1km de carrera entre cada estación — sin reducir el ritmo',
                        'Registra tiempo total y tiempo por estación',
                        'Evalúa recuperación post-simulación durante 48h',
                    ],
                    'color': '#f59e0b',
                },
            ),
            {
                'semana_desde_hoy': _semanas_restantes,
                'fecha': _fe.strftime('%-d %b %Y'),
                'titulo': 'Race Day',
                'desc': _fe.strftime('%-d %b %Y'),
                'icono': 'fa-trophy',
                'pasado': _dias_restantes < 0,
                'esta_semana': 0 <= _dias_restantes <= 7,
                'tipo_hito': None,
                'entreno': None,
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

    # ── PERFIL ATLÉTICO ───────────────────────────────────────────────────────
    perfil_atletico = None
    if objetivo_activo:
        from .services import HyroxAthleticProfile
        try:
            perfil_atletico = HyroxAthleticProfile.compute(objetivo_activo)
        except Exception:
            logger.exception("[HYROX] Error calculando perfil atlético")

    # ── ÍNDICE DE INTERFERENCIA ───────────────────────────────────────────────
    interferencia_index = []
    if objetivo_activo:
        from .services import InterferenceIndexService
        try:
            interferencia_index = InterferenceIndexService.compute_for_objective(objetivo_activo)
        except Exception:
            logger.exception("[HYROX] Error calculando interferencia_index")

    # ── STATION INTELLIGENCE DIAGNOSIS ────────────────────────────────────────
    station_diagnosis = None
    if objetivo_activo:
        from .station_intelligence import HyroxStationIntelligence as _SI
        _estacion_fuga = None
        _is_interference = False
        _sin_datos = False
        if interferencia_index:
            _estacion_fuga = interferencia_index[0].get('estacion')
            _is_interference = True
        elif estaciones_debiles:
            _estacion_fuga = estaciones_debiles[0].get('nombre')
        else:
            # Sin datos históricos: mostrar guía de referencia con SkiErg
            _estacion_fuga = 'SkiErg'
            _sin_datos = True
        if _estacion_fuga:
            _tip = _SI.get_station_tip(_estacion_fuga)
            _diag_text = _SI.get_diagnosis(_estacion_fuga, {'is_interference': _is_interference})
            _corrective = _SI.get_corrective_session(_estacion_fuga) or []
            if _tip:
                station_diagnosis = {
                    'estacion': _estacion_fuga,
                    'display_name': _tip['display_name'],
                    'causa': _diag_text,
                    'corrective_work': _SI.get_common_mistakes(_estacion_fuga)[:2],
                    'corrective_exercises': [a['nombre_ejercicio'] for a in _corrective],
                    'sin_datos': _sin_datos,
                    'technical_focus': _tip['technical_focus'],
                    'description': _tip.get('description', ''),
                    'positions': _tip.get('positions', []),
                    'rules': _tip.get('rules', []),
                    'weights': _tip.get('weights', {}),
                }

    # ── RACE CARD TÁCTICA + MODO COMPETICIÓN ─────────────────────────────────
    race_card = None
    modo_competicion = False
    race_day_briefing = None
    if objetivo_activo and objetivo_activo.tiempo_5k_base:
        from .services import RaceCardService
        try:
            race_card = RaceCardService.generate(objetivo_activo, splits_estaciones, interferencia_index)
        except Exception:
            logger.exception("[HYROX] Error generando race_card")
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

    # Guardar tiempo estimado en el log de hoy para poder calcular tendencia mañana
    if race_briefing and race_briefing.get('tiempo_estimado_seg'):
        try:
            from .models import HyroxReadinessLog
            HyroxReadinessLog.objects.filter(
                objective=objetivo_activo, fecha=timezone.now().date()
            ).update(tiempo_estimado_seg=race_briefing['tiempo_estimado_seg'])
        except Exception:
            pass

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

    # ── CURVAS DE PROGRESIÓN ──────────────────────────────────────────────────
    curvas_progresion = {}
    if objetivo_activo:
        from .training_engine import HyroxLoadManager
        import json as _json
        _curvas_def = [
            ('carrera',   None,         'Carrera · Ritmo',       'min/km'),
            ('fuerza',    'sentadilla',  'Sentadilla · Peso',     'kg'),
            ('fuerza',    'muerto',      'Peso Muerto · Peso',    'kg'),
            ('hyrox_station', 'sled',   'Sled Push · Peso',      'kg'),
        ]
        for _tipo, _kw, _label, _unit in _curvas_def:
            try:
                _puntos = HyroxLoadManager.get_progression_curve(
                    objetivo_activo, _tipo, ejercicio_keyword=_kw, semanas=10
                )
                from datetime import datetime as _dtp
                def _fmt_fecha(f):
                    try:
                        return _dtp.strptime(str(f), '%Y-%m-%d').strftime('%d/%m')
                    except Exception:
                        return str(f)
                _key = _tipo + ('_' + _kw if _kw else '')
                if _puntos:
                    if _tipo == 'carrera':
                        _display = [{'f': _fmt_fecha(p['fecha']), 'v': round(p['valor'] / 60, 2)} for p in _puntos]
                    else:
                        _display = [{'f': _fmt_fecha(p['fecha']), 'v': p['valor']} for p in _puntos]
                    _vals = [p['v'] for p in _display]
                    _min_v, _max_v = min(_vals), max(_vals)
                    _trend = None
                    if len(_vals) >= 4:
                        _early = sum(_vals[:2]) / 2
                        _late  = sum(_vals[-2:]) / 2
                        if _tipo == 'carrera':
                            _trend = 'mejora' if _late < _early else ('empeora' if _late > _early else 'estable')
                        else:
                            _trend = 'mejora' if _late > _early else ('empeora' if _late < _early else 'estable')
                    curvas_progresion[_key] = {
                        'label': _label, 'unit': _unit,
                        'puntos': _display, 'min_v': _min_v, 'max_v': _max_v,
                        'trend': _trend, 'json': _json.dumps(_display),
                        'sin_datos': False,
                    }
                else:
                    curvas_progresion[_key] = {
                        'label': _label, 'unit': _unit,
                        'puntos': [], 'sin_datos': True,
                    }
            except Exception:
                pass
        pass  # curvas_progresion already initialized as dict

    context = {
        'competition_progress': competition_progress,
        'macro_data': macro_data,
        'cliente': cliente,
        'objetivo_activo': objetivo_activo,
        'sesiones': sesiones_completadas,
        'plan_semanas': plan_semanas if objetivo_activo else [],
        'stats_semana': stats_semana,
        'resumen_semanal': resumen_semanal,
        'readiness_svg_points': readiness_svg_points,
        'readiness_score_hoy': current_score if objetivo_activo else None,
        'readiness_recovery_delta': _recovery_delta,
        'readiness_gym_nota': _gym_nota,
        'mental_focus': mental_focus if objetivo_activo else None,
        'strength_balance': strength_balance if objetivo_activo else None,
        'readiness_breakdown': readiness_breakdown if objetivo_activo else None,
        'pace_prediction': pace_prediction if objetivo_activo else None,
        'morning_briefing': morning_briefing if objetivo_activo else None,
        'daily_push': daily_push if objetivo_activo else None,
        'smart_alerts': smart_alerts if objetivo_activo else [],
        'lesion_activa': lesion_activa,
        'evolucion_carrera': evolucion_carrera,
        'splits_estaciones': splits_estaciones,
        'splits_categoria': objetivo_activo.get_categoria_display() if objetivo_activo else None,
        'splits_ref_label': splits_ref_label,
        'splits_edad': edad_atleta,
        'race_prediction': race_prediction,
        'top_perdidas': top_perdidas,
        'estaciones_debiles': estaciones_debiles,
        'fases_timeline': fases_timeline,
        'milestones': milestones,
        'objetivo_id': objetivo_activo.id if objetivo_activo else None,
        'sustituciones_activas': sustituciones_activas if 'sustituciones_activas' in locals() else [],
        'interferencia_index': interferencia_index,
        'race_card': race_card,
        'modo_competicion': modo_competicion,
        'race_day_briefing': race_day_briefing,
        'race_briefing': race_briefing,
        'sesion_override': sesion_override,
        'perfil_atletico': perfil_atletico,
        'curvas_progresion': curvas_progresion,
        'checkin_hoy': _checkin_hoy(cliente),
        'station_diagnosis': station_diagnosis,
        'post_session_diagnosis': post_session_diagnosis,
    }

    # ── Semáforo de Intención ─────────────────────────────────────
    from django.core.cache import cache as _cache
    _semaforo_key = f'semaforo_{cliente.pk}'
    semaforo = _cache.get(_semaforo_key)
    if semaforo is None:
        try:
            from core.daily_decision import DailyDecisionEngine
            semaforo = DailyDecisionEngine.get_estado_hoy(cliente)
            _cache.set(_semaforo_key, semaforo, 1800)
        except Exception:
            semaforo = None
    context['semaforo'] = semaforo

    return render(request, 'hyrox/dashboard.html', context)


def _corregir_fecha_sesion_completada(sesion):
    """
    Si la sesión completada tenía fecha futura (planificada para mañana
    pero ejecutada hoy), actualiza tanto HyroxSession.fecha como el
    registro en ActividadRealizada (hub) para que aparezca en los paneles.
    """
    from django.utils.timezone import now as _now
    from entrenos.models import ActividadRealizada
    hoy = _now().date()
    if sesion.fecha <= hoy:
        return
    sesion.fecha = hoy
    try:
        ActividadRealizada.objects.filter(sesion_hyrox=sesion).update(fecha=hoy)
    except Exception:
        pass


@login_required
def crear_objetivo(request):
    cliente = getattr(request.user, 'cliente_perfil', None)
    objetivo_existente = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()

    if request.method == 'POST':
        form = HyroxObjectiveForm(request.POST, instance=objetivo_existente)
        if form.is_valid():
            objetivo = form.save(commit=False)
            objetivo.cliente = cliente
            objetivo.estado = 'activo'
            objetivo.save()

            hoy = timezone.now().date()
            HyroxSession.objects.filter(
                objective=objetivo, estado='planificado', fecha__gte=hoy
            ).delete()
            HyroxTrainingEngine.generate_training_plan(objetivo)

            if objetivo_existente:
                messages.success(request, "Objetivo actualizado. El plan se ha regenerado desde hoy.")
            else:
                messages.success(request, "Objetivo Hyrox creado y plan generado. ¡A por todas!")
            return redirect('hyrox:dashboard')
        else:
            # Mostrar errores de validación explícitamente
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    else:
        # GET: usar instance directamente si existe (pre-rellena todos los campos)
        form = HyroxObjectiveForm(instance=objetivo_existente)

    dias_semana = [(0,'Lun'),(1,'Mar'),(2,'Mié'),(3,'Jue'),(4,'Vie'),(5,'Sáb'),(6,'Dom')]
    return render(request, 'hyrox/crear_objetivo.html', {
        'form': form,
        'dias_semana': dias_semana,
        'es_edicion': objetivo_existente is not None,
    })

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
def iniciar_hito(request, objective_id, tipo_hito):
    """Crea una HyroxSession pre-rellena para un hito del macrociclo y redirige al flujo de registro."""
    objetivo = get_object_or_404(HyroxObjective, id=objective_id, cliente=request.user.cliente_perfil)
    from .training_engine import HyroxTrainingEngine as _HTE
    from .models import HyroxActivity

    hoy = timezone.now().date()
    pesos = _HTE.PESOS_OFICIALES.get(objetivo.categoria, _HTE.PESOS_OFICIALES['open_men'])

    HITOS = {
        'test_5k': {
            'titulo': '[HITO:test_5k] Test de ritmo 5K',
            'actividades': [
                {'tipo': 'carrera', 'nombre': 'Calentamiento 10 min suave',
                 'metricas': {'distancia_m': 1500, 'notas': 'Ritmo muy suave. Prepara el cuerpo.'}},
                {'tipo': 'carrera', 'nombre': 'Test 5K — Máximo esfuerzo',
                 'metricas': {'distancia_m': 5000, 'notas': 'Corre los 5 km al máximo esfuerzo sostenible. Registra el tiempo total exacto.'}},
                {'tipo': 'carrera', 'nombre': 'Vuelta a la calma',
                 'metricas': {'distancia_m': 800, 'notas': 'Ritmo muy suave, 5 min de recuperación activa.'}},
            ],
        },
        'sim_completa': {
            'titulo': '[HITO:sim_completa] Primera simulación completa (70%)',
            'actividades': [
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'skierg', 'nombre': 'SkiErg', 'metricas': {'distancia_m': 1000, 'notas': '70% potencia, 32-38 tirones/min.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sled Push', 'metricas': {'distancia_m': 50, 'peso_kg': round(pesos['sled_push'] * 0.7)}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sled Pull', 'metricas': {'distancia_m': 50, 'peso_kg': round(pesos['sled_pull'] * 0.7)}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Burpee Broad Jumps', 'metricas': {'distancia_m': 80, 'notas': '80 m continuos, ritmo constante.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'ergometro', 'nombre': 'Rowing 1000m', 'metricas': {'distancia_m': 1000, 'notas': 'Damper 4-5, ritmo sostenible.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Farmers Carry', 'metricas': {'distancia_m': 200, 'peso_kg': round(pesos['farmers'] * 0.7)}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sandbag Lunges', 'metricas': {'distancia_m': 100, 'peso_kg': round(pesos['sandbag'] * 0.7)}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Wall Balls', 'metricas': {'reps_total': 100, 'peso_kg': pesos['wall_ball'], 'notas': '70% esfuerzo, sets de 10-15 reps.'}},
            ],
        },
        'sim_peso_oficial': {
            'titulo': '[HITO:sim_peso_oficial] Simulación a peso oficial',
            'actividades': [
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'skierg', 'nombre': 'SkiErg', 'metricas': {'distancia_m': 1000, 'notas': 'Ritmo de competición.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sled Push', 'metricas': {'distancia_m': 50, 'peso_kg': pesos['sled_push']}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sled Pull', 'metricas': {'distancia_m': 50, 'peso_kg': pesos['sled_pull']}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Burpee Broad Jumps', 'metricas': {'distancia_m': 80, 'notas': 'Ritmo de competición desde el inicio.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'ergometro', 'nombre': 'Rowing 1000m', 'metricas': {'distancia_m': 1000, 'notas': 'Damper 4-5.'}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Farmers Carry', 'metricas': {'distancia_m': 200, 'peso_kg': pesos['farmers']}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Sandbag Lunges', 'metricas': {'distancia_m': 100, 'peso_kg': pesos['sandbag']}},
                {'tipo': 'carrera', 'nombre': 'Carrera 1 km', 'metricas': {'distancia_m': 1000}},
                {'tipo': 'hyrox_station', 'nombre': 'Wall Balls', 'metricas': {'reps_total': 100, 'peso_kg': pesos['wall_ball']}},
            ],
        },
    }

    config = HITOS.get(tipo_hito)
    if not config:
        messages.error(request, "Tipo de hito no reconocido.")
        return redirect('hyrox:dashboard')

    # Crear la sesión del hito (o reutilizar si ya existe para hoy)
    sesion_existente = HyroxSession.objects.filter(
        objective=objetivo, fecha=hoy,
        titulo__startswith=f'[HITO:{tipo_hito}]',
        estado='planificado'
    ).first()

    if sesion_existente:
        sesion = sesion_existente
    else:
        sesion = HyroxSession.objects.create(
            objective=objetivo,
            fecha=hoy,
            titulo=config['titulo'],
            estado='planificado',
        )
        for act in config['actividades']:
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad=act['tipo'],
                nombre_ejercicio=act['nombre'],
                data_metricas=act['metricas'],
            )

    return redirect('hyrox:registrar_entrenamiento_session', objective_id=objetivo.id, session_id=sesion.id)


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

            # Si el usuario eligió el plan original, restaurar actividades del snapshot
            usar_plan_original = request.POST.get('usar_plan_original') == '1'
            if usar_plan_original and '[AUTO-OVERRIDE]' in (sesion.titulo or ''):
                primera_act = sesion.activities.first()
                snapshot = []
                if primera_act and primera_act.data_planificado:
                    snapshot = primera_act.data_planificado.get('plan_original', [])
                if snapshot:
                    from hyrox.models import HyroxActivity
                    sesion.activities.all().delete()
                    for item in snapshot:
                        HyroxActivity.objects.create(
                            sesion=sesion,
                            tipo_actividad=item.get('tipo', 'otro'),
                            nombre_ejercicio=item.get('nombre', ''),
                            data_metricas=item.get('metricas', {}) or {},
                        )
                    sesion.titulo = sesion.titulo.replace('[AUTO-OVERRIDE] ', '')
                    sesion.save(update_fields=['titulo'])

            # Procesamiento de la IA
            if sesion.notas_raw:
                sustituir_material = form.cleaned_data.get('sustituir_material', False)
                parsed_data = HyroxParserService.parse_workout_text(sesion.notas_raw, sustituir_material=sustituir_material)
                if parsed_data:
                    resultados_save = HyroxParserService.save_parsed_session(sesion, parsed_data)
                    actividades = resultados_save.get('activities', []) if isinstance(resultados_save, dict) else []
                    new_records = resultados_save.get('new_records', []) if isinstance(resultados_save, dict) else []

                    # Override distancia_km from direct form fields — más fiable que el parser de texto
                    _form_dists = {}
                    for _k, _v in request.POST.items():
                        if _k.startswith('act_dist_km_'):
                            try:
                                _form_dists[int(_k[12:])] = round(float(_v.replace(',', '.')), 2)
                            except (ValueError, TypeError):
                                pass
                    if _form_dists:
                        for _i, _act in enumerate(sesion.activities.order_by('id'), start=1):
                            _dist = _form_dists.get(_i)
                            if _dist and _dist > 0:
                                _m = _act.data_metricas or {}
                                _m['distancia_km'] = _dist
                                _act.data_metricas = _m
                                _act.save(update_fields=['data_metricas'])
                    
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
                m = dict(act.data_metricas or {})
                changed = False
                t_s_raw = request.POST.get(f'act_tiempo_s_{i}')
                if t_s_raw and t_s_raw.strip():
                    t_s = int(t_s_raw)
                    if t_s > 0:
                        m['tiempo_s'] = t_s
                        changed = True
                reps_raw = request.POST.get(f'act_reps_st_{i}', '').strip()
                kg_raw = request.POST.get(f'act_kg_st_{i}', '').strip()
                if reps_raw:
                    try:
                        m['reps_total'] = int(reps_raw)
                        changed = True
                    except ValueError:
                        pass
                if kg_raw:
                    try:
                        m['peso_kg'] = float(kg_raw)
                        changed = True
                    except ValueError:
                        pass
                if changed:
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
                _corregir_fecha_sesion_completada(sesion)

                # Calculate cumplimiento_ratio from per-activity hidden inputs
                acts_for_compl = list(sesion.activities.all().order_by('id'))
                compl_scores = []
                for _i, _act in enumerate(acts_for_compl, 1):
                    _raw = request.POST.get(f'act_done_{_i}', '')
                    try:
                        _frac = float(_raw)
                        if 0.0 <= _frac <= 1.0:
                            compl_scores.append(_frac)
                    except (ValueError, TypeError):
                        pass
                if compl_scores:
                    sesion.cumplimiento_ratio = round(sum(compl_scores) / len(compl_scores), 3)

                sesion.save()

                # Guardar station feedback del wizard de diagnóstico
                sf_json = request.POST.get('station_feedback_json', '').strip()
                if sf_json:
                    try:
                        import json as _json
                        sf_data = _json.loads(sf_json)
                        if isinstance(sf_data, list) and sf_data:
                            sesion.station_feedback = sf_data
                            sesion.save(update_fields=['station_feedback'])
                    except (ValueError, KeyError):
                        pass

                # Phase 8 & 9 & 14: Bucle de Feedback Continuo Post-Procesamiento.
                # 1. Ajuste de volumen inmediato por Energía Pre-Entreno
                HyroxTrainingEngine.scale_volume_by_energy(sesion)

                # 2. Evaluamos la sesión completada (RPE, Volumen) y ajustamos la(s) siguiente(s)
                alertas = HyroxTrainingEngine.apply_continuous_adaptation(sesion)
                if alertas:
                     for alerta in alertas:
                          messages.info(request, f"⚡ {alerta}")

                # 3. Actualización automática de RMs — el entrenador aprende
                from .training_engine import RMAutoUpdater, PaceAutoUpdater
                mensajes_rm = RMAutoUpdater.update_from_session(sesion)
                for msg in mensajes_rm:
                    messages.success(request, f"💪 {msg}")

                # 4. Actualización de ritmo 5K desde carrera libre
                mensajes_pace = PaceAutoUpdater.update_from_session(sesion)
                for msg in mensajes_pace:
                    messages.success(request, f"🏃 {msg}")

                # 5. Calibración de RPE personal — detección de sesgo sistemático
                from .training_engine import RPECalibrator, DeloadAutoTrigger
                mensajes_rpe = RPECalibrator.check_and_notify(sesion)
                for msg in mensajes_rpe:
                    messages.info(request, f"📊 {msg}")

                # 6. Deload automático por TSB < -25
                mensajes_deload = DeloadAutoTrigger.check_and_apply(sesion)
                for msg in mensajes_deload:
                    messages.warning(request, f"⚡ {msg}")

                # Hito: detectar tipo y lanzar adaptación del plan
                tipo_hito_sesion = None
                if sesion.titulo:
                    for _th in ('test_5k', 'sim_completa', 'sim_peso_oficial'):
                        if f'[HITO:{_th}]' in sesion.titulo:
                            tipo_hito_sesion = _th
                            break

                if tipo_hito_sesion == 'test_5k':
                    # Actualizar tiempo_5k_base antes de llamar al engine
                    act_5k = sesion.activities.filter(nombre_ejercicio='Test 5K — Máximo esfuerzo').first()
                    if act_5k and act_5k.data_metricas:
                        tiempo_s = act_5k.data_metricas.get('tiempo_s')
                        if tiempo_s and int(tiempo_s) > 0:
                            mins = int(tiempo_s) // 60
                            segs = int(tiempo_s) % 60
                            nuevo_tiempo = f"{mins}:{segs:02d}"
                            objetivo.tiempo_5k_base = nuevo_tiempo
                            objetivo.save(update_fields=['tiempo_5k_base'])

                if tipo_hito_sesion:
                    from .training_engine import PostMilestoneEngine
                    mensajes_hito = PostMilestoneEngine.adapt_after_milestone(sesion, tipo_hito_sesion)
                    for msg in mensajes_hito:
                        messages.success(request, f"🎯 {msg}")

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
            from .station_intelligence import HyroxStationIntelligence as _SI
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
                # Inject Station Intelligence technical focus
                act.station_focus = _SI.get_station_tip(act.nombre_ejercicio)
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

        # Si el usuario eligió usar el plan original, sustituir actividades_planificadas
        plan_elegido = request.GET.get('plan', 'ajustado')
        if es_override and plan_elegido == 'original' and plan_original_snapshot:
            class _SnapshotAct:
                def __init__(self, item):
                    self.nombre_ejercicio = item.get('nombre', '')
                    self.tipo_actividad = item.get('tipo', 'otro')
                    self.data_metricas = item.get('metricas', {}) or {}
                    self.data_planificado = {}
                    self.series_processed = []
                    self.display_name = self.nombre_ejercicio
                    self.is_substituted = False
            actividades_planificadas = [_SnapshotAct(item) for item in plan_original_snapshot]

        form = HyroxSessionNotesForm(initial={'titulo': titulo_limpio})

    from .station_intelligence import HyroxStationIntelligence as _SI_reg
    _sf_stations = [
        {'key': k, 'name': v['display_name']}
        for k, v in _SI_reg.STATIONS.items()
    ]

    return render(request, 'hyrox/registrar_entrenamiento.html', {
        'form': form,
        'objetivo': objetivo,
        'sesion_planificada': sesion_planificada,
        'actividades_planificadas': actividades_planificadas if 'actividades_planificadas' in locals() else sesion_planificada.activities.all() if sesion_planificada else [],
        'lesion_activa': lesion_activa,
        'es_override': es_override if 'es_override' in locals() else False,
        'titulo_limpio': titulo_limpio if 'titulo_limpio' in locals() else '',
        'plan_original_snapshot': plan_original_snapshot if 'plan_original_snapshot' in locals() else [],
        'plan_elegido': plan_elegido if 'plan_elegido' in locals() else 'ajustado',
        'sf_stations': _sf_stations,
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
            _corregir_fecha_sesion_completada(sesion)
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
        _REPS_STATIONS = {'wall ball', 'wall balls'}
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
            elif is_reps_station:  # antes que is_fuerza: Wall Balls puede tener 'series' del plan
                reps = request.POST.get(f'act_reps_total_{act.id}')
                kg = request.POST.get(f'act_kg_{act.id}')
                if reps:
                    peso = float(kg) if kg else None
                    m['series'] = [{'reps': int(reps), 'peso_kg': peso}] if peso else [{'reps': int(reps)}]
                    m['reps_total'] = int(reps)
                if kg: m['peso_kg'] = float(kg)
            elif is_fuerza:
                series = m.get('series') or []
                for i, serie in enumerate(series):
                    reps_f = request.POST.get(f'act_reps_{act.id}_{i}')
                    kg_f = request.POST.get(f'act_kg_serie_{act.id}_{i}')
                    if reps_f: serie['reps'] = int(reps_f)
                    if kg_f: serie['peso_kg'] = float(kg_f); serie['peso'] = float(kg_f)
                m['series'] = series
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
            # update_fields evita que los signals regeneren el plan futuro.
            # Al editar una sesión pasada solo queremos recalcular la carga,
            # no adaptar las sesiones planificadas.
            campos_sesion = ['estado', 'rpe_global', 'tiempo_total_minutos', 'hr_media', 'hr_maxima']
            session.save(update_fields=campos_sesion)

            # Recalcular TRIMP / zona / CTL-ATL-TSB y sincronizar hub manualmente
            try:
                from hyrox.signals import _calcular_y_guardar_carga
                _calcular_y_guardar_carga(session)
            except Exception as e_carga:
                _log.warning(f'[EDIT session={session.id}] No se pudo recalcular carga: {e_carga}')

            try:
                from entrenos.models import ActividadRealizada
                carga_ua = None
                if session.rpe_global and session.tiempo_total_minutos:
                    carga_ua = round(session.rpe_global * session.tiempo_total_minutos, 1)
                ActividadRealizada.objects.filter(sesion_hyrox=session).update(
                    rpe_medio=session.rpe_global,
                    duracion_minutos=session.tiempo_total_minutos,
                    carga_ua=carga_ua,
                )
            except Exception as e_hub:
                _log.warning(f'[EDIT session={session.id}] No se pudo actualizar hub: {e_hub}')

        except Exception as e:
            import traceback as _tb
            _log.error(f'[EDIT session={session.id}] ERROR en session.save(): {e}\n{_tb.format_exc()}')
        messages.success(request, "Sesión actualizada correctamente.")
        return redirect('hyrox:dashboard')

    TIPO_ACT_CARRERA = {'carrera', 'cardio_sustituto'}
    TIPO_ACT_ESTACION = {'hyrox_station', 'ergometro', 'isometrico', 'hiit', 'remo', 'skierg', 'bici', 'otro'}
    # Estaciones Hyrox que funcionan por reps+kg, no por distancia
    ESTACIONES_REPS = {'wall ball', 'wall balls'}

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
        elif es_reps_station:
            # Wall Balls y similares: siempre reps_total + kg, aunque tengan series del plan
            tipo = 'reps_kg'
        elif m.get('series'):
            # Series guardadas → editar como fuerza
            tipo = 'fuerza'
        elif ta == 'fuerza':
            tipo = 'fuerza'
        elif ta in TIPO_ACT_ESTACION and m.get('distancia_m') is not None:
            tipo = 'estacion'
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

        import re as _re
        _nombre_raw = act.nombre_ejercicio or act.get_tipo_actividad_display()
        _nombre = _re.sub(r'\s*\[\d+s\]', '', _nombre_raw, flags=_re.IGNORECASE).strip()

        actividades_ctx.append({
            'id': act.id,
            'nombre': _nombre,
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
@require_POST
def api_registro_recuperacion(request, lesion_id):
    """AJAX — registra el estado diario de recuperación y devuelve el nuevo estado."""
    from .models import UserInjury, DailyRecoveryEntry
    from .services import InjuryPhaseManager

    lesion = get_object_or_404(UserInjury, id=lesion_id, cliente=request.user.cliente_perfil)
    try:
        dolor_reposo      = max(0, min(10, int(request.POST.get('dolor_reposo', 0))))
        dolor_movimiento  = max(0, min(10, int(request.POST.get('dolor_movimiento', 0))))
        inflamacion       = max(1, min(10, int(request.POST.get('inflamacion', 1))))
        rango             = max(1, min(10, int(request.POST.get('rango', 5))))
        notas             = request.POST.get('notas', '').strip()[:300]

        from datetime import date as _date
        entry, _ = DailyRecoveryEntry.objects.update_or_create(
            lesion=lesion,
            fecha=_date.today(),
            defaults={
                'dolor_reposo':        dolor_reposo,
                'dolor_movimiento':    dolor_movimiento,
                'inflamacion_percibida': inflamacion,
                'rango_movimiento':    rango,
                'notas_usuario':       notas or None,
            }
        )

        # Evaluar transición de fase automáticamente
        InjuryPhaseManager.evaluate_phase_transition(lesion)
        lesion.refresh_from_db()

        # ¿Puede marcarse como recuperada ya?
        puede_alta = (
            dolor_reposo == 0 and dolor_movimiento <= 1
            and inflamacion == 1 and rango >= 8
        )

        return JsonResponse({
            'ok': True,
            'fase': lesion.fase,
            'activa': lesion.activa,
            'puede_alta': puede_alta,
            'msg': f'Registrado. Fase actual: {lesion.fase}.'
                   + (' Puedes marcar alta.' if puede_alta else ''),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'msg': str(e)}, status=400)


@login_required
@require_POST
def api_marcar_recuperada(request, lesion_id):
    """AJAX — marca la lesión como recuperada."""
    from .models import UserInjury
    from django.utils import timezone as tz

    lesion = get_object_or_404(UserInjury, id=lesion_id, cliente=request.user.cliente_perfil)
    lesion.fase = 'RECUPERADO'
    lesion.activa = False
    lesion.fecha_resolucion = tz.now().date()
    lesion.save()

    from django.core.cache import cache
    cache.set(f"bio_needs_regen_{lesion.cliente.id}", True, timeout=3600)
    request.session.pop(f'plan_anual_{lesion.cliente.id}', None)
    request.session.modified = True

    try:
        from core.bio_context import BioContextProvider
        BioContextProvider.force_clean_future_workouts(lesion.cliente)
    except Exception:
        pass

    return JsonResponse({'ok': True, 'msg': '¡Recuperado! Las restricciones han desaparecido.'})


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



# ─────────────────────────────────────────────────────────────────────────────
# STRAVA INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

import hashlib
import hmac
import urllib.parse
from datetime import datetime as _dt

from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from .models import StravaToken, StravaActivityRaw


def _strava_refresh_token(token: StravaToken) -> StravaToken:
    """Exchange a stale token for a fresh one via Strava API."""
    import requests as _req
    resp = _req.post('https://www.strava.com/oauth/token', data={
        'client_id':     django_settings.STRAVA_CLIENT_ID,
        'client_secret': django_settings.STRAVA_CLIENT_SECRET,
        'grant_type':    'refresh_token',
        'refresh_token': token.refresh_token,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    from django.utils import timezone as _tz
    token.access_token  = data['access_token']
    token.refresh_token = data['refresh_token']
    token.expires_at    = _tz.datetime.fromtimestamp(data['expires_at'], tz=__import__('datetime').timezone.utc)
    token.save()
    return token


def _strava_get_activity(token: StravaToken, activity_id: int) -> dict:
    """Fetch full activity from Strava API, refreshing token if needed."""
    import requests as _req
    if token.is_expired():
        token = _strava_refresh_token(token)
    resp = _req.get(
        f'https://www.strava.com/api/v3/activities/{activity_id}',
        headers={'Authorization': f'Bearer {token.access_token}'},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@login_required
def strava_connect(request):
    """Redirect user to Strava OAuth page."""
    params = urllib.parse.urlencode({
        'client_id':     django_settings.STRAVA_CLIENT_ID,
        'redirect_uri':  request.build_absolute_uri('/hyrox/strava/callback/'),
        'response_type': 'code',
        'approval_prompt': 'auto',
        'scope':         'activity:read_all',
    })
    return redirect(f'https://www.strava.com/oauth/authorize?{params}')


@login_required
def strava_callback(request):
    """Handle OAuth callback, save tokens, redirect to Hyrox dashboard."""
    import requests as _req
    from django.utils import timezone as _tz

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Conexión con Strava cancelada.')
        return redirect('hyrox:dashboard')

    try:
        resp = _req.post('https://www.strava.com/oauth/token', data={
            'client_id':     django_settings.STRAVA_CLIENT_ID,
            'client_secret': django_settings.STRAVA_CLIENT_SECRET,
            'code':          code,
            'grant_type':    'authorization_code',
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        cliente = request.user.cliente_perfil
        expires = _tz.datetime.fromtimestamp(data['expires_at'], tz=__import__('datetime').timezone.utc)
        StravaToken.objects.update_or_create(
            cliente=cliente,
            defaults={
                'athlete_id':    data['athlete']['id'],
                'access_token':  data['access_token'],
                'refresh_token': data['refresh_token'],
                'expires_at':    expires,
            }
        )
        messages.success(request, '¡Strava conectado! Las nuevas actividades llegarán automáticamente.')
    except Exception as exc:
        messages.error(request, f'Error conectando con Strava: {exc}')

    return redirect('hyrox:strava_reconciliacion')


@csrf_exempt
def strava_webhook(request):
    """
    GET  — Strava subscription verification challenge.
    POST — Incoming activity event; stage it for user review.
    """
    if request.method == 'GET':
        challenge    = request.GET.get('hub.challenge', '')
        verify_token = request.GET.get('hub.verify_token', '')
        if verify_token == django_settings.STRAVA_VERIFY_TOKEN:
            return JsonResponse({'hub.challenge': challenge})
        return HttpResponse(status=403)

    if request.method == 'POST':
        import json as _json
        try:
            body    = _json.loads(request.body)
            aspect  = body.get('aspect_type')       # 'create' | 'update' | 'delete'
            obj_type = body.get('object_type')      # 'activity'
            act_id  = body.get('object_id')
            ath_id  = body.get('owner_id')

            if aspect == 'create' and obj_type == 'activity':
                try:
                    token = StravaToken.objects.select_related('cliente').get(athlete_id=ath_id)
                    # Avoid duplicate inserts
                    if not StravaActivityRaw.objects.filter(strava_id=act_id).exists():
                        raw = _strava_get_activity(token, act_id)
                        from datetime import date as _date
                        fecha_str = raw.get('start_date_local', '')[:10]
                        fecha = _date.fromisoformat(fecha_str) if fecha_str else _date.today()
                        StravaActivityRaw.objects.create(
                            cliente          = token.cliente,
                            strava_id        = act_id,
                            fecha_actividad  = fecha,
                            tipo_strava      = raw.get('type', ''),
                            nombre_strava    = raw.get('name', ''),
                            duracion_segundos = raw.get('moving_time', 0),
                            hr_media         = raw.get('average_heartrate') or None,
                            hr_maxima        = raw.get('max_heartrate') or None,
                            distancia_metros = raw.get('distance') or None,
                            raw_json         = raw,
                        )
                except StravaToken.DoesNotExist:
                    pass  # Activity for an unregistered athlete — ignore
                except Exception:
                    pass  # Never let webhook fail with non-200
        except Exception:
            pass
        return HttpResponse(status=200)

    return HttpResponse(status=405)


@login_required
def strava_reconciliacion(request):
    """List pending Strava activities and let the user decide what to do."""
    from entrenos.models import EntrenoRealizado

    cliente = request.user.cliente_perfil
    pendientes = StravaActivityRaw.objects.filter(
        cliente=cliente, estado='pending'
    ).select_related('hyrox_session')

    objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()

    from datetime import timedelta

    from django.db.models import Q
    from entrenos.models import EntrenoRealizado as _ER

    # IDs explícitos ya vinculados a Strava — fuente de verdad fiable
    # (el reverso strava_sources falla cuando entreno_gym_id quedó a None)
    gym_ids_sync = set(
        StravaActivityRaw.objects.filter(
            cliente=cliente,
            estado__in=['merged', 'created'],
            entreno_gym__isnull=False,
        ).values_list('entreno_gym_id', flat=True)
    )
    hyrox_ids_sync = set(
        StravaActivityRaw.objects.filter(
            cliente=cliente,
            estado__in=['merged', 'created'],
            hyrox_session__isnull=False,
        ).values_list('hyrox_session_id', flat=True)
    )

    # Entrenos de gym no sincronizados (para búsqueda manual — últimos 90 días)
    from datetime import date as _date
    hace_90 = _date.today() - timedelta(days=90)
    gym_sin_sync = list(
        _ER.objects.filter(cliente=cliente, fecha__gte=hace_90)
        .exclude(id__in=gym_ids_sync)
        .order_by('-fecha')
    )

    items = []
    for act in pendientes:
        fecha_min = act.fecha_actividad - timedelta(days=1)
        fecha_max = act.fecha_actividad + timedelta(days=1)
        hyrox_matches = []
        gym_matches   = []

        if objetivo:
            hyrox_matches = list(
                HyroxSession.objects.filter(
                    objective=objetivo,
                    fecha__range=(fecha_min, fecha_max),
                    estado='completado',
                ).exclude(id__in=hyrox_ids_sync)
                .order_by('id')
            )

        gym_matches = list(
            _ER.objects.filter(cliente=cliente)
            .filter(
                Q(hub_actividad__fecha_realizado__range=(fecha_min, fecha_max)) |
                Q(hub_actividad__fecha_realizado__isnull=True, fecha__range=(fecha_min, fecha_max)) |
                Q(hub_actividad__isnull=True, fecha__range=(fecha_min, fecha_max))
            )
            .exclude(id__in=gym_ids_sync)
            .distinct().order_by('id')
        )

        # Preselect best candidate based on Strava type
        tipo_hyrox = act.tipo_hyrox()
        if tipo_hyrox in ('carrera', 'remo', 'bici', 'cardio_sustituto', 'hiit'):
            preselect = ('hyrox', hyrox_matches[0].id) if hyrox_matches else ('gym', gym_matches[0].id) if gym_matches else None
        else:
            preselect = ('gym', gym_matches[0].id) if gym_matches else ('hyrox', hyrox_matches[0].id) if hyrox_matches else None

        items.append({
            'actividad':      act,
            'hyrox_matches':  hyrox_matches,
            'gym_matches':    gym_matches,
            'total_matches':  len(hyrox_matches) + len(gym_matches),
            'preselect':      preselect,
        })

    return render(request, 'hyrox/strava_reconciliacion.html', {
        'items':        items,
        'objetivo':     objetivo,
        'tiene_token':  StravaToken.objects.filter(cliente=cliente).exists(),
        'gym_sin_sync': gym_sin_sync,
    })


@login_required
@require_POST
def strava_procesar(request, actividad_id):
    """
    accion:
      'ignore'       — descartar
      'merge_hyrox'  — fusionar con HyroxSession existente
      'merge_gym'    — fusionar con EntrenoRealizado existente
      'create_hyrox' — nueva HyroxSession
      'create_gym'   — nueva ActividadRealizada directa (sin ejercicios)
    """
    from django.db import transaction
    from entrenos.models import EntrenoRealizado, ActividadRealizada

    cliente = request.user.cliente_perfil
    act = get_object_or_404(StravaActivityRaw, id=actividad_id, cliente=cliente, estado='pending')
    accion = request.POST.get('accion')
    duracion_min = act.duracion_segundos / 60

    def _rpe():
        try:
            return int(request.POST.get('rpe', '')) or None
        except (ValueError, TypeError):
            return None

    def _trimp_from_strava(hr_media, duracion_min):
        """TRIMP de Banister a partir de FC media. Usa objetivo activo si existe; sino fc_max=185."""
        if not hr_media or not duracion_min:
            return None
        from .training_engine import HyroxLoadManager
        objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        return HyroxLoadManager.calcular_trimp(duracion_min, hr_media, objetivo)

    # ── IGNORAR ──────────────────────────────────────────────────────────────
    if accion == 'ignore':
        act.estado = 'ignored'
        act.save()
        return JsonResponse({'ok': True, 'msg': 'Actividad ignorada.'})

    # ── FUSIONAR CON HYROX ───────────────────────────────────────────────────
    if accion == 'merge_hyrox':
        objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not objetivo:
            return JsonResponse({'ok': False, 'msg': 'No tienes un objetivo Hyrox activo.'}, status=400)
        sesion = get_object_or_404(HyroxSession, id=request.POST.get('session_id'), objective=objetivo)
        ov_tiempo    = request.POST.get('override_tiempo', 'mine')
        ov_hr_media  = request.POST.get('override_hr_media', 'mine')
        ov_hr_maxima = request.POST.get('override_hr_maxima', 'mine')
        if ov_hr_media == 'strava' and act.hr_media:
            sesion.hr_media = act.hr_media
        elif not sesion.hr_media and act.hr_media:
            sesion.hr_media = act.hr_media
        if ov_hr_maxima == 'strava' and act.hr_maxima:
            sesion.hr_maxima = act.hr_maxima
        elif not sesion.hr_maxima and act.hr_maxima:
            sesion.hr_maxima = act.hr_maxima
        if ov_tiempo == 'strava' or not sesion.tiempo_total_minutos:
            sesion.tiempo_total_minutos = int(duracion_min)
        if not sesion.trimp and sesion.hr_media:
            from .training_engine import HyroxLoadManager
            sesion.trimp = HyroxLoadManager.calcular_trimp(sesion.tiempo_total_minutos, sesion.hr_media, objetivo)
        sesion.save()
        # Actualizar distancia de la actividad de carrera con el dato real de Strava
        if act.distancia_metros:
            strava_km = round(act.distancia_metros / 1000, 2)
            carrera_act = sesion.activities.filter(tipo_actividad__in=['carrera', 'cardio_sustituto']).first()
            if carrera_act:
                _m = carrera_act.data_metricas or {}
                _m['distancia_km'] = strava_km
                carrera_act.data_metricas = _m
                carrera_act.save(update_fields=['data_metricas'])
        act.estado = 'merged'
        act.hyrox_session = sesion
        act.save()
        rpe_info = f' · RPE {sesion.rpe_global}' if sesion.rpe_global else ' (sin RPE — no computará en ACWR)'
        return JsonResponse({'ok': True, 'msg': f'Fusionado con sesión Hyrox{rpe_info}.'})

    # ── FUSIONAR CON GYM ─────────────────────────────────────────────────────
    if accion == 'merge_gym':
        entreno = get_object_or_404(EntrenoRealizado, id=request.POST.get('entreno_id'), cliente=cliente)
        ov_tiempo    = request.POST.get('override_tiempo', 'mine')
        ov_hr_media  = request.POST.get('override_hr_media', 'mine')
        ov_hr_maxima = request.POST.get('override_hr_maxima', 'mine')
        if ov_hr_media == 'strava' and act.hr_media:
            entreno.frecuencia_cardiaca_promedio = act.hr_media
        elif not entreno.frecuencia_cardiaca_promedio and act.hr_media:
            entreno.frecuencia_cardiaca_promedio = act.hr_media
        if ov_hr_maxima == 'strava' and act.hr_maxima:
            entreno.frecuencia_cardiaca_maxima = act.hr_maxima
        elif not entreno.frecuencia_cardiaca_maxima and act.hr_maxima:
            entreno.frecuencia_cardiaca_maxima = act.hr_maxima
        if ov_tiempo == 'strava' or not entreno.duracion_minutos:
            entreno.duracion_minutos = int(duracion_min)
        entreno.save()
        # Actualizar hub ActividadRealizada con FC, RPE y recalcular carga_ua
        rpe_manual = _rpe()
        try:
            ar = ActividadRealizada.objects.get(entreno_gym=entreno)
            hr_final = entreno.frecuencia_cardiaca_promedio
            trimp = _trimp_from_strava(hr_final, ar.duracion_minutos or int(duracion_min))
            update_fields = []
            if act.hr_media and not ar.hr_media:
                ar.hr_media = act.hr_media
                update_fields.append('hr_media')
            if act.hr_maxima and not ar.hr_maxima:
                ar.hr_maxima = act.hr_maxima
                update_fields.append('hr_maxima')
            # Guardar RPE manual si el usuario lo seleccionó
            if rpe_manual and not ar.rpe_medio:
                ar.rpe_medio = rpe_manual
                update_fields.append('rpe_medio')
            # TRIMP prevalece; sRPE como fallback si no hay FC
            if trimp:
                ar.carga_ua = trimp
                update_fields.append('carga_ua')
            elif (ar.rpe_medio or rpe_manual) and not ar.carga_ua:
                rpe_carga = ar.rpe_medio or rpe_manual
                ar.carga_ua = round(rpe_carga * duracion_min, 1)
                update_fields.append('carga_ua')
            if update_fields:
                ar.save(update_fields=update_fields)
        except ActividadRealizada.DoesNotExist:
            pass
        act.estado     = 'merged'
        act.entreno_gym = entreno
        act.save()
        fc_info = f' · TRIMP calculado desde FC {act.hr_media} bpm' if act.hr_media else ''
        return JsonResponse({'ok': True, 'msg': f'Datos Strava fusionados con entreno de gym del {act.fecha_actividad}{fc_info}.'})

    # ── CREAR HYROX ──────────────────────────────────────────────────────────
    if accion == 'create_hyrox':
        objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not objetivo:
            return JsonResponse({'ok': False, 'msg': 'No tienes un objetivo Hyrox activo.'}, status=400)
        tipo  = request.POST.get('tipo_actividad', act.tipo_hyrox())
        rpe   = _rpe()
        from .training_engine import HyroxLoadManager
        trimp = HyroxLoadManager.calcular_trimp(int(duracion_min), act.hr_media, objetivo) if act.hr_media else None
        with transaction.atomic():
            sesion = HyroxSession.objects.create(
                objective=objetivo, fecha=act.fecha_actividad,
                titulo=act.nombre_strava or f'Strava — {act.tipo_strava}',
                estado='completado', tiempo_total_minutos=int(duracion_min),
                hr_media=act.hr_media, hr_maxima=act.hr_maxima,
                trimp=trimp, rpe_global=rpe,
            )
            HyroxActivity.objects.create(
                sesion=sesion, tipo_actividad=tipo,
                nombre_ejercicio=act.nombre_strava or act.tipo_strava,
                data_metricas={
                    'distancia_km':   round(act.distancia_metros / 1000, 2) if act.distancia_metros else '',
                    'tiempo_minutos': round(duracion_min, 1),
                    'hr_media': act.hr_media, 'hr_maxima': act.hr_maxima,
                    'fuente': 'strava', 'strava_id': act.strava_id,
                },
            )
        act.estado = 'created'
        act.hyrox_session = sesion
        act.save()
        trimp_info = f' · TRIMP {trimp}' if trimp else (' · RPE {rpe}' if rpe else ' (sin FC ni RPE — ACWR sin carga)')
        return JsonResponse({'ok': True, 'msg': f'Nueva sesión Hyrox creada desde Strava{trimp_info}.'})

    # ── CREAR GYM (ActividadRealizada directa) ───────────────────────────────
    if accion == 'create_gym':
        _STRAVA_TO_TIPO = {
            'Run': 'carrera', 'Walk': 'otro', 'Hike': 'otro',
            'Ride': 'ciclismo', 'VirtualRide': 'ciclismo', 'EBikeRide': 'ciclismo',
            'Rowing': 'remo', 'WeightTraining': 'gym', 'Workout': 'gym',
            'Soccer': 'futbol', 'Football': 'futbol',
            'Swim': 'natacion', 'Yoga': 'yoga',
        }
        tipo_actividad = _STRAVA_TO_TIPO.get(act.tipo_strava, 'otro')
        rpe_manual = _rpe()
        # carga_ua: TRIMP (fisiológico, desde FC) si hay FC; sRPE si solo hay RPE manual
        trimp = _trimp_from_strava(act.hr_media, duracion_min)
        carga_ua = trimp or (round(rpe_manual * duracion_min, 1) if rpe_manual else None)
        ActividadRealizada.objects.create(
            cliente=cliente,
            tipo=tipo_actividad,
            titulo=act.nombre_strava or f'Strava — {act.tipo_strava}',
            fecha=act.fecha_actividad,
            duracion_minutos=int(duracion_min),
            rpe_medio=rpe_manual,
            carga_ua=carga_ua,
            distancia_metros=int(act.distancia_metros) if act.distancia_metros else None,
            hr_media=act.hr_media,
            hr_maxima=act.hr_maxima,
            fuente='strava',
        )
        act.estado = 'created'
        act.save()
        if trimp:
            acwr_info = f' · TRIMP {trimp} (FC {act.hr_media} bpm) — computará en ACWR'
        elif rpe_manual:
            acwr_info = f' · RPE {rpe_manual} — computará en ACWR'
        else:
            acwr_info = ' (sin FC ni RPE — no computará en ACWR)'
        return JsonResponse({'ok': True, 'msg': f'Actividad registrada{acwr_info}.'})

    return JsonResponse({'ok': False, 'msg': 'Acción no reconocida.'}, status=400)


@login_required
@require_POST
def strava_importar_recientes(request):
    """Fetch last 30 days of activities from Strava API and stage them as pending."""
    import requests as _req
    from datetime import date as _date, timedelta as _td

    cliente = request.user.cliente_perfil
    try:
        token = StravaToken.objects.get(cliente=cliente)
    except StravaToken.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': 'No hay cuenta de Strava conectada.'}, status=400)

    if token.is_expired():
        try:
            token = _strava_refresh_token(token)
        except Exception as e:
            return JsonResponse({'ok': False, 'msg': f'Error renovando token: {e}'}, status=400)

    after_ts = int((_date.today() - _td(days=30)).strftime('%s') if hasattr(_date.today(), 'strftime') else
                   (__import__('datetime').datetime.combine(_date.today() - _td(days=30), __import__('datetime').time.min)).timestamp())

    try:
        resp = _req.get(
            'https://www.strava.com/api/v3/athlete/activities',
            headers={'Authorization': f'Bearer {token.access_token}'},
            params={'after': after_ts, 'per_page': 50},
            timeout=15,
        )
        resp.raise_for_status()
        activities = resp.json()
    except Exception as e:
        return JsonResponse({'ok': False, 'msg': f'Error conectando con Strava: {e}'}, status=400)

    nuevas = 0
    for raw in activities:
        act_id = raw.get('id')
        if not act_id or StravaActivityRaw.objects.filter(strava_id=act_id).exists():
            continue
        fecha_str = raw.get('start_date_local', '')[:10]
        try:
            from datetime import date as _d2
            fecha = _d2.fromisoformat(fecha_str)
        except Exception:
            continue
        StravaActivityRaw.objects.create(
            cliente           = cliente,
            strava_id         = act_id,
            fecha_actividad   = fecha,
            tipo_strava       = raw.get('type', ''),
            nombre_strava     = raw.get('name', ''),
            duracion_segundos = raw.get('moving_time', 0),
            hr_media          = raw.get('average_heartrate') or None,
            hr_maxima         = raw.get('max_heartrate') or None,
            distancia_metros  = raw.get('distance') or None,
            raw_json          = raw,
        )
        nuevas += 1

    if nuevas:
        return JsonResponse({'ok': True, 'msg': f'{nuevas} actividad{"es" if nuevas != 1 else ""} importada{"s" if nuevas != 1 else ""}. Revísalas abajo.'})
    return JsonResponse({'ok': True, 'msg': 'No hay actividades nuevas en los últimos 30 días.'})


@login_required
def guia_tecnica(request):
    from .station_intelligence import HyroxStationIntelligence as SI
    orden = ['skierg', 'sled_push', 'sled_pull', 'burpees', 'rowing', 'farmers_carry', 'sandbag_lunges', 'wall_balls']
    estaciones = []
    for i, key in enumerate(orden, start=1):
        data = SI.STATIONS.get(key, {})
        estaciones.append({
            'num': f'{i:02d}',
            'key': key,
            'display_name': data.get('display_name', key),
            'icon': data.get('icon', 'fa-circle'),
            'description': data.get('description', ''),
            'technical_focus': data.get('technical_focus', []),
            'positions': data.get('positions', []),
            'common_mistakes': data.get('common_mistakes', []),
            'strategy': data.get('strategy', []),
            'rules': data.get('rules', []),
            'weights': data.get('weights', {}),
            'corrective_work': data.get('corrective_work', []),
            'completo': bool(data.get('description') and data.get('positions') and data.get('rules')),
        })
    return render(request, 'hyrox/guia_tecnica.html', {'estaciones': estaciones})
