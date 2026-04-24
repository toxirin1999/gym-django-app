import logging
import math
import datetime
from datetime import timedelta
from django.utils import timezone
from .models import HyroxObjective, HyroxSession, HyroxActivity

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HYROX LOAD MANAGER — Carga objetiva, zonas cardíacas, TRIMP, CTL/ATL/TSB
# ══════════════════════════════════════════════════════════════════════════════

class HyroxLoadManager:
    """
    Gestión científica de la carga de entrenamiento:
    · TRIMP (Banister): carga objetiva por sesión = duración × intensidad relativa FC
    · CTL (42 días): Chronic Training Load → fitness acumulado
    · ATL  (7 días): Acute Training Load   → fatiga reciente
    · TSB: CTL - ATL → "forma" del atleta (positivo=fresco, negativo=fatigado)
    · Zonas Z1-Z5 calibradas a la FC máx real del atleta
    · Validación RPE vs FC: detecta subestimación/sobreestimación subjetiva
    """

    # Factor b de Banister: mayor en hombres por diferencias hormonales
    B_FACTOR = {'M': 1.92, 'F': 1.67}

    # Rangos de cada zona como fracción de FC máxima
    ZONAS_FC = {
        'Z1': (0.00, 0.60),
        'Z2': (0.60, 0.70),
        'Z3': (0.70, 0.80),
        'Z4': (0.80, 0.90),
        'Z5': (0.90, 1.01),
    }

    ZONA_INFO = {
        'Z1': {'nombre': 'Recuperación Activa',     'uso': 'Descanso activo, vuelta a la calma'},
        'Z2': {'nombre': 'Aeróbico Base',            'uso': 'Motor de resistencia, quema de grasas'},
        'Z3': {'nombre': 'Tempo / Umbral Aeróbico',  'uso': 'Carreras de ritmo, umbral de lactato'},
        'Z4': {'nombre': 'Umbral Láctico',           'uso': 'Intervalos de alta intensidad'},
        'Z5': {'nombre': 'VO₂max / Anaeróbico',      'uso': 'Sprints, HIIT máximo'},
    }

    # Zona → RPE esperado (rango aproximado)
    RPE_POR_ZONA = {
        'Z1': (1, 4), 'Z2': (4, 6), 'Z3': (6, 7), 'Z4': (7, 9), 'Z5': (9, 10)
    }

    @classmethod
    def get_fc_max(cls, objetivo):
        """FC máxima: real si está registrada, sino 220-edad."""
        if objetivo.fc_max_real:
            return objetivo.fc_max_real
        try:
            edad = (timezone.now().date() - objetivo.cliente.fecha_nacimiento).days // 365
            return max(150, 220 - edad)
        except Exception:
            return 185

    @classmethod
    def get_fc_reposo(cls, objetivo):
        return objetivo.fc_reposo if objetivo.fc_reposo is not None else 60

    @classmethod
    def get_zonas_absolutas(cls, objetivo):
        """Devuelve rangos de FC en lpm para cada zona, calibrados al atleta."""
        fc_max = cls.get_fc_max(objetivo)
        zonas = {}
        for zona, (low, high) in cls.ZONAS_FC.items():
            zonas[zona] = {
                'min_lpm': round(fc_max * low),
                'max_lpm': round(fc_max * min(high, 1.0)),
                **cls.ZONA_INFO[zona],
            }
        return zonas

    @classmethod
    def calcular_zona_predominante(cls, hr_media, objetivo):
        """Determina la zona cardíaca predominante según FC media de la sesión."""
        if not hr_media or not objetivo:
            return None
        fc_max = cls.get_fc_max(objetivo)
        pct = hr_media / fc_max
        for zona, (low, high) in cls.ZONAS_FC.items():
            if low <= pct < high:
                return zona
        return 'Z5'

    @classmethod
    def calcular_trimp(cls, duracion_min, hr_media, objetivo):
        """
        TRIMP de Banister.
        Fórmula: T × HRR × e^(b × HRR)
        donde HRR = (FC_media - FC_reposo) / (FC_max - FC_reposo)
        """
        if not duracion_min or not hr_media:
            return None
        fc_max  = cls.get_fc_max(objetivo)
        fc_rep  = cls.get_fc_reposo(objetivo)
        b       = cls.B_FACTOR.get(getattr(objetivo, 'genero', 'M'), 1.92)

        if fc_max <= fc_rep:
            return None

        hrr = (hr_media - fc_rep) / (fc_max - fc_rep)
        hrr = max(0.0, min(hrr, 1.0))
        trimp = duracion_min * hrr * math.exp(b * hrr)
        return round(trimp, 1)

    @classmethod
    def calcular_ctl_atl_tsb(cls, objetivo, hasta_fecha=None):
        """
        CTL/ATL/TSB usando exponential weighted moving average (EWMA).
        Constantes de tiempo: CTL=42 días, ATL=7 días.
        TSB = CTL - ATL (Training Stress Balance = "forma").
        """
        if hasta_fecha is None:
            hasta_fecha = timezone.now().date()

        sesiones = list(
            HyroxSession.objects.filter(
                objective=objetivo,
                estado='completado',
                trimp__isnull=False,
                fecha__lte=hasta_fecha,
            ).order_by('fecha').values('fecha', 'trimp')
        )

        if not sesiones:
            return {'ctl': 0.0, 'atl': 0.0, 'tsb': 0.0}

        # Construir mapa fecha → TRIMP total del día
        trimp_por_dia = {}
        for s in sesiones:
            d = s['fecha']
            trimp_por_dia[d] = trimp_por_dia.get(d, 0) + s['trimp']

        desde = sesiones[0]['fecha']
        dias  = (hasta_fecha - desde).days + 1

        ctl = atl = 0.0
        k_ctl = 1 / 42.0
        k_atl = 1 / 7.0

        fecha_cursor = desde
        for _ in range(dias):
            t = trimp_por_dia.get(fecha_cursor, 0)
            ctl = ctl + (t - ctl) * k_ctl
            atl = atl + (t - atl) * k_atl
            fecha_cursor += timedelta(days=1)

        tsb = round(ctl - atl, 1)
        return {'ctl': round(ctl, 1), 'atl': round(atl, 1), 'tsb': tsb}

    @classmethod
    def validar_rpe_vs_fc(cls, sesion):
        """
        Cross-validación RPE subjetivo vs FC objetiva.
        Retorna string de alerta si hay discordancia significativa, o None si es coherente.
        """
        if not sesion.rpe_global or not sesion.hr_media:
            return None

        objetivo = sesion.objective
        fc_max   = cls.get_fc_max(objetivo)
        zona     = cls.calcular_zona_predominante(sesion.hr_media, objetivo)
        pct_fc   = round((sesion.hr_media / fc_max) * 100)
        rpe      = sesion.rpe_global
        rango    = cls.RPE_POR_ZONA.get(zona, (1, 10))

        if rpe < rango[0] - 1:
            return (
                f"⚠️ FC/RPE DISCORDANTE: FC media {sesion.hr_media} lpm "
                f"({zona} — {pct_fc}% FCmax) pero reportaste RPE {rpe}. "
                f"Subestimas el esfuerzo real. El TRIMP objetivo ajusta la próxima sesión."
            )
        if rpe > rango[1] + 1:
            return (
                f"📊 RPE alto vs FC moderada: RPE {rpe} con FC {sesion.hr_media} lpm ({zona}). "
                f"Posible fatiga mental o inicio de sobreentrenamiento. Revisa el descanso."
            )
        return None

    @classmethod
    def get_acwr(cls, objetivo):
        """
        Acute:Chronic Workload Ratio = ATL / CTL.
        > 1.5  → zona roja (riesgo lesión por pico de carga)
        0.8-1.3 → zona óptima de rendimiento
        < 0.8  → desentrenamiento (carga insuficiente)
        """
        carga = cls.calcular_ctl_atl_tsb(objetivo)
        ctl = carga['ctl']
        atl = carga['atl']
        if ctl <= 0:
            return None
        return round(atl / ctl, 2)

    @classmethod
    def get_fc_reposo_basal(cls, objetivo, dias=14):
        """
        FC de reposo basal = media rolling de los últimos N días con lectura.
        Prioriza lecturas en HyroxReadinessLog; fallback al campo del objetivo.
        """
        from .models import HyroxReadinessLog
        lecturas = list(
            HyroxReadinessLog.objects.filter(
                objective=objetivo,
                fc_reposo__isnull=False,
            ).order_by('-fecha')[:dias].values_list('fc_reposo', flat=True)
        )
        if lecturas:
            return round(sum(lecturas) / len(lecturas))
        return objetivo.fc_reposo if objetivo.fc_reposo is not None else 60

    @classmethod
    def get_sleep_penalty(cls, objetivo, dias=7):
        """
        Penalización de carga derivada del sueño reciente (HyroxReadinessLog).
        Retorna un valor 0–8 que se resta al TSB efectivo antes de calcular cargas:
          < 6 h sueño  → +4   |  6–7 h → +2
          calidad < 4  → +3   |  4–5   → +1.5
        Un atleta bien descansado no recibe penalización (retorna 0).
        """
        from .models import HyroxReadinessLog
        lecturas = list(
            HyroxReadinessLog.objects.filter(objective=objetivo)
            .order_by('-fecha')[:dias]
            .values('horas_sueno', 'calidad_sueno')
        )
        if not lecturas:
            return 0.0
        total = 0.0
        for l in lecturas:
            horas   = l.get('horas_sueno') or 0
            calidad = l.get('calidad_sueno') or 5
            p = 0.0
            if horas and horas < 6:
                p += 4.0
            elif horas and horas < 7:
                p += 2.0
            if calidad and calidad < 4:
                p += 3.0
            elif calidad and calidad < 6:
                p += 1.5
            total += p
        return round(total / len(lecturas), 1)

    @classmethod
    def get_progression_curve(cls, objetivo, tipo_actividad, ejercicio_keyword=None, semanas=8):
        """
        Devuelve lista de (fecha, valor) con la progresión de una métrica clave.
        - carrera: ritmo promedio en seg/km
        - hyrox_station / fuerza: peso máximo usado
        Útil para detectar estancamiento real vs. RPE subjetivo.
        """
        desde = timezone.now().date() - timedelta(weeks=semanas)
        actividades = (
            HyroxActivity.objects
            .filter(
                sesion__objective=objetivo,
                sesion__estado='completado',
                sesion__fecha__gte=desde,
                tipo_actividad=tipo_actividad,
            )
            .order_by('sesion__fecha')
            .values('sesion__fecha', 'data_metricas', 'nombre_ejercicio')
        )

        curva = []
        for a in actividades:
            if ejercicio_keyword and ejercicio_keyword.lower() not in a['nombre_ejercicio'].lower():
                continue
            m = a['data_metricas'] or {}
            valor = None
            if tipo_actividad == 'carrera':
                ritmo = m.get('ritmo_real', '')
                if ritmo:
                    try:
                        parts = ritmo.replace('/km', '').split(':')
                        valor = int(parts[0]) * 60 + int(parts[1])
                    except Exception:
                        pass
                elif m.get('distancia_km') and m.get('tiempo_minutos'):
                    km = float(m['distancia_km'])
                    mins = float(m['tiempo_minutos'])
                    if km > 0:
                        valor = round((mins * 60) / km)
            elif tipo_actividad in ('hyrox_station', 'fuerza'):
                peso = m.get('peso_kg')
                if peso:
                    valor = float(peso)
                elif m.get('series'):
                    pesos = [float(s.get('peso_kg', s.get('peso', 0))) for s in m['series'] if s.get('peso_kg') or s.get('peso')]
                    if pesos:
                        valor = max(pesos)
            if valor is not None:
                curva.append({'fecha': str(a['sesion__fecha']), 'valor': valor})
        return curva

    @classmethod
    def get_zona_para_template(cls, template, is_taper=False, is_deload=False):
        """Zona cardíaca objetivo según tipo de sesión."""
        if is_taper or is_deload:
            return 'Z1' if is_deload else 'Z2'
        return {
            'cardio':         'Z2',
            'simulacion':     'Z3',
            'hyrox_stations': 'Z3',
            'fuerza_metcon':  'Z2',
            'calibracion':    'Z1',
        }.get(template, 'Z2')

    @classmethod
    def get_prescripcion_zona(cls, template, objetivo, is_taper=False, is_deload=False):
        """
        Devuelve texto de prescripción de zona con lpm reales del atleta.
        Útil para incluir en las notas de las actividades planificadas.
        """
        zona     = cls.get_zona_para_template(template, is_taper, is_deload)
        fc_max   = cls.get_fc_max(objetivo)
        low, high = cls.ZONAS_FC[zona]
        min_lpm  = round(fc_max * low)
        max_lpm  = round(fc_max * min(high, 1.0))
        nombre   = cls.ZONA_INFO[zona]['nombre']
        return f"Zona objetivo: {zona} — {nombre} · FC {min_lpm}-{max_lpm} lpm"

    @classmethod
    def get_estado_forma(cls, tsb):
        """Clasifica el estado de forma según TSB."""
        if tsb is None:
            return {'estado': 'Sin datos', 'recomendacion': 'Registra FC y duración para calibrar.'}
        if tsb >= 10:
            return {'estado': 'Fresco / Listo', 'recomendacion': 'Óptimo para intensidad máxima o competición.'}
        if tsb >= 0:
            return {'estado': 'Óptimo', 'recomendacion': 'Zona ideal de entrenamiento productivo.'}
        if tsb >= -15:
            return {'estado': 'Acumulando carga', 'recomendacion': 'Progresando. Vigila descanso y nutrición.'}
        if tsb >= -25:
            return {'estado': 'Fatiga alta', 'recomendacion': 'Reduce intensidad. Prioriza sueño y recuperación.'}
        return {'estado': '⚠️ Sobreentrenamiento', 'recomendacion': 'Descanso obligatorio 48-72h antes de retomar.'}


