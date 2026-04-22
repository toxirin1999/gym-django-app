import os
import json
import re
import google.generativeai as genai
from django.conf import settings

# Intentamos obtener la API key del settings, o del entorno
GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def calcular_rm_estimado(peso: float, reps: int) -> float:
    """
    Fórmula de Brzycki para estimar 1RM: peso × (1 + reps / 30).
    Fuente única para servicios y señales.
    """
    if peso <= 0 or reps <= 0:
        return 0.0
    return round(peso * (1 + reps / 30.0), 1)


class HyroxParserService:

    # Palabras clave para clasificar el tipo de actividad
    _KEYWORDS_HYROX = {
        'sled push', 'sled pull', 'trineo', 'empuje trineo', 'arrastre trineo',
        'wall ball', 'wall balls', 'skierg', 'ski erg', 'remo ergometro',
        'burpee broad jump', 'burpees broad', 'sandbag lunge', 'sandbag lunges',
        'farmers carry', 'farmer carry',
    }
    _KEYWORDS_CARRERA = {
        'carrera', 'correr', 'running', 'trote', 'sprint', 'run',
    }
    _KEYWORDS_CARDIO = {
        'bici', 'ciclismo', 'assault bike', 'remo', 'rowing', 'skierg',
        'ski erg', 'ergometro', 'eliptica',
    }
    _KEYWORDS_FUERZA = {
        'sentadilla', 'squat', 'peso muerto', 'deadlift', 'press', 'curl',
        'remo con', 'jalón', 'jalon', 'dominada', 'pull up', 'pull-up',
        'hip thrust', 'zancada', 'lunge', 'prensa', 'hack squat', 'rumano',
        'extensión', 'extension', 'flexión', 'flexion', 'plancha', 'plank',
    }

    @staticmethod
    def _classify_type(nombre: str) -> str:
        n = nombre.lower()
        for kw in HyroxParserService._KEYWORDS_HYROX:
            if kw in n:
                return 'hyrox_station'
        for kw in HyroxParserService._KEYWORDS_CARRERA:
            if kw in n:
                return 'carrera'
        for kw in HyroxParserService._KEYWORDS_CARDIO:
            if kw in n:
                return 'ergometro'
        return 'fuerza'

    @staticmethod
    def _calcular_cumplimiento_actividad(real: dict, plan: dict, tipo: str) -> float | None:
        """
        Devuelve un ratio 0-1 comparando métricas reales vs. planificadas.
        Retorna None si no hay datos planificados comparables.
        """
        if not plan:
            return None
        # Carrera: ratio distancia real / planificada
        if tipo in ('carrera', 'cardio_sustituto') and 'distancia_km' in plan:
            plan_km = float(plan['distancia_km'] or 0)
            real_km = float(real.get('distancia_km') or 0)
            return min(real_km / plan_km, 1.0) if plan_km > 0 else None
        # Estación: ratio distancia en metros
        if tipo == 'hyrox_station' and 'distancia_m' in plan:
            plan_m = float(plan['distancia_m'] or 0)
            real_m = float(real.get('distancia_m') or 0)
            return min(real_m / plan_m, 1.0) if plan_m > 0 else None
        # Fuerza: ratio de volumen total (series × reps × peso)
        if 'series' in plan and 'series' in real:
            def volumen(series):
                return sum(
                    float(s.get('reps', 0)) * max(float(s.get('peso_kg', s.get('peso', 1))), 1)
                    for s in series if s.get('reps')
                )
            plan_vol = volumen(plan['series'])
            real_vol = volumen(real['series'])
            return min(real_vol / plan_vol, 1.0) if plan_vol > 0 else None
        # Solo reps (sin peso, e.g. Wall Balls)
        if 'series' in plan and 'series' in real:
            plan_reps = sum(int(s.get('reps', 0)) for s in plan['series'])
            real_reps = sum(int(s.get('reps', 0)) for s in real['series'])
            return min(real_reps / plan_reps, 1.0) if plan_reps > 0 else None
        return None

    @staticmethod
    def _estimate_fatigue(actividades: list, rpe: float | None) -> str:
        n = len(actividades)
        if rpe and rpe >= 8:
            return 'Alta'
        if rpe and rpe >= 6:
            return 'Media'
        return 'Alta' if n >= 5 else 'Media' if n >= 3 else 'Baja'

    @staticmethod
    def parse_workout_text(raw_text, sustituir_material=False):
        """
        Parser local (sin IA) que convierte texto libre en JSON estructurado.
        Reconoce patrones comunes: 4x8@80kg, 5km, 50m@100kg, series de N reps, etc.
        Devuelve el mismo formato que save_parsed_session espera.
        """
        actividades = []

        # Patrones de extracción
        # Series×Reps con peso: 4x8@80kg · 4x8 @80 · 4 series 8 reps 80kg
        re_series_reps_peso = re.compile(
            r'(\d+)\s*[x×]\s*(\d+)\s*(?:reps?)?\s*(?:[@a]|con|@|a\s)?\s*(\d+(?:[.,]\d+)?)\s*kg',
            re.IGNORECASE
        )
        # Series×Reps sin peso: 4x8 · 3x15
        re_series_reps = re.compile(r'(\d+)\s*[x×]\s*(\d+)\s*(?:reps?)?', re.IGNORECASE)
        # Distancia en km: 5km · 5 km
        re_dist_km = re.compile(r'(\d+(?:[.,]\d+)?)\s*km', re.IGNORECASE)
        # Distancia en metros: 50m · 1000m
        re_dist_m = re.compile(r'(\d+(?:[.,]\d+)?)\s*m\b', re.IGNORECASE)
        # Tiempo en segundos o minutos: 30s · 2min · 2:30
        re_tiempo = re.compile(r'(\d+)\s*(?:s(?:eg(?:undos?)?)?|min(?:utos?)?)', re.IGNORECASE)
        # Peso suelto: @ 80kg · con 80kg
        re_peso_suelto = re.compile(r'(?:[@a]|con)\s*(\d+(?:[.,]\d+)?)\s*kg', re.IGNORECASE)
        # Ritmo de carrera: "ritmo 4:30" · "4:30/km" · "a 5:00" · "pace 4:45"
        re_ritmo = re.compile(
            r'(?:ritmo|pace|a)\s+(\d{1,2}):(\d{2})\s*(?:/km)?|(\d{1,2}):(\d{2})\s*/km',
            re.IGNORECASE
        )
        # N series de N reps
        re_series_de_reps = re.compile(
            r'(\d+)\s*series?\s+(?:de\s+)?(\d+)\s*(?:reps?|repeticiones?)',
            re.IGNORECASE
        )
        # Reps@kg individual: "4@18kg, 4@18kg" (formato generado por el formulario)
        re_reps_at_kg = re.compile(r'(\d+)\s*@\s*(\d+(?:[.,]\d+)?)\s*kg', re.IGNORECASE)
        # Reps simples: "15 reps, 15 reps" (formulario sin peso)
        re_reps_simple = re.compile(r'(\d+)\s*reps?', re.IGNORECASE)
        # Tiempo en minutos (específico): "8min" → float
        re_tiempo_min = re.compile(r'(\d+(?:[.,]\d+)?)\s*min', re.IGNORECASE)

        for raw_line in raw_text.splitlines():
            line = raw_line.strip().lstrip('-•·*').strip()
            if not line or len(line) < 3:
                continue
            # Ignorar líneas que son solo metadatos (RPE, FC, etc.)
            if re.match(r'^(?:rpe|fc|hr|rpm|tiempo total|duraci[oó]n)\b', line, re.IGNORECASE):
                continue

            # Extraer nombre: todo antes del primer número de métricas
            # Incluye decimales (1.8km, 5.0km) en el split
            nombre_match = re.split(
                r'\s+(?=\d+(?:[.,]\d+)?\s*[x×km]|\d+(?:[.,]\d+)?\s*(?:series?|reps?|kg|min|seg))',
                line, maxsplit=1
            )
            nombre = nombre_match[0].strip(' :')
            resto = nombre_match[1] if len(nombre_match) > 1 else line[len(nombre):]
            if not nombre or len(nombre) < 2:
                continue

            tipo = HyroxParserService._classify_type(nombre)
            series_data = []
            carrera_data = {}

            # 1. Intentar extraer series×reps con peso
            m = re_series_reps_peso.search(resto or line)
            if m:
                n_series = int(m.group(1))
                reps = int(m.group(2))
                peso = float(m.group(3).replace(',', '.'))
                series_data = [{'reps': reps, 'peso': peso} for _ in range(n_series)]

            # 1b. Reps@kg individuales: "4@18kg, 4@18kg, 4@18kg" (formato del formulario)
            elif re_reps_at_kg.search(resto or line):
                matches = re_reps_at_kg.findall(resto or line)
                series_data = [{'reps': int(r), 'peso': float(k.replace(',', '.'))} for r, k in matches]
                # Limpiar nombre si las series quedaron embebidas (e.g. "Ejercicio: 4@18kg, ...")
                clean_nombre = re.sub(r'\s*:?\s*\d+@\d+.*$', '', nombre).strip(' :')
                if clean_nombre and len(clean_nombre) >= 2:
                    nombre = clean_nombre

            # 2. "N series de N reps"
            elif re_series_de_reps.search(resto or line):
                m2 = re_series_de_reps.search(resto or line)
                n_series = int(m2.group(1))
                reps = int(m2.group(2))
                peso_m = re_peso_suelto.search(resto or line)
                peso = float(peso_m.group(1).replace(',', '.')) if peso_m else 0
                series_data = [{'reps': reps, 'peso': peso} if peso else {'reps': reps} for _ in range(n_series)]

            # 3. Series×Reps sin peso
            elif re_series_reps.search(resto or line):
                m3 = re_series_reps.search(resto or line)
                n_series = int(m3.group(1))
                reps = int(m3.group(2))
                peso_m = re_peso_suelto.search(resto or line)
                peso = float(peso_m.group(1).replace(',', '.')) if peso_m else 0
                series_data = [{'reps': reps, 'peso': peso} if peso else {'reps': reps} for _ in range(n_series)]

            # 3b. Reps simples separadas por coma: "15 reps, 15 reps" (formulario sin peso)
            # También captura un único "100 reps @4kg" (Wall Balls desde el formulario)
            elif re_reps_simple.search(resto or line):
                counts = re_reps_simple.findall(resto or line) or re_reps_simple.findall(line)
                peso_m = re_peso_suelto.search(resto or line)
                peso = float(peso_m.group(1).replace(',', '.')) if peso_m else 0
                series_data = [{'reps': int(r), 'peso': peso} if peso else {'reps': int(r)} for r in counts]

            # 4. Distancia en km (carrera) — busca en línea completa para capturar "Carrera 1.8km · 8min"
            elif re_dist_km.search(line):
                m4 = re_dist_km.search(line)
                dist = float(m4.group(1).replace(',', '.'))
                carrera_data = {'distancia_km': dist}
                if tipo not in ('carrera', 'ergometro', 'hyrox_station'):
                    tipo = 'carrera'
                # Extraer tiempo en minutos
                mt = re_tiempo_min.search(line)
                if mt:
                    carrera_data['tiempo_minutos'] = float(mt.group(1).replace(',', '.'))
                # Extraer ritmo real si está en la línea: "ritmo 4:30" o "4:30/km"
                mr = re_ritmo.search(line)
                if mr:
                    mins = int(mr.group(1) or mr.group(3))
                    secs = int(mr.group(2) or mr.group(4))
                    carrera_data['ritmo_real'] = f"{mins}:{secs:02d}/km"

            # 5. Distancia en metros (estaciones)
            elif re_dist_m.search(line):
                m5 = re_dist_m.search(line)
                dist_m = float(m5.group(1).replace(',', '.'))
                peso_m = re_peso_suelto.search(line)
                peso = float(peso_m.group(1).replace(',', '.')) if peso_m else 0
                carrera_data = {'distancia_m': int(dist_m)}
                if peso:
                    carrera_data['peso_kg'] = peso

            # 6. Solo tiempo
            elif re_tiempo.search(line):
                m6 = re_tiempo.search(line)
                valor = int(m6.group(1))
                unidad = m6.group(0)
                seg = valor * 60 if 'min' in unidad.lower() else valor
                series_data = [{'tiempo_sec': seg}]

            # 7. Sin métricas: guardar el nombre al menos
            else:
                series_data = []

            act = {
                'tipo_actividad': tipo,
                'nombre_ejercicio': nombre,
            }
            if series_data:
                act['series_data'] = series_data
            if carrera_data:
                act['carrera_data'] = carrera_data

            actividades.append(act)

        fatigue = HyroxParserService._estimate_fatigue(actividades, None)
        return {
            'ai_evaluation_score': None,
            'muscle_fatigue_index': fatigue,
            'feedback': None,
            'actividades': actividades,
        } if actividades else None

    @staticmethod
    def save_parsed_session(session, parsed_data):
        """
        Recibe el JSON desde `parse_workout_text` y crea los objetos HyroxActivity,
        además de guardar el feedback generado.
        """
        from hyrox.models import HyroxActivity
        
        if not parsed_data:
            return False
            
        if isinstance(parsed_data, list):
            # Fallback en caso de que Gemini se equivoque y devuelva solo la lista
            actividades_list = parsed_data
            feedback_text = None
            ai_score = None
            fatigue_idx = None
        else:
            actividades_list = parsed_data.get("actividades", parsed_data.get("Actividades", []))
            feedback_text = parsed_data.get("feedback", parsed_data.get("Feedback", None))
            ai_score = parsed_data.get("ai_evaluation_score", None)
            fatigue_idx = parsed_data.get("muscle_fatigue_index", None)
            
        # Almacenamos el feedback y métricas de Fase 8 en la sesión
        session_updated = False
        if feedback_text:
            # feedback_ia no existe en el modelo; se descarta (campo eliminado)
            session_updated = True
        if ai_score is not None:
            session.ai_evaluation_score = ai_score
            session_updated = True
        if fatigue_idx:
            session.muscle_fatigue_index = fatigue_idx
            session_updated = True
            
        if not actividades_list:
            # Si no hay actividades pero sí hay feedback, al menos lo guardamos
            if session_updated:
                session.parsed_by_ia = True
                session.save()
            return {'activities': [], 'new_records': []}
            
        # ── SNAPSHOT DEL PLAN ──────────────────────────────────────────────────
        # Guardar lo planificado ANTES de borrar, agrupado por tipo_actividad+índice
        # para poder calcular el cumplimiento real vs. plan.
        ritmo_planificado_seg = None
        plan_snapshot = {}  # {(tipo_actividad, idx): data_metricas_planificado}
        tipo_counters = {}
        for act_plan in HyroxActivity.objects.filter(sesion=session).order_by('id'):
            ta = act_plan.tipo_actividad
            idx = tipo_counters.get(ta, 0)
            tipo_counters[ta] = idx + 1
            m = act_plan.data_metricas or {}
            plan_snapshot[(ta, idx)] = m
            # Extraer ritmo objetivo de carrera para la comparativa de pace
            if ta == 'carrera' and not ritmo_planificado_seg:
                ro = m.get('ritmo_objetivo')
                if ro:
                    try:
                        p = ro.replace('/km', '').strip().split(':')
                        ritmo_planificado_seg = int(p[0]) * 60 + int(p[1])
                    except Exception:
                        pass

        # Borrar actividades previas (planificadas) antes de insertar las reales registradas
        HyroxActivity.objects.filter(sesion=session).delete()

        activities_created = []
        new_records = []
        cumplimiento_scores = []  # list de ratios (0-1) por actividad comparable

        # Recuperar el objetivo para actualizar RM
        objetivo = session.objective
        real_tipo_counters = {}

        for item in actividades_list:
            tipo = item.get("tipo_actividad", item.get("tipo", "otro"))
            nombre = item.get("nombre_ejercicio", item.get("nombre", item.get("ejercicio", "Desconocido")))

            data_metricas = {}
            if "is_equivalencia" in item and item["is_equivalencia"]:
                data_metricas["is_equivalencia"] = True

            series_data = []
            if "series_data" in item:
                data_metricas["series"] = item["series_data"]
                series_data = item["series_data"]

            if "carrera_data" in item:
                data_metricas.update(item["carrera_data"])

            # ── Recuperar plan para esta actividad ──────────────────────────
            real_idx = real_tipo_counters.get(tipo, 0)
            real_tipo_counters[tipo] = real_idx + 1
            plan_m = plan_snapshot.get((tipo, real_idx), {})

            # Calcular ratio de cumplimiento individual
            ratio = HyroxParserService._calcular_cumplimiento_actividad(data_metricas, plan_m, tipo)
            if ratio is not None:
                cumplimiento_scores.append(ratio)

            activity = HyroxActivity.objects.create(
                sesion=session,
                tipo_actividad=tipo,
                nombre_ejercicio=nombre,
                data_metricas=data_metricas,
                data_planificado=plan_m if plan_m else None,
            )
            activities_created.append(activity)

            # --- Comparación ritmo real vs planificado (carrera) ---
            if tipo == 'carrera' and ritmo_planificado_seg:
                ritmo_real_str = (item.get('carrera_data') or {}).get('ritmo_real')
                if ritmo_real_str:
                    try:
                        p = ritmo_real_str.replace('/km', '').strip().split(':')
                        ritmo_real_seg = int(p[0]) * 60 + int(p[1])
                        diferencia_seg = ritmo_planificado_seg - ritmo_real_seg
                        # El usuario fue MÁS rápido que lo planificado
                        if diferencia_seg > 15:
                            zona_real = 'Tempo/Umbral' if diferencia_seg > 45 else 'Z3'
                            plan_mins, plan_secs = divmod(ritmo_planificado_seg, 60)
                            ritmo_plan_str = f"{plan_mins}:{plan_secs:02d}/km"
                            activity.data_metricas['alerta_ritmo'] = (
                                f"⚡ Fuiste {diferencia_seg}s/km más rápido que el ritmo Z2 planificado "
                                f"({ritmo_real_str} real vs {ritmo_plan_str} objetivo). "
                                f"Zona real: {zona_real}. Esto suma fatiga neurológica y muscular adicional. "
                                f"El sistema ha ajustado la carga de tu próxima sesión."
                            )
                            activity.save()
                            # Inyectar fatiga extra en la próxima sesión planificada
                            from .models import HyroxSession
                            prox = HyroxSession.objects.filter(
                                objective=session.objective,
                                estado='planificado',
                                fecha__gt=session.fecha
                            ).order_by('fecha').first()
                            if prox and prox.muscle_fatigue_index != 'Alta':
                                prox.muscle_fatigue_index = 'Media' if diferencia_seg < 45 else 'Alta'
                                from django.utils import timezone
                                prox.fatiga_updated_at = timezone.now()
                                prox.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])
                    except Exception:
                        pass

            # --- Sincronización Automática de PBs ---
            if tipo == 'fuerza' and (objetivo and isinstance(series_data, list)):
                rm_estimado_max = 0
                for serie in series_data:
                    try:
                        peso = float(serie.get("peso", 0))
                        reps = int(serie.get("reps", 0))
                        if peso > 0 and reps > 0:
                            rm_serie = calcular_rm_estimado(peso, reps)
                            if rm_serie > rm_estimado_max:
                                rm_estimado_max = round(rm_serie, 1)
                    except (ValueError, TypeError):
                        pass
                
                if rm_estimado_max > 0:
                    nombre_lower = nombre.lower()
                    
                    # Chequear Sentadilla
                    if "sentadilla" in nombre_lower or "squat" in nombre_lower:
                        rm_actual = float(objetivo.rm_sentadilla or 0)
                        if rm_estimado_max > rm_actual:
                            objetivo.rm_sentadilla = rm_estimado_max
                            objetivo.save()
                            new_records.append({"ejercicio": "Sentadilla", "old": rm_actual, "new": rm_estimado_max})
                            
                    # Chequear Peso Muerto
                    elif "peso muerto" in nombre_lower or "deadlift" in nombre_lower:
                        rm_actual = float(objetivo.rm_peso_muerto or 0)
                        if rm_estimado_max > rm_actual:
                            objetivo.rm_peso_muerto = rm_estimado_max
                            objetivo.save()
                            new_records.append({"ejercicio": "Peso Muerto", "old": rm_actual, "new": rm_estimado_max})
            
        # ── Guardar cumplimiento en la sesión ──────────────────────────────
        session.parsed_by_ia = True
        if cumplimiento_scores:
            session.cumplimiento_ratio = round(sum(cumplimiento_scores) / len(cumplimiento_scores), 3)
        session.save()
        return {'activities': activities_created, 'new_records': new_records}

