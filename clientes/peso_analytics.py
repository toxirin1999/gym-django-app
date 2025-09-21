# Módulo de análisis avanzado para el control de peso
# Inspirado en las funcionalidades de HappyScale

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import statistics
from django.db.models import QuerySet

class AnalizadorPeso:
    """
    Clase para realizar análisis avanzados de peso corporal,
    incluyendo tendencias, predicciones y métricas motivacionales.
    """
    
    def __init__(self, registros_peso: QuerySet):
        """
        Inicializa el analizador con los registros de peso del cliente.
        
        Args:
            registros_peso: QuerySet de PesoDiario ordenado por fecha
        """
        self.registros = list(registros_peso.order_by('fecha'))
        self.pesos = [float(r.peso_kg) for r in self.registros]
        self.fechas = [r.fecha for r in self.registros]
    
    def calcular_promedio_movil(self, dias: int = 7) -> List[Dict]:
        """
        Calcula el promedio móvil de peso para suavizar fluctuaciones diarias.
        
        Args:
            dias: Número de días para el promedio móvil (por defecto 7)
            
        Returns:
            Lista de diccionarios con fecha y promedio móvil
        """
        if len(self.registros) < dias:
            return []
        
        promedios = []
        for i in range(dias - 1, len(self.registros)):
            inicio = max(0, i - dias + 1)
            peso_promedio = statistics.mean(self.pesos[inicio:i + 1])
            promedios.append({
                'fecha': self.fechas[i],
                'peso_promedio': round(peso_promedio, 2)
            })
        
        return promedios
    
    def calcular_tendencia_semanal(self) -> Dict:
        """
        Calcula la tendencia de peso en los últimos 7 días.
        
        Returns:
            Diccionario con información de la tendencia semanal
        """
        if len(self.registros) < 2:
            return {'cambio': 0, 'direccion': 'sin_datos', 'porcentaje': 0}
        
        # Obtener registros de los últimos 7 días
        fecha_limite = date.today() - timedelta(days=7)
        registros_recientes = [r for r in self.registros if r.fecha >= fecha_limite]
        
        if len(registros_recientes) < 2:
            return {'cambio': 0, 'direccion': 'sin_datos', 'porcentaje': 0}
        
        peso_inicial = float(registros_recientes[0].peso_kg)
        peso_final = float(registros_recientes[-1].peso_kg)
        cambio = peso_final - peso_inicial
        porcentaje = (cambio / peso_inicial) * 100 if peso_inicial > 0 else 0
        
        if cambio > 0.1:
            direccion = 'subiendo'
        elif cambio < -0.1:
            direccion = 'bajando'
        else:
            direccion = 'estable'
        
        return {
            'cambio': round(cambio, 2),
            'direccion': direccion,
            'porcentaje': round(porcentaje, 2)
        }
    
    def calcular_tendencia_mensual(self) -> Dict:
        """
        Calcula la tendencia de peso en los últimos 30 días.
        
        Returns:
            Diccionario con información de la tendencia mensual
        """
        if len(self.registros) < 2:
            return {'cambio': 0, 'direccion': 'sin_datos', 'porcentaje': 0}
        
        # Obtener registros de los últimos 30 días
        fecha_limite = date.today() - timedelta(days=30)
        registros_recientes = [r for r in self.registros if r.fecha >= fecha_limite]
        
        if len(registros_recientes) < 2:
            return {'cambio': 0, 'direccion': 'sin_datos', 'porcentaje': 0}
        
        peso_inicial = float(registros_recientes[0].peso_kg)
        peso_final = float(registros_recientes[-1].peso_kg)
        cambio = peso_final - peso_inicial
        porcentaje = (cambio / peso_inicial) * 100 if peso_inicial > 0 else 0
        
        if cambio > 0.5:
            direccion = 'subiendo'
        elif cambio < -0.5:
            direccion = 'bajando'
        else:
            direccion = 'estable'
        
        return {
            'cambio': round(cambio, 2),
            'direccion': direccion,
            'porcentaje': round(porcentaje, 2)
        }
    
    def predecir_fecha_objetivo(self, peso_objetivo: float) -> Optional[date]:
        """
        Predice cuándo se alcanzará un peso objetivo basándose en la tendencia actual.
        
        Args:
            peso_objetivo: Peso objetivo en kg
            
        Returns:
            Fecha estimada para alcanzar el objetivo o None si no es posible predecir
        """
        if len(self.registros) < 14:  # Necesitamos al menos 2 semanas de datos
            return None
        
        # Calcular la tasa de cambio promedio por día en las últimas 2 semanas
        registros_recientes = self.registros[-14:]
        if len(registros_recientes) < 2:
            return None
        
        peso_inicial = float(registros_recientes[0].peso_kg)
        peso_final = float(registros_recientes[-1].peso_kg)
        dias_transcurridos = (registros_recientes[-1].fecha - registros_recientes[0].fecha).days
        
        if dias_transcurridos == 0:
            return None
        
        tasa_cambio_diaria = (peso_final - peso_inicial) / dias_transcurridos
        
        # Si la tasa de cambio es muy pequeña, no podemos hacer una predicción confiable
        if abs(tasa_cambio_diaria) < 0.01:
            return None
        
        # Calcular días necesarios para alcanzar el objetivo
        diferencia_peso = peso_objetivo - peso_final
        dias_necesarios = diferencia_peso / tasa_cambio_diaria
        
        # Solo hacer predicciones para objetivos alcanzables en un plazo razonable (1 año)
        if dias_necesarios < 0 or dias_necesarios > 365:
            return None
        
        fecha_predicha = self.fechas[-1] + timedelta(days=int(dias_necesarios))
        return fecha_predicha
    
    def calcular_metricas_motivacionales(self) -> Dict:
        """
        Calcula métricas motivacionales para mantener al usuario comprometido.
        
        Returns:
            Diccionario con métricas motivacionales
        """
        if not self.registros:
            return {}
        
        # Racha de registros consecutivos
        racha_actual = self._calcular_racha_actual()
        
        # Peso mínimo y máximo histórico
        peso_minimo = min(self.pesos)
        peso_maximo = max(self.pesos)
        peso_actual = self.pesos[-1]
        
        # Progreso desde el inicio
        if len(self.registros) > 1:
            peso_inicial = self.pesos[0]
            cambio_total = peso_actual - peso_inicial
            porcentaje_cambio_total = (cambio_total / peso_inicial) * 100
        else:
            cambio_total = 0
            porcentaje_cambio_total = 0
        
        return {
            'racha_dias': racha_actual,
            'peso_minimo': peso_minimo,
            'peso_maximo': peso_maximo,
            'peso_actual': peso_actual,
            'cambio_total': round(cambio_total, 2),
            'porcentaje_cambio_total': round(porcentaje_cambio_total, 2),
            'total_registros': len(self.registros)
        }
    
    def _calcular_racha_actual(self) -> int:
        """
        Calcula la racha actual de días consecutivos con registro de peso.
        
        Returns:
            Número de días consecutivos con registro
        """
        if not self.registros:
            return 0
        
        racha = 1
        fecha_actual = self.fechas[-1]
        
        # Verificar hacia atrás desde la fecha más reciente
        for i in range(len(self.fechas) - 2, -1, -1):
            fecha_anterior = self.fechas[i]
            diferencia = (fecha_actual - fecha_anterior).days
            
            if diferencia == 1:
                racha += 1
                fecha_actual = fecha_anterior
            else:
                break
        
        return racha
    
    def generar_resumen_completo(self, objetivo_peso: Optional[float] = None) -> Dict:
        """
        Genera un resumen completo con todas las métricas y análisis.
        
        Args:
            objetivo_peso: Peso objetivo opcional para incluir predicciones
            
        Returns:
            Diccionario con resumen completo del análisis
        """
        resumen = {
            'tendencia_semanal': self.calcular_tendencia_semanal(),
            'tendencia_mensual': self.calcular_tendencia_mensual(),
            'metricas_motivacionales': self.calcular_metricas_motivacionales(),
            'promedio_movil': self.calcular_promedio_movil()
        }
        
        if objetivo_peso:
            resumen['prediccion_objetivo'] = self.predecir_fecha_objetivo(objetivo_peso)
        
        return resumen