# ══════════════════════════════════════════════════════════════════════════════

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
    def _calcular_porcentaje_rm(week, weeks_to_plan, is_deload, is_taper,
                                 rpe_acumulado=None, tsb=None, sleep_penalty=0.0):
        """
        Progresión de carga ponderada por:
        1. Calendario (semana del macrociclo)
        2. RPE acumulado (últimas 3 sesiones) — señal subjetiva
        3. TSB + penalización sueño (señal objetiva de forma/fatiga)

        TSB efectivo = TSB real − sleep_penalty (sueño deficiente reduce forma percibida)
        TSB > +10  → atleta fresco: acelerar progresión
        TSB 0-10   → zona óptima: progresión normal
        TSB -15-0  → carga acumulada: prudencia
        TSB < -20  → fatiga excesiva: reducir carga
        """
        if is_taper:
            return 0.50
        if is_deload:
            return 0.60
        if weeks_to_plan <= 1:
            return 0.70

        progreso = week / max(weeks_to_plan - 1, 1)
        base_pct = round(0.65 + (progreso * 0.20), 3)

        # Ajuste por RPE acumulado (señal subjetiva)
        if rpe_acumulado is not None:
            if rpe_acumulado > 8.5:
                base_pct = max(round(base_pct - 0.05, 3), 0.65)
            elif rpe_acumulado < 6.0:
                base_pct = min(round(base_pct + 0.05, 3), 0.85)

        # TSB efectivo: combinamos forma objetiva + penalización por sueño deficiente
        tsb_eff = None
        if tsb is not None:
            tsb_eff = tsb - sleep_penalty
        elif sleep_penalty > 0:
            tsb_eff = -sleep_penalty  # sin historial TRIMP, el sueño ya indica fatiga

        # Ajuste por TSB efectivo (prioridad sobre RPE)
        if tsb_eff is not None:
            if tsb_eff < -25:
                base_pct = max(round(base_pct - 0.12, 3), 0.60)
            elif tsb_eff < -15:
                base_pct = max(round(base_pct - 0.07, 3), 0.63)
            elif tsb_eff < -5:
                base_pct = max(round(base_pct - 0.03, 3), 0.65)
            elif tsb_eff > 10:
                base_pct = min(round(base_pct + 0.05, 3), 0.90)

        return base_pct

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

    # Pesos oficiales de competición por categoría (kg)
    PESOS_OFICIALES = {
        'open_men':     {'sled_push': 152, 'sled_pull': 103, 'farmers': 24, 'sandbag': 20, 'wall_ball': 6},
        'open_women':   {'sled_push': 102, 'sled_pull':  78, 'farmers': 16, 'sandbag': 10, 'wall_ball': 4},
        'pro_men':      {'sled_push': 152, 'sled_pull': 103, 'farmers': 32, 'sandbag': 20, 'wall_ball': 6},
        'pro_women':    {'sled_push': 102, 'sled_pull':  78, 'farmers': 20, 'sandbag': 10, 'wall_ball': 4},
        'doubles_men':  {'sled_push': 152, 'sled_pull': 103, 'farmers': 24, 'sandbag': 20, 'wall_ball': 6},
        'doubles_women':{'sled_push': 102, 'sled_pull':  78, 'farmers': 16, 'sandbag': 10, 'wall_ball': 4},
        'doubles_mixed':{'sled_push': 102, 'sled_pull':  78, 'farmers': 20, 'sandbag': 15, 'wall_ball': 5},
        'relay':        {'sled_push': 152, 'sled_pull': 103, 'farmers': 24, 'sandbag': 20, 'wall_ball': 6},
    }

    @classmethod
    def _pesos_progresivos(cls, categoria, week, weeks_to_plan, is_deload, is_taper,
                           nivel='intermedio', rpe_acumulado=None, tsb=None):
        """
        Devuelve los pesos de trabajo para estaciones con carga, escalados
        progresivamente desde ~55% del oficial (semana 1) hasta 100% (simulación/peak).

        Fase        | Factor base
        Adaptation  | 0.55 → 0.65  (semanas 1-4)
        Accumulation| 0.65 → 0.80  (semanas 5-12)
        Intensif.   | 0.80 → 0.95  (semanas 13-20)
        Simulation  | 1.00
        Deload      | factor_fase × 0.75
        Taper       | 0.55  (reducción de volumen, no reintroducir carga)
        """
        oficiales = cls.PESOS_OFICIALES.get(categoria, cls.PESOS_OFICIALES['open_men'])

        if is_taper:
            factor = 0.55
        elif is_deload:
            progreso = week / max(weeks_to_plan - 1, 1)
            factor = round((0.55 + progreso * 0.45) * 0.75, 3)
        else:
            progreso = week / max(weeks_to_plan - 1, 1)
            factor = round(0.55 + progreso * 0.45, 3)   # 0.55 → 1.00 lineal

            # Ajuste por RPE acumulado (subjetivo)
            if rpe_acumulado is not None:
                if rpe_acumulado > 8.5:
                    factor = max(factor - 0.05, 0.55)
                elif rpe_acumulado < 6.0:
                    factor = min(factor + 0.03, 1.00)

            # Ajuste por TSB (objetivo, prioridad sobre RPE)
            if tsb is not None:
                if tsb < -25:
                    factor = max(factor - 0.10, 0.55)
                elif tsb < -15:
                    factor = max(factor - 0.06, 0.57)
                elif tsb < -5:
                    factor = max(factor - 0.03, 0.58)
                elif tsb > 10:
                    factor = min(factor + 0.04, 1.00)

        # Ajuste por nivel de experiencia
        nivel_mult = {'principiante': 0.85, 'intermedio': 1.00, 'avanzado': 1.05}.get(nivel, 1.00)
        factor = round(min(factor * nivel_mult, 1.00), 3)

        def _kg(clave, redondeo=5):
            oficial = oficiales[clave]
            raw = oficial * factor
            # Redondear al múltiplo de redondeo más cercano (placas reales)
            return max(redondeo, round(raw / redondeo) * redondeo)

        return {
            'sled_push':  _kg('sled_push', 5),
            'sled_pull':  _kg('sled_pull', 5),
            'farmers':    _kg('farmers',   2),   # por mano
            'sandbag':    _kg('sandbag',   2),
            'wall_ball':  oficiales['wall_ball'], # el kg de wall ball no progresa (hay tallas fijas)
            'factor':     factor,
            'oficiales':  oficiales,
        }

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

    @staticmethod
    def _get_gym_external_load(cliente, dias=7):
        """
        Lee ActividadRealizada (hub unificado) para los últimos N días — SOLO LECTURA.
        Calcula la carga externa de gym que el algoritmo Hyrox debe considerar.
        No escribe nada en entrenos; los dos módulos quedan desacoplados.
        """
        try:
            from entrenos.models import ActividadRealizada
            cutoff = (timezone.now() - timedelta(days=dias)).date()
            actividades = list(ActividadRealizada.objects.filter(
                cliente=cliente,
                tipo='gym',
                fecha__gte=cutoff,
            ))
            count = len(actividades)
            if count == 0:
                return {'entrenos_count': 0, 'volumen_total_kg': 0, 'rpe_medio_gym': 0.0, 'fatiga_gym': 'Baja'}

            volumen_total = sum(float(a.volumen_kg or 0) for a in actividades)
            rpes = [float(a.rpe_medio) for a in actividades if a.rpe_medio]
            rpe_medio = round(sum(rpes) / len(rpes), 1) if rpes else 0.0

            # Alta: ≥3 sesiones en la semana, o volumen >15 000 kg, o RPE medio >7.5
            if count >= 3 or volumen_total > 15000 or rpe_medio > 7.5:
                fatiga_gym = 'Alta'
            elif count >= 2 or volumen_total > 8000 or rpe_medio > 6.5:
                fatiga_gym = 'Media'
            else:
                fatiga_gym = 'Baja'

            return {
                'entrenos_count': count,
                'volumen_total_kg': round(volumen_total),
                'rpe_medio_gym': rpe_medio,
                'fatiga_gym': fatiga_gym,
            }
        except Exception:
            return {'entrenos_count': 0, 'volumen_total_kg': 0, 'rpe_medio_gym': 0.0, 'fatiga_gym': 'Baja'}

    # ─────────────────────────────────────────────────────────────────────────
    # GENERACIÓN DEL PLAN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _distribuir_dias(dias_preferidos: list, n: int) -> list:
        """
        Devuelve n días de la semana (0-6) con al menos 1 día de descanso
        entre sesiones consecutivas. Respeta los días preferidos cuando es
        posible; si tienen días adyacentes, prioriza los primeros y busca
        sustitutos con separación correcta para los restantes.
        """
        # Plantillas óptimas garantizadas por n de sesiones
        FALLBACKS = {
            1: [0],
            2: [0, 3],
            3: [0, 2, 5],
            4: [0, 2, 4, 6],
            5: [0, 2, 4, 6, 8 % 7],  # no aplicable (máx 4)
        }

        candidatos = sorted(set(d for d in dias_preferidos if 0 <= d <= 6))

        # Filtrar candidatos respetando separación mínima de 2 días
        resultado = []
        for d in candidatos:
            if not resultado or d - resultado[-1] >= 2:
                resultado.append(d)
            if len(resultado) == n:
                return resultado

        # Completar con días del pool general que tengan separación >= 2
        for d in range(7):
            if len(resultado) >= n:
                break
            if d in resultado:
                continue
            if all(abs(d - r) >= 2 for r in resultado):
                resultado.append(d)

        resultado = sorted(resultado[:n])

        # Fallback garantizado si no se pudo completar con separación correcta
        if len(resultado) < n or any(
            resultado[i+1] - resultado[i] < 2 for i in range(len(resultado)-1)
        ):
            resultado = FALLBACKS.get(n, [0, 2, 4, 6])

        return resultado[:n]

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

        # RPE acumulado real de las últimas 3 sesiones Hyrox completadas
        ultimas_sesiones_hyrox = list(
            HyroxSession.objects.filter(objective=objective, estado='completado')
            .order_by('-fecha')[:3]
        )
        rpe_vals = [s.rpe_global for s in ultimas_sesiones_hyrox if s.rpe_global is not None]
        rpe_acumulado = round(sum(rpe_vals) / len(rpe_vals), 2) if rpe_vals else None

        # TSB actual (Training Stress Balance) — señal objetiva de forma/fatiga
        carga_actual = HyroxLoadManager.calcular_ctl_atl_tsb(objective)
        tsb_actual   = carga_actual['tsb'] if carga_actual['ctl'] > 0 else None

        # Penalización por sueño deficiente (últimos 7 días)
        sleep_penalty = HyroxLoadManager.get_sleep_penalty(objective)

        # Volumen semanal base por categoría
        sessions_per_week = 5 if 'pro' in objective.categoria else 4

        # Tags de lesiones activas — restricciones GRADUADAS según fase de lesión
        from .models import UserInjury
        # Movimientos de alto impacto que se restringen incluso en SUB_AGUDA
        _HIGH_IMPACT = {'impacto_vertical', 'triple_extension_explosiva', 'flexion_plantar'}
        lesiones_activas = UserInjury.objects.filter(cliente=objective.cliente, activa=True)
        restricted_tags = set()
        retorno_tags = set()  # tags en fase RETORNO: permitidos con carga reducida, no bloqueados
        for inj in lesiones_activas:
            if not inj.tags_restringidos:
                continue
            if inj.fase == 'AGUDA':
                # Fase aguda: bloquear todos los tags restringidos
                restricted_tags.update(inj.tags_restringidos)
            elif inj.fase == 'SUB_AGUDA':
                # Sub-aguda: solo bloquear los de alto impacto real
                restricted_tags.update(t for t in inj.tags_restringidos if t in _HIGH_IMPACT)
            elif inj.fase == 'RETORNO':
                # Retorno: no bloquear pero marcar para reducción de carga
                retorno_tags.update(inj.tags_restringidos)

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
                dias_raw = [int(p) for p in dias_pref.split(',')]
            except Exception:
                dias_raw = [0, 2, 4, 6]

            sessions_per_week_capped = min(sessions_per_week, 4)

            # Distribuir con separación mínima de 1 día de descanso
            dias_asignados = HyroxTrainingEngine._distribuir_dias(
                dias_raw, sessions_per_week_capped
            )

            try:
                dia_fuerza = dias_asignados[0]
                dia_cardio = dias_asignados[1]
                dia_espe   = dias_asignados[2]
                dia_simul  = dias_asignados[3] if sessions_per_week_capped >= 4 else dias_asignados[2]
            except IndexError:
                dia_fuerza, dia_cardio, dia_espe, dia_simul = 0, 2, 4, 6

            shared = dict(
                objective=objective,
                is_taper=is_taper,
                is_deload=is_deload,
                week=week,
                weeks_to_plan=weeks_to_plan,
                restricted_tags=restricted_tags,
                retorno_tags=retorno_tags,
                rpe_acumulado=rpe_acumulado,
                tsb=tsb_actual,
                sleep_penalty=sleep_penalty,
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

        # Modo Competición: congelar el plan la semana previa al evento
        hoy = timezone.now().date()
        if objective.fecha_evento and (objective.fecha_evento - hoy).days <= 7:
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

        # RPE fresco de las últimas 3 sesiones (más actualizado que el del plan)
        sesiones_recientes = list(HyroxSession.objects.filter(
            objective=sesion_completada.objective,
            estado='completado',
        ).order_by('-fecha')[:3])
        rpe_vals_frescos = [s.rpe_global for s in sesiones_recientes if s.rpe_global is not None]
        rpe_acumulado_fresco = round(sum(rpe_vals_frescos) / len(rpe_vals_frescos), 2) if rpe_vals_frescos else None

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

        # --- TRIGGER 2: ESTANCAMIENTO (2 sesiones seguidas RPE <= 5 + validación curva progresión) ---
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
                        # Validar estancamiento real con curva objetiva antes de incrementar
                        curva = HyroxLoadManager.get_progression_curve(
                            sesion_completada.objective, tipo, semanas=4
                        )
                        # Estancamiento confirmado si la curva tiene >= 3 puntos y no mejora
                        hay_plateau = True
                        if len(curva) >= 3:
                            valores = [p['valor'] for p in curva[-3:]]
                            # Para carrera: mejora = valores decrecen (menos seg/km)
                            # Para fuerza/stations: mejora = valores crecen
                            if tipo == 'carrera':
                                hay_plateau = (max(valores) - min(valores)) < 10  # < 10 seg/km variación
                            else:
                                hay_plateau = (max(valores) - min(valores)) / max(valores) < 0.05  # < 5% variación

                        if not hay_plateau:
                            continue  # La curva muestra progresión real, no estancamiento

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
                                    f"He detectado carga baja persistente en {tipo.capitalize()} "
                                    f"(RPE ≤5 confirmado en curva objetiva). "
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

        # --- TRIGGER 4: FATIGA CRÓNICA DE SNC (3 sesiones consecutivas RPE > 8.5) ---
        # El SNC no se recupera igual que el músculo. 3 sesiones seguidas al límite
        # sin descenso indica agotamiento neurológico. Se bloquea la intensificación.
        ultimas_3 = list(HyroxSession.objects.filter(
            objective=sesion_completada.objective,
            estado='completado',
            fecha__lte=sesion_completada.fecha,
        ).order_by('-fecha')[:3])
        rpes_snc = [s.rpe_global for s in ultimas_3 if s.rpe_global is not None]
        if len(rpes_snc) == 3 and all(r > 8.5 for r in rpes_snc):
            proxima_fuerza = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='planificado',
                fecha__gt=sesion_completada.fecha,
                titulo__icontains='fuerza',
            ).order_by('fecha').first()
            if proxima_fuerza:
                snc_mutated = False
                for act in proxima_fuerza.activities.filter(tipo_actividad='fuerza'):
                    porcentaje_actual = act.data_metricas.get('porcentaje_rm', 75)
                    if porcentaje_actual > 70:
                        factor_reduccion = 70.0 / porcentaje_actual
                        if 'series' in act.data_metricas:
                            for serie in act.data_metricas['series']:
                                if 'peso_kg' in serie:
                                    serie['peso_kg'] = round(float(serie['peso_kg']) * factor_reduccion)
                        act.data_metricas['porcentaje_rm'] = 70
                        notas = act.data_metricas.get('notas', '')
                        act.data_metricas['notas'] = notas + " | ⚡ Bloqueo SNC: 3 sesiones RPE>8.5. Carga capada al 70% RM para proteger el sistema nervioso."
                        act.save()
                        snc_mutated = True
                if snc_mutated:
                    mensajes_ui.append(
                        f"⚡ {nombre}: Detecto fatiga nerviosa acumulada (3 sesiones seguidas con RPE > 8.5). "
                        f"He capado la próxima sesión de fuerza al 70% RM. El SNC necesita margen para recuperarse antes de la competición."
                    )

        # --- TRIGGER 5: SOBRECARGA PROGRESIVA (cumplimiento alto + RPE sostenible) ---
        # Si el atleta completó ≥ 90% del plan con RPE ≤ 7 dos sesiones seguidas,
        # la carga planificada es demasiado baja → subir 5-8% en la siguiente sesión.
        cumplimiento = sesion_completada.cumplimiento_ratio
        if cumplimiento is not None and cumplimiento >= 0.90 and rpe is not None and rpe <= 7:
            prev_sesion = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='completado',
                fecha__lt=sesion_completada.fecha
            ).order_by('-fecha').first()

            prev_cumplimiento = getattr(prev_sesion, 'cumplimiento_ratio', None) if prev_sesion else None
            prev_rpe = getattr(prev_sesion, 'rpe_global', None) if prev_sesion else None

            if (prev_cumplimiento is not None and prev_cumplimiento >= 0.90
                    and prev_rpe is not None and prev_rpe <= 7):
                # Dos sesiones seguidas con cumplimiento ≥ 90% y RPE ≤ 7 → progresión
                next_sesion = HyroxSession.objects.filter(
                    objective=sesion_completada.objective,
                    estado='planificado',
                    fecha__gt=sesion_completada.fecha,
                ).order_by('fecha').first()

                if next_sesion:
                    factor = 1.07  # +7%
                    progresion_mutated = False
                    for act in next_sesion.activities.all():
                        m = act.data_metricas or {}
                        mutated = False
                        if 'series' in m:
                            for serie in m['series']:
                                if 'peso_kg' in serie:
                                    serie['peso_kg'] = round(float(serie['peso_kg']) * factor, 1)
                                    mutated = True
                                elif 'reps' in serie:
                                    # Sin peso: aumentar reps en 1
                                    serie['reps'] = int(serie['reps']) + 1
                                    mutated = True
                        if 'distancia_km' in m:
                            m['distancia_km'] = round(float(m['distancia_km']) * factor, 2)
                            mutated = True
                        if mutated:
                            notas = m.get('notas', '')
                            m['notas'] = (notas + f" | 📈 Progresión +7%: cumplimiento ≥90% y RPE≤7 dos sesiones seguidas.").strip(' |')
                            act.data_metricas = m
                            act.save()
                            progresion_mutated = True

                    if progresion_mutated:
                        mensajes_ui.append(
                            f"📈 {nombre}: Excelente consistencia. Completaste el plan al {int(cumplimiento*100)}% "
                            f"con RPE {rpe} dos semanas seguidas. He incrementado un 7% la carga del "
                            f"{next_sesion.fecha.strftime('%d/%m')} para seguir progresando."
                        )

        # --- TRIGGER 6: ACWR ZONA ROJA (riesgo lesión por pico de carga) ---
        # ACWR > 1.5 indica que la carga reciente duplica la crónica → alto riesgo lesión.
        # Actuamos con reducción preventiva + alerta al usuario.
        acwr = HyroxLoadManager.get_acwr(sesion_completada.objective)
        if acwr is not None and acwr > 1.5:
            proxima_acwr = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='planificado',
                fecha__gt=sesion_completada.fecha,
            ).order_by('fecha').first()

            if proxima_acwr:
                acwr_mutated = False
                for act in proxima_acwr.activities.all():
                    m = act.data_metricas or {}
                    mutated = False
                    if 'series' in m:
                        for serie in m['series']:
                            if 'peso_kg' in serie:
                                serie['peso_kg'] = round(float(serie['peso_kg']) * 0.85, 1)
                                mutated = True
                            if 'reps' in serie:
                                serie['reps'] = max(1, round(int(serie['reps']) * 0.85))
                                mutated = True
                    if 'distancia_km' in m:
                        m['distancia_km'] = round(float(m['distancia_km']) * 0.85, 2)
                        mutated = True
                    if mutated:
                        notas = m.get('notas', '')
                        m['notas'] = (notas + f" | ⚠️ ACWR {acwr}: carga reciente excede la crónica. Reducción preventiva -15%.").strip(' |')
                        act.data_metricas = m
                        act.save()
                        acwr_mutated = True

                if acwr_mutated:
                    mensajes_ui.append(
                        f"⚠️ {nombre}: Tu ratio carga-aguda/crónica es {acwr} (límite seguro: 1.3). "
                        f"El riesgo de lesión se dispara en esta zona. He reducido un 15% la sesión "
                        f"del {proxima_acwr.fecha.strftime('%d/%m')} para devolverte al rango óptimo."
                    )

        # --- TRIGGER 7: SUEÑO DEFICIENTE CRÓNICO ---
        # Si el sueño reciente es muy deficiente, reducir carga preventivamente.
        sleep_penalty = HyroxLoadManager.get_sleep_penalty(sesion_completada.objective, dias=7)
        if sleep_penalty >= 4.0:
            proxima_sleep = HyroxSession.objects.filter(
                objective=sesion_completada.objective,
                estado='planificado',
                fecha__gt=sesion_completada.fecha,
            ).order_by('fecha').first()
            if proxima_sleep:
                sleep_mutated = False
                for act in proxima_sleep.activities.all():
                    m = dict(act.data_metricas or {})
                    mutated = False
                    if 'series' in m:
                        for serie in m['series']:
                            if 'peso_kg' in serie:
                                serie['peso_kg'] = round(float(serie['peso_kg']) * 0.90, 1)
                                mutated = True
                    if 'distancia_km' in m:
                        m['distancia_km'] = round(float(m['distancia_km']) * 0.90, 1)
                        mutated = True
                    if mutated:
                        notas = m.get('notas', '')
                        if 'Ajuste sueño' not in notas:
                            m['notas'] = (notas + f" | 😴 Ajuste sueño: déficit crónico detectado (penalización {sleep_penalty}). Carga -10%.").strip(' |')
                        act.data_metricas = m
                        act.save()
                        sleep_mutated = True
                if sleep_mutated:
                    mensajes_ui.append(
                        f"😴 {nombre}: El análisis de tu sueño reciente indica déficit crónico. "
                        f"He reducido un 10% la carga de la sesión del {proxima_sleep.fecha.strftime('%d/%m')} "
                        f"para optimizar la recuperación."
                    )

        # --- TRIGGER 8: DURACIÓN REAL VS PLANIFICADA (tiempo_s por ejercicio) ---
        # Si el atleta tarda >30% más de lo planificado en los ejercicios,
        # añadir una nota de ajuste a la próxima sesión.
        actividades_con_tiempo = [
            a for a in sesion_completada.activities.all()
            if (a.data_metricas or {}).get('tiempo_s', 0) > 0
        ]
        if actividades_con_tiempo and sesion_completada.tiempo_total_minutos:
            total_ejercicios_s  = sum(int(a.data_metricas['tiempo_s']) for a in actividades_con_tiempo)
            total_planificado_s = sesion_completada.tiempo_total_minutos * 60
            if total_planificado_s > 0:
                ratio_duracion = total_ejercicios_s / total_planificado_s
                if ratio_duracion > 1.30:
                    proxima_larga = HyroxSession.objects.filter(
                        objective=sesion_completada.objective,
                        estado='planificado',
                        fecha__gt=sesion_completada.fecha,
                    ).order_by('fecha').first()
                    if proxima_larga:
                        for act in proxima_larga.activities.all():
                            m = dict(act.data_metricas or {})
                            notas = m.get('notas', '')
                            if 'Ajuste duración' not in notas:
                                m['notas'] = (notas + (
                                    f" | ⏱ Ajuste duración: la sesión anterior ocupó {int(ratio_duracion*100)}% "
                                    f"del tiempo planificado. Acorta pausas o reduce series si el tiempo es limitante."
                                )).strip(' |')
                                act.data_metricas = m
                                act.save()
                    mensajes_ui.append(
                        f"⏱ {nombre}: Tus ejercicios ocuparon el {int(ratio_duracion*100)}% del tiempo total planificado. "
                        f"He añadido una nota en la próxima sesión para ajustar los tiempos de descanso."
                    )

        return mensajes_ui

    # ─────────────────────────────────────────────────────────────────────────
    # ESCALA DE VOLUMEN POR ENERGÍA PRE-ENTRENO
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def scale_volume_by_energy(sesion: HyroxSession):
        """
        Escala el volumen de la sesión según energía pre-entreno y carga externa del gym.
        - energia < 5:   70% volumen (energía crítica)
        - energia 5-6:   85% volumen (energía moderada-baja, tier nuevo)
        - energia 7-8:   sin cambio
        - energia > 8:   sugerencia de subir ritmo
        Además lee ActividadRealizada para detectar fatiga acumulada del gym.
        """
        if sesion.nivel_energia_pre is None:
            return False

        is_mutated = False
        energia = sesion.nivel_energia_pre

        # Carga externa gym (últimos 3 días)
        gym_load = HyroxTrainingEngine._get_gym_external_load(
            sesion.objective.cliente, dias=3
        )
        gym_aviso = ""
        if gym_load['fatiga_gym'] == 'Alta':
            gym_aviso = (
                f" | ⚠️ Gym detectado: {gym_load['entrenos_count']} sesiones últimos 3 días "
                f"(vol. {gym_load['volumen_total_kg']} kg, RPE {gym_load['rpe_medio_gym']}). "
                f"Prioriza técnica sobre carga absoluta hoy."
            )
        elif gym_load['fatiga_gym'] == 'Media' and gym_load['rpe_medio_gym'] > 6.5:
            gym_aviso = (
                f" | 📊 Gym moderado detectado. Carga acumulada de {gym_load['volumen_total_kg']} kg "
                f"esta semana. Escucha el cuerpo en los primeros sets."
            )

        if energia < 5:
            ajuste_notas = "📉 Ajuste por Energía Baja (70% Volumen)"
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
                        act.data_metricas['notas'] = f"{notas_actuales} | {ajuste_notas}{gym_aviso}".strip(" |")
                    act.save()
                    is_mutated = True

        elif energia <= 6:
            # Nuevo tier: energía moderada-baja → 85% volumen, 90% carga
            ajuste_notas = "📉 Ajuste por Energía Moderada-Baja (85% Volumen)"
            for act in sesion.activities.all():
                mutated_act = False
                if 'series' in act.data_metricas:
                    for serie in act.data_metricas['series']:
                        if 'reps' in serie:
                            serie['reps'] = max(1, round(int(serie['reps']) * 0.85))
                            mutated_act = True
                        if 'peso_kg' in serie:
                            serie['peso_kg'] = max(1, round(float(serie['peso_kg']) * 0.90))
                            mutated_act = True
                if 'distancia_km' in act.data_metricas:
                    act.data_metricas['distancia_km'] = round(float(act.data_metricas['distancia_km']) * 0.85, 1)
                    mutated_act = True
                if mutated_act:
                    notas_actuales = act.data_metricas.get('notas', '')
                    if "Ajuste" not in notas_actuales:
                        act.data_metricas['notas'] = f"{notas_actuales} | {ajuste_notas}{gym_aviso}".strip(" |")
                    act.save()
                    is_mutated = True

        elif energia > 8:
            ajuste_notas = "🔥 Energía Óptima: Considera subir el ritmo o carga en la última serie."
            for act in sesion.activities.all():
                notas_actuales = act.data_metricas.get('notas', '')
                if "Energía Óptima" not in notas_actuales:
                    act.data_metricas['notas'] = f"{notas_actuales} | {ajuste_notas}{gym_aviso}".strip(" |")
                    act.save()
                    is_mutated = True

        elif gym_aviso:
            # Energía normal (7-8) pero hay fatiga de gym: solo añadir aviso sin reducir volumen
            for act in sesion.activities.all():
                notas_actuales = act.data_metricas.get('notas', '')
                if "Gym detectado" not in notas_actuales and "Gym moderado" not in notas_actuales:
                    act.data_metricas['notas'] = f"{notas_actuales}{gym_aviso}".strip(" |")
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
        restricted_tags=None,
        retorno_tags=None,
        rpe_acumulado=None,
        tsb=None,
        sleep_penalty=0.0,
    ):
        """
        Crea la sesión y sus actividades planificadas basadas en el template,
        escaladas a los RM del usuario, nivel de experiencia, semana del macrociclo
        y estado de forma objetivo (TSB).
        """
        if HyroxSession.objects.filter(objective=objective, fecha=fecha).exists():
            return

        restricted_tags = restricted_tags or set()
        retorno_tags    = retorno_tags or set()
        nivel           = getattr(objective, 'nivel_experiencia', 'intermedio') or 'intermedio'
        nombre_cliente  = objective.cliente.nombre
        vol             = _VOLUMEN_POR_NIVEL.get(nivel, _VOLUMEN_POR_NIVEL['intermedio'])

        # Prescripción de zona cardíaca para esta sesión
        prescripcion_zona = HyroxLoadManager.get_prescripcion_zona(
            template, objective, is_taper, is_deload
        )

        sesion = HyroxSession.objects.create(
            objective=objective,
            fecha=fecha,
            titulo=titulo,
            estado='planificado'
        )

        rm_squat    = objective.rm_sentadilla  or 60.0
        rm_deadlift = objective.rm_peso_muerto or 80.0

        # Calibrar RM desde rendimiento reciente si hay datos más actualizados
        if template != 'calibracion':
            curva_sq = HyroxLoadManager.get_progression_curve(objective, 'fuerza', 'sentadilla', semanas=6)
            if curva_sq:
                max_real_sq = max(p['valor'] for p in curva_sq)
                # Si el atleta ha levantado >90% del RM registrado, estimar RM actualizado
                if max_real_sq > rm_squat * 0.90:
                    rm_squat = max(rm_squat, round(max_real_sq / 0.85))
            curva_dl = HyroxLoadManager.get_progression_curve(objective, 'fuerza', 'muerto', semanas=6)
            if curva_dl:
                max_real_dl = max(p['valor'] for p in curva_dl)
                if max_real_dl > rm_deadlift * 0.90:
                    rm_deadlift = max(rm_deadlift, round(max_real_dl / 0.85))

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

            # Progresión de % RM: calendario + RPE + TSB + sueño
            porcentaje_rm = HyroxTrainingEngine._calcular_porcentaje_rm(
                week, weeks_to_plan, is_deload, is_taper,
                rpe_acumulado=rpe_acumulado, tsb=tsb, sleep_penalty=sleep_penalty
            )

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

            # Ajuste RETORNO: lesión en fase de reincorporación → -15% de carga
            _retorno_pierna = {'impacto_vertical', 'flexion_rodilla_profunda', 'empuje_pierna',
                               'flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo'}
            if retorno_tags and any(tag in retorno_tags for tag in _retorno_pierna):
                peso_trabajo *= 0.85
                notas_ej += ' | ⚕️ Fase RETORNO: carga reducida al 85% como precaución biomecánica.'

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

            # Coach tip personalizado con zona cardíaca real
            edad         = getattr(objetivo := objective.cliente, 'edad', None)
            if not edad:
                try:
                    edad = (timezone.now().date() - objective.cliente.fecha_nacimiento).days // 365
                except Exception:
                    edad = 35
            reserva_reps = '2' if rpe_target <= 8 else '1'
            tsb_estado   = HyroxLoadManager.get_estado_forma(tsb)
            coach_tip    = (
                f"{nombre_cliente}, estamos en {fase_nombre} ({round(porcentaje_rm * 100)} % RM). "
                f"Hoy buscamos RPE {rpe_target}, guarda {reserva_reps} rep en reserva. "
                f"Forma actual: {tsb_estado['estado']}. {prescripcion_zona}."
            )
            if tsb is not None and tsb < -20:
                coach_tip += " ⚠️ Fatiga acumulada detectada: reduce el peso si notas que el cuerpo no responde."
            if edad and edad >= 45:
                coach_tip += (
                    f" ⚠️ Ajuste (+40): Calentamiento articular estricto de 10 min antes de la primera serie "
                    f"efectiva a {round(peso_trabajo)} kg. Cuida la excéntrica (2 s de bajada)."
                )
            elif edad and edad <= 25:
                coach_tip += " Máxima explosividad concéntrica aprovechando tu recuperación de SNC."

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
                    "zona_cardiaca":  prescripcion_zona,
                    "tsb_al_planificar": tsb,
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

            # Zona cardíaca real en lpm
            zona_cardio = HyroxLoadManager.get_zona_para_template('cardio', is_taper, is_deload)
            fc_max_obj  = HyroxLoadManager.get_fc_max(objective)
            low_z, high_z = HyroxLoadManager.ZONAS_FC[zona_cardio]
            lpm_min = round(fc_max_obj * low_z)
            lpm_max = round(fc_max_obj * min(high_z, 1.0))

            if ritmos:
                zona_nombre = HyroxLoadManager.ZONA_INFO[zona_cardio]['nombre']
                nota_ritmo  = (
                    f"Ritmo objetivo {zona_cardio} ({zona_nombre}): {ritmos['ritmo_z2']} · "
                    f"FC {lpm_min}-{lpm_max} lpm. "
                    f"Referencia tempo: {ritmos['ritmo_tempo']}. "
                    f"Si tu FC sube de {lpm_max} lpm, baja el ritmo aunque el pace sea lento."
                )
                ritmo_guardar = ritmos['ritmo_z2']
            else:
                nota_ritmo    = (
                    f"Mantener FC en {zona_cardio} ({lpm_min}-{lpm_max} lpm). "
                    f"Sin tiempo 5K registrado — calibra por pulsaciones."
                )
                ritmo_guardar = None

            metricas = {
                "planificado":    True,
                "distancia_km":   distancia if not is_sub else round(distancia * 0.8, 1),
                "zona_objetivo":  zona_cardio,
                "fc_min_lpm":     lpm_min,
                "fc_max_lpm":     lpm_max,
                "notas":          (
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
            pesos = HyroxTrainingEngine._pesos_progresivos(
                objective.categoria, week, weeks_to_plan,
                is_deload, is_taper, nivel, rpe_acumulado, tsb
            )

            # Wall Balls: reps objetivo progresivos (de parciales a 100 reps)
            wb_reps_max = {'principiante': 15, 'intermedio': 25, 'avanzado': 30}.get(nivel, 25)
            progreso_wb = week / max(weeks_to_plan - 1, 1)
            wb_reps = max(8, round(8 + progreso_wb * (wb_reps_max - 8)))
            if is_deload or is_taper:
                wb_reps = max(6, round(wb_reps * 0.60))

            nota_progresion = (
                f"Peso de trabajo: {round(pesos['factor']*100)}% del oficial "
                f"({pesos['oficiales']['sled_push']} kg sled / "
                f"{pesos['oficiales']['sandbag']} kg sandbag / "
                f"{pesos['oficiales']['wall_ball']} kg WB). "
                f"Progresión automática hacia el peso de competición."
            )

            estaciones = [
                {
                    'nombre': 'Sled Push',
                    'distancia_m': 50,
                    'peso_kg': pesos['sled_push'],
                    'coach_tip': f"Peso hoy: {pesos['sled_push']} kg → oficial: {pesos['oficiales']['sled_push']} kg",
                    'tags': ['empuje_pierna', 'carga_distal_pierna'],
                },
                {
                    'nombre': 'Wall Balls',
                    'series': [{"reps": wb_reps, "peso_kg": pesos['wall_ball']} for _ in range(3)],
                    'coach_tip': f"{wb_reps} reps × {pesos['wall_ball']} kg (oficial: {pesos['oficiales']['wall_ball']} kg / 100 reps)",
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda'],
                },
                {
                    'nombre': 'Burpees Broad Jump',
                    'distancia_m': 80,
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'triple_extension_explosiva'],
                },
                {
                    'nombre': 'Sandbag Lunges',
                    'distancia_m': 80,
                    'peso_kg': pesos['sandbag'],
                    'coach_tip': f"Peso hoy: {pesos['sandbag']} kg → oficial: {pesos['oficiales']['sandbag']} kg",
                    'tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'estabilidad_tobillo'],
                },
                {
                    'nombre': 'Farmers Carry',
                    'distancia_m': 200,
                    'peso_kg': pesos['farmers'],
                    'coach_tip': f"{pesos['farmers']} kg/mano → oficial: {pesos['oficiales']['farmers']} kg/mano",
                    'tags': ['lumbar_carga'],
                },
            ]

            for est in estaciones:
                if restricted_tags and any(tag in restricted_tags for tag in est.get('tags', [])):
                    logger.info(f"Bio-Safe: Saltando {est['nombre']} por restricciones biomecánicas.")
                    continue
                nombre_est = est.pop('nombre')
                tags_est   = est.pop('tags', None)
                HyroxActivity.objects.create(
                    sesion=sesion,
                    tipo_actividad='hyrox_station',
                    nombre_ejercicio=nombre_est,
                    data_metricas={"planificado": True, **est}
                )

        # ── SIMULACIÓN ────────────────────────────────────────────────────────
        elif template == 'simulacion':
            if not is_taper and not is_deload:
                is_sub = 'impacto_vertical' in restricted_tags or 'carrera' in restricted_tags
                pesos  = HyroxTrainingEngine._pesos_progresivos(
                    objective.categoria, week, weeks_to_plan,
                    False, False, nivel, rpe_acumulado, tsb
                )

                dist_carrera = HyroxTrainingEngine._distancia_carrera(nivel, week, weeks_to_plan, False, False)
                dist_tramo   = round(min(dist_carrera * 0.35, 2.0), 1)

                # Wall Balls en simulación: 50 reps (subimos progresivamente a 100)
                progreso_sim = week / max(weeks_to_plan - 1, 1)
                wb_sim_reps  = max(15, round(15 + progreso_sim * 85))  # 15 → 100

                segmentos = [
                    {
                        'tipo': 'cardio_sustituto' if is_sub else 'carrera',
                        'nombre': f"{'Remo / SkiErg' if is_sub else 'Carrera'} Tramo 1",
                        'metricas': {"planificado": True, "distancia_km": dist_tramo},
                    },
                    {
                        'tipo': 'hyrox_station',
                        'nombre': 'Sled Push',
                        'metricas': {
                            "planificado": True, "distancia_m": 50,
                            "peso_kg": pesos['sled_push'],
                            "coach_tip": f"{pesos['sled_push']} kg → oficial {pesos['oficiales']['sled_push']} kg",
                        },
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
                        'metricas': {
                            "planificado": True, "distancia_m": 25,
                            "peso_kg": pesos['sled_pull'],
                            "coach_tip": f"{pesos['sled_pull']} kg → oficial {pesos['oficiales']['sled_pull']} kg",
                        },
                    },
                    {
                        'tipo': 'cardio_sustituto' if is_sub else 'carrera',
                        'nombre': f"{'Remo / SkiErg' if is_sub else 'Carrera'} Tramo 3",
                        'metricas': {"planificado": True, "distancia_km": dist_tramo},
                    },
                    {
                        'tipo': 'hyrox_station',
                        'nombre': 'Wall Balls',
                        'metricas': {
                            "planificado": True,
                            "series": [{"reps": wb_sim_reps, "peso_kg": pesos['wall_ball']}],
                            "coach_tip": f"{wb_sim_reps} reps × {pesos['wall_ball']} kg (objetivo: 100 reps)",
                        },
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