class HyroxCoachService:
    @staticmethod
    def _obtener_contexto_atleta(user_id):
        from .models import HyroxObjective
        
        try:
            # Asumimos que el usuario tiene un objetivo activo
            objetivo = HyroxObjective.objects.filter(cliente__user_id=user_id, estado='activo').first()
            if not objetivo:
                return None
                
            contexto = {
                "user_id": user_id,
                "nombre": objetivo.cliente.nombre,
                "rm_sentadilla": objetivo.rm_sentadilla or "No registrado",
                "rm_pm": objetivo.rm_peso_muerto or "No registrado",
                "categoria": objetivo.get_categoria_display(),
                "fecha_evento": objetivo.fecha_evento,
                "lesiones": objetivo.lesiones_previas or "Ninguna",
                "nivel": objetivo.get_nivel_experiencia_display(),
                "readiness_score": objetivo.get_race_readiness_score(),
            }
            
            # Phase X: Añadir logros recientes de fuerza
            try:
                progress_data = CompetitionStandardsService.get_user_standards_progress(user_id)
                if progress_data and progress_data.get('logros'):
                    contexto["logros_estandar"] = progress_data['logros']
            except Exception as e:
                print(f"Error cargando logros de competición: {e}")
                
            return contexto
        except Exception as e:
            print(f"Error obteniendo contexto del atleta: {e}")
            return None

    @staticmethod
    def _clasificar_intencion(texto_usuario, contexto, history=None):
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY no está configurada")
             
        system_prompt = f"""
Eres clasificador de intenciones para un sistema de entrenamiento HYROX.

Contexto del usuario:
Nombre: {contexto.get('nombre', 'Atleta')}
Intención: Clasifica el mensaje del usuario en una de estas dos categorías:
1. "registro": Si el usuario está proporcionando datos de un entrenamiento (series, repeticiones, tiempos, distancias, pesos).
2. "charla": Si el usuario está comentando sensaciones, dolores, fatiga, dudas o motivación, sin datos claros de entrenamiento para registrar.

Responde ÚNICAMENTE con un JSON válido:
{{
    "intencion": "registro" o "charla",
    "razon": "Breve justificación de por qué"
}}
"""
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        try:
            response = model.generate_content(texto_usuario)
            response_text = response.text.strip()
            
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx+1]
                data = json.loads(json_str)
                return data.get("intencion", "registro") # Por defecto registro si hay dudas
            return "registro"
        except Exception as e:
            print(f"Error en clasificación de intención: {e}")
            return "registro"

    @staticmethod
    def _generar_respuesta_charla(texto_usuario, contexto, history=None):
        from .models import HyroxObjective
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY no está configurada")

        # ── Análisis de tendencia RPE vs cargas ──────────────────────────────
        tendencia_nota = ""
        try:
            objetivo = HyroxObjective.objects.filter(
                cliente__user_id=contexto.get('user_id'), estado='activo'
            ).first()
            if objetivo:
                sesiones_recientes = list(
                    objetivo.sessions.filter(estado='completado')
                    .exclude(rpe_global__isnull=True)
                    .order_by('fecha')
                    .values('rpe_global', 'fecha', 'ai_evaluation_score')
                )[-8:]  # Últimas 8 sesiones con RPE

                if len(sesiones_recientes) >= 3:
                    # Tendencia RPE: promedio primera mitad vs segunda mitad
                    mid = len(sesiones_recientes) // 2
                    rpe_inicial = sum(s['rpe_global'] for s in sesiones_recientes[:mid]) / mid
                    rpe_reciente = sum(s['rpe_global'] for s in sesiones_recientes[mid:]) / (len(sesiones_recientes) - mid)
                    # Tendencia cargas: ai_score (proxy de intensidad)
                    scores = [s['ai_evaluation_score'] for s in sesiones_recientes if s['ai_evaluation_score']]
                    cargas_subiendo = (scores[-1] > scores[0]) if len(scores) >= 2 else False
                    rpe_bajando = rpe_reciente < rpe_inicial - 0.3

                    if rpe_bajando and cargas_subiendo:
                        tendencia_nota = (
                            "\n\n⚠️ INSTRUCCIÓN ESPECIAL (solo si el usuario pregunta por su estado o progreso): "
                            "Di EXACTAMENTE esto (puedes adaptarlo levemente): "
                            f"'{contexto.get('nombre', 'David')}, tu condición física está madurando. "
                            "Estás moviendo pesos de competición con un coste energético menor. "
                            "Tu base para el 19 de abril es cada vez más sólida.' "
                            f"(RPE ha bajado de {rpe_inicial:.1f} a {rpe_reciente:.1f} en las últimas sesiones "
                            "mientras las cargas aumentan)"
                        )
        except Exception:
            pass

        system_prompt = f"""
Eres un entrenador de vanguardia de HYROX. Empático pero disciplinado.

Contexto de tu atleta actual ({contexto.get('nombre', 'Atleta')}):
- RM Sentadilla: {contexto.get('rm_sentadilla')} kg
- RM Peso Muerto: {contexto.get('rm_pm')} kg
- Nivel: {contexto.get('nivel')}
- Lesiones conocidas: {contexto.get('lesiones')}
- Objetivo: {contexto.get('categoria')} el {contexto.get('fecha_evento')}
- Estándares de Fuerza Completados (Al menos 100%): {', '.join(contexto.get('logros_estandar', [])) if contexto.get('logros_estandar') else 'Ninguno todavía'}
- Race Readiness: {contexto.get('readiness_score', '?')}% (40% Técnica / 30% Eficiencia RPE / 30% Simulacros)
{tendencia_nota}

El usuario NO te está registrando un entreno ahora mismo, te está hablando sobre sus sensaciones, fatiga o motivación.
RESPONDE DIRECTAMENTE AL USUARIO. Sé conciso, no te enrolles. Usa un tono motivador y estratégico. Si menciona dolor/lesión, recuérdale la importancia de la recuperación.
Si el usuario ha completado algún estándar recientemente o lo ves en la lista de Estándares Completados, fíjate si no lo habías felicitado y haz una breve mención tipo "Un pilar de la reconstrucción completado".
"""
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        
        try:
            response = model.generate_content(texto_usuario)
            return response.text.strip()
        except Exception as e:
            print(f"Error generando respuesta de charla: {e}")
            return "Parece que hay un problema con la IA ahora mismo. Descansa y vuelve más tarde."


    @staticmethod
    def procesar_mensaje(user_id, texto_usuario, session=None, history=None):
        """
        Punto de entrada principal. 
        1. Obtiene contexto.
        2. Clasifica intención.
        3. Deriva a HyroxParserService (si es registro) o genera respuesta de chat (si es charla).
        """
        contexto = HyroxCoachService._obtener_contexto_atleta(user_id)
        if not contexto:
            return {
                "tipo": "error",
                "mensaje": "No tienes un objetivo Hyrox activo configurado. Por favor, crea uno primero."
            }

        # Detección rápida por keywords — no gasta cuota de Gemini
        texto_lower = texto_usuario.lower()
        SIMULACION_KEYWORDS = ('simulaci', 'simula', 'tiempo estimado', 'cuánto tardaría',
                               'cuanto tardaria', 'race time', 'predice mi', 'predice tiempo')
        if any(kw in texto_lower for kw in SIMULACION_KEYWORDS):
            sim = HyroxRaceSimulator.simular(user_id)
            if 'error' in sim:
                return {"tipo": "charla", "mensaje": sim['error']}
            return {
                "tipo": "charla",
                "mensaje": sim['mensaje_coach'],
                "simulacion": sim,
            }

        intencion = HyroxCoachService._clasificar_intencion(texto_usuario, contexto, history)
        
        if intencion == "charla" or (session is None):
            # Es charla, o intentó registrar pero no pasó una sesión (ej: desde un chat global en la app)
            respuesta = HyroxCoachService._generar_respuesta_charla(texto_usuario, contexto, history)
            return {
                "tipo": "charla",
                "mensaje": respuesta
            }
        else:
            # Es registro. Derivamos al Parser original.
            parsed_data = HyroxParserService.parse_workout_text(texto_usuario)
            if not parsed_data:
                return {
                    "tipo": "error",
                    "mensaje": "Lamentablemente no he podido extraer las métricas de tu sesión. ¿Podrías escribirlo más claro?"
                }
                
            resultados_save = HyroxParserService.save_parsed_session(session, parsed_data)
            
            # Cargar feedback original
            mensaje_feedback = parsed_data.get("feedback", "Entrenamiento registrado correctamente.")
            
            # Phase Y: Inyectar celebración de PBs y mejora RM
            new_records = resultados_save.get('new_records', []) if isinstance(resultados_save, dict) else []
            if new_records:
                for record in new_records:
                    ejercicio = record['ejercicio']
                    old = record['old']
                    new = record['new']
                    if old == 0:
                        promedio_str = f"Has establecido tu RM inicial estimado de {ejercicio} en {new}kg. ¡Primer paso en la reconstrucción!"
                    else:
                        mejora = round(((new - old) / old) * 100, 1)
                        promedio_str = f"Tu RM estimado de {ejercicio} ha subido de {old}kg a {new}kg. ¡Estás un {mejora}% más fuerte en este pilar!"
                    
                    mensaje_feedback += f"\n\n🔥 ¡Nuevo Récord Personal! {promedio_str}"

            # Phase Z: Notas de equivalencias → estándares HYROX
            activities_created = resultados_save.get('activities', []) if isinstance(resultados_save, dict) else []
            if activities_created:
                try:
                    notas_equiv = CompetitionStandardsService.detectar_notas_equivalencias_sesion(
                        activities_created, user_id=session.objective.cliente.user_id
                    )
                    for nota in notas_equiv:
                        mensaje_feedback += f"\n\n{nota}"
                except Exception:
                    pass  # No bloquear el flujo por notas de equivalencias

            return {
                "tipo": "registro",
                "mensaje": mensaje_feedback,
                "datos_brutos": parsed_data,
                "new_records": new_records
            }


    @staticmethod
    def get_proactive_greeting(user_id):
        from django.utils import timezone
        from .models import HyroxSession
        from django.core.cache import cache
        
        # Generar clave de caché única por usuario y día
        hoy = timezone.now().date()
        cache_key = f'proactive_greeting_{user_id}_{hoy}'
        
        # Verificar si ya existe un saludo en caché
        cached_greeting = cache.get(cache_key)
        if cached_greeting:
            return cached_greeting
            
        contexto = HyroxCoachService._obtener_contexto_atleta(user_id)
        if not contexto:
            return "¡Hola! Veo que no tienes un objetivo activo. ¿Nos ponemos a ello?"
            
        # Buscar sesión de hoy
        sesion_hoy = HyroxSession.objects.filter(
            objective__cliente__user_id=user_id,
            objective__estado='activo',
            fecha=hoy,
            estado='planificado'
        ).first()
        
        texto_sesion = f"Hoy toca: {sesion_hoy.titulo}." if sesion_hoy else "Hoy no hay sesión planificada, día de descanso activo o movilidad."
        
        # Buscar última fatiga
        ultima_sesion = HyroxSession.objects.filter(
            objective__cliente__user_id=user_id,
            objective__estado='activo',
            estado='completado'
        ).order_by('-fecha').first()
        
        fatiga_reciente = ultima_sesion.muscle_fatigue_index if ultima_sesion else "Desconocida"

        # --- Fatigue Decay Engine (variable por tipo de sesión) ---
        # Los tiempos de recuperación no son iguales para todos los estímulos:
        #   Simulacro (fuerza + carrera juntas): 72h → Baja, 48h → Media
        #   Fuerza pesada o estaciones Hyrox:   48h → Baja, 24h → Media
        #   Cardio Z2 / carrera ligera:          24h → Baja, 12h → Media
        if sesion_hoy and sesion_hoy.muscle_fatigue_index == 'Alta' and sesion_hoy.fatiga_updated_at:
            horas_pasadas = (timezone.now() - sesion_hoy.fatiga_updated_at).total_seconds() / 3600.0
            titulo_lower = (sesion_hoy.titulo or '').lower()
            tipos_act = set(sesion_hoy.activities.values_list('tipo_actividad', flat=True))
            es_simulacro = bool(tipos_act & {'fuerza', 'hyrox_station'}) and bool(tipos_act & {'carrera', 'cardio_sustituto'})
            es_cardio_puro = tipos_act <= {'carrera', 'cardio_sustituto', 'bici', 'remo', 'skierg'}

            if es_simulacro:
                umbral_baja, umbral_media = 72, 48
            elif es_cardio_puro:
                umbral_baja, umbral_media = 24, 12
            else:
                umbral_baja, umbral_media = 48, 24  # fuerza o estaciones

            if horas_pasadas > umbral_baja:
                sesion_hoy.muscle_fatigue_index = 'Baja'
                sesion_hoy.save(update_fields=['muscle_fatigue_index'])
            elif horas_pasadas > umbral_media:
                sesion_hoy.muscle_fatigue_index = 'Media'
                sesion_hoy.save(update_fields=['muscle_fatigue_index'])

        # --- Integración de Macrociclo y Penalización por inactividad ---
        from .models import HyroxObjective
        objetivo_activo = HyroxObjective.objects.filter(cliente__user_id=user_id, estado='activo').first()
        macro_data = HyroxMacrocycleEngine.get_current_phase(objetivo_activo, return_metadata=True)
        fase = macro_data.get('fase', 'Fase de Base')
        semanas = macro_data.get('semanas_restantes', 12)
        pct_progreso = macro_data.get('pct_progreso', 0)
        
        # Lenguaje espacial para el Coach
        lenguaje_posicional = f"Estamos al {pct_progreso}% de la preparación total. Te encuentras en {fase}."
        if pct_progreso > 40 and pct_progreso < 60:
            lenguaje_posicional = f"Estamos cruzando el ecuador de la {fase}."
        elif pct_progreso >= 90:
            lenguaje_posicional = f"Estamos en la recta final, entrando en el Tapering absoluto."

        inactivo_run, dias_run, tiene_credito_futbol, preguntar_bool = HyroxMacrocycleEngine.detect_running_inactivity(user_id)
        
        alerta_inactividad = ""
        if preguntar_bool:
            alerta_inactividad = "\n⚠️ INSTRUCCIÓN CRÍTICA: El atleta no tiene registros de carrera recientes. Pregúntale amigablemente: 'David, no veo carreras registradas últimamente, ¿has estado activo con el fútbol o alguna otra actividad aeróbica?'."
        elif inactivo_run and not tiene_credito_futbol:
            alerta_inactividad = f"\n⚠️ ALERTA DE INACTIVIDAD AERÓBICA: Lleva {dias_run} días sin correr ni compensar con fútbol. DEBES dedicar tu mensaje a recordarle estrictamente que el motor aeróbico es crítico para el 19 de Abril."
        elif inactivo_run and tiene_credito_futbol:
            alerta_inactividad = f"\n⚠️ ALERTA MITIGADA: Lleva {dias_run} días sin correr, pero el FÚTBOL está manteniendo su base aeróbica. Recuérdale que el fútbol ayuda, pero pronto hay que volver a correr."
            
        alerta_gym = ""
        if sesion_hoy and sesion_hoy.muscle_fatigue_index and sesion_hoy.fatiga_updated_at:
            horas_recuperacion = int((timezone.now() - sesion_hoy.fatiga_updated_at).total_seconds() / 3600.0)
            if sesion_hoy.muscle_fatigue_index == 'Alta':
                alerta_gym = f"\n⚠️ ALERTA DE FATIGA RECIENTE (hace {horas_recuperacion}h): La fatiga sigue ALTA. Prioriza técnica y descanso, nada de Sled o sentadillas pesadas hoy."
            elif sesion_hoy.muscle_fatigue_index == 'Media':
                alerta_gym = f"\n⚠️ ALERTA FATIGA DECAY (hace {horas_recuperacion}h): Fatiga bajando a MODERADA. Puedes subir algo la intensidad sin llegar al límite."
            elif sesion_hoy.muscle_fatigue_index == 'Baja':
                alerta_gym = f"\n⚠️ RECUPERACIÓN COMPLETADA (hace {horas_recuperacion}h): Fatiga asimilada. Puedes rendir al máximo hoy."

        # --- Módulo de Lesión y Pain Score ---
        from .models import UserInjury, DailyRecoveryEntry
        lesion_activa = UserInjury.objects.filter(cliente__user_id=user_id, activa=True).first()
        alerta_lesion = ""
        
        if lesion_activa:
            # Normalizar slug a nombre amigable
            nombres_zonas = {
                'rodilla': 'rodilla', 'gemelo': 'gemelo', 'tobillo': 'tobillo',
                'isquiotibial': 'isquiotibial', 'cuadriceps': 'cuádriceps', 'cadera': 'cadera',
                'pie': 'pie', 'hombro': 'hombro', 'codo': 'codo', 'muneca': 'muñeca',
                'pectoral': 'pectoral', 'dorsal': 'dorsal', 'lumbar': 'espalda baja',
                'cervical': 'zona cervical', 'abdomen': 'core'
            }
            zona_normalizada = nombres_zonas.get(lesion_activa.zona_afectada.lower(), lesion_activa.zona_afectada)
            
            ultimo_reporte = DailyRecoveryEntry.objects.filter(lesion=lesion_activa, fecha=hoy).first()
            if not ultimo_reporte:
                ultimo_reporte = DailyRecoveryEntry.objects.filter(lesion=lesion_activa).order_by('-fecha').first()
                
            if ultimo_reporte:
                fase_med = lesion_activa.fase
                dolor = ultimo_reporte.dolor_movimiento
                if dolor > 5:
                    alerta_lesion = f"\n🚨 ALERTA MÉDICA (Fase {fase_med}): Veo que tu {zona_normalizada} sigue con MUCHO DOLOR ({dolor}/10). El sistema ha bloqueado ejercicios de impacto. Tu prioridad HOY es la recuperación activa y la movilidad. NO fuerces."
                elif dolor > 3:
                    alerta_lesion = f"\n⚠️ PRECAUCIÓN (Fase {fase_med}): Veo que tu {zona_normalizada} sigue en fase de recuperación con molestias ({dolor}/10). Vamos a por un entreno adaptado. Escucha a tu cuerpo en cada serie."
                else:
                    alerta_lesion = f"\n✅ PROGRESO CLÍNICO (Fase {fase_med}): Dolor muy bajo ({dolor}/10) en tu {zona_normalizada}. Vas por muy buen camino. Sigue las sesiones adaptadas hasta completar la fase de retorno."
            else:
                alerta_lesion = f"\n⚠️ SEGUIMIENTO MÉDICO: Veo que tu {zona_normalizada} sigue en fase de recuperación. Recuerda registrar tu nivel de dolor de hoy para que el sistema adapte o libere el entrenamiento."
        
        # Phase 13: Transition Alert
        if not alerta_lesion:
            from core.bio_context import BioContextProvider
            readiness = BioContextProvider.get_readiness_score(objetivo_activo.cliente)
            if readiness.get('is_in_transition'):
                alerta_lesion = "\n✅ FASE DE TRANSICIÓN: Usa EXACTAMENTE esta frase en tu saludo: '✅ Test superado, David. Has vuelto a la carga máxima, pero durante esta primera semana limitaremos tu volumen al 85% como medida de precaución biomecánica'"

        
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY no está configurada")
             
        system_prompt = f"""
Eres un entrenador de vanguardia de HYROX. Empático pero enfocado en la disciplina.
Tu tarea es generar un ÚNICO mensaje de saludo inicial (máximo 3 líneas) para cuando tu atleta abre la app hoy.

Contexto de tu atleta ({contexto.get('nombre', 'Atleta')}):
- RM Sentadilla: {contexto.get('rm_sentadilla')} kg
- Fase de Peridización Actual: {fase} ({semanas} semanas para HYROX)
- Objetivo: {contexto.get('categoria')} el {contexto.get('fecha_evento')}
- Entrenamiento de hoy: {texto_sesion}
- Fatiga registrada en última sesión: {fatiga_reciente}{alerta_inactividad}{alerta_gym}{alerta_lesion}

Instrucciones:
1. Saluda por su nombre.
2. Si hay ALERTA MÉDICA (lesión) o DE INACTIVIDAD, que ese sea el núcleo principal de tu mensaje. La prioridad siempre la tiene la lesión.
3. Si no hay alerta, menciona brevemente lo que toca hoy y conecta con la fase actual ({fase}).
4. Si la fatiga es "Alta" y no hay alerta específica, recuérdale cuidar el cuerpo.
5. NO añadas comillas, no saludes dos veces ni uses prefijos como "Coach:". Solo el mensaje directo de 2-3 frases.
"""
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        try:
            # Mandamos un trigger vacío, todo el contexto está en el prompt de sistema
            response = model.generate_content("Genera el saludo del día")
            saludo = response.text.strip()
            
            # Guardamos el resultado en caché por 3600 segundos (1 hora)
            cache.set(cache_key, saludo, timeout=3600)
            
            return saludo
        except Exception as e:
            print(f"Error generando saludo inicial: {e}")
            return f"Hola {contexto.get('nombre', 'Atleta')}. {texto_sesion} ¡A por el día!"

