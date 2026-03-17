"""
Servicio de Evaluación Profesional de Entrenamiento
====================================================
Genera evaluaciones detalladas basadas en principios de periodización,
ciencia del ejercicio y metodologías de entrenadores de élite.

Basado en:
- Dr. Mike Israetel (Renaissance Periodization) - Volumen landmarks
- Eric Helms (3DMJ) - Periodización y RPE
- Greg Nuckols (Stronger by Science) - Progresión y frecuencia
- Brad Schoenfeld - Hipertrofia y frecuencia óptima
- Tim Gabbett - ACWR y gestión de carga

Autor: David (Hotel Puente Romano) - Proyecto Fitness App
"""

from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACIÓN BASADA EN LITERATURA CIENTÍFICA
# =============================================================================

# Volumen Landmarks (Mike Israetel - RP)
# MEV = Minimum Effective Volume, MAV = Maximum Adaptive Volume, MRV = Maximum Recoverable Volume
VOLUME_LANDMARKS = {
    'Pecho':      {'MEV': 8,  'MAV': 12, 'MRV': 22},
    'Espalda':    {'MEV': 8,  'MAV': 14, 'MRV': 25},
    'Hombros':    {'MEV': 6,  'MAV': 12, 'MRV': 22},
    'Cuádriceps': {'MEV': 6,  'MAV': 12, 'MRV': 20},
    'Isquios':    {'MEV': 4,  'MAV': 10, 'MRV': 16},
    'Glúteos':    {'MEV': 0,  'MAV': 8,  'MRV': 16},  # A menudo trabajado indirectamente
    'Bíceps':     {'MEV': 4,  'MAV': 10, 'MRV': 20},
    'Tríceps':    {'MEV': 4,  'MAV': 8,  'MRV': 18},
    'Core':       {'MEV': 0,  'MAV': 8,  'MRV': 16},
}

# Frecuencia óptima por grupo (Schoenfeld meta-análisis)
FRECUENCIA_OPTIMA = {
    'minima': 1,
    'optima_hipertrofia': 2,
    'maxima_recomendada': 4
}

# Zonas de RPE (Eric Helms)
RPE_ZONES = {
    'recuperacion': (1, 5),      # RPE 1-5: Muy ligero, deload
    'acumulacion': (6, 7),       # RPE 6-7: Fase de volumen
    'intensificacion': (8, 9),   # RPE 8-9: Fase de fuerza/peaking
    'maximo': (10, 10)           # RPE 10: Máximo esfuerzo (usar con moderación)
}

# Zonas ACWR (Tim Gabbett)
ACWR_ZONES = {
    'muy_baja': (0, 0.5),
    'baja': (0.5, 0.8),
    'optima': (0.8, 1.3),        # Sweet spot
    'cuidado': (1.3, 1.5),
    'peligro': (1.5, float('inf'))
}

# Ratios de fuerza ideales (literatura general powerlifting/atletismo)
RATIOS_IDEALES = {
    'Press Banca / Sentadilla': {'min': 0.55, 'ideal': 0.65, 'max': 0.75},
    'Peso Muerto / Sentadilla': {'min': 1.0, 'ideal': 1.15, 'max': 1.3},
    'Press Militar / Press Banca': {'min': 0.55, 'ideal': 0.65, 'max': 0.75},
    'Remo / Press Banca': {'min': 0.9, 'ideal': 1.0, 'max': 1.1},  # Idealmente igual o superior
}

# Progresión esperada por nivel (% mensual aproximado)
PROGRESION_ESPERADA = {
    'principiante': {'min': 2.0, 'max': 5.0},    # 0-1 año
    'intermedio': {'min': 0.5, 'max': 2.0},      # 1-3 años
    'avanzado': {'min': 0.1, 'max': 0.5},        # 3+ años
}


