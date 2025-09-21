# 🧮 CALCULADORAS Y ALGORITMOS DEL CENTRO DE ANÁLISIS
# Archivo: analytics/calculadoras.py

from django.db.models import Sum, Avg, Max, Min, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from scipy import stats
import json

from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from .models import MetricaRendimiento, AnalisisEjercicio, TendenciaProgresion

class CalculadoraMetricas:
    """
    Calculadora principal de métricas de rendimiento
    """
    
    def __init__(self, cliente):
        self.cliente = cliente
    
    def calcular_resumen_periodo(self, fecha_inicio, fecha_fin):
        """
        Calcular resumen de métricas para un período específico
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )
        
        if not entrenamientos.exists():
            return self._metricas_vacias()
        
        # Métricas básicas
        total_entrenamientos = entrenamientos.count()
        volumen_total = entrenamientos.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0
        duracion_total = entrenamientos.aggregate(Sum('duracion_minutos'))['duracion_minutos__sum'] or 0
        calorias_totales = entrenamientos.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0
        
        # Métricas promedio
        volumen_promedio = volumen_total / total_entrenamientos if total_entrenamientos > 0 else 0
        duracion_promedio = duracion_total / total_entrenamientos if total_entrenamientos > 0 else 0
        
        # Intensidad promedio (volumen / duración)
        intensidad_promedio = volumen_total / duracion_total if duracion_total > 0 else 0
        
        # Frecuencia semanal
        dias_periodo = (fecha_fin - fecha_inicio).days + 1
        semanas = dias_periodo / 7
        frecuencia_semanal = total_entrenamientos / semanas if semanas > 0 else 0
        
        # Métricas cardíacas
        fc_promedio = entrenamientos.aggregate(Avg('frecuencia_cardiaca_promedio'))['frecuencia_cardiaca_promedio__avg']
        fc_maxima = entrenamientos.aggregate(Max('frecuencia_cardiaca_maxima'))['frecuencia_cardiaca_maxima__max']
        
        # Consistencia (días con entrenamiento / días totales)
        dias_con_entrenamiento = entrenamientos.values('fecha').distinct().count()
        consistencia = (dias_con_entrenamiento / dias_periodo) * 100 if dias_periodo > 0 else 0
        
        return {
            'total_entrenamientos': total_entrenamientos,
            'volumen_total': float(volumen_total),
            'volumen_promedio': float(volumen_promedio),
            'duracion_total': duracion_total,
            'duracion_promedio': float(duracion_promedio),
            'intensidad_promedio': float(intensidad_promedio),
            'calorias_totales': float(calorias_totales or 0),
            'frecuencia_semanal': float(frecuencia_semanal),
            'fc_promedio': float(fc_promedio or 0),
            'fc_maxima': fc_maxima or 0,
            'consistencia': float(consistencia),
            'dias_con_entrenamiento': dias_con_entrenamiento,
            'dias_periodo': dias_periodo
        }
    
    def calcular_metricas_diarias(self, fecha):
        """
        Calcular métricas para un día específico
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha=fecha
        )
        
        if not entrenamientos.exists():
            return None
        
        # Métricas básicas del día
        volumen_total = entrenamientos.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0
        duracion_total = entrenamientos.aggregate(Sum('duracion_minutos'))['duracion_minutos__sum'] or 0
        calorias_totales = entrenamientos.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0
        
        # Intensidad del día
        intensidad_promedio = volumen_total / duracion_total if duracion_total > 0 else 0
        
        # Análisis por grupo muscular
        volumen_por_grupo = self._calcular_volumen_por_grupo(entrenamientos)
        
        # Crear o actualizar métrica de rendimiento
        metrica, created = MetricaRendimiento.objects.update_or_create(
            cliente=self.cliente,
            fecha=fecha,
            defaults={
                'volumen_total': volumen_total,
                'intensidad_promedio': intensidad_promedio,
                'duracion_total': duracion_total,
                'calorias_totales': calorias_totales or 0,
                'entrenamientos_dia': entrenamientos.count(),
                'ejercicios_totales': self._contar_ejercicios_dia(entrenamientos),
                'volumen_por_grupo': volumen_por_grupo,
                'fc_promedio': entrenamientos.aggregate(Avg('frecuencia_cardiaca_promedio'))['frecuencia_cardiaca_promedio__avg'],
                'fc_maxima': entrenamientos.aggregate(Max('frecuencia_cardiaca_maxima'))['frecuencia_cardiaca_maxima__max'],
            }
        )
        
        return metrica
    
    def recalcular_periodo(self, fecha_inicio, fecha_fin):
        """
        Recalcular métricas para todo un período
        """
        fecha_actual = fecha_inicio
        dias_calculados = 0
        
        while fecha_actual <= fecha_fin:
            self.calcular_metricas_diarias(fecha_actual)
            fecha_actual += timedelta(days=1)
            dias_calculados += 1
        
        return dias_calculados
    
    def _calcular_volumen_por_grupo(self, entrenamientos):
        """
        Calcular volumen por grupo muscular
        """
        # Mapeo de ejercicios a grupos musculares
        grupos_musculares = {
            'pecho': ['press', 'bench', 'pecho', 'chest'],
            'espalda': ['pull', 'row', 'lat', 'espalda', 'back'],
            'piernas': ['squat', 'leg', 'pierna', 'cuadriceps', 'femoral'],
            'hombros': ['shoulder', 'press militar', 'hombro', 'deltoides'],
            'brazos': ['curl', 'triceps', 'biceps', 'brazo'],
            'core': ['abs', 'abdominal', 'core', 'plancha']
        }
        
        volumen_por_grupo = {}
        
        for entreno in entrenamientos:
            ejercicios = EjercicioLiftinDetallado.objects.filter(entreno=entreno)
            
            for ejercicio in ejercicios:
                nombre_lower = ejercicio.nombre_ejercicio.lower()
                grupo_encontrado = 'otros'
                
                for grupo, palabras_clave in grupos_musculares.items():
                    if any(palabra in nombre_lower for palabra in palabras_clave):
                        grupo_encontrado = grupo
                        break
                
                # Calcular volumen del ejercicio (peso * series * repeticiones promedio)
                reps_promedio = (ejercicio.repeticiones_min + ejercicio.repeticiones_max) / 2 if ejercicio.repeticiones_min and ejercicio.repeticiones_max else 10
                volumen_ejercicio = float(ejercicio.peso_kg) * ejercicio.series_realizadas * reps_promedio
                
                volumen_por_grupo[grupo_encontrado] = volumen_por_grupo.get(grupo_encontrado, 0) + volumen_ejercicio
        
        return volumen_por_grupo
    
    def _contar_ejercicios_dia(self, entrenamientos):
        """
        Contar ejercicios únicos del día
        """
        ejercicios_unicos = set()
        for entreno in entrenamientos:
            ejercicios = EjercicioLiftinDetallado.objects.filter(entreno=entreno)
            for ejercicio in ejercicios:
                ejercicios_unicos.add(ejercicio.nombre_ejercicio)
        return len(ejercicios_unicos)
    
    def _metricas_vacias(self):
        """
        Retornar métricas vacías cuando no hay datos
        """
        return {
            'total_entrenamientos': 0,
            'volumen_total': 0,
            'volumen_promedio': 0,
            'duracion_total': 0,
            'duracion_promedio': 0,
            'intensidad_promedio': 0,
            'calorias_totales': 0,
            'frecuencia_semanal': 0,
            'fc_promedio': 0,
            'fc_maxima': 0,
            'consistencia': 0,
            'dias_con_entrenamiento': 0,
            'dias_periodo': 0
        }

