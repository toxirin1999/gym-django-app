# 🤖 ALGORITMOS DE IA Y RECOMENDACIONES
# Archivo: analytics/algoritmos.py

from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from scipy import stats
import json

from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from .models import (
    MetricaRendimiento, AnalisisEjercicio, TendenciaProgresion,
    PrediccionRendimiento, RecomendacionEntrenamiento
)
from .calculadoras import CalculadoraMetricas, CalculadoraProgresion

class GeneradorRecomendaciones:
    """
    Generador inteligente de recomendaciones personalizadas
    """
    
    def __init__(self, cliente):
        self.cliente = cliente
        self.calculadora = CalculadoraMetricas(cliente)
    
    def generar_recomendaciones(self):
        """
        Generar recomendaciones basadas en análisis de datos
        """
        recomendaciones = []
        
        # Analizar últimos 30 días
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        # Obtener métricas del período
        metricas = self.calculadora.calcular_resumen_periodo(fecha_inicio, fecha_fin)
        
        # Generar diferentes tipos de recomendaciones
        recomendaciones.extend(self._analizar_frecuencia(metricas))
        recomendaciones.extend(self._analizar_volumen(metricas))
        recomendaciones.extend(self._analizar_intensidad(metricas))
        recomendaciones.extend(self._analizar_progresion())
        recomendaciones.extend(self._analizar_recuperacion(metricas))
        recomendaciones.extend(self._analizar_variedad())
        
        # Guardar recomendaciones en la base de datos
        recomendaciones_guardadas = []
        for rec_data in recomendaciones:
            recomendacion = RecomendacionEntrenamiento.objects.create(
                cliente=self.cliente,
                tipo=rec_data['tipo'],
                titulo=rec_data['titulo'],
                descripcion=rec_data['descripcion'],
                prioridad=rec_data['prioridad'],
                metricas_base=rec_data.get('metricas_base', {}),
                impacto_esperado=rec_data['impacto_esperado'],
                ejercicio_relacionado=rec_data.get('ejercicio_relacionado'),
                expires_at=timezone.now() + timedelta(days=30)
            )
            recomendaciones_guardadas.append(recomendacion)
        
        return recomendaciones_guardadas
    
    def _analizar_frecuencia(self, metricas):
        """
        Analizar frecuencia de entrenamiento y generar recomendaciones
        """
        recomendaciones = []
        frecuencia_semanal = metricas['frecuencia_semanal']
        
        if frecuencia_semanal < 2:
            recomendaciones.append({
                'tipo': 'frecuencia',
                'titulo': 'Aumentar Frecuencia de Entrenamiento',
                'descripcion': f'Tu frecuencia actual es de {frecuencia_semanal:.1f} entrenamientos por semana. Para obtener mejores resultados, se recomienda entrenar al menos 3-4 veces por semana. Esto permitirá una mejor adaptación muscular y progresión más consistente.',
                'prioridad': 1,
                'impacto_esperado': 'Mejora significativa en fuerza y masa muscular',
                'metricas_base': {'frecuencia_actual': frecuencia_semanal}
            })
        
        elif frecuencia_semanal > 6:
            recomendaciones.append({
                'tipo': 'recuperacion',
                'titulo': 'Considerar Días de Descanso',
                'descripcion': f'Estás entrenando {frecuencia_semanal:.1f} veces por semana, lo cual es muy intenso. Considera incluir al menos 1-2 días de descanso completo para permitir una recuperación adecuada y prevenir el sobreentrenamiento.',
                'prioridad': 2,
                'impacto_esperado': 'Mejor recuperación y prevención de lesiones',
                'metricas_base': {'frecuencia_actual': frecuencia_semanal}
            })
        
        return recomendaciones
    
    def _analizar_volumen(self, metricas):
        """
        Analizar volumen de entrenamiento
        """
        recomendaciones = []
        volumen_promedio = metricas['volumen_promedio']
        
        # Comparar con rangos recomendados (estos valores pueden ajustarse)
        if volumen_promedio < 5000:  # kg por sesión
            recomendaciones.append({
                'tipo': 'volumen',
                'titulo': 'Incrementar Volumen de Entrenamiento',
                'descripcion': f'Tu volumen promedio por sesión es de {volumen_promedio:.0f} kg. Para maximizar el crecimiento muscular, considera aumentar gradualmente el volumen agregando series adicionales o ejercicios complementarios.',
                'prioridad': 2,
                'impacto_esperado': 'Mayor estímulo para crecimiento muscular',
                'metricas_base': {'volumen_actual': volumen_promedio}
            })
        
        elif volumen_promedio > 20000:  # kg por sesión
            recomendaciones.append({
                'tipo': 'volumen',
                'titulo': 'Optimizar Volumen de Entrenamiento',
                'descripcion': f'Tu volumen promedio de {volumen_promedio:.0f} kg por sesión es muy alto. Considera enfocarte en la calidad sobre la cantidad, priorizando ejercicios compuestos y técnica perfecta.',
                'prioridad': 2,
                'impacto_esperado': 'Mejor eficiencia y menor fatiga',
                'metricas_base': {'volumen_actual': volumen_promedio}
            })
        
        return recomendaciones
    
    def _analizar_intensidad(self, metricas):
        """
        Analizar intensidad de entrenamiento
        """
        recomendaciones = []
        intensidad_promedio = metricas['intensidad_promedio']
        
        if intensidad_promedio < 100:  # kg/minuto
            recomendaciones.append({
                'tipo': 'intensidad',
                'titulo': 'Aumentar Intensidad del Entrenamiento',
                'descripcion': f'Tu intensidad promedio es de {intensidad_promedio:.1f} kg/min. Para mejorar la fuerza y potencia, considera reducir los tiempos de descanso entre series o aumentar el peso utilizado.',
                'prioridad': 2,
                'impacto_esperado': 'Mejora en fuerza y capacidad cardiovascular',
                'metricas_base': {'intensidad_actual': intensidad_promedio}
            })
        
        return recomendaciones
    
    def _analizar_progresion(self):
        """
        Analizar progresión en ejercicios específicos
        """
        recomendaciones = []
        
        # Obtener ejercicios más frecuentes
        ejercicios_frecuentes = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=timezone.now().date() - timedelta(days=60)
        ).values('nombre_ejercicio').annotate(
            frecuencia=Count('id')
        ).filter(frecuencia__gte=5).order_by('-frecuencia')[:5]
        
        for ejercicio_data in ejercicios_frecuentes:
            nombre_ejercicio = ejercicio_data['nombre_ejercicio']
            calculadora_progresion = CalculadoraProgresion(self.cliente, nombre_ejercicio)
            tendencia = calculadora_progresion.calcular_tendencia(60)
            
            if tendencia and tendencia.tipo_tendencia == 'estable':
                recomendaciones.append({
                    'tipo': 'ejercicio',
                    'titulo': f'Romper Estancamiento en {nombre_ejercicio}',
                    'descripcion': f'Has mostrado una progresión estable en {nombre_ejercicio} durante las últimas semanas. Considera implementar técnicas avanzadas como series descendentes, pausa-repeticiones, o cambiar el rango de repeticiones para estimular nueva adaptación.',
                    'prioridad': 2,
                    'impacto_esperado': 'Superación de meseta y nueva progresión',
                    'ejercicio_relacionado': nombre_ejercicio,
                    'metricas_base': {
                        'tipo_tendencia': tendencia.tipo_tendencia,
                        'velocidad_progresion': float(tendencia.velocidad_progresion)
                    }
                })
            
            elif tendencia and tendencia.tipo_tendencia == 'decreciente':
                recomendaciones.append({
                    'tipo': 'tecnica',
                    'titulo': f'Revisar Técnica en {nombre_ejercicio}',
                    'descripcion': f'Se ha detectado una tendencia decreciente en {nombre_ejercicio}. Esto podría indicar fatiga acumulada o problemas de técnica. Considera reducir temporalmente la carga y enfocarte en la forma correcta.',
                    'prioridad': 1,
                    'impacto_esperado': 'Prevención de lesiones y mejora técnica',
                    'ejercicio_relacionado': nombre_ejercicio,
                    'metricas_base': {
                        'tipo_tendencia': tendencia.tipo_tendencia,
                        'velocidad_progresion': float(tendencia.velocidad_progresion)
                    }
                })
        
        return recomendaciones
    
    def _analizar_recuperacion(self, metricas):
        """
        Analizar patrones de recuperación
        """
        recomendaciones = []
        consistencia = metricas['consistencia']
        
        if consistencia < 50:  # Menos del 50% de días con entrenamiento
            recomendaciones.append({
                'tipo': 'recuperacion',
                'titulo': 'Mejorar Consistencia de Entrenamiento',
                'descripcion': f'Tu consistencia de entrenamiento es del {consistencia:.1f}%. Para obtener mejores resultados, trata de mantener una rutina más regular. Considera programar entrenamientos en días específicos y crear recordatorios.',
                'prioridad': 1,
                'impacto_esperado': 'Mejores resultados a largo plazo',
                'metricas_base': {'consistencia_actual': consistencia}
            })
        
        return recomendaciones
    
    def _analizar_variedad(self):
        """
        Analizar variedad de ejercicios
        """
        recomendaciones = []
        
        # Contar ejercicios únicos en los últimos 30 días
        ejercicios_unicos = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=timezone.now().date() - timedelta(days=30)
        ).values_list('nombre_ejercicio', flat=True).distinct().count()
        
        if ejercicios_unicos < 10:
            recomendaciones.append({
                'tipo': 'variacion',
                'titulo': 'Aumentar Variedad de Ejercicios',
                'descripcion': f'Has realizado {ejercicios_unicos} ejercicios diferentes en el último mes. Considera incorporar nuevos ejercicios para trabajar los músculos desde diferentes ángulos y prevenir adaptaciones excesivas.',
                'prioridad': 3,
                'impacto_esperado': 'Desarrollo muscular más completo',
                'metricas_base': {'ejercicios_unicos': ejercicios_unicos}
            })
        
        return recomendaciones