class EvaluacionProfesionalService:
    """
    Servicio principal de evaluación profesional.
    Genera análisis detallados como un coach de élite.
    """
    
    # =========================================================================
    # MÉTODO PRINCIPAL: Evaluación Completa
    # =========================================================================
    
    @staticmethod
    def generar_evaluacion_completa(cliente, semanas=4):
        """
        Genera una evaluación profesional completa del entrenamiento.
        
        Args:
            cliente: Objeto Cliente de Django
            semanas: Número de semanas a analizar (default 4 = 1 mesociclo)
            
        Returns:
            dict: Evaluación completa con puntuaciones, diagnósticos y recomendaciones
        """
        logger.info(f"🔬 Iniciando evaluación profesional para {cliente.nombre}")
        
        fecha_inicio = timezone.now().date() - timedelta(weeks=semanas)
        
        # Recopilar todas las métricas
        metricas = EvaluacionProfesionalService._recopilar_metricas(cliente, fecha_inicio)
        
        # Si no hay datos suficientes
        if metricas['total_sesiones'] < 3:
            return {
                'evaluacion_posible': False,
                'mensaje': 'Se necesitan al menos 3 sesiones para generar una evaluación significativa.',
                'sesiones_registradas': metricas['total_sesiones']
            }
        
        # Generar evaluaciones por categoría
        evaluacion_volumen = EvaluacionProfesionalService._evaluar_volumen(metricas)
        evaluacion_frecuencia = EvaluacionProfesionalService._evaluar_frecuencia(metricas)
        evaluacion_intensidad = EvaluacionProfesionalService._evaluar_intensidad(metricas)
        evaluacion_progresion = EvaluacionProfesionalService._evaluar_progresion(metricas)
        evaluacion_carga = EvaluacionProfesionalService._evaluar_carga_acwr(metricas)
        evaluacion_equilibrio = EvaluacionProfesionalService._evaluar_equilibrio_muscular(metricas)
        evaluacion_consistencia = EvaluacionProfesionalService._evaluar_consistencia(metricas)
        
        # Calcular puntuación global (0-100)
        puntuacion_global = EvaluacionProfesionalService._calcular_puntuacion_global({
            'volumen': evaluacion_volumen,
            'frecuencia': evaluacion_frecuencia,
            'intensidad': evaluacion_intensidad,
            'progresion': evaluacion_progresion,
            'carga': evaluacion_carga,
            'equilibrio': evaluacion_equilibrio,
            'consistencia': evaluacion_consistencia
        })
        
        # Generar diagnóstico principal y recomendaciones prioritarias
        diagnostico_principal = EvaluacionProfesionalService._generar_diagnostico_principal(
            puntuacion_global,
            evaluacion_volumen,
            evaluacion_frecuencia,
            evaluacion_intensidad,
            evaluacion_progresion,
            evaluacion_carga,
            evaluacion_equilibrio,
            evaluacion_consistencia
        )
        
        recomendaciones = EvaluacionProfesionalService._generar_recomendaciones_priorizadas(
            evaluacion_volumen,
            evaluacion_frecuencia,
            evaluacion_intensidad,
            evaluacion_progresion,
            evaluacion_carga,
            evaluacion_equilibrio,
            evaluacion_consistencia
        )
        
        return {
            'evaluacion_posible': True,
            'fecha_evaluacion': timezone.now(),
            'periodo_analizado': {
                'semanas': semanas,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': timezone.now().date()
            },
            'metricas_raw': metricas,
            'puntuacion_global': puntuacion_global,
            'diagnostico_principal': diagnostico_principal,
            'evaluaciones': {
                'volumen': evaluacion_volumen,
                'frecuencia': evaluacion_frecuencia,
                'intensidad': evaluacion_intensidad,
                'progresion': evaluacion_progresion,
                'carga': evaluacion_carga,
                'equilibrio': evaluacion_equilibrio,
                'consistencia': evaluacion_consistencia
            },
            'recomendaciones': recomendaciones,
            'resumen_ejecutivo': EvaluacionProfesionalService._generar_resumen_ejecutivo(
                puntuacion_global, diagnostico_principal, recomendaciones
            )
        }
    
    # =========================================================================
    # RECOPILACIÓN DE MÉTRICAS
    # =========================================================================
    
    @staticmethod
    def _recopilar_metricas(cliente, fecha_inicio):
        """Recopila todas las métricas necesarias para la evaluación."""
        from entrenos.models import EntrenoRealizado, EjercicioRealizado, SesionEntrenamiento
        
        # Entrenamientos en el período
        entrenos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        )
        
        # Ejercicios realizados
        ejercicios = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        )
        
        # Sesiones de entrenamiento
        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio
        )
        
        # Calcular métricas por grupo muscular
        series_por_grupo = defaultdict(int)
        volumen_por_grupo = defaultdict(float)
        frecuencia_por_grupo = defaultdict(set)  # Set de fechas únicas por grupo
        
        for ej in ejercicios:
            grupo = ej.grupo_muscular or 'Otros'
            series_por_grupo[grupo] += int(ej.series or 1)
            volumen_por_grupo[grupo] += float(ej.peso_kg or 0) * int(ej.series or 1) * int(ej.repeticiones or 1)
            frecuencia_por_grupo[grupo].add(ej.entreno.fecha)
        
        # Convertir frecuencia a días únicos
        dias_entrenamiento = set()
        for e in entrenos:
            dias_entrenamiento.add(e.fecha)
        
        # Calcular semanas en el período
        dias_periodo = (timezone.now().date() - fecha_inicio).days
        semanas_periodo = max(1, dias_periodo / 7)
        
        # Series semanales por grupo
        series_semanales = {g: round(s / semanas_periodo, 1) for g, s in series_por_grupo.items()}
        
        # Frecuencia semanal por grupo (días únicos / semanas)
        frecuencia_semanal = {g: round(len(fechas) / semanas_periodo, 1) for g, fechas in frecuencia_por_grupo.items()}
        
        # RPE datos
        rpe_values = [s.rpe_medio for s in sesiones if s.rpe_medio]
        
        # Progresión por ejercicio principal
        progresion_ejercicios = EvaluacionProfesionalService._calcular_progresion_ejercicios(cliente, fecha_inicio)
        
        return {
            'total_sesiones': entrenos.count(),
            'dias_entrenados': len(dias_entrenamiento),
            'semanas_periodo': semanas_periodo,
            'series_totales': sum(series_por_grupo.values()),
            'series_por_grupo': dict(series_por_grupo),
            'series_semanales_por_grupo': series_semanales,
            'volumen_total': sum(volumen_por_grupo.values()),
            'volumen_por_grupo': dict(volumen_por_grupo),
            'frecuencia_semanal_global': round(len(dias_entrenamiento) / semanas_periodo, 1),
            'frecuencia_semanal_por_grupo': frecuencia_semanal,
            'rpe_promedio': round(sum(rpe_values) / len(rpe_values), 1) if rpe_values else None,
            'rpe_maximo': max(rpe_values) if rpe_values else None,
            'rpe_minimo': min(rpe_values) if rpe_values else None,
            'rpe_distribucion': EvaluacionProfesionalService._calcular_distribucion_rpe(rpe_values),
            'progresion_ejercicios': progresion_ejercicios,
            'acwr': EvaluacionProfesionalService._calcular_acwr_simple(cliente),
            'fechas_entrenamiento': sorted(dias_entrenamiento)
        }
    
    @staticmethod
    def _calcular_progresion_ejercicios(cliente, fecha_inicio):
        """Calcula la progresión de peso en ejercicios principales."""
        from entrenos.models import EjercicioRealizado
        
        # Ejercicios principales a trackear
        ejercicios_principales = [
            'press banca con barra', 'sentadilla trasera con barra',
            'peso muerto', 'press militar con barra'
        ]
        
        progresiones = {}
        
        for ej_nombre in ejercicios_principales:
            registros = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=ej_nombre.split()[0],  # Buscar por palabra clave
                completado=True,
                peso_kg__gt=0
            ).order_by('entreno__fecha')
            
            if registros.count() >= 2:
                primer_registro = registros.first()
                ultimo_registro = registros.last()
                
                peso_inicial = float(primer_registro.peso_kg)
                peso_final = float(ultimo_registro.peso_kg)
                
                dias = (ultimo_registro.entreno.fecha - primer_registro.entreno.fecha).days
                
                if peso_inicial > 0 and dias > 0:
                    cambio_absoluto = peso_final - peso_inicial
                    cambio_porcentual = (cambio_absoluto / peso_inicial) * 100
                    cambio_mensual = (cambio_porcentual / dias) * 30 if dias > 0 else 0
                    
                    progresiones[ej_nombre] = {
                        'peso_inicial': peso_inicial,
                        'peso_final': peso_final,
                        'cambio_kg': round(cambio_absoluto, 1),
                        'cambio_porcentual': round(cambio_porcentual, 1),
                        'cambio_mensual_estimado': round(cambio_mensual, 2),
                        'dias_trackeo': dias,
                        'tendencia': 'subiendo' if cambio_absoluto > 0 else ('bajando' if cambio_absoluto < 0 else 'estable')
                    }
        
        return progresiones
    
    @staticmethod
    def _calcular_distribucion_rpe(rpe_values):
        """Calcula la distribución de RPE en zonas."""
        if not rpe_values:
            return {}
        
        distribucion = {
            'recuperacion': 0,
            'acumulacion': 0,
            'intensificacion': 0,
            'maximo': 0
        }
        
        for rpe in rpe_values:
            if rpe <= 5:
                distribucion['recuperacion'] += 1
            elif rpe <= 7:
                distribucion['acumulacion'] += 1
            elif rpe <= 9:
                distribucion['intensificacion'] += 1
            else:
                distribucion['maximo'] += 1
        
        total = len(rpe_values)
        return {k: round(v / total * 100, 1) for k, v in distribucion.items()}
    
    @staticmethod
    def _calcular_acwr_simple(cliente):
        """Calcula el ACWR de forma simplificada."""
        from entrenos.models import EntrenoRealizado
        
        hoy = timezone.now().date()
        hace_7_dias = hoy - timedelta(days=7)
        hace_28_dias = hoy - timedelta(days=28)
        
        # Carga aguda (última semana)
        carga_aguda = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=hace_7_dias
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0
        
        # Carga crónica (últimas 4 semanas)
        carga_cronica = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=hace_28_dias
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0
        
        # Promedio semanal crónico
        promedio_cronico = carga_cronica / 4 if carga_cronica > 0 else 0
        
        # ACWR
        acwr = round(carga_aguda / promedio_cronico, 2) if promedio_cronico > 0 else 0
        
        # Determinar zona
        zona = 'desconocida'
        for nombre_zona, (min_val, max_val) in ACWR_ZONES.items():
            if min_val <= acwr < max_val:
                zona = nombre_zona
                break
        
        return {
            'valor': acwr,
            'carga_aguda': round(carga_aguda, 0),
            'carga_cronica_semanal': round(promedio_cronico, 0),
            'zona': zona
        }
    
    # =========================================================================
    # EVALUACIONES POR CATEGORÍA
    # =========================================================================
    
    @staticmethod
    def _evaluar_volumen(metricas):
        """Evalúa el volumen de entrenamiento por grupo muscular."""
        series_semanales = metricas.get('series_semanales_por_grupo', {})
        
        evaluaciones = []
        puntuacion_total = 0
        grupos_evaluados = 0
        
        for grupo, landmarks in VOLUME_LANDMARKS.items():
            series = series_semanales.get(grupo, 0)
            mev = landmarks['MEV']
            mav = landmarks['MAV']
            mrv = landmarks['MRV']
            
            # Determinar estado
            if series == 0:
                estado = 'sin_entrenar'
                puntuacion = 0
                mensaje = f"No hay registro de entrenamiento directo para {grupo}."
                severidad = 'info' if grupo in ['Glúteos', 'Core'] else 'warning'
            elif series < mev:
                estado = 'suboptimo'
                puntuacion = 30
                mensaje = f"{grupo}: {series} series/semana está por debajo del MEV ({mev}). Probablemente insuficiente para progresar."
                severidad = 'warning'
            elif series <= mav:
                estado = 'optimo'
                puntuacion = 100
                mensaje = f"{grupo}: {series} series/semana está en el rango óptimo (MEV-MAV: {mev}-{mav})."
                severidad = 'success'
            elif series <= mrv:
                estado = 'alto'
                puntuacion = 70
                mensaje = f"{grupo}: {series} series/semana está entre MAV y MRV ({mav}-{mrv}). Bueno para fases de volumen, pero vigila la recuperación."
                severidad = 'info'
            else:
                estado = 'excesivo'
                puntuacion = 20
                mensaje = f"{grupo}: {series} series/semana excede el MRV ({mrv}). Riesgo alto de sobreentrenamiento."
                severidad = 'danger'
            
            evaluaciones.append({
                'grupo': grupo,
                'series_semanales': series,
                'mev': mev,
                'mav': mav,
                'mrv': mrv,
                'estado': estado,
                'puntuacion': puntuacion,
                'mensaje': mensaje,
                'severidad': severidad
            })
            
            if series > 0:
                puntuacion_total += puntuacion
                grupos_evaluados += 1
        
        puntuacion_promedio = round(puntuacion_total / grupos_evaluados, 1) if grupos_evaluados > 0 else 0
        
        return {
            'puntuacion': puntuacion_promedio,
            'evaluaciones_por_grupo': evaluaciones,
            'grupos_suboptimos': [e for e in evaluaciones if e['estado'] == 'suboptimo'],
            'grupos_excesivos': [e for e in evaluaciones if e['estado'] == 'excesivo'],
            'grupos_optimos': [e for e in evaluaciones if e['estado'] == 'optimo'],
            'resumen': EvaluacionProfesionalService._generar_resumen_volumen(evaluaciones, puntuacion_promedio)
        }
    
    @staticmethod
    def _generar_resumen_volumen(evaluaciones, puntuacion):
        """Genera un resumen textual de la evaluación de volumen."""
        suboptimos = [e['grupo'] for e in evaluaciones if e['estado'] == 'suboptimo']
        excesivos = [e['grupo'] for e in evaluaciones if e['estado'] == 'excesivo']
        optimos = [e['grupo'] for e in evaluaciones if e['estado'] == 'optimo']
        
        if puntuacion >= 80:
            base = "Tu distribución de volumen está bien equilibrada."
        elif puntuacion >= 60:
            base = "Tu volumen general es aceptable pero hay margen de mejora."
        else:
            base = "Tu volumen de entrenamiento necesita ajustes significativos."
        
        detalles = []
        if suboptimos:
            detalles.append(f"Grupos con volumen insuficiente: {', '.join(suboptimos)}.")
        if excesivos:
            detalles.append(f"Grupos con volumen excesivo: {', '.join(excesivos)}.")
        if optimos:
            detalles.append(f"Grupos en rango óptimo: {', '.join(optimos)}.")
        
        return base + " " + " ".join(detalles)
    
    @staticmethod
    def _evaluar_frecuencia(metricas):
        """Evalúa la frecuencia de entrenamiento."""
        frecuencia_global = metricas.get('frecuencia_semanal_global', 0)
        frecuencia_por_grupo = metricas.get('frecuencia_semanal_por_grupo', {})
        
        # Evaluación frecuencia global
        if frecuencia_global < 2:
            estado_global = 'muy_baja'
            puntuacion_global = 30
            mensaje_global = f"Entrenas solo {frecuencia_global} días/semana. Para hipertrofia se recomienda mínimo 3-4 días."
        elif frecuencia_global < 3:
            estado_global = 'baja'
            puntuacion_global = 50
            mensaje_global = f"Frecuencia de {frecuencia_global} días/semana. Aceptable pero subóptimo para máxima hipertrofia."
        elif frecuencia_global <= 5:
            estado_global = 'optima'
            puntuacion_global = 100
            mensaje_global = f"Frecuencia de {frecuencia_global} días/semana. Rango óptimo para la mayoría de objetivos."
        elif frecuencia_global <= 6:
            estado_global = 'alta'
            puntuacion_global = 80
            mensaje_global = f"Frecuencia de {frecuencia_global} días/semana. Alta pero sostenible si la recuperación es adecuada."
        else:
            estado_global = 'muy_alta'
            puntuacion_global = 50
            mensaje_global = f"Entrenas {frecuencia_global} días/semana. Muy alto, asegura descanso adecuado."
        
        # Evaluar frecuencia por grupo muscular
        grupos_frecuencia_baja = []
        grupos_frecuencia_optima = []
        
        for grupo, freq in frecuencia_por_grupo.items():
            if freq < FRECUENCIA_OPTIMA['minima']:
                grupos_frecuencia_baja.append({'grupo': grupo, 'frecuencia': freq})
            elif freq >= FRECUENCIA_OPTIMA['optima_hipertrofia']:
                grupos_frecuencia_optima.append({'grupo': grupo, 'frecuencia': freq})
        
        return {
            'puntuacion': puntuacion_global,
            'frecuencia_global': frecuencia_global,
            'estado': estado_global,
            'mensaje': mensaje_global,
            'frecuencia_por_grupo': frecuencia_por_grupo,
            'grupos_frecuencia_baja': grupos_frecuencia_baja,
            'grupos_frecuencia_optima': grupos_frecuencia_optima,
            'recomendacion_frecuencia': FRECUENCIA_OPTIMA
        }
    
    @staticmethod
    def _evaluar_intensidad(metricas):
        """Evalúa la intensidad del entrenamiento basada en RPE."""
        rpe_promedio = metricas.get('rpe_promedio')
        rpe_distribucion = metricas.get('rpe_distribucion', {})
        
        if rpe_promedio is None:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'No hay datos de RPE registrados. Considera trackear el RPE para mejor análisis.',
                'rpe_promedio': None,
                'distribucion': {}
            }
        
        # Evaluar RPE promedio
        if rpe_promedio < 6:
            estado = 'muy_bajo'
            puntuacion = 50
            mensaje = f"RPE promedio de {rpe_promedio}. Intensidad muy baja, probablemente no estás retando tu cuerpo lo suficiente."
        elif rpe_promedio < 7:
            estado = 'bajo'
            puntuacion = 70
            mensaje = f"RPE promedio de {rpe_promedio}. Bueno para fases de acumulación/volumen."
        elif rpe_promedio <= 8:
            estado = 'optimo'
            puntuacion = 100
            mensaje = f"RPE promedio de {rpe_promedio}. Rango óptimo para la mayoría del entrenamiento."
        elif rpe_promedio <= 9:
            estado = 'alto'
            puntuacion = 80
            mensaje = f"RPE promedio de {rpe_promedio}. Alto pero sostenible en fases de intensificación."
        else:
            estado = 'muy_alto'
            puntuacion = 40
            mensaje = f"RPE promedio de {rpe_promedio}. Muy alto, riesgo de fatiga acumulada y sobreentrenamiento."
        
        # Analizar distribución
        pct_recuperacion = rpe_distribucion.get('recuperacion', 0)
        pct_maximo = rpe_distribucion.get('maximo', 0)
        
        advertencias = []
        if pct_recuperacion < 10 and estado in ['alto', 'muy_alto']:
            advertencias.append("Considera incluir más sesiones de recuperación activa (RPE 5-6).")
        if pct_maximo > 20:
            advertencias.append("Demasiadas sesiones al máximo (RPE 10). Esto limita la recuperación.")
        
        return {
            'puntuacion': puntuacion,
            'estado': estado,
            'mensaje': mensaje,
            'rpe_promedio': rpe_promedio,
            'rpe_maximo': metricas.get('rpe_maximo'),
            'rpe_minimo': metricas.get('rpe_minimo'),
            'distribucion': rpe_distribucion,
            'advertencias': advertencias
        }
    
    @staticmethod
    def _evaluar_progresion(metricas):
        """Evalúa la progresión en los ejercicios principales."""
        progresiones = metricas.get('progresion_ejercicios', {})
        
        if not progresiones:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'No hay suficientes datos para evaluar progresión. Continúa trackeando tus ejercicios principales.',
                'ejercicios': {}
            }
        
        evaluaciones = []
        puntuacion_total = 0
        
        for ejercicio, datos in progresiones.items():
            cambio_mensual = datos['cambio_mensual_estimado']
            
            # Evaluar según nivel (asumimos intermedio por defecto)
            nivel_esperado = PROGRESION_ESPERADA['intermedio']
            
            if cambio_mensual < 0:
                estado = 'regresion'
                puntuacion = 20
                mensaje = f"Regresión de {abs(cambio_mensual):.1f}%/mes. Revisar recuperación, nutrición o técnica."
            elif cambio_mensual < nivel_esperado['min']:
                estado = 'estancado'
                puntuacion = 50
                mensaje = f"Progresión de {cambio_mensual:.1f}%/mes. Por debajo de lo esperado para un intermedio."
            elif cambio_mensual <= nivel_esperado['max']:
                estado = 'normal'
                puntuacion = 100
                mensaje = f"Progresión de {cambio_mensual:.1f}%/mes. Dentro del rango esperado."
            else:
                estado = 'excelente'
                puntuacion = 100
                mensaje = f"Progresión de {cambio_mensual:.1f}%/mes. Excelente, típico de principiante o tras un deload."
            
            evaluaciones.append({
                'ejercicio': ejercicio,
                'datos': datos,
                'estado': estado,
                'puntuacion': puntuacion,
                'mensaje': mensaje
            })
            
            puntuacion_total += puntuacion
        
        puntuacion_promedio = round(puntuacion_total / len(evaluaciones), 1) if evaluaciones else 0
        
        return {
            'puntuacion': puntuacion_promedio,
            'estado': 'evaluado',
            'ejercicios': evaluaciones,
            'ejercicios_en_regresion': [e for e in evaluaciones if e['estado'] == 'regresion'],
            'ejercicios_estancados': [e for e in evaluaciones if e['estado'] == 'estancado'],
            'resumen': EvaluacionProfesionalService._generar_resumen_progresion(evaluaciones)
        }
    
    @staticmethod
    def _generar_resumen_progresion(evaluaciones):
        """Genera resumen de la progresión."""
        if not evaluaciones:
            return "Sin datos de progresión disponibles."
        
        en_regresion = len([e for e in evaluaciones if e['estado'] == 'regresion'])
        estancados = len([e for e in evaluaciones if e['estado'] == 'estancado'])
        progresando = len([e for e in evaluaciones if e['estado'] in ['normal', 'excelente']])
        
        if en_regresion > 0:
            return f"⚠️ {en_regresion} ejercicio(s) en regresión. Prioridad: revisar volumen, recuperación y nutrición."
        elif estancados > progresando:
            return f"📊 Mayoría de ejercicios estancados ({estancados}/{len(evaluaciones)}). Considera variar el estímulo."
        else:
            return f"✅ Buena progresión general ({progresando}/{len(evaluaciones)} ejercicios mejorando)."
    
    @staticmethod
    def _evaluar_carga_acwr(metricas):
        """Evalúa la carga de entrenamiento usando ACWR."""
        acwr_data = metricas.get('acwr', {})
        acwr = acwr_data.get('valor', 0)
        zona = acwr_data.get('zona', 'desconocida')
        
        if zona == 'optima':
            puntuacion = 100
            estado = 'optimo'
            mensaje = f"ACWR de {acwr}. Estás en la zona óptima (0.8-1.3) para maximizar adaptaciones con bajo riesgo de lesión."
        elif zona == 'baja':
            puntuacion = 60
            estado = 'baja'
            mensaje = f"ACWR de {acwr}. Carga por debajo de lo óptimo. Puedes aumentar gradualmente el volumen."
        elif zona == 'muy_baja':
            puntuacion = 40
            estado = 'muy_baja'
            mensaje = f"ACWR de {acwr}. Carga muy baja, probablemente en fase de deload o inicio de programa."
        elif zona == 'cuidado':
            puntuacion = 50
            estado = 'cuidado'
            mensaje = f"ACWR de {acwr}. Zona de precaución (1.3-1.5). Vigila señales de fatiga."
        elif zona == 'peligro':
            puntuacion = 20
            estado = 'peligro'
            mensaje = f"ACWR de {acwr}. ⚠️ Zona de peligro (>1.5). Alto riesgo de lesión. Reduce la carga inmediatamente."
        else:
            puntuacion = None
            estado = 'sin_datos'
            mensaje = "No hay suficientes datos para calcular ACWR."
        
        return {
            'puntuacion': puntuacion,
            'acwr': acwr,
            'zona': zona,
            'estado': estado,
            'mensaje': mensaje,
            'carga_aguda': acwr_data.get('carga_aguda', 0),
            'carga_cronica_semanal': acwr_data.get('carga_cronica_semanal', 0),
            'zonas_referencia': ACWR_ZONES
        }
    
    @staticmethod
    def _evaluar_equilibrio_muscular(metricas):
        """Evalúa el equilibrio entre grupos musculares antagonistas."""
        from entrenos.services.estadisticas_service import EstadisticasService
        
        # Usar el servicio existente para obtener 1RM estimados
        # (Esto asume que el cliente está disponible en el contexto)
        # Por simplicidad, evaluamos basándonos en el volumen relativo
        
        volumen_por_grupo = metricas.get('volumen_por_grupo', {})
        
        # Calcular ratios de volumen (aproximación)
        pecho = volumen_por_grupo.get('Pecho', 0)
        espalda = volumen_por_grupo.get('Espalda', 0)
        cuadriceps = volumen_por_grupo.get('Cuádriceps', 0)
        isquios = volumen_por_grupo.get('Isquios', 0)
        
        evaluaciones = []
        puntuacion_total = 0
        evaluaciones_count = 0
        
        # Ratio empuje/tracción (idealmente tracción >= empuje)
        if pecho > 0 and espalda > 0:
            ratio_traccion_empuje = espalda / pecho
            if ratio_traccion_empuje >= 1.0:
                estado = 'equilibrado'
                puntuacion = 100
                mensaje = f"Ratio tracción/empuje: {ratio_traccion_empuje:.2f}. Bien equilibrado."
            elif ratio_traccion_empuje >= 0.8:
                estado = 'aceptable'
                puntuacion = 70
                mensaje = f"Ratio tracción/empuje: {ratio_traccion_empuje:.2f}. Ligeramente desbalanceado hacia empuje."
            else:
                estado = 'desequilibrado'
                puntuacion = 40
                mensaje = f"Ratio tracción/empuje: {ratio_traccion_empuje:.2f}. Desequilibrio significativo. Aumenta trabajo de espalda."
            
            evaluaciones.append({
                'tipo': 'traccion_empuje',
                'ratio': round(ratio_traccion_empuje, 2),
                'estado': estado,
                'puntuacion': puntuacion,
                'mensaje': mensaje
            })
            puntuacion_total += puntuacion
            evaluaciones_count += 1
        
        # Ratio cuádriceps/isquios (idealmente isquios ~60-70% de cuádriceps)
        if cuadriceps > 0 and isquios > 0:
            ratio_isquios_cuads = isquios / cuadriceps
            if 0.5 <= ratio_isquios_cuads <= 0.8:
                estado = 'equilibrado'
                puntuacion = 100
                mensaje = f"Ratio isquios/cuádriceps: {ratio_isquios_cuads:.2f}. Bien equilibrado."
            elif ratio_isquios_cuads < 0.5:
                estado = 'desequilibrado'
                puntuacion = 50
                mensaje = f"Ratio isquios/cuádriceps: {ratio_isquios_cuads:.2f}. Isquios subentrenados respecto a cuádriceps."
            else:
                estado = 'alto'
                puntuacion = 80
                mensaje = f"Ratio isquios/cuádriceps: {ratio_isquios_cuads:.2f}. Buen énfasis en cadena posterior."
            
            evaluaciones.append({
                'tipo': 'isquios_cuadriceps',
                'ratio': round(ratio_isquios_cuads, 2),
                'estado': estado,
                'puntuacion': puntuacion,
                'mensaje': mensaje
            })
            puntuacion_total += puntuacion
            evaluaciones_count += 1
        
        puntuacion_promedio = round(puntuacion_total / evaluaciones_count, 1) if evaluaciones_count > 0 else None
        
        return {
            'puntuacion': puntuacion_promedio,
            'evaluaciones': evaluaciones,
            'mensaje': "Equilibrio muscular evaluado basándose en distribución de volumen." if evaluaciones else "Insuficientes datos para evaluar equilibrio."
        }
    
    @staticmethod
    def _evaluar_consistencia(metricas):
        """Evalúa la consistencia en el entrenamiento."""
        fechas = metricas.get('fechas_entrenamiento', [])
        semanas = metricas.get('semanas_periodo', 1)
        frecuencia_esperada = 4  # Asumimos objetivo de 4 días/semana
        
        if len(fechas) < 2:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'Insuficientes datos para evaluar consistencia.'
            }
        
        # Calcular gaps entre entrenamientos
        gaps = []
        fechas_sorted = sorted(fechas)
        for i in range(1, len(fechas_sorted)):
            gap = (fechas_sorted[i] - fechas_sorted[i-1]).days
            gaps.append(gap)
        
        gap_promedio = sum(gaps) / len(gaps) if gaps else 0
        gap_maximo = max(gaps) if gaps else 0
        
        # Evaluar
        dias_entrenados = len(fechas)
        dias_esperados = semanas * frecuencia_esperada
        porcentaje_cumplimiento = (dias_entrenados / dias_esperados) * 100 if dias_esperados > 0 else 0
        
        if porcentaje_cumplimiento >= 90:
            puntuacion = 100
            estado = 'excelente'
            mensaje = f"Excelente consistencia: {dias_entrenados} días en {semanas:.1f} semanas ({porcentaje_cumplimiento:.0f}% del objetivo)."
        elif porcentaje_cumplimiento >= 75:
            puntuacion = 80
            estado = 'buena'
            mensaje = f"Buena consistencia: {dias_entrenados} días ({porcentaje_cumplimiento:.0f}% del objetivo)."
        elif porcentaje_cumplimiento >= 50:
            puntuacion = 60
            estado = 'moderada'
            mensaje = f"Consistencia moderada: {dias_entrenados} días ({porcentaje_cumplimiento:.0f}% del objetivo). Hay margen de mejora."
        else:
            puntuacion = 40
            estado = 'baja'
            mensaje = f"Consistencia baja: {dias_entrenados} días ({porcentaje_cumplimiento:.0f}% del objetivo). La adherencia es clave para progresar."
        
        # Advertencia si hay gaps muy grandes
        advertencias = []
        if gap_maximo > 7:
            advertencias.append(f"Se detectó un gap de {gap_maximo} días sin entrenar. La consistencia es más importante que la perfección.")
        
        return {
            'puntuacion': puntuacion,
            'estado': estado,
            'mensaje': mensaje,
            'dias_entrenados': dias_entrenados,
            'gap_promedio': round(gap_promedio, 1),
            'gap_maximo': gap_maximo,
            'porcentaje_cumplimiento': round(porcentaje_cumplimiento, 1),
            'advertencias': advertencias
        }
    
    # =========================================================================
    # PUNTUACIÓN GLOBAL Y DIAGNÓSTICO
    # =========================================================================
    
    @staticmethod
    def _calcular_puntuacion_global(evaluaciones):
        """Calcula la puntuación global ponderada."""
        pesos = {
            'volumen': 0.20,
            'frecuencia': 0.15,
            'intensidad': 0.15,
            'progresion': 0.20,
            'carga': 0.10,
            'equilibrio': 0.10,
            'consistencia': 0.10
        }
        
        puntuacion_total = 0
        peso_total = 0
        
        for categoria, peso in pesos.items():
            eval_cat = evaluaciones.get(categoria, {})
            punt = eval_cat.get('puntuacion')
            
            if punt is not None:
                puntuacion_total += punt * peso
                peso_total += peso
        
        # Normalizar si no todas las categorías tienen datos
        if peso_total > 0:
            return round((puntuacion_total / peso_total), 1)
        return 0
    
    @staticmethod
    def _generar_diagnostico_principal(puntuacion, ev_vol, ev_freq, ev_int, ev_prog, ev_carga, ev_eq, ev_cons):
        """Genera el diagnóstico principal basado en todas las evaluaciones."""
        
        if puntuacion >= 85:
            nivel = 'excelente'
            emoji = '🏆'
            titulo = 'Entrenamiento de Élite'
            descripcion = 'Tu programa de entrenamiento está muy bien estructurado. Estás aplicando principios científicos correctamente.'
        elif puntuacion >= 70:
            nivel = 'bueno'
            emoji = '✅'
            titulo = 'Buen Programa'
            descripcion = 'Tu entrenamiento es sólido con algunos puntos de mejora identificados.'
        elif puntuacion >= 55:
            nivel = 'mejorable'
            emoji = '📊'
            titulo = 'Programa Mejorable'
            descripcion = 'Hay varios aspectos que podrían optimizarse para maximizar tus resultados.'
        else:
            nivel = 'revisar'
            emoji = '⚠️'
            titulo = 'Requiere Revisión'
            descripcion = 'Se identificaron múltiples áreas que necesitan atención para un programa efectivo.'
        
        # Identificar el problema principal
        problemas = []
        
        if ev_carga.get('estado') == 'peligro':
            problemas.append(('Carga excesiva (ACWR)', 'critico'))
        if ev_vol.get('grupos_excesivos'):
            problemas.append(('Volumen excesivo en algunos grupos', 'alto'))
        if ev_prog.get('ejercicios_en_regresion'):
            problemas.append(('Regresión en ejercicios principales', 'alto'))
        if ev_cons.get('estado') == 'baja':
            problemas.append(('Baja consistencia', 'medio'))
        if ev_vol.get('grupos_suboptimos'):
            problemas.append(('Volumen insuficiente en algunos grupos', 'medio'))
        
        return {
            'nivel': nivel,
            'emoji': emoji,
            'titulo': titulo,
            'descripcion': descripcion,
            'puntuacion': puntuacion,
            'problemas_identificados': problemas
        }
    
    @staticmethod
    def _generar_recomendaciones_priorizadas(ev_vol, ev_freq, ev_int, ev_prog, ev_carga, ev_eq, ev_cons):
        """Genera recomendaciones ordenadas por prioridad."""
        recomendaciones = []
        
        # PRIORIDAD 1: Seguridad (ACWR)
        if ev_carga.get('estado') == 'peligro':
            recomendaciones.append({
                'prioridad': 1,
                'categoria': 'seguridad',
                'icono': '🚨',
                'titulo': 'Reducir carga inmediatamente',
                'descripcion': 'Tu ratio ACWR indica alto riesgo de lesión. Reduce el volumen un 30-40% esta semana.',
                'accion': 'Implementar semana de deload'
            })
        
        # PRIORIDAD 2: Regresión
        if ev_prog.get('ejercicios_en_regresion'):
            ejercicios = [e['ejercicio'] for e in ev_prog['ejercicios_en_regresion']]
            recomendaciones.append({
                'prioridad': 2,
                'categoria': 'progresion',
                'icono': '📉',
                'titulo': 'Atender regresión en ejercicios',
                'descripcion': f'Ejercicios en regresión: {", ".join(ejercicios)}. Revisa técnica, recuperación y nutrición.',
                'accion': 'Reducir volumen temporalmente y enfocarse en calidad'
            })
        
        # PRIORIDAD 3: Consistencia
        if ev_cons.get('estado') in ['baja', 'moderada']:
            recomendaciones.append({
                'prioridad': 3,
                'categoria': 'adherencia',
                'icono': '📅',
                'titulo': 'Mejorar consistencia',
                'descripcion': 'La adherencia es el factor #1 para resultados. Prioriza entrenamientos más cortos pero consistentes.',
                'accion': f'Objetivo: entrenar al menos {max(3, ev_cons.get("dias_entrenados", 0) + 1)} días por semana'
            })
        
        # PRIORIDAD 4: Volumen subóptimo
        grupos_sub = ev_vol.get('grupos_suboptimos', [])
        if grupos_sub:
            grupos_nombres = [g['grupo'] for g in grupos_sub[:3]]
            recomendaciones.append({
                'prioridad': 4,
                'categoria': 'volumen',
                'icono': '📦',
                'titulo': 'Aumentar volumen en grupos rezagados',
                'descripcion': f'Grupos con volumen insuficiente: {", ".join(grupos_nombres)}.',
                'accion': 'Añadir 2-4 series semanales por grupo'
            })
        
        # PRIORIDAD 5: Equilibrio muscular
        desequilibrios = [e for e in ev_eq.get('evaluaciones', []) if e.get('estado') == 'desequilibrado']
        if desequilibrios:
            for d in desequilibrios:
                recomendaciones.append({
                    'prioridad': 5,
                    'categoria': 'equilibrio',
                    'icono': '⚖️',
                    'titulo': f'Corregir desequilibrio: {d["tipo"]}',
                    'descripcion': d['mensaje'],
                    'accion': 'Ajustar proporción de ejercicios'
                })
        
        # PRIORIDAD 6: Intensidad
        if ev_int.get('estado') == 'muy_bajo':
            recomendaciones.append({
                'prioridad': 6,
                'categoria': 'intensidad',
                'icono': '🔥',
                'titulo': 'Aumentar intensidad',
                'descripcion': 'Tu RPE promedio es muy bajo. Estás dejando repeticiones en reserva.',
                'accion': 'Trabaja más cerca del fallo (RPE 7-9 en series efectivas)'
            })
        elif ev_int.get('estado') == 'muy_alto':
            recomendaciones.append({
                'prioridad': 6,
                'categoria': 'intensidad',
                'icono': '😤',
                'titulo': 'Moderar intensidad',
                'descripcion': 'Tu RPE promedio es muy alto. Esto limita la recuperación y el volumen total.',
                'accion': 'Reserva el RPE 9-10 solo para las últimas series'
            })
        
        return sorted(recomendaciones, key=lambda x: x['prioridad'])
    
    @staticmethod
    def _generar_resumen_ejecutivo(puntuacion, diagnostico, recomendaciones):
        """Genera un resumen ejecutivo para mostrar en el dashboard."""
        
        # Top 3 recomendaciones
        top_recomendaciones = recomendaciones[:3]
        
        resumen = {
            'puntuacion': puntuacion,
            'nivel': diagnostico['nivel'],
            'titulo': f"{diagnostico['emoji']} {diagnostico['titulo']}",
            'descripcion': diagnostico['descripcion'],
            'acciones_inmediatas': [r['titulo'] for r in top_recomendaciones],
            'mensaje_motivacional': EvaluacionProfesionalService._generar_mensaje_motivacional(puntuacion)
        }
        
        return resumen
    
    @staticmethod
    def _generar_mensaje_motivacional(puntuacion):
        """Genera un mensaje motivacional basado en la puntuación."""
        if puntuacion >= 85:
            return "🎯 Estás entrenando como un profesional. ¡Mantén el rumbo!"
        elif puntuacion >= 70:
            return "💪 Buen trabajo. Pequeños ajustes te llevarán al siguiente nivel."
        elif puntuacion >= 55:
            return "📈 Tienes una base sólida. Enfócate en las recomendaciones y verás mejoras significativas."
        else:
            return "🌱 Cada experto fue alguna vez un principiante. Los ajustes sugeridos marcarán una gran diferencia."