class CompetitionStandardsService:
    # Estándares oficiales por categoría de HYROX.
    # Formato simple (distancia pura): valor numérico en metros
    # Formato dual (carga + volumen): {'kg': X, 'vol': Y, 'vol_unit': 'reps'|'m'}
    ESTANDARES_OFICIALES = {
        'open_men': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 152, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 103, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 24, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 20, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 6, 'vol': 100, 'vol_unit': 'reps'},
        },
        'open_women': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 102, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 78, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 16, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 10, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 4, 'vol': 100, 'vol_unit': 'reps'},
        },
        'pro_men': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 152, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 153, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 32, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 30, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 9, 'vol': 100, 'vol_unit': 'reps'},
        },
        'pro_women': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 102, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 103, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 24, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 20, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 6, 'vol': 100, 'vol_unit': 'reps'},
        },
        'doubles_men': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 152, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 103, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 24, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 20, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 6, 'vol': 100, 'vol_unit': 'reps'},
        },
        'doubles_women': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 102, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 78, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 16, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 10, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 4, 'vol': 100, 'vol_unit': 'reps'},
        },
        'doubles_mixed': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 152, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 103, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 24, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 20, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 6, 'vol': 100, 'vol_unit': 'reps'},
        },
        'relay': {
            'SkiErg': 1000,
            'Sled Push': {'kg': 125, 'vol': 50, 'vol_unit': 'm'},
            'Sled Pull': {'kg': 75, 'vol': 50, 'vol_unit': 'm'},
            'Burpee Broad Jumps': 80,
            'Rowing': 1000,
            'Farmers Carry': {'kg': 24, 'vol': 200, 'vol_unit': 'm'},
            'Sandbag Lunges': {'kg': 20, 'vol': 100, 'vol_unit': 'm'},
            'Wall Balls': {'kg': 6, 'vol': 100, 'vol_unit': 'reps'},
        },
    }

    # Equivalencias de ejercicios (heurística)
    EQUIVALENCIAS = {
        # Modo 'kg' (default): peso_max_serie × factor → kg_registrado
        'Prensa de piernas': {'target': 'Sled Push',      'factor': 1.0,  'mode': 'kg'},
        'Remo polea baja':   {'target': 'Sled Pull',      'factor': 1.0,  'mode': 'kg'},
        'Zancadas':          {'target': 'Sandbag Lunges', 'factor': 0.7,  'mode': 'kg'},
        'Thruster':          {'target': 'Wall Balls',     'factor': 1.0,  'mode': 'kg'},
        'Paseo del Granjero': {'target': 'Farmers Carry',  'factor': 1.0,  'mode': 'kg'},
        'Paseo granjero':    {'target': 'Farmers Carry',  'factor': 1.0,  'mode': 'kg'},
        'Farmer walk':       {'target': 'Farmers Carry',  'factor': 1.0,  'mode': 'kg'},
        'Remo':              {'target': 'Rowing',         'factor': 1.0,  'mode': 'vol'},
        # Modo 'reps_to_dist': total_reps × factor → vol_registrado (metros)
        'Burpees':             {'target': 'Burpee Broad Jumps', 'factor': 1.3, 'mode': 'reps_to_dist'},
        # Alias de nombre exacto guardado por el parser
        'Burpees Broad Jump':  {'target': 'Burpee Broad Jumps', 'factor': 1.0, 'mode': 'dist'},
    }

    @classmethod
    def get_user_standards_progress(cls, user_id):
        from .models import HyroxObjective, HyroxActivity
        from django.db.models import Max

        objetivo = HyroxObjective.objects.filter(cliente__user_id=user_id, estado='activo').first()
        if not objetivo:
            return {'progreso': [], 'logros': []}

        categoria = objetivo.categoria
        estandares = cls.ESTANDARES_OFICIALES.get(categoria, dict())
        progreso_estandares = []
        logros_recientes = []

        EJERCICIOS_DISTANCIA_PURA = ('SkiErg', 'Rowing', 'Burpee')

        for estandar_nombre, objetivo_std in estandares.items():

            # ── Determinar si es métrica simple o dual ──────────────────────
            es_dual = isinstance(objetivo_std, dict)
            if es_dual:
                kg_objetivo = float(objetivo_std['kg'])
                vol_objetivo = float(objetivo_std['vol'])
                vol_unit = objetivo_std['vol_unit']
            else:
                # Simple: solo distancia pura (SkiErg, Rowing, Burpee)
                kg_objetivo = 0.0
                vol_objetivo = float(objetivo_std)
                vol_unit = 'm'

            kg_registrado = 0.0
            vol_registrado = 0.0

            # ── 1. Buscar actividades directas ──────────────────────────────
            actividades_directas = HyroxActivity.objects.filter(
                sesion__objective=objetivo,
                nombre_ejercicio__icontains=estandar_nombre
            ).values('data_metricas')

            for act in actividades_directas:
                metricas = act.get('data_metricas', {}) or {}
                series = metricas.get('series', [])
                # Soportar distancia en clave 'distancia', 'distancia_m' o 'distancia_km'
                distancia = float(metricas.get('distancia', 0) or 0)
                if not distancia:
                    distancia = float(metricas.get('distancia_m', 0) or 0)
                if not distancia:
                    distancia = float(metricas.get('distancia_km', 0) or 0) * 1000
                total_reps = 0

                if isinstance(series, list):
                    for serie in series:
                        peso_serie = float(serie.get('peso_kg', serie.get('peso', 0)) or 0)
                        reps_serie = float(serie.get('reps', 0) or 0)
                        kg_registrado = max(kg_registrado, peso_serie)
                        total_reps += reps_serie
                elif isinstance(series, dict):
                    peso_serie = float(series.get('peso_kg', series.get('peso', 0)) or 0)
                    reps_serie = float(series.get('reps', 0) or 0)
                    kg_registrado = max(kg_registrado, peso_serie)
                    total_reps = reps_serie

                # Fallback: peso_kg en nivel raíz (ej. Sandbag Lunges planificadas)
                if not kg_registrado:
                    kg_registrado = max(kg_registrado, float(metricas.get('peso_kg', 0) or 0))

                # Volumen acumulado
                if vol_unit == 'reps':
                    vol_registrado = max(vol_registrado, total_reps)
                else:
                    vol_registrado = max(vol_registrado, distancia)

            # ── 2. Equivalencias ────────────────────────────────────────────
            for equiv_nombre, equiv_data in cls.EQUIVALENCIAS.items():
                if equiv_data['target'] == estandar_nombre:
                    mode = equiv_data.get('mode', 'kg')
                    act_equiv = HyroxActivity.objects.filter(
                        sesion__objective=objetivo,
                        nombre_ejercicio__icontains=equiv_nombre
                    ).values('data_metricas')

                    for act in act_equiv:
                        metricas = act.get('data_metricas', {}) or {}
                        series = metricas.get('series', [])

                        if mode == 'dist':
                            # Alias exacto: leer distancia directamente
                            distancia_equiv = float(metricas.get('distancia', metricas.get('distancia_m', 0)) or 0)
                            vol_registrado = max(vol_registrado, distancia_equiv * equiv_data['factor'])
                        elif mode == 'reps_to_dist':
                            # Contar reps totales y convertir a distancia (metros)
                            total_reps_equiv = 0.0
                            if isinstance(series, list):
                                for serie in series:
                                    total_reps_equiv += float(serie.get('reps', 0) or 0)
                            elif isinstance(series, dict):
                                total_reps_equiv = float(series.get('reps', 0) or 0)
                            distancia_equiv = total_reps_equiv * equiv_data['factor']
                            vol_registrado = max(vol_registrado, distancia_equiv)
                        else:
                            # Modo 'kg': peso máximo de serie × factor
                            peso_equiv = 0.0
                            if isinstance(series, list):
                                for serie in series:
                                    peso_equiv = max(peso_equiv, float(serie.get('peso_kg', serie.get('peso', 0)) or 0))
                            elif isinstance(series, dict):
                                peso_equiv = float(series.get('peso_kg', series.get('peso', 0)) or 0)
                            kg_registrado = max(kg_registrado, peso_equiv * equiv_data['factor'])

            kg_registrado = round(kg_registrado, 1)
            vol_registrado = round(vol_registrado, 1)

            # ── 3. Porcentaje ponderado ─────────────────────────────────────
            if es_dual:
                pct_kg  = min((kg_registrado  / kg_objetivo)  * 100, 100) if kg_objetivo  > 0 else 0
                pct_vol = min((vol_registrado / vol_objetivo) * 100, 100) if vol_objetivo > 0 else 0
                porcentaje = int(pct_kg * 0.4 + pct_vol * 0.6)
            else:
                # Solo distancia pura
                pct_vol = min((vol_registrado / vol_objetivo) * 100, 100) if vol_objetivo > 0 else 0
                porcentaje = int(pct_vol)
                pct_kg = 0.0

            # ── 4. Unidad y flags ───────────────────────────────────────────
            es_distancia_pura = any(k in estandar_nombre for k in EJERCICIOS_DISTANCIA_PURA)
            unidad_kg = 'kg'
            unidad_vol = vol_unit

            if porcentaje == 100:
                logros_recientes.append(estandar_nombre)

            progreso_estandares.append({
                'nombre': estandar_nombre,
                # Compatibilidad hacia atrás
                'peso_objetivo': kg_objetivo if es_dual else vol_objetivo,
                'peso_actual': kg_registrado if es_dual else vol_registrado,
                'unidad': unidad_kg if es_dual else 'm',
                # Métricas duales
                'es_dual': es_dual,
                'kg_objetivo': kg_objetivo,
                'kg_actual': kg_registrado,
                'vol_objetivo': vol_objetivo,
                'vol_actual': vol_registrado,
                'vol_unit': vol_unit,
                # Progreso
                'pct_kg': round(pct_kg),
                'pct_vol': round(pct_vol if es_dual else pct_vol),
                'porcentaje': porcentaje,
                'is_completed': porcentaje == 100,
                'es_distancia': es_distancia_pura,
            })

        # Calculate global progress (average of all station percentages)
        progreso_global = 0
        if progreso_estandares:
            progreso_global = round(sum(s['porcentaje'] for s in progreso_estandares) / len(progreso_estandares))

        return {
            'progreso': progreso_estandares,
            'logros': logros_recientes,
            'progreso_global': progreso_global,
        }

    @classmethod
    def detectar_notas_equivalencias_sesion(cls, activities_created, user_id):
        """
        Examina las actividades recién creadas y detecta si alguna
        activa una equivalencia hacia un estándar HYROX.
        Devuelve una lista de strings con notas del coach.
        """
        from .models import HyroxObjective
        notas = []

        objetivo = HyroxObjective.objects.filter(
            cliente__user_id=user_id, estado='activo'
        ).first()
        if not objetivo:
            return notas

        categoria = objetivo.categoria
        estandares = cls.ESTANDARES_OFICIALES.get(categoria, {})
        nombre_atleta = objetivo.cliente.nombre

        for act in activities_created:
            nombre_ej = act.nombre_ejercicio if hasattr(act, 'nombre_ejercicio') else str(act)
            dm = act.data_metricas if hasattr(act, 'data_metricas') else {}

            for equiv_nombre, equiv_data in cls.EQUIVALENCIAS.items():
                if equiv_nombre.lower() not in nombre_ej.lower():
                    continue

                target = equiv_data['target']
                mode = equiv_data.get('mode', 'kg')
                factor = equiv_data['factor']
                objetivo_std = estandares.get(target)
                if not objetivo_std:
                    continue

                series = (dm or {}).get('series', [])

                if mode == 'reps_to_dist':
                    total_reps = 0.0
                    if isinstance(series, list):
                        for s in series:
                            total_reps += float(s.get('reps', 0) or 0)
                    metros = round(total_reps * factor, 1)
                    if metros > 0:
                        vol_obj = float(objetivo_std) if not isinstance(objetivo_std, dict) else float(objetivo_std.get('vol', 80))
                        pct = round(min(metros / vol_obj * 100, 100), 1)
                        notas.append(
                            f"🔗 {nombre_atleta}, tus {int(total_reps)} burpees de hoy equivalen a **{metros}m** en Burpee Broad Jumps "
                            f"(+{pct}% del objetivo de {int(vol_obj)}m). ¡La explosividad se construye rep a rep!"
                        )
                else:
                    # Modo kg
                    peso_max = 0.0
                    if isinstance(series, list):
                        for s in series:
                            peso_max = max(peso_max, float(s.get('peso_kg', s.get('peso', 0)) or 0))
                    elif isinstance(series, dict):
                        peso_max = float(series.get('peso_kg', series.get('peso', 0)) or 0)

                    kg_transferido = round(peso_max * factor, 1)
                    if kg_transferido > 0:
                        kg_obj = float(objetivo_std.get('kg', 20)) if isinstance(objetivo_std, dict) else float(objetivo_std)
                        pct = round(min(kg_transferido / kg_obj * 100, 100), 1)
                        notas.append(
                            f"🔗 {nombre_atleta}, tus {nombre_ej} de hoy han sumado **{kg_transferido}kg** (×{factor}) "
                            f"de transferencia hacia tu estándar de **{target}** (+{pct}% del objetivo de {kg_obj}kg). "
                            f"Estamos construyendo esa fuerza funcional, ladrillo a ladrillo."
                        )

        return notas