class PredictorRendimiento:
    """
    Predictor de rendimiento futuro usando machine learning básico
    """
    
    def __init__(self, cliente):
        self.cliente = cliente
    
    def predecir_1rm(self, nombre_ejercicio, dias_futuro=30):
        """
        Predecir 1RM futuro para un ejercicio específico
        """
        calculadora = CalculadoraProgresion(self.cliente, nombre_ejercicio)
        datos_historicos = calculadora.calcular_progresion_temporal(
            fecha_inicio=timezone.now().date() - timedelta(days=90)
        )
        
        if len(datos_historicos) < 5:
            return None
        
        # Preparar datos para predicción
        fechas_num = [(datetime.strptime(d['fecha'], '%Y-%m-%d').date() - datos_historicos[0]['fecha']).days for d in datos_historicos]
        one_rms = [d['one_rm_estimado'] for d in datos_historicos]
        
        # Regresión lineal simple
        slope, intercept, r_value, p_value, std_err = stats.linregress(fechas_num, one_rms)
        
        # Predecir valor futuro
        dias_desde_inicio = (timezone.now().date() + timedelta(days=dias_futuro) - datos_historicos[0]['fecha']).days
        one_rm_predicho = slope * dias_desde_inicio + intercept
        
        # Calcular confianza basada en R²
        confianza = (r_value ** 2) * 100
        
        # Crear predicción
        prediccion = PrediccionRendimiento.objects.create(
            cliente=self.cliente,
            nombre_ejercicio=nombre_ejercicio,
            tipo_prediccion='1rm',
            valor_actual=one_rms[-1],
            valor_predicho=max(one_rm_predicho, one_rms[-1]),  # No predecir retroceso
            fecha_prediccion=timezone.now().date() + timedelta(days=dias_futuro),
            confianza=min(confianza, 95),  # Máximo 95% de confianza
            algoritmo_usado='regresion_lineal',
            parametros={
                'slope': slope,
                'intercept': intercept,
                'r_value': r_value,
                'datos_utilizados': len(datos_historicos)
            },
            datos_entrenamiento=len(datos_historicos)
        )
        
        return prediccion
    
    def predecir_volumen_semanal(self, semanas_futuro=4):
        """
        Predecir volumen semanal futuro
        """
        # Obtener datos de volumen semanal histórico
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(weeks=12)  # 12 semanas de historia
        
        volumenes_semanales = []
        fecha_semana = fecha_inicio
        
        while fecha_semana <= fecha_fin:
            fecha_fin_semana = fecha_semana + timedelta(days=6)
            
            volumen_semana = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_semana,
                fecha__lte=fecha_fin_semana
            ).aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0
            
            volumenes_semanales.append(float(volumen_semana))
            fecha_semana += timedelta(days=7)
        
        if len(volumenes_semanales) < 4:
            return None
        
        # Usar media móvil para predicción
        ventana = min(4, len(volumenes_semanales))
        volumen_promedio = np.mean(volumenes_semanales[-ventana:])
        
        # Calcular tendencia
        semanas_num = list(range(len(volumenes_semanales)))
        slope, intercept, r_value, p_value, std_err = stats.linregress(semanas_num, volumenes_semanales)
        
        # Predecir volumen futuro
        volumen_predicho = volumen_promedio + (slope * semanas_futuro)
        
        # Confianza basada en consistencia histórica
        std_volumen = np.std(volumenes_semanales)
        cv = std_volumen / volumen_promedio if volumen_promedio > 0 else 1
        confianza = max(20, 100 - (cv * 100))  # Mínimo 20% de confianza
        
        prediccion = PrediccionRendimiento.objects.create(
            cliente=self.cliente,
            tipo_prediccion='volumen',
            valor_actual=volumenes_semanales[-1],
            valor_predicho=max(volumen_predicho, 0),
            fecha_prediccion=timezone.now().date() + timedelta(weeks=semanas_futuro),
            confianza=min(confianza, 90),
            algoritmo_usado='media_movil_con_tendencia',
            parametros={
                'ventana': ventana,
                'slope': slope,
                'cv': cv,
                'datos_utilizados': len(volumenes_semanales)
            },
            datos_entrenamiento=len(volumenes_semanales)
        )
        
        return prediccion
    
    def generar_predicciones_principales(self):
        """
        Generar predicciones para los ejercicios principales del cliente
        """
        predicciones = []
        
        # Obtener ejercicios más frecuentes
        ejercicios_principales = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=timezone.now().date() - timedelta(days=60)
        ).values('nombre_ejercicio').annotate(
            frecuencia=Count('id')
        ).filter(frecuencia__gte=8).order_by('-frecuencia')[:3]
        
        # Generar predicciones de 1RM para ejercicios principales
        for ejercicio_data in ejercicios_principales:
            nombre_ejercicio = ejercicio_data['nombre_ejercicio']
            prediccion = self.predecir_1rm(nombre_ejercicio)
            if prediccion:
                predicciones.append(prediccion)
        
        # Generar predicción de volumen semanal
        prediccion_volumen = self.predecir_volumen_semanal()
        if prediccion_volumen:
            predicciones.append(prediccion_volumen)
        
        return predicciones

