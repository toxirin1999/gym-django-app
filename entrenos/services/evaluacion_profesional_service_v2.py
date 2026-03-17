"""
Servicio de Evaluación Profesional de Entrenamiento v2.0
=========================================================
Genera evaluaciones detalladas basadas en principios de periodización,
ciencia del ejercicio y metodologías de entrenadores de élite.

NOVEDADES v2.0:
- Comparativa Plan Helms vs Realidad
- Distribución de RPE en gráfico
- Desglose de puntuación global
- Rangos ideales en ratios de equilibrio
- Tooltips explicativos para métricas
- Mini tendencias históricas

Basado en:
- Dr. Mike Israetel (Renaissance Periodization) - Volumen landmarks
- Eric Helms (3DMJ) - Periodización y RPE
- Greg Nuckols (Stronger by Science) - Progresión y frecuencia
- Brad Schoenfeld - Hipertrofia y frecuencia óptima
- Tim Gabbett - ACWR y gestión de carga
"""

from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURACIÓN Y CONSTANTES CIENTÍFICAS
# =============================================================================

# Volume Landmarks (Mike Israetel - RP)
VOLUME_LANDMARKS = {
    'Pecho': {'MEV': 8, 'MAV': 12, 'MRV': 22},
    'Espalda': {'MEV': 8, 'MAV': 14, 'MRV': 25},
    'Hombros': {'MEV': 6, 'MAV': 12, 'MRV': 22},
    'Cuádriceps': {'MEV': 6, 'MAV': 12, 'MRV': 20},
    'Isquios': {'MEV': 4, 'MAV': 10, 'MRV': 16},
    'Glúteos': {'MEV': 0, 'MAV': 8, 'MRV': 16},
    'Bíceps': {'MEV': 4, 'MAV': 10, 'MRV': 20},
    'Tríceps': {'MEV': 4, 'MAV': 8, 'MRV': 18},
    'Core': {'MEV': 0, 'MAV': 8, 'MRV': 16},
}

# Frecuencia óptima (Schoenfeld meta-análisis)
FRECUENCIA_OPTIMA = {
    'minima': 1,
    'optima_hipertrofia': 2,
    'maxima_recomendada': 4
}

# Zonas ACWR (Tim Gabbett)
ACWR_ZONES = {
    'muy_baja': (0, 0.5),
    'baja': (0.5, 0.8),
    'optima': (0.8, 1.3),
    'cuidado': (1.3, 1.5),
    'peligro': (1.5, float('inf'))
}

# Ratios de equilibrio ideales
RATIOS_IDEALES = {
    'traccion_empuje': {
        'nombre': 'Tracción / Empuje',
        'min': 0.9, 'ideal': 1.0, 'max': 1.2,
        'descripcion': 'Idealmente la tracción (espalda) debería ser igual o mayor que el empuje (pecho)',
        'tooltip': 'Un ratio < 1.0 indica que empujas más de lo que tiras, lo cual puede causar desequilibrios posturales y lesiones de hombro.'
    },
    'isquios_cuadriceps': {
        'nombre': 'Isquios / Cuádriceps',
        'min': 0.5, 'ideal': 0.65, 'max': 0.8,
        'descripcion': 'Los isquios deberían recibir 50-80% del volumen de cuádriceps',
        'tooltip': 'Un ratio bajo aumenta el riesgo de lesiones de rodilla y desequilibrio en la cadena posterior.'
    }
}

# Pesos para puntuación global
PESOS_PUNTUACION = {
    'volumen': {'peso': 0.20, 'nombre': 'Volumen', 'icono': 'fa-layer-group', 'color': '#8B5CF6'},
    'frecuencia': {'peso': 0.15, 'nombre': 'Frecuencia', 'icono': 'fa-calendar-check', 'color': '#06B6D4'},
    'intensidad': {'peso': 0.15, 'nombre': 'Intensidad', 'icono': 'fa-fire', 'color': '#F59E0B'},
    'progresion': {'peso': 0.20, 'nombre': 'Progresión', 'icono': 'fa-chart-line', 'color': '#10B981'},
    'carga': {'peso': 0.10, 'nombre': 'Carga (ACWR)', 'icono': 'fa-weight-hanging', 'color': '#EF4444'},
    'equilibrio': {'peso': 0.10, 'nombre': 'Equilibrio', 'icono': 'fa-balance-scale', 'color': '#EC4899'},
    'consistencia': {'peso': 0.10, 'nombre': 'Consistencia', 'icono': 'fa-check-double', 'color': '#3B82F6'},
}

# Tooltips explicativos para métricas complejas
TOOLTIPS = {
    'MEV': 'Minimum Effective Volume - El volumen mínimo necesario para estimular adaptaciones. Por debajo de esto, probablemente no progresarás.',
    'MAV': 'Maximum Adaptive Volume - El rango de volumen donde obtienes las mejores adaptaciones. Tu punto dulce.',
    'MRV': 'Maximum Recoverable Volume - El máximo que puedes hacer y aún recuperarte. Superarlo lleva al sobreentrenamiento.',
    'ACWR': 'Acute:Chronic Workload Ratio - Compara tu carga reciente (7 días) con tu promedio (28 días). Entre 0.8-1.3 es óptimo.',
    'RPE': 'Rate of Perceived Exertion - Escala del 1-10 de esfuerzo percibido. RPE 10 = fallo muscular, RPE 7 = 3 reps en reserva.',
    'Volumen': 'Número de series efectivas por grupo muscular por semana. Es el principal driver de hipertrofia.',
    'Frecuencia': 'Veces que entrenas cada grupo muscular por semana. 2x/semana es óptimo para hipertrofia.',
    'Deload': 'Semana de descarga con 40-60% del volumen normal. Necesario cada 4-8 semanas para recuperación.',
}