class HyroxRaceSimulator:
    """
    Motor de simulación de carrera HYROX.
    Calcula un tiempo estimado de finalización basándose en el perfil del atleta,
    sus RMs actuales, volumen de entrenamiento reciente y ritmo de carrera base.
    """

    # Tiempos de referencia para atleta de nivel medio (segundos por estación)
    # Basados en resultados oficiales de categoria Open
    TIEMPOS_BASE_OPEN_SEGUNDOS = {
        'SkiErg':            240,  # 4:00 min - 1000m
        'Sled Push':         180,  # 3:00 min - 50m
        'Sled Pull':         180,  # 3:00 min - 50m
        'Burpee Broad Jumps':240,  # 4:00 min - 80m
        'Rowing':            240,  # 4:00 min - 1000m
        'Farmers Carry':     120,  # 2:00 min - 200m
        'Sandbag Lunges':    360,  # 6:00 min - 100m
        'Wall Balls':        240,  # 4:00 min - 100 reps
    }

    # El tramo de carrera entre estaciones: 8 x 1km 
    DISTANCIA_CARRERA_TOTAL_M = 8000

    @classmethod
    def simular(cls, user_id):
        """
        Punto de entrada. Devuelve un dict con:
          - tiempo_total_str: "01:15:20"
          - desglose: lista de (nombre_estacion, segundos, penalizacion_pct)
          - carrera_segundos: tiempo total corriendo
          - mensaje_coach: string narrativo para el coach
        """
        from .models import HyroxObjective, HyroxActivity, HyroxSession
        from django.utils import timezone
        from datetime import timedelta

        objetivo = HyroxObjective.objects.filter(
            cliente__user_id=user_id, estado='activo'
        ).first()

        if not objetivo:
            return {'error': 'No hay objetivo activo.'}

        rm_sq  = float(objetivo.rm_sentadilla or 50.0)
        rm_dl  = float(objetivo.rm_peso_muerto or 80.0)
        t5k_str = objetivo.tiempo_5k_base or '28:00'
        categoria = objetivo.categoria
        nombre = objetivo.cliente.nombre

        # --- Convertir tiempo 5k a segundos ---
        t5k_seg = cls._tiempo_str_a_segundos(t5k_str)
        if t5k_seg is None:
            t5k_seg = 28 * 60  # 28:00 fallback explícito si el string es inválido

        # --- Calcular ritmo de 1km en segundos ---
        ritmo_1km_seg = t5k_seg / 5.0  # segundos por km

        # --- Obtener actividades de últimas 4 semanas ---
        hace_4_semanas = timezone.now().date() - timedelta(weeks=4)
        actividades_recientes = HyroxActivity.objects.filter(
            sesion__objective=objetivo,
            sesion__fecha__gte=hace_4_semanas,
        )

        # Volumen total de fuerza piernas (Sentadilla, Prensa, Lunges...) en kg·reps
        volumen_pierna = 0
        volumen_brazos = 0
        fatiga_registros = []

        for act in actividades_recientes:
            dm = act.data_metricas or {}
            series = dm.get('series', [])
            if isinstance(series, list):
                for s in series:
                    peso = float(s.get('peso_kg', s.get('peso', 0)) or 0)
                    reps = float(s.get('reps', 0) or 0)
                    nombre_ej = act.nombre_ejercicio.lower()
                    if any(k in nombre_ej for k in ('sentadilla', 'prensa', 'lunges', 'zancada')):
                        volumen_pierna += peso * reps
                    elif any(k in nombre_ej for k in ('press', 'remo', 'jalón', 'pull')):
                        volumen_brazos += peso * reps

        # Fatiga media de las últimas sesiones
        sesiones_recientes = HyroxSession.objects.filter(
            objective=objetivo,
            fecha__gte=hace_4_semanas,
            estado='completado'
        ).order_by('-fecha')[:8]

        fatiga_alta = sum(1 for s in sesiones_recientes if s.muscle_fatigue_index == 'Alta')
        total_sesiones = sesiones_recientes.count()
        pct_fatiga_alta = (fatiga_alta / total_sesiones) if total_sesiones > 0 else 0

        # Con fatiga alta frecuente -> mejor resistencia láctica -> mejora ritmo 5%
        ajuste_resistencia = 0.95 if pct_fatiga_alta > 0.5 else 1.0

        # --- Estándares oficiales para penalización ---
        estandares = CompetitionStandardsService.ESTANDARES_OFICIALES.get(categoria, {})

        # --- Calcular tiempo de cada estación ---
        desglose = []

        for estacion, tiempo_base in cls.TIEMPOS_BASE_OPEN_SEGUNDOS.items():
            penalizacion = 0.0  # porcentaje adicional de tiempo

            if estacion in ('Sled Push',):
                std_peso = estandares.get('Sled Push', 152)
                pct_fuerza = min(rm_sq / std_peso, 1.0)
                if pct_fuerza < 0.6:
                    penalizacion = (0.6 - pct_fuerza) * 1.5  # hasta +90% extra
                elif pct_fuerza < 1.0:
                    penalizacion = (1.0 - pct_fuerza) * 0.5

            elif estacion in ('Sled Pull',):
                std_peso = estandares.get('Sled Pull', 103)
                pct_fuerza = min(rm_dl / std_peso, 1.0)
                if pct_fuerza < 0.6:
                    penalizacion = (0.6 - pct_fuerza) * 1.5
                elif pct_fuerza < 1.0:
                    penalizacion = (1.0 - pct_fuerza) * 0.4

            elif estacion == 'Sandbag Lunges':
                # A más volumen de pierna -> menor penalización
                pct_volumen = min(volumen_pierna / 5000.0, 1.0)  # 5000 kg·rep = buena base
                penalizacion = (1.0 - pct_volumen) * 0.4

            elif estacion == 'Wall Balls':
                pct_volumen = min(volumen_brazos / 3000.0, 1.0)
                penalizacion = (1.0 - pct_volumen) * 0.25

            elif estacion in ('SkiErg', 'Rowing'):
                penalizacion = (ajuste_resistencia - 1.0)  # negativo si mejor resistencia

            tiempo_estacion = tiempo_base * (1 + penalizacion)
            desglose.append({
                'nombre': estacion,
                'segundos': round(tiempo_estacion),
                'penalizacion_pct': round(penalizacion * 100, 1),
            })

        # --- Carrera: 8km al ritmo ajustado ---
        carrera_segundos = ritmo_1km_seg * 8 * ajuste_resistencia

        # --- Transiciones: 2 min fijo ---
        transiciones_seg = 120

        total_segundos = sum(d['segundos'] for d in desglose) + carrera_segundos + transiciones_seg
        tiempo_total_str = cls._segundos_a_tiempo_str(int(total_segundos))

        # --- Calculos narrativos para el coach ---
        pilar_mas_debil = max(desglose, key=lambda x: x['penalizacion_pct'])
        carrera_str = cls._segundos_a_tiempo_str(int(carrera_segundos))
        rm_sq_objetivo = round(estandares.get('Sled Push', 152) * 0.85, 0)

        mensaje_coach = (
            f"{nombre}, con tu RM de sentadilla actual ({rm_sq}kg) y tu ritmo base de 5K ({t5k_str}), "
            f"tu tiempo estimado HOY en HYROX sería de **{tiempo_total_str}**.\n\n"
            f"Tu carrera ocupa {carrera_str}, y tu mayor freno ahora mismo es la estación de "
            f"**{pilar_mas_debil['nombre']}** (+{pilar_mas_debil['penalizacion_pct']}% sobre tiempo ideal).\n\n"
            f"Para bajar de la hora, nuestra prioridad absoluta estas semanas será llevar tu fuerza funcional "
            f"en Sled Push hasta ~{rm_sq_objetivo}kg de transferencia. Cada kilo cuenta en el trineo."
        )

        return {
            'tiempo_total_str': tiempo_total_str,
            'total_segundos': int(total_segundos),
            'desglose': desglose,
            'carrera_segundos': int(carrera_segundos),
            'carrera_str': carrera_str,
            'mensaje_coach': mensaje_coach,
        }

    @staticmethod
    def _tiempo_str_a_segundos(tiempo_str):
        """
        Convierte 'MM:SS' o 'HH:MM:SS' a segundos.
        Retorna None si el formato es inválido o el valor está vacío,
        para que el llamador pueda decidir cómo manejarlo en vez de
        asumir silenciosamente 28 min.
        """
        import logging
        logger = logging.getLogger(__name__)
        if not tiempo_str or not str(tiempo_str).strip():
            logger.warning("_tiempo_str_a_segundos: tiempo_str vacío o None")
            return None
        try:
            partes = str(tiempo_str).strip().split(':')
            if len(partes) == 2:
                return int(partes[0]) * 60 + int(partes[1])
            elif len(partes) == 3:
                return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
        except Exception as e:
            logger.warning(f"_tiempo_str_a_segundos: formato inválido '{tiempo_str}': {e}")
        return None

    @staticmethod
    def _segundos_a_tiempo_str(segundos):
        """Convierte segundos a 'HH:MM:SS'."""
        h = segundos // 3600
        m = (segundos % 3600) // 60
        s = segundos % 60
        return f"{h:02d}:{m:02d}:{s:02d}"