class AnalizadorPatrones:
    """
    Analizador de patrones avanzados en los datos de entrenamiento
    """
    
    def __init__(self, cliente):
        self.cliente = cliente
    
    def detectar_estancamientos(self, nombre_ejercicio, ventana_dias=30):
        """
        Detectar estancamientos en la progresión de un ejercicio
        """
        calculadora = CalculadoraProgresion(self.cliente, nombre_ejercicio)
        datos = calculadora.calcular_progresion_temporal(
            fecha_inicio=timezone.now().date() - timedelta(days=90)
        )
        
        if len(datos) < 6:
            return []
        
        estancamientos = []
        pesos_maximos = [d['peso_maximo'] for d in datos]
        
        # Detectar períodos sin progresión significativa
        for i in range(len(pesos_maximos) - 3):
            ventana = pesos_maximos[i:i+4]
            if max(ventana) - min(ventana) < max(ventana) * 0.05:  # Menos del 5% de variación
                estancamientos.append({
                    'inicio': datos[i]['fecha'],
                    'fin': datos[i+3]['fecha'],
                    'peso_promedio': np.mean(ventana),
                    'duracion_dias': (datetime.strptime(datos[i+3]['fecha'], '%Y-%m-%d') - 
                                    datetime.strptime(datos[i]['fecha'], '%Y-%m-%d')).days
                })
        
        return estancamientos
    
    def analizar_patrones_semanales(self):
        """
        Analizar patrones de entrenamiento por día de la semana
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=timezone.now().date() - timedelta(days=90)
        )
        
        patrones_semanales = {}
        
        for entreno in entrenamientos:
            dia_semana = entreno.fecha.strftime('%A')
            
            if dia_semana not in patrones_semanales:
                patrones_semanales[dia_semana] = {
                    'entrenamientos': 0,
                    'volumen_total': 0,
                    'duracion_total': 0
                }
            
            patrones_semanales[dia_semana]['entrenamientos'] += 1
            patrones_semanales[dia_semana]['volumen_total'] += float(entreno.volumen_total_kg or 0)
            patrones_semanales[dia_semana]['duracion_total'] += entreno.duracion_minutos or 0
        
        # Calcular promedios
        for dia, datos in patrones_semanales.items():
            if datos['entrenamientos'] > 0:
                datos['volumen_promedio'] = datos['volumen_total'] / datos['entrenamientos']
                datos['duracion_promedio'] = datos['duracion_total'] / datos['entrenamientos']
        
        return patrones_semanales