class EvaluacionProfesionalServiceV2:
    """
    Servicio principal de evaluación profesional v2.0
    """

    # =========================================================================
    # MÉTODO PRINCIPAL
    # =========================================================================

    @staticmethod
    def generar_evaluacion_completa(cliente, semanas=4):
        """
        Genera una evaluación profesional completa del entrenamiento.
        """
        logger.info(f"🔬 Iniciando evaluación profesional v2 para {cliente.nombre}")

        fecha_inicio = timezone.now().date() - timedelta(weeks=semanas)

        # Recopilar métricas
        metricas = EvaluacionProfesionalServiceV2._recopilar_metricas(cliente, fecha_inicio, semanas)

        if metricas['total_sesiones'] < 3:
            return {
                'evaluacion_posible': False,
                'mensaje': 'Se necesitan al menos 3 sesiones para generar una evaluación significativa.',
                'sesiones_registradas': metricas['total_sesiones'],
                'version': '2.0'
            }

        # Generar evaluaciones por categoría
        evaluacion_volumen = EvaluacionProfesionalServiceV2._evaluar_volumen(metricas)
        evaluacion_frecuencia = EvaluacionProfesionalServiceV2._evaluar_frecuencia(metricas)
        evaluacion_intensidad = EvaluacionProfesionalServiceV2._evaluar_intensidad(metricas)
        evaluacion_progresion = EvaluacionProfesionalServiceV2._evaluar_progresion(metricas, cliente)
        evaluacion_carga = EvaluacionProfesionalServiceV2._evaluar_carga_acwr(metricas)
        evaluacion_equilibrio = EvaluacionProfesionalServiceV2._evaluar_equilibrio_muscular(metricas)
        evaluacion_consistencia = EvaluacionProfesionalServiceV2._evaluar_consistencia(metricas)

        # Comparativa con Plan Helms (NUEVO v2)
        comparativa_plan = EvaluacionProfesionalServiceV2._comparar_con_plan_helms(cliente, metricas, semanas)

        # Calcular puntuación global con desglose
        evaluaciones_dict = {
            'volumen': evaluacion_volumen,
            'frecuencia': evaluacion_frecuencia,
            'intensidad': evaluacion_intensidad,
            'progresion': evaluacion_progresion,
            'carga': evaluacion_carga,
            'equilibrio': evaluacion_equilibrio,
            'consistencia': evaluacion_consistencia
        }

        puntuacion_resultado = EvaluacionProfesionalServiceV2._calcular_puntuacion_global_con_desglose(
            evaluaciones_dict)

        # Generar diagnóstico y recomendaciones
        diagnostico_principal = EvaluacionProfesionalServiceV2._generar_diagnostico_principal(
            puntuacion_resultado['puntuacion_total'],
            evaluaciones_dict
        )

        recomendaciones = EvaluacionProfesionalServiceV2._generar_recomendaciones_priorizadas(evaluaciones_dict)

        # Datos para gráficos (NUEVO v2)
        datos_graficos = EvaluacionProfesionalServiceV2._preparar_datos_graficos(
            metricas, evaluaciones_dict, puntuacion_resultado
        )

        return {
            'evaluacion_posible': True,
            'version': '2.0',
            'fecha_evaluacion': timezone.now(),
            'periodo_analizado': {
                'semanas': semanas,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': timezone.now().date()
            },
            'metricas_raw': metricas,
            'puntuacion_global': puntuacion_resultado['puntuacion_total'],
            'puntuacion_desglose': puntuacion_resultado['desglose'],
            'diagnostico_principal': diagnostico_principal,
            'evaluaciones': evaluaciones_dict,
            'comparativa_plan_helms': comparativa_plan,
            'recomendaciones': recomendaciones,
            'datos_graficos': datos_graficos,
            'tooltips': TOOLTIPS,
            'resumen_ejecutivo': EvaluacionProfesionalServiceV2._generar_resumen_ejecutivo(
                puntuacion_resultado['puntuacion_total'], diagnostico_principal, recomendaciones
            )
        }

    # =========================================================================
    # RECOPILACIÓN DE MÉTRICAS
    # =========================================================================

    @staticmethod
    def _recopilar_metricas(cliente, fecha_inicio, semanas):
        """Recopila todas las métricas necesarias."""
        from entrenos.models import EntrenoRealizado, EjercicioRealizado, SesionEntrenamiento

        entrenos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        )

        ejercicios = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        )

        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio
        )

        # Métricas por grupo muscular
        series_por_grupo = defaultdict(int)
        volumen_por_grupo = defaultdict(float)
        frecuencia_por_grupo = defaultdict(set)
        ejercicios_por_grupo = defaultdict(list)

        for ej in ejercicios:
            grupo = ej.grupo_muscular or 'Otros'
            if grupo not in VOLUME_LANDMARKS and grupo != 'Otros':
                grupo = 'Otros'

            series_por_grupo[grupo] += int(ej.series or 1)
            volumen_por_grupo[grupo] += float(ej.peso_kg or 0) * int(ej.series or 1) * int(ej.repeticiones or 1)
            frecuencia_por_grupo[grupo].add(ej.entreno.fecha)
            ejercicios_por_grupo[grupo].append({
                'nombre': ej.nombre_ejercicio,
                'peso': float(ej.peso_kg or 0),
                'series': int(ej.series or 1),
                'reps': int(ej.repeticiones or 1),
                'fecha': ej.entreno.fecha
            })

        # Días de entrenamiento
        dias_entrenamiento = set()
        for e in entrenos:
            dias_entrenamiento.add(e.fecha)

        semanas_periodo = max(1, semanas)

        # Series semanales
        series_semanales = {g: round(s / semanas_periodo, 1) for g, s in series_por_grupo.items()}
        frecuencia_semanal = {g: round(len(fechas) / semanas_periodo, 1) for g, fechas in frecuencia_por_grupo.items()}

        # RPE datos
        rpe_values = [s.rpe_medio for s in sesiones if s.rpe_medio]
        rpe_por_sesion = []
        for s in sesiones:
            if s.rpe_medio:
                rpe_por_sesion.append({
                    'fecha': s.entreno.fecha.isoformat() if hasattr(s.entreno, 'fecha') else None,
                    'rpe': s.rpe_medio
                })

        # Historial de volumen semanal (para tendencias)
        volumen_por_semana = EvaluacionProfesionalServiceV2._calcular_volumen_por_semana(cliente, semanas * 2)

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
            'rpe_por_sesion': rpe_por_sesion,
            'rpe_distribucion': EvaluacionProfesionalServiceV2._calcular_distribucion_rpe(rpe_values),
            'ejercicios_por_grupo': dict(ejercicios_por_grupo),
            'acwr': EvaluacionProfesionalServiceV2._calcular_acwr(cliente),
            'fechas_entrenamiento': sorted(dias_entrenamiento),
            'volumen_por_semana': volumen_por_semana,
        }

    @staticmethod
    def _calcular_volumen_por_semana(cliente, semanas_atras):
        """Calcula el volumen total por semana para tendencias."""
        from entrenos.models import EntrenoRealizado

        hoy = timezone.now().date()
        resultado = []

        for i in range(semanas_atras, 0, -1):
            inicio_semana = hoy - timedelta(weeks=i)
            fin_semana = inicio_semana + timedelta(days=6)

            volumen = EntrenoRealizado.objects.filter(
                cliente=cliente,
                fecha__gte=inicio_semana,
                fecha__lte=fin_semana
            ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

            resultado.append({
                'semana': f'S-{i}',
                'volumen': float(volumen),
                'fecha_inicio': inicio_semana.isoformat()
            })

        return resultado

    @staticmethod
    def _calcular_distribucion_rpe(rpe_values):
        """Calcula distribución de RPE para gráfico."""
        if not rpe_values:
            return {'labels': [], 'data': [], 'colores': []}

        # Contar por zona
        zonas = {
            'RPE 1-5': 0,
            'RPE 6': 0,
            'RPE 7': 0,
            'RPE 8': 0,
            'RPE 9': 0,
            'RPE 10': 0
        }

        colores = {
            'RPE 1-5': '#3B82F6',  # Azul - muy ligero
            'RPE 6': '#10B981',  # Verde - ligero
            'RPE 7': '#84CC16',  # Lima - moderado
            'RPE 8': '#F59E0B',  # Naranja - duro
            'RPE 9': '#EF4444',  # Rojo - muy duro
            'RPE 10': '#991B1B'  # Rojo oscuro - máximo
        }

        for rpe in rpe_values:
            if rpe <= 5:
                zonas['RPE 1-5'] += 1
            elif rpe <= 6:
                zonas['RPE 6'] += 1
            elif rpe <= 7:
                zonas['RPE 7'] += 1
            elif rpe <= 8:
                zonas['RPE 8'] += 1
            elif rpe <= 9:
                zonas['RPE 9'] += 1
            else:
                zonas['RPE 10'] += 1

        # Convertir a porcentajes
        total = len(rpe_values)

        return {
            'labels': list(zonas.keys()),
            'data': [round(v / total * 100, 1) for v in zonas.values()],
            'counts': list(zonas.values()),
            'colores': [colores[k] for k in zonas.keys()],
            'total_sesiones': total
        }

    @staticmethod
    def _calcular_acwr(cliente):
        """Calcula el ACWR."""
        from entrenos.models import EntrenoRealizado

        hoy = timezone.now().date()
        hace_7_dias = hoy - timedelta(days=7)
        hace_28_dias = hoy - timedelta(days=28)

        carga_aguda = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=hace_7_dias
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

        carga_cronica = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=hace_28_dias
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

        promedio_cronico = carga_cronica / 4 if carga_cronica > 0 else 0
        acwr = round(carga_aguda / promedio_cronico, 2) if promedio_cronico > 0 else 0

        zona = 'desconocida'
        for nombre_zona, (min_val, max_val) in ACWR_ZONES.items():
            if min_val <= acwr < max_val:
                zona = nombre_zona
                break

        return {
            'valor': acwr,
            'carga_aguda': round(float(carga_aguda), 0),
            'carga_cronica_semanal': round(float(promedio_cronico), 0),
            'zona': zona
        }

    # =========================================================================
    # COMPARATIVA CON PLAN HELMS (NUEVO v2)
    # =========================================================================

    @staticmethod
    def _comparar_con_plan_helms(cliente, metricas, semanas):
        """Compara el entrenamiento real con el plan Helms generado."""
        try:
            # Generar el plan Helms al vuelo usando el planificador
            from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente

            # Crear perfil del cliente y generar plan
            perfil = crear_perfil_desde_cliente(cliente)
            planificador = PlanificadorHelms(perfil)
            plan = planificador.generar_plan_anual()

            # Obtener la semana actual del año
            semana_actual = timezone.now().isocalendar()[1]

            # Buscar la fase actual en el plan
            fase_actual = None
            periodizacion = plan.get('metadata', {}).get('periodizacion_completa', [])

            for bloque in periodizacion:
                if semana_actual in bloque.get('semanas', []):
                    fase_actual = bloque
                    break

            if not fase_actual:
                return {'disponible': False, 'mensaje': 'No se encontró la fase actual en el plan.'}

            # Comparar métricas
            comparaciones = []

            # 1. Comparar RPE
            rpe_planificado = fase_actual.get('rpe_fin', fase_actual.get('intensidad_rpe', [7, 8])[-1] if isinstance(
                fase_actual.get('intensidad_rpe'), (list, tuple)) else 7)
            rpe_real = metricas.get('rpe_promedio', 0)

            if rpe_real:
                diff_rpe = rpe_real - rpe_planificado
                comparaciones.append({
                    'metrica': 'RPE Promedio',
                    'planificado': rpe_planificado,
                    'real': rpe_real,
                    'diferencia': round(diff_rpe, 1),
                    'estado': 'ok' if abs(diff_rpe) <= 1 else ('alto' if diff_rpe > 0 else 'bajo'),
                    'icono': 'fa-fire'
                })

            # 2. Comparar volumen multiplicador
            vol_mult_plan = fase_actual.get('vol_fin', fase_actual.get('volumen_multiplicador', 1.0))
            # Estimar volumen real vs esperado

            # 3. Comparar rango de repeticiones
            rep_range_plan = fase_actual.get('rep_range', '8-12')

            comparaciones.append({
                'metrica': 'Rango de Reps',
                'planificado': rep_range_plan,
                'real': 'Ver distribución',
                'diferencia': None,
                'estado': 'info',
                'icono': 'fa-repeat'
            })

            # 4. Información de la fase
            return {
                'disponible': True,
                'fase_actual': {
                    'nombre': fase_actual.get('nombre', 'Desconocida'),
                    'fase': fase_actual.get('fase', 'desconocida'),
                    'descripcion': fase_actual.get('descripcion', ''),
                    'semana_del_año': semana_actual,
                    'rpe_objetivo': (fase_actual.get('rpe_inicio', 7), fase_actual.get('rpe_fin', 8)),
                    'rep_range': fase_actual.get('rep_range', '8-12'),
                    'volumen_multiplicador': vol_mult_plan
                },
                'comparaciones': comparaciones,
                'adherencia_estimada': EvaluacionProfesionalServiceV2._calcular_adherencia_plan(metricas, fase_actual)
            }

        except Exception as e:
            logger.error(f"Error comparando con plan Helms: {e}")
            return {'disponible': False, 'mensaje': f'Error al cargar el plan: {str(e)}'}

    @staticmethod
    def _calcular_adherencia_plan(metricas, fase):
        """Calcula el porcentaje de adherencia al plan."""
        puntos = 0
        max_puntos = 0

        # RPE dentro del rango
        rpe_real = metricas.get('rpe_promedio')
        if rpe_real:
            rpe_min = fase.get('rpe_inicio', 7)
            rpe_max = fase.get('rpe_fin', 8)
            max_puntos += 30
            if rpe_min <= rpe_real <= rpe_max:
                puntos += 30
            elif abs(rpe_real - rpe_min) <= 1 or abs(rpe_real - rpe_max) <= 1:
                puntos += 20

        # Frecuencia de entrenamiento
        freq = metricas.get('frecuencia_semanal_global', 0)
        max_puntos += 30
        if freq >= 3:
            puntos += 30
        elif freq >= 2:
            puntos += 20

        # Consistencia
        dias = metricas.get('dias_entrenados', 0)
        semanas = metricas.get('semanas_periodo', 1)
        if semanas > 0 and dias > 0:
            max_puntos += 40
            ratio = dias / (semanas * 4)  # Asumiendo 4 días objetivo
            puntos += min(40, int(ratio * 40))

        return round((puntos / max_puntos * 100) if max_puntos > 0 else 0, 1)

    # =========================================================================
    # EVALUACIONES POR CATEGORÍA
    # =========================================================================

    @staticmethod
    def _evaluar_volumen(metricas):
        """Evalúa el volumen por grupo muscular."""
        series_semanales = metricas.get('series_semanales_por_grupo', {})

        evaluaciones = []
        puntuacion_total = 0
        grupos_evaluados = 0

        for grupo, landmarks in VOLUME_LANDMARKS.items():
            series = series_semanales.get(grupo, 0)
            mev = landmarks['MEV']
            mav = landmarks['MAV']
            mrv = landmarks['MRV']

            if series == 0:
                estado = 'sin_entrenar'
                puntuacion = 0
                mensaje = f"Sin entrenamiento directo registrado."
                severidad = 'info' if grupo in ['Glúteos', 'Core'] else 'warning'
                color = '#6B7280'
            elif series < mev:
                estado = 'suboptimo'
                puntuacion = 30
                mensaje = f"Por debajo del MEV. Insuficiente para progresar."
                severidad = 'warning'
                color = '#F59E0B'
            elif series <= mav:
                estado = 'optimo'
                puntuacion = 100
                mensaje = f"En el rango óptimo (MEV-MAV)."
                severidad = 'success'
                color = '#10B981'
            elif series <= mrv:
                estado = 'alto'
                puntuacion = 70
                mensaje = f"Entre MAV y MRV. Vigila la recuperación."
                severidad = 'info'
                color = '#06B6D4'
            else:
                estado = 'excesivo'
                puntuacion = 20
                mensaje = f"Excede el MRV. Riesgo de sobreentrenamiento."
                severidad = 'danger'
                color = '#EF4444'

            # Calcular posición en la barra (0-100%)
            if mrv > 0:
                posicion_actual = min(100, (series / mrv) * 100)
                posicion_mev = (mev / mrv) * 100
                posicion_mav = (mav / mrv) * 100
            else:
                posicion_actual = posicion_mev = posicion_mav = 0

            evaluaciones.append({
                'grupo': grupo,
                'series_semanales': series,
                'mev': mev,
                'mav': mav,
                'mrv': mrv,
                'estado': estado,
                'puntuacion': puntuacion,
                'mensaje': mensaje,
                'severidad': severidad,
                'color': color,
                'posicion_actual': round(posicion_actual, 1),
                'posicion_mev': round(posicion_mev, 1),
                'posicion_mav': round(posicion_mav, 1)
            })

            if series > 0 or grupo not in ['Glúteos', 'Core']:
                puntuacion_total += puntuacion
                grupos_evaluados += 1

        puntuacion_promedio = round(puntuacion_total / grupos_evaluados, 1) if grupos_evaluados > 0 else 0

        return {
            'puntuacion': puntuacion_promedio,
            'evaluaciones_por_grupo': evaluaciones,
            'grupos_suboptimos': [e for e in evaluaciones if e['estado'] == 'suboptimo'],
            'grupos_excesivos': [e for e in evaluaciones if e['estado'] == 'excesivo'],
            'grupos_optimos': [e for e in evaluaciones if e['estado'] == 'optimo'],
            'resumen': EvaluacionProfesionalServiceV2._generar_resumen_volumen(evaluaciones, puntuacion_promedio)
        }

    @staticmethod
    def _generar_resumen_volumen(evaluaciones, puntuacion):
        """Genera resumen de volumen."""
        optimos = len([e for e in evaluaciones if e['estado'] == 'optimo'])
        total = len([e for e in evaluaciones if e['series_semanales'] > 0])

        if puntuacion >= 80:
            return f"Excelente distribución de volumen. {optimos}/{total} grupos en rango óptimo."
        elif puntuacion >= 60:
            return f"Volumen aceptable. {optimos}/{total} grupos optimizados."
        else:
            return f"Volumen necesita ajustes. Solo {optimos}/{total} grupos en rango óptimo."

    @staticmethod
    def _evaluar_frecuencia(metricas):
        """Evalúa la frecuencia de entrenamiento."""
        frecuencia_global = metricas.get('frecuencia_semanal_global', 0)
        frecuencia_por_grupo = metricas.get('frecuencia_semanal_por_grupo', {})

        if frecuencia_global < 2:
            estado = 'muy_baja'
            puntuacion = 30
            mensaje = f"{frecuencia_global} días/semana. Mínimo recomendado: 3-4 días."
        elif frecuencia_global < 3:
            estado = 'baja'
            puntuacion = 50
            mensaje = f"{frecuencia_global} días/semana. Aceptable pero subóptimo."
        elif frecuencia_global <= 5:
            estado = 'optima'
            puntuacion = 100
            mensaje = f"{frecuencia_global} días/semana. Rango óptimo."
        elif frecuencia_global <= 6:
            estado = 'alta'
            puntuacion = 80
            mensaje = f"{frecuencia_global} días/semana. Alta pero sostenible."
        else:
            estado = 'muy_alta'
            puntuacion = 50
            mensaje = f"{frecuencia_global} días/semana. Muy alto, asegura descanso."

        return {
            'puntuacion': puntuacion,
            'frecuencia_global': frecuencia_global,
            'estado': estado,
            'mensaje': mensaje,
            'frecuencia_por_grupo': frecuencia_por_grupo,
            'recomendacion': FRECUENCIA_OPTIMA
        }

    @staticmethod
    def _evaluar_intensidad(metricas):
        """Evalúa la intensidad basada en RPE."""
        rpe_promedio = metricas.get('rpe_promedio')
        rpe_distribucion = metricas.get('rpe_distribucion', {})

        if rpe_promedio is None:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'No hay datos de RPE. Considera trackear el esfuerzo percibido.',
                'rpe_promedio': None,
                'distribucion': rpe_distribucion
            }

        if rpe_promedio < 6:
            estado = 'muy_bajo'
            puntuacion = 50
            mensaje = f"RPE {rpe_promedio}. Intensidad muy baja, no estás retando tu cuerpo."
        elif rpe_promedio < 7:
            estado = 'bajo'
            puntuacion = 70
            mensaje = f"RPE {rpe_promedio}. Bueno para acumulación de volumen."
        elif rpe_promedio <= 8:
            estado = 'optimo'
            puntuacion = 100
            mensaje = f"RPE {rpe_promedio}. Rango óptimo para la mayoría de objetivos."
        elif rpe_promedio <= 9:
            estado = 'alto'
            puntuacion = 80
            mensaje = f"RPE {rpe_promedio}. Alto pero sostenible en intensificación."
        else:
            estado = 'muy_alto'
            puntuacion = 40
            mensaje = f"RPE {rpe_promedio}. Muy alto, riesgo de fatiga acumulada."

        return {
            'puntuacion': puntuacion,
            'estado': estado,
            'mensaje': mensaje,
            'rpe_promedio': rpe_promedio,
            'rpe_maximo': metricas.get('rpe_maximo'),
            'rpe_minimo': metricas.get('rpe_minimo'),
            'distribucion': rpe_distribucion
        }

    @staticmethod
    def _evaluar_progresion(metricas, cliente):
        """Evalúa la progresión en ejercicios principales."""
        from entrenos.models import EjercicioRealizado

        ejercicios_principales = ['press banca', 'sentadilla', 'peso muerto', 'press militar']
        evaluaciones = []

        for ej_key in ejercicios_principales:
            registros = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=ej_key,
                completado=True,
                peso_kg__gt=0
            ).order_by('entreno__fecha')

            if registros.count() >= 3:
                primero = registros.first()
                ultimo = registros.last()

                peso_inicial = float(primero.peso_kg)
                peso_final = float(ultimo.peso_kg)
                dias = (ultimo.entreno.fecha - primero.entreno.fecha).days or 1

                cambio_kg = peso_final - peso_inicial
                cambio_pct = (cambio_kg / peso_inicial * 100) if peso_inicial > 0 else 0
                cambio_mensual = (cambio_pct / dias * 30) if dias > 0 else 0

                # Tendencia (últimos 5 registros)
                ultimos_5 = list(registros.order_by('-entreno__fecha')[:5])
                tendencia = [{'peso': float(r.peso_kg), 'fecha': r.entreno.fecha.isoformat()} for r in
                             reversed(ultimos_5)]

                if cambio_kg < 0:
                    estado = 'regresion'
                    puntuacion = 20
                elif cambio_mensual < 0.5:
                    estado = 'estancado'
                    puntuacion = 50
                else:
                    estado = 'progresando'
                    puntuacion = 100

                evaluaciones.append({
                    'ejercicio': ej_key.title(),
                    'peso_inicial': peso_inicial,
                    'peso_final': peso_final,
                    'cambio_kg': round(cambio_kg, 1),
                    'cambio_pct': round(cambio_pct, 1),
                    'cambio_mensual': round(cambio_mensual, 2),
                    'dias': dias,
                    'estado': estado,
                    'puntuacion': puntuacion,
                    'tendencia': tendencia
                })

        if not evaluaciones:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'Insuficientes datos de progresión.',
                'ejercicios': []
            }

        puntuacion_promedio = round(sum(e['puntuacion'] for e in evaluaciones) / len(evaluaciones), 1)

        return {
            'puntuacion': puntuacion_promedio,
            'estado': 'evaluado',
            'ejercicios': evaluaciones,
            'ejercicios_en_regresion': [e for e in evaluaciones if e['estado'] == 'regresion'],
            'ejercicios_estancados': [e for e in evaluaciones if e['estado'] == 'estancado'],
            'resumen': f"{len([e for e in evaluaciones if e['estado'] == 'progresando'])}/{len(evaluaciones)} ejercicios progresando."
        }

    @staticmethod
    def _evaluar_carga_acwr(metricas):
        """Evalúa la carga usando ACWR."""
        acwr_data = metricas.get('acwr', {})
        acwr = acwr_data.get('valor', 0)
        zona = acwr_data.get('zona', 'desconocida')

        zonas_config = {
            'optima': (100, 'ok', 'Zona óptima (0.8-1.3). Máximas adaptaciones con bajo riesgo.'),
            'baja': (60, 'bajo', 'Carga por debajo de lo óptimo. Puedes aumentar gradualmente.'),
            'muy_baja': (40, 'muy_bajo', 'Carga muy baja. Fase de deload o inicio de programa.'),
            'cuidado': (50, 'cuidado', 'Zona de precaución (1.3-1.5). Vigila señales de fatiga.'),
            'peligro': (20, 'peligro', '⚠️ Zona de peligro (>1.5). Alto riesgo de lesión.')
        }

        config = zonas_config.get(zona, (None, 'sin_datos', 'Sin datos suficientes.'))

        return {
            'puntuacion': config[0],
            'acwr': acwr,
            'zona': zona,
            'estado': config[1],
            'mensaje': config[2],
            'carga_aguda': acwr_data.get('carga_aguda', 0),
            'carga_cronica_semanal': acwr_data.get('carga_cronica_semanal', 0),
            'zonas_referencia': {k: {'min': v[0], 'max': v[1]} for k, v in ACWR_ZONES.items()}
        }

    @staticmethod
    def _evaluar_equilibrio_muscular(metricas):
        """Evalúa el equilibrio entre grupos antagonistas."""
        volumen_por_grupo = metricas.get('volumen_por_grupo', {})

        evaluaciones = []
        puntuacion_total = 0
        evaluaciones_count = 0

        # Tracción vs Empuje
        pecho = volumen_por_grupo.get('Pecho', 0)
        espalda = volumen_por_grupo.get('Espalda', 0)

        if pecho > 0 and espalda > 0:
            ratio = round(espalda / pecho, 2)
            config = RATIOS_IDEALES['traccion_empuje']

            if config['min'] <= ratio <= config['max']:
                estado = 'equilibrado'
                puntuacion = 100
            elif ratio < config['min']:
                estado = 'desequilibrado'
                puntuacion = 50
            else:
                estado = 'ok_alto'
                puntuacion = 90

            evaluaciones.append({
                'tipo': 'traccion_empuje',
                'nombre': config['nombre'],
                'ratio': ratio,
                'rango_ideal': f"{config['min']}-{config['max']}",
                'valor_ideal': config['ideal'],
                'estado': estado,
                'puntuacion': puntuacion,
                'tooltip': config['tooltip'],
                'descripcion': config['descripcion']
            })
            puntuacion_total += puntuacion
            evaluaciones_count += 1

        # Isquios vs Cuádriceps
        cuadriceps = volumen_por_grupo.get('Cuádriceps', 0)
        isquios = volumen_por_grupo.get('Isquios', 0)

        if cuadriceps > 0 and isquios > 0:
            ratio = round(isquios / cuadriceps, 2)
            config = RATIOS_IDEALES['isquios_cuadriceps']

            if config['min'] <= ratio <= config['max']:
                estado = 'equilibrado'
                puntuacion = 100
            elif ratio < config['min']:
                estado = 'desequilibrado'
                puntuacion = 50
            else:
                estado = 'ok_alto'
                puntuacion = 90

            evaluaciones.append({
                'tipo': 'isquios_cuadriceps',
                'nombre': config['nombre'],
                'ratio': ratio,
                'rango_ideal': f"{config['min']}-{config['max']}",
                'valor_ideal': config['ideal'],
                'estado': estado,
                'puntuacion': puntuacion,
                'tooltip': config['tooltip'],
                'descripcion': config['descripcion']
            })
            puntuacion_total += puntuacion
            evaluaciones_count += 1

        return {
            'puntuacion': round(puntuacion_total / evaluaciones_count, 1) if evaluaciones_count > 0 else None,
            'evaluaciones': evaluaciones,
            'mensaje': f"{len([e for e in evaluaciones if e['estado'] == 'equilibrado'])}/{len(evaluaciones)} ratios equilibrados." if evaluaciones else "Sin datos suficientes."
        }

    @staticmethod
    def _evaluar_consistencia(metricas):
        """Evalúa la consistencia en el entrenamiento."""
        fechas = metricas.get('fechas_entrenamiento', [])
        semanas = metricas.get('semanas_periodo', 1)

        if len(fechas) < 2:
            return {
                'puntuacion': None,
                'estado': 'sin_datos',
                'mensaje': 'Insuficientes datos.'
            }

        # Calcular gaps
        fechas_sorted = sorted(fechas)
        gaps = [(fechas_sorted[i] - fechas_sorted[i - 1]).days for i in range(1, len(fechas_sorted))]

        gap_promedio = sum(gaps) / len(gaps) if gaps else 0
        gap_maximo = max(gaps) if gaps else 0

        dias_entrenados = len(fechas)
        dias_esperados = semanas * 4
        porcentaje = (dias_entrenados / dias_esperados * 100) if dias_esperados > 0 else 0

        if porcentaje >= 90:
            puntuacion, estado = 100, 'excelente'
        elif porcentaje >= 75:
            puntuacion, estado = 80, 'buena'
        elif porcentaje >= 50:
            puntuacion, estado = 60, 'moderada'
        else:
            puntuacion, estado = 40, 'baja'

        return {
            'puntuacion': puntuacion,
            'estado': estado,
            'mensaje': f"{dias_entrenados} días en {semanas} semanas ({porcentaje:.0f}% del objetivo).",
            'dias_entrenados': dias_entrenados,
            'gap_promedio': round(gap_promedio, 1),
            'gap_maximo': gap_maximo,
            'porcentaje_cumplimiento': round(porcentaje, 1)
        }

    # =========================================================================
    # PUNTUACIÓN GLOBAL CON DESGLOSE
    # =========================================================================

    @staticmethod
    def _calcular_puntuacion_global_con_desglose(evaluaciones):
        """Calcula puntuación global con desglose visual."""
        desglose = []
        puntuacion_total = 0
        peso_total = 0

        for categoria, config in PESOS_PUNTUACION.items():
            eval_cat = evaluaciones.get(categoria, {})
            punt = eval_cat.get('puntuacion')

            contribucion = 0
            if punt is not None:
                contribucion = punt * config['peso']
                puntuacion_total += contribucion
                peso_total += config['peso']

            desglose.append({
                'categoria': categoria,
                'nombre': config['nombre'],
                'icono': config['icono'],
                'color': config['color'],
                'peso': config['peso'],
                'peso_porcentaje': round(config['peso'] * 100),
                'puntuacion_categoria': punt,
                'contribucion': round(contribucion, 1),
                'tiene_datos': punt is not None
            })

        puntuacion_normalizada = round(puntuacion_total / peso_total, 1) if peso_total > 0 else 0

        return {
            'puntuacion_total': puntuacion_normalizada,
            'desglose': desglose
        }

    # =========================================================================
    # DIAGNÓSTICO Y RECOMENDACIONES
    # =========================================================================

    @staticmethod
    def _generar_diagnostico_principal(puntuacion, evaluaciones):
        """Genera diagnóstico principal."""
        if puntuacion >= 85:
            nivel, emoji, titulo = 'excelente', '🏆', 'Entrenamiento de Élite'
            descripcion = 'Tu programa está muy bien estructurado. Aplicas principios científicos correctamente.'
        elif puntuacion >= 70:
            nivel, emoji, titulo = 'bueno', '✅', 'Buen Programa'
            descripcion = 'Entrenamiento sólido con algunos puntos de mejora.'
        elif puntuacion >= 55:
            nivel, emoji, titulo = 'mejorable', '📊', 'Programa Mejorable'
            descripcion = 'Varios aspectos podrían optimizarse para mejores resultados.'
        else:
            nivel, emoji, titulo = 'revisar', '⚠️', 'Requiere Revisión'
            descripcion = 'Se identificaron múltiples áreas que necesitan atención.'

        return {
            'nivel': nivel,
            'emoji': emoji,
            'titulo': titulo,
            'descripcion': descripcion,
            'puntuacion': puntuacion
        }

    @staticmethod
    def _generar_recomendaciones_priorizadas(evaluaciones):
        """Genera recomendaciones ordenadas por prioridad."""
        recomendaciones = []

        # ACWR peligroso
        if evaluaciones.get('carga', {}).get('estado') == 'peligro':
            recomendaciones.append({
                'prioridad': 1, 'categoria': 'seguridad', 'icono': '🚨',
                'titulo': 'Reducir carga inmediatamente',
                'descripcion': 'Tu ACWR indica alto riesgo de lesión. Reduce volumen 30-40%.',
                'accion': 'Implementar semana de deload'
            })

        # Regresión
        if evaluaciones.get('progresion', {}).get('ejercicios_en_regresion'):
            ejs = [e['ejercicio'] for e in evaluaciones['progresion']['ejercicios_en_regresion']]
            recomendaciones.append({
                'prioridad': 2, 'categoria': 'progresion', 'icono': '📉',
                'titulo': 'Atender regresión en ejercicios',
                'descripcion': f'Ejercicios en regresión: {", ".join(ejs)}.',
                'accion': 'Revisar técnica, recuperación y nutrición'
            })

        # Consistencia baja
        if evaluaciones.get('consistencia', {}).get('estado') in ['baja', 'moderada']:
            recomendaciones.append({
                'prioridad': 3, 'categoria': 'adherencia', 'icono': '📅',
                'titulo': 'Mejorar consistencia',
                'descripcion': 'La adherencia es el factor #1. Prioriza constancia sobre perfección.',
                'accion': 'Entrenar mínimo 3 días por semana'
            })

        # Volumen subóptimo
        suboptimos = evaluaciones.get('volumen', {}).get('grupos_suboptimos', [])
        if suboptimos:
            grupos = [g['grupo'] for g in suboptimos[:3]]
            recomendaciones.append({
                'prioridad': 4, 'categoria': 'volumen', 'icono': '📦',
                'titulo': 'Aumentar volumen en grupos rezagados',
                'descripcion': f'Grupos bajo MEV: {", ".join(grupos)}.',
                'accion': 'Añadir 2-4 series semanales por grupo'
            })

        # Desequilibrio
        desequilibrios = [e for e in evaluaciones.get('equilibrio', {}).get('evaluaciones', []) if
                          e.get('estado') == 'desequilibrado']
        for d in desequilibrios:
            recomendaciones.append({
                'prioridad': 5, 'categoria': 'equilibrio', 'icono': '⚖️',
                'titulo': f'Corregir desequilibrio: {d["nombre"]}',
                'descripcion': f'Ratio actual: {d["ratio"]} (ideal: {d["rango_ideal"]}).',
                'accion': 'Ajustar proporción de ejercicios'
            })

        return sorted(recomendaciones, key=lambda x: x['prioridad'])

    @staticmethod
    def _generar_resumen_ejecutivo(puntuacion, diagnostico, recomendaciones):
        """Genera resumen ejecutivo."""
        mensajes_motivacionales = {
            'excelente': "🎯 Estás entrenando como un profesional. ¡Mantén el rumbo!",
            'bueno': "💪 Buen trabajo. Pequeños ajustes te llevarán al siguiente nivel.",
            'mejorable': "📈 Tienes base sólida. Las recomendaciones marcarán diferencia.",
            'revisar': "🌱 Cada experto fue principiante. Los ajustes sugeridos ayudarán mucho."
        }

        return {
            'puntuacion': puntuacion,
            'nivel': diagnostico['nivel'],
            'titulo': f"{diagnostico['emoji']} {diagnostico['titulo']}",
            'descripcion': diagnostico['descripcion'],
            'acciones_inmediatas': [r['titulo'] for r in recomendaciones[:3]],
            'mensaje_motivacional': mensajes_motivacionales.get(diagnostico['nivel'], '')
        }

    # =========================================================================
    # PREPARAR DATOS PARA GRÁFICOS
    # =========================================================================

    @staticmethod
    def _preparar_datos_graficos(metricas, evaluaciones, puntuacion_resultado):
        """Prepara todos los datos necesarios para los gráficos."""
        return {
            # Gráfico de donut - Desglose de puntuación
            'puntuacion_donut': {
                'labels': [d['nombre'] for d in puntuacion_resultado['desglose'] if d['tiene_datos']],
                'data': [d['contribucion'] for d in puntuacion_resultado['desglose'] if d['tiene_datos']],
                'colores': [d['color'] for d in puntuacion_resultado['desglose'] if d['tiene_datos']]
            },

            # Gráfico de barras - Distribución RPE
            'rpe_distribucion': metricas.get('rpe_distribucion', {}),

            # Gráfico de línea - Tendencia de volumen
            'volumen_tendencia': metricas.get('volumen_por_semana', []),

            # Gráfico de barras - Volumen por grupo muscular
            'volumen_grupos': {
                'labels': list(metricas.get('series_semanales_por_grupo', {}).keys()),
                'data': list(metricas.get('series_semanales_por_grupo', {}).values()),
                'mev': [VOLUME_LANDMARKS.get(g, {}).get('MEV', 0) for g in
                        metricas.get('series_semanales_por_grupo', {}).keys()],
                'mav': [VOLUME_LANDMARKS.get(g, {}).get('MAV', 0) for g in
                        metricas.get('series_semanales_por_grupo', {}).keys()],
            },

            # Mini sparklines de progresión por ejercicio
            'progresion_sparklines': {
                ej['ejercicio']: ej.get('tendencia', [])
                for ej in evaluaciones.get('progresion', {}).get('ejercicios', [])
            }
        }