class CalculadoraProgresion:
    """
    Calculadora especializada en análisis de progresión por ejercicio
    """
    
    def __init__(self, cliente, nombre_ejercicio):
        self.cliente = cliente
        self.nombre_ejercicio = nombre_ejercicio
    
    def calcular_progresion_temporal(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcular progresión temporal de un ejercicio
        """
        if not fecha_inicio:
            fecha_inicio = timezone.now().date() - timedelta(days=90)
        if not fecha_fin:
            fecha_fin = timezone.now().date()
        
        # Obtener todos los registros del ejercicio en el período
        ejercicios = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=self.cliente,
            nombre_ejercicio=self.nombre_ejercicio,
            entreno__fecha__gte=fecha_inicio,
            entreno__fecha__lte=fecha_fin
        ).select_related('entreno').order_by('entreno__fecha')
        
        if not ejercicios.exists():
            return []
        
        # Agrupar por fecha y calcular métricas
        datos_por_fecha = {}
        
        for ejercicio in ejercicios:
            fecha = ejercicio.entreno.fecha
            
            if fecha not in datos_por_fecha:
                datos_por_fecha[fecha] = {
                    'fecha': fecha,
                    'pesos': [],
                    'volumenes': [],
                    'series_totales': 0,
                    'repeticiones_totales': 0
                }
            
            # Calcular volumen del ejercicio
            reps_promedio = (ejercicio.repeticiones_min + ejercicio.repeticiones_max) / 2 if ejercicio.repeticiones_min and ejercicio.repeticiones_max else 10
            volumen = float(ejercicio.peso_kg) * ejercicio.series_realizadas * reps_promedio
            
            datos_por_fecha[fecha]['pesos'].append(float(ejercicio.peso_kg))
            datos_por_fecha[fecha]['volumenes'].append(volumen)
            datos_por_fecha[fecha]['series_totales'] += ejercicio.series_realizadas
            datos_por_fecha[fecha]['repeticiones_totales'] += reps_promedio * ejercicio.series_realizadas
        
        # Procesar datos y calcular métricas finales
        progresion_data = []
        
        for fecha, datos in sorted(datos_por_fecha.items()):
            peso_maximo = max(datos['pesos'])
            peso_promedio = sum(datos['pesos']) / len(datos['pesos'])
            volumen_total = sum(datos['volumenes'])
            
            # Calcular 1RM estimado usando fórmula de Brzycki
            one_rm_estimado = self._calcular_1rm(peso_maximo, datos['repeticiones_totales'] / datos['series_totales'])
            
            progresion_data.append({
                'fecha': fecha.isoformat(),
                'peso_maximo': peso_maximo,
                'peso_promedio': peso_promedio,
                'volumen_total': volumen_total,
                'one_rm_estimado': one_rm_estimado,
                'series_totales': datos['series_totales']
            })
        
        return progresion_data
    
    def calcular_tendencia(self, dias=90):
        """
        Calcular tendencia de progresión usando regresión lineal
        """
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=dias)
        
        datos_progresion = self.calcular_progresion_temporal(fecha_inicio, fecha_fin)
        
        if len(datos_progresion) < 3:
            return None
        
        # Preparar datos para regresión
        fechas_num = [(datetime.strptime(d['fecha'], '%Y-%m-%d').date() - fecha_inicio).days for d in datos_progresion]
        pesos_maximos = [d['peso_maximo'] for d in datos_progresion]
        volumenes = [d['volumen_total'] for d in datos_progresion]
        
        # Regresión lineal para peso
        slope_peso, intercept_peso, r_value_peso, p_value_peso, std_err_peso = stats.linregress(fechas_num, pesos_maximos)
        
        # Regresión lineal para volumen
        slope_volumen, intercept_volumen, r_value_volumen, p_value_volumen, std_err_volumen = stats.linregress(fechas_num, volumenes)
        
        # Determinar tipo de tendencia
        if abs(r_value_peso) < 0.3:
            tipo_tendencia = 'irregular'
        elif slope_peso > 0:
            tipo_tendencia = 'creciente'
        elif slope_peso < 0:
            tipo_tendencia = 'decreciente'
        else:
            tipo_tendencia = 'estable'
        
        # Calcular velocidad de progresión (% por semana)
        peso_inicial = pesos_maximos[0] if pesos_maximos else 0
        velocidad_progresion = (slope_peso * 7 / peso_inicial * 100) if peso_inicial > 0 else 0
        
        # Crear o actualizar tendencia
        tendencia, created = TendenciaProgresion.objects.update_or_create(
            cliente=self.cliente,
            nombre_ejercicio=self.nombre_ejercicio,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            defaults={
                'periodo_dias': dias,
                'tipo_tendencia': tipo_tendencia,
                'velocidad_progresion': velocidad_progresion,
                'consistencia': abs(r_value_peso) * 100,
                'confianza': (1 - p_value_peso) * 100 if p_value_peso < 1 else 0,
                'valor_inicial': pesos_maximos[0] if pesos_maximos else 0,
                'valor_final': pesos_maximos[-1] if pesos_maximos else 0,
                'valor_maximo': max(pesos_maximos) if pesos_maximos else 0,
            }
        )
        
        return tendencia
    
    def _calcular_1rm(self, peso, repeticiones):
        """
        Calcular 1RM estimado usando fórmula de Brzycki
        """
        if repeticiones <= 1:
            return peso
        
        # Fórmula de Brzycki: 1RM = peso / (1.0278 - 0.0278 * repeticiones)
        one_rm = peso / (1.0278 - 0.0278 * repeticiones)
        return round(one_rm, 2)

class CalculadoraComparativas:
    """
    Calculadora para análisis comparativos
    """
    
    def __init__(self, cliente):
        self.cliente = cliente
    
    def comparar_con_poblacion(self, metrica, fecha_inicio, fecha_fin):
        """
        Comparar métricas del cliente con la población general
        """
        # Métricas del cliente
        calculadora_cliente = CalculadoraMetricas(self.cliente)
        metricas_cliente = calculadora_cliente.calcular_resumen_periodo(fecha_inicio, fecha_fin)
        valor_cliente = metricas_cliente.get(metrica, 0)
        
        # Métricas de la población (excluyendo al cliente)
        metricas_poblacion = MetricaRendimiento.objects.filter(
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        ).exclude(cliente=self.cliente)
        
        if not metricas_poblacion.exists():
            return None
        
        # Calcular estadísticas de la población
        if metrica == 'volumen_total':
            valores_poblacion = list(metricas_poblacion.values_list('volumen_total', flat=True))
        elif metrica == 'intensidad_promedio':
            valores_poblacion = list(metricas_poblacion.values_list('intensidad_promedio', flat=True))
        elif metrica == 'calorias_totales':
            valores_poblacion = list(metricas_poblacion.values_list('calorias_totales', flat=True))
        else:
            return None
        
        # Filtrar valores válidos
        valores_poblacion = [float(v) for v in valores_poblacion if v is not None and v > 0]
        
        if not valores_poblacion:
            return None
        
        # Calcular percentil
        percentil = stats.percentileofscore(valores_poblacion, valor_cliente)
        
        # Calcular estadísticas
        media_poblacion = np.mean(valores_poblacion)
        std_poblacion = np.std(valores_poblacion)
        
        # Determinar clasificación
        if percentil >= 95:
            clasificacion = 'excepcional'
        elif percentil >= 80:
            clasificacion = 'muy_bueno'
        elif percentil >= 60:
            clasificacion = 'bueno'
        elif percentil >= 40:
            clasificacion = 'promedio'
        elif percentil >= 20:
            clasificacion = 'por_debajo'
        else:
            clasificacion = 'necesita_mejora'
        
        # Determinar significancia estadística
        z_score = (valor_cliente - media_poblacion) / std_poblacion if std_poblacion > 0 else 0
        
        if abs(z_score) >= 2:
            significancia = 'muy_significativa'
        elif abs(z_score) >= 1.5:
            significancia = 'significativa'
        elif abs(z_score) >= 1:
            significancia = 'moderada'
        else:
            significancia = 'no_significativa'
        
        return {
            'valor_cliente': valor_cliente,
            'media_poblacion': media_poblacion,
            'percentil': percentil,
            'clasificacion': clasificacion,
            'significancia': significancia,
            'z_score': z_score,
            'tamaño_muestra': len(valores_poblacion)
        }