class HyroxMacrocycleEngine:
    """
    Motor central de periodización inteligente hacia HYROX (19 de Abril 2026).
    Gestiona las fases del entrenamiento, sobrecarga progresiva y penalizaciones por inactividad.
    """
    EVENT_DATE = "2026-04-19"

    @classmethod
    def get_current_phase(cls, objetivo=None, return_metadata=False):
        """
        Calcula las semanas restantes hasta el evento y determina la fase actual.
        Si return_metadata=True, devuelve información detallada para MacrocycleTimelineBar.
        """
        from django.utils import timezone
        import datetime

        # Fecha objetivo por defecto 19 Abril 2026, salvo que el objetivo tenga otra
        fecha_evento_str = cls.EVENT_DATE
        if objetivo and objetivo.fecha_evento:
            fecha_evento_str = str(objetivo.fecha_evento)

        try:
            fecha_obj = datetime.datetime.strptime(fecha_evento_str, "%Y-%m-%d").date()
        except ValueError:
            return ("Fase de Base", 12) if not return_metadata else {}

        # Suponemos que el entrenamiento empezó aprox. 12 semanas antes (ej. finales de enero)
        fecha_inicio_ciclo = datetime.date(2026, 1, 26) 
        
        hoy = timezone.now().date()
        dias_restantes = (fecha_obj - hoy).days
        semanas_restantes = max(0, dias_restantes // 7)
        
        # Para la barra de progreso
        dias_totales = (fecha_obj - fecha_inicio_ciclo).days if (fecha_obj - fecha_inicio_ciclo).days > 0 else 84
        dias_pasados = (hoy - fecha_inicio_ciclo).days
        pct_progreso = min(max((dias_pasados / dias_totales) * 100, 0), 100)

        # Definición de las Fases del Macrociclo Hyrox
        mantra = ""
        fase = ""
        fase_numero = 1

        if semanas_restantes >= 9:
            fase = "Fase de Base Estructural"
            mantra = "Enfoque en técnica, volumen suave y corrección de desequilibrios."
            fase_numero = 1
        elif 5 <= semanas_restantes <= 8:
            fase = "Fase de Potencia Específica"
            mantra = "Construyendo la potencia pesada para dominar el Sled Push y Wall Balls."
            fase_numero = 2
        elif 2 <= semanas_restantes <= 4:
            fase = "Fase de Simulación Real"
            mantra = "Carrera intervenida. Acostumbrando el cuerpo a correr bajo fatiga severa."
            fase_numero = 3
        else:
            fase = "Fase de Tapering"
            mantra = "Recuperación, afinación y puesta a punto. El trabajo ya está hecho."
            fase_numero = 4

        if return_metadata:
            return {
                'fase': fase,
                'semanas_restantes': semanas_restantes,
                'dias_totales': dias_totales,
                'dias_pasados': dias_pasados,
                'pct_progreso': round(pct_progreso, 1),
                'mantra': mantra,
                'fase_numero': fase_numero
            }
        
        return fase, semanas_restantes

    @classmethod
    def calculate_progressive_overload(cls, user_id):
        """
        Analiza las últimas 3 sesiones. Si el RPE medio es < 7 y el muscle_fatigue es 'Baja',
        devuelve un factor de sobrecarga de 1.05 (+5%).
        """
        from .models import HyroxObjective
        objetivo = HyroxObjective.objects.filter(cliente__user_id=user_id, estado='activo').first()
        if not objetivo:
            return 1.0

        ultimas_sesiones = list(
            objetivo.sessions.filter(estado='completado')
            .order_by('-fecha')[:3]
        )

        if len(ultimas_sesiones) == 3:
            rpes = [s.rpe_global for s in ultimas_sesiones if s.rpe_global is not None]
            if len(rpes) == 3:
                rpe_medio = sum(rpes) / 3.0
                fatigas_bajas = all(s.muscle_fatigue_index and s.muscle_fatigue_index.lower() == 'baja' for s in ultimas_sesiones)
                
                if rpe_medio < 7 and fatigas_bajas:
                    return 1.05 # Sobrecarga del 5%
        
        return 1.0 # Mantenimiento

    @classmethod
    def detect_running_inactivity(cls, user_id):
        """
        Chequea si han pasado más de 7 días sin registrar 'carrera'.
        Retorna (inactivo_bool, dias_sin_correr, tiene_credito_futbol, preguntar_bool).
        """
        from .models import HyroxActivity, HyroxObjective
        from django.utils import timezone

        objetivo = HyroxObjective.objects.filter(cliente__user_id=user_id, estado='activo').first()
        if not objetivo:
            return False, 0, False, False

        ultima_carrera = HyroxActivity.objects.filter(
            sesion__objective=objetivo,
            sesion__estado='completado',
            tipo_actividad='carrera'
        ).order_by('-sesion__fecha').first()

        tiene_credito_futbol = False
        hoy = timezone.now().date()
        
        # Buscar crédito aeróbico alternativo (Fútbol) en los últimos 7 días con RPE >= 7
        hace_7_dias = hoy - timezone.timedelta(days=7)
        partido_futbol = HyroxActivity.objects.filter(
            sesion__objective=objetivo,
            sesion__estado='completado',
            nombre_ejercicio__icontains='futbol',
            sesion__fecha__gte=hace_7_dias,
            sesion__rpe_global__gte=7
        ).exists()
        
        if partido_futbol:
            tiene_credito_futbol = True

        if ultima_carrera and ultima_carrera.sesion.fecha:
            dias_sin_correr = (hoy - ultima_carrera.sesion.fecha).days
            inactivo = dias_sin_correr > 7
            return inactivo, dias_sin_correr, tiene_credito_futbol, False
        else:
            # Si no ha corrido nunca registrado, no asumo 14 días. Activo flag de "preguntar".
            return True, 7, tiene_credito_futbol, True

class InjuryPhaseManager:
    """
    Gestiona el ciclo de vida biológico de una lesión basado en los DailyRecoveryEntry.
    Automatiza las subidas (Upgrade) y caídas (Downgrade) de fase.
    """
    @staticmethod
    def evaluate_phase_transition(injury):
        from .models import DailyRecoveryEntry, UserInjury

        if not injury.activa:
            return None

        # Obtener los registros diarios más recientes
        registros = DailyRecoveryEntry.objects.filter(lesion=injury).order_by('-fecha')
        
        if not registros.exists():
            return None

        recent_entries = list(registros[:3])

        # 1. Evaluar Downgrade (Pico de dolor, subida >2 respecto al día anterior)
        if len(recent_entries) >= 2:
            hoy = recent_entries[0]
            ayer = recent_entries[1]
            
            dolor_reposo_diff = hoy.dolor_reposo - ayer.dolor_reposo
            dolor_mov_diff = hoy.dolor_movimiento - ayer.dolor_movimiento
            
            # Si el dolor salta abruptamente (ej ayer=2, hoy=5 -> sube 3)
            if dolor_reposo_diff > 2 or dolor_mov_diff > 2:
                # Degradamos fase a la inicial (Aguda)
                if injury.fase != UserInjury.Fase.AGUDA:
                    injury.fase = UserInjury.Fase.AGUDA
                    # Endurecemos bloqueos añadiendo impacto
                    if "impacto_vertical" not in injury.tags_restringidos:
                        injury.tags_restringidos.append("impacto_vertical")
                    injury.save()
                    return {"action": "DOWNGRADE", "msg": "Retroceso detectado: pico de dolor agudo. Volvemos a Fase Aguda. Bloqueos estrictos reactivados."}

        # 2. Evaluar Upgrade a Sub-aguda
        if injury.fase == UserInjury.Fase.AGUDA and len(recent_entries) == 3:
            # Si en los 3 días dolor_reposo < 2 y dolor_movimiento < 4
            mejora_continua = all(r.dolor_reposo < 2 and r.dolor_movimiento < 4 for r in recent_entries)
            if mejora_continua:
                injury.fase = UserInjury.Fase.SUB_AGUDA
                injury.save()
                return {"action": "UPGRADE", "msg": "Inflamación bajo control durante 3 días. Pasamos a Fase Sub-Aguda (Movilidad activa permitida)."}

        # 3. Evaluar Upgrade a Retorno
        if injury.fase == UserInjury.Fase.SUB_AGUDA and len(recent_entries) == 3:
            # Si 3 días dolor es muy bajo/nulo (reposo 0, mov <= 1)
            curacion_clinica = all(r.dolor_reposo == 0 and r.dolor_movimiento <= 1 for r in recent_entries)
            if curacion_clinica:
                injury.fase = UserInjury.Fase.RETORNO
                injury.save()
                return {"action": "UPGRADE", "msg": "Sin dolor clínico. Iniciamos Fase de Retorno (Fuerza progresiva tolerada)."}
                
        # 4. Evaluar Upgrade a Recuperado (Alta Médica)
        if injury.fase == UserInjury.Fase.RETORNO and len(recent_entries) == 3:
            # Si 3 días seguidos el dolor es totalmente nulo y rango de movimiento casi completo
            curacion_total = all(r.dolor_reposo == 0 and r.dolor_movimiento == 0 and r.rango_movimiento >= 9 for r in recent_entries)
            if curacion_total:
                from django.utils import timezone
                injury.fase = UserInjury.Fase.RECUPERADO
                injury.activa = False
                injury.fecha_resolucion = timezone.now().date()
                injury.save()
                return {"action": "UPGRADE", "msg": "¡Alta Médica! Recuperación al 100%. Regresas al plan normal sin restricciones."}

        return None
