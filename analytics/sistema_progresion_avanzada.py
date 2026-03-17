from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from clientes.models import Cliente


class TipoProgresion(Enum):
    CARGA = "carga"
    VOLUMEN = "volumen"
    DENSIDAD = "densidad"
    COMPLEJIDAD = "complejidad"
    MANTENIMIENTO = "mantenimiento"
    DESCARGA = "descarga"


class EstadoProgresion(Enum):
    PROGRESANDO = "progresando"
    ESTANCADO = "estancado"
    REGRESANDO = "regresando"
    SOBRECARGADO = "sobrecargado"


@dataclass
class RegistroSerie:
    """Representa una única serie de un ejercicio."""
    peso: float
    repeticiones: int
    rpe: Optional[float] = None


@dataclass
class RegistroEjercicio:
    """Representa todas las series de un ejercicio en una sesión de entrenamiento."""
    fecha: datetime
    ejercicio: str
    series: List[RegistroSerie]
    # Campos adicionales que tu sistema de progresión necesita
    repeticiones_planificadas: int
    rpe_planificado: int
    rpe_real: int
    tiempo_descanso: int
    notas: str = ""


@dataclass
class RegistroSesion:
    fecha: datetime
    ejercicio: str
    peso: float
    series: int
    repeticiones_completadas: List[int]
    repeticiones_planificadas: int
    rpe_planificado: int
    rpe_real: int
    tiempo_descanso: int
    notas: str = ""


@dataclass
class MetricasProgresion:
    ejercicio: str
    carga_total_promedio: float
    volumen_semanal: int
    intensidad_promedio: float
    frecuencia_semanal: int
    tendencia_carga: str  # "subiendo", "bajando", "estable"
    dias_sin_progresion: int
    ultima_progresion: Optional[datetime]


class SistemaProgresionAvanzada:
    '''
    Sistema avanzado de progresión que implementa múltiples tipos de progresión
    según la metodología Helms
    '''

    def __init__(self, cliente_id: int):
        self.cliente = get_object_or_404(Cliente, id=cliente_id)
        self.historial_sesiones: Dict[str, List[RegistroSesion]] = {}
        self.metricas_por_ejercicio: Dict[str, MetricasProgresion] = {}
        self.criterios_progresion = self._definir_criterios_progresion()

    # Helper methods para compatibilidad con RegistroEjercicio y RegistroSesion
    def _obtener_peso(self, sesion):
        """Obtiene el peso de una sesión, compatible con ambos tipos"""
        if hasattr(sesion, 'peso'):
            return sesion.peso
        elif hasattr(sesion, 'series') and sesion.series:
            return sum(s.peso for s in sesion.series) / len(sesion.series)
        return 0

    def _obtener_repeticiones_totales(self, sesion):
        """Obtiene repeticiones totales, compatible con ambos tipos"""
        if hasattr(sesion, 'repeticiones_completadas'):
            if isinstance(sesion.repeticiones_completadas, list):
                return sum(sesion.repeticiones_completadas)
            return sesion.repeticiones_completadas
        elif hasattr(sesion, 'series') and sesion.series:
            return sum(s.repeticiones for s in sesion.series)
        return 0

    def _obtener_series_totales(self, sesion) -> int:
        """Obtiene el número total de series, compatible con ambos tipos"""
        if hasattr(sesion, 'series'):
            if isinstance(sesion.series, list):
                return len(sesion.series)
            return sesion.series
        return 0

    def calcular_ratios_fuerza(self) -> Dict:
        """
        Calcula los ratios de fuerza basándose en los 1RM actuales del cliente.
        Esta es la única fuente de verdad para los ratios.
        """
        print("🔥 Calculando ratios de fuerza desde SistemaProgresionAvanzada (versión corregida)...")

        # Leemos los 1RM directamente del modelo Cliente.
        records_1rm = self.cliente.one_rm_data or {}
        print(f"   -> 1RMs leídos del cliente: {records_1rm}")

        # Lógica para normalizar nombres para los ratios
        records_normalizados = {}
        mapeo_nombres = {
            'sentadilla': ['sentadilla trasera con barra', 'sentadilla frontal con barra'],
            'press banca': ['press banca con barra', 'press banca con mancuernas'],
            'peso muerto': ['peso muerto', 'peso muerto rumano', 'peso muerto sumo'],
        }

        for nombre_canonico, variaciones in mapeo_nombres.items():
            max_rm = 0
            for variacion in variaciones:
                if variacion in records_1rm and records_1rm[variacion] > max_rm:
                    max_rm = records_1rm[variacion]
            if max_rm > 0:
                records_normalizados[nombre_canonico] = max_rm

        print(f"   -> 1RMs normalizados para ratios: {records_normalizados}")

        # Cálculo de ratios
        press = records_normalizados.get('press banca', 0)
        sentadilla = records_normalizados.get('sentadilla', 0)
        peso_muerto = records_normalizados.get('peso muerto', 0)

        ratios = []
        if sentadilla > 0:
            ratios.append({
                'nombre': 'Press/Sentadilla',
                'valor': round(press / sentadilla, 2) if press > 0 else 0,
                'estado': 'optimo' if 0.7 <= (press / sentadilla) <= 0.8 else 'bajo'
            })
            ratios.append({
                'nombre': 'Peso Muerto/Sentadilla',
                'valor': round(peso_muerto / sentadilla, 2) if peso_muerto > 0 else 0,
                'estado': 'optimo' if 1.2 <= (peso_muerto / sentadilla) <= 1.3 else 'bajo'
            })

        return {
            'ratios': ratios,
            'puntos_debiles': [r['nombre'] for r in ratios if r['estado'] != 'optimo'],
            'grafico_radar': {
                'labels': [r['nombre'] for r in ratios],
                'valores': [r['valor'] for r in ratios],
                'optimos': [0.75, 1.25]
            }
        }

    def _definir_criterios_progresion(self) -> Dict[str, Dict]:
        '''Define criterios específicos para cada tipo de progresión'''
        return {
            'carga': {
                'condicion': 'completar_todas_reps_rpe_objetivo',
                'incremento_minimo': 2.5,  # kg
                'incremento_maximo': 10.0,  # kg
                'sesiones_consecutivas_requeridas': 2
            },
            'volumen': {
                'condicion': 'carga_estancada_pero_rpe_bajo',
                'incremento_series': 1,
                'maximo_series': 6,
                'sesiones_consecutivas_requeridas': 3
            },
            'densidad': {
                'condicion': 'volumen_maximo_alcanzado',
                'reduccion_descanso': 15,  # segundos
                'descanso_minimo': 60,  # segundos
                'sesiones_consecutivas_requeridas': 2
            },
            'complejidad': {
                'condicion': 'parametros_basicos_optimizados',
                'variaciones_disponibles': ['tempo', 'rango_movimiento', 'estabilidad'],
                'sesiones_consecutivas_requeridas': 4
            }
        }

    def registrar_sesion(self, registro: RegistroSesion):
        '''Registra una nueva sesión de entrenamiento'''
        ejercicio = registro.ejercicio

        if ejercicio not in self.historial_sesiones:
            self.historial_sesiones[ejercicio] = []

        self.historial_sesiones[ejercicio].append(registro)
        self._actualizar_metricas_ejercicio(ejercicio)

    def _actualizar_metricas_ejercicio(self, ejercicio: str):
        '''Actualiza métricas de progresión para un ejercicio específico'''
        historial = self.historial_sesiones[ejercicio]

        if not historial:
            return

        # Calcular métricas básicas
        sesiones_recientes = historial[-4:]  # Últimas 4 sesiones

        carga_total_promedio = sum(
            self._obtener_peso(s) * self._obtener_repeticiones_totales(s)
            for s in sesiones_recientes
        ) / len(sesiones_recientes)

        volumen_semanal = sum(
            self._obtener_repeticiones_totales(s)
            for s in sesiones_recientes
        )

        # Helper para obtener RPE
        def obtener_rpe(sesion):
            if hasattr(sesion, 'rpe_real'):
                return sesion.rpe_real
            elif hasattr(sesion, 'series') and sesion.series:
                rpes = [s.rpe for s in sesion.series if s.rpe is not None]
                return sum(rpes) / len(rpes) if rpes else 7.0
            return 7.0

        intensidad_promedio = sum(obtener_rpe(s) for s in sesiones_recientes) / len(sesiones_recientes)

        # Calcular tendencia de carga
        if len(historial) >= 2:
            carga_anterior = self._obtener_peso(historial[-2]) * self._obtener_repeticiones_totales(historial[-2])
            carga_actual = self._obtener_peso(historial[-1]) * self._obtener_repeticiones_totales(historial[-1])

            if carga_actual > carga_anterior * 1.05:
                tendencia = "subiendo"
            elif carga_actual < carga_anterior * 0.95:
                tendencia = "bajando"
            else:
                tendencia = "estable"
        else:
            tendencia = "insuficientes_datos"

        # Calcular días sin progresión
        dias_sin_progresion = self._calcular_dias_sin_progresion(ejercicio)

        # Encontrar última progresión
        ultima_progresion = self._encontrar_ultima_progresion(ejercicio)

        # Actualizar métricas
        self.metricas_por_ejercicio[ejercicio] = MetricasProgresion(
            ejercicio=ejercicio,
            carga_total_promedio=carga_total_promedio,
            volumen_semanal=volumen_semanal,
            intensidad_promedio=intensidad_promedio,
            frecuencia_semanal=len(sesiones_recientes),
            tendencia_carga=tendencia,
            dias_sin_progresion=dias_sin_progresion,
            ultima_progresion=ultima_progresion
        )

    def _calcular_dias_sin_progresion(self, ejercicio: str) -> int:
        '''Calcula días desde la última progresión significativa'''
        historial = self.historial_sesiones[ejercicio]

        if len(historial) < 2:
            return 0

        dias = 0
        for i in range(len(historial) - 1, 0, -1):
            sesion_actual = historial[i]
            sesion_anterior = historial[i - 1]

            # Verificar si hubo progresión
            carga_actual = self._obtener_peso(sesion_actual) * self._obtener_repeticiones_totales(sesion_actual)
            carga_anterior = self._obtener_peso(sesion_anterior) * self._obtener_repeticiones_totales(sesion_anterior)

            if carga_actual > carga_anterior * 1.05:  # 5% de incremento
                break

            dias += (sesion_actual.fecha - sesion_anterior.fecha).days

        return dias

    def _encontrar_ultima_progresion(self, ejercicio: str) -> Optional[datetime]:
        '''Encuentra la fecha de la última progresión significativa'''
        historial = self.historial_sesiones[ejercicio]

        if len(historial) < 2:
            return None

        for i in range(len(historial) - 1, 0, -1):
            sesion_actual = historial[i]
            sesion_anterior = historial[i - 1]

            carga_actual = self._obtener_peso(sesion_actual) * self._obtener_repeticiones_totales(sesion_actual)
            carga_anterior = self._obtener_peso(sesion_anterior) * self._obtener_repeticiones_totales(sesion_anterior)

            if carga_actual > carga_anterior * 1.05:
                return sesion_actual.fecha

        return None

    def determinar_tipo_progresion(self, ejercicio: str) -> TipoProgresion:
        '''Determina qué tipo de progresión aplicar para un ejercicio'''
        if ejercicio not in self.historial_sesiones:
            return TipoProgresion.CARGA

        historial = self.historial_sesiones[ejercicio]
        if len(historial) < 2:
            return TipoProgresion.CARGA

        ultima_sesion = historial[-1]
        metricas = self.metricas_por_ejercicio.get(ejercicio)

        if not metricas:
            return TipoProgresion.CARGA

        # Verificar condiciones para progresión de carga
        if self._puede_progresar_carga(ejercicio):
            return TipoProgresion.CARGA

        # Verificar condiciones para progresión de volumen
        elif self._puede_progresar_volumen(ejercicio):
            return TipoProgresion.VOLUMEN

        # Verificar condiciones para progresión de densidad
        elif self._puede_progresar_densidad(ejercicio):
            return TipoProgresion.DENSIDAD

        # Verificar si necesita descarga
        elif self._necesita_descarga(ejercicio):
            return TipoProgresion.DESCARGA

        # Si está estancado, considerar progresión de complejidad
        elif metricas.dias_sin_progresion > 14:
            return TipoProgresion.COMPLEJIDAD

        return TipoProgresion.MANTENIMIENTO

    def _puede_progresar_carga(self, ejercicio: str) -> bool:
        '''Verifica si puede progresar en carga'''
        historial = self.historial_sesiones[ejercicio]
        if len(historial) < 2:
            return True

        # Verificar últimas 2 sesiones
        sesiones_recientes = historial[-2:]

        for sesion in sesiones_recientes:
            # Verificar si completó todas las repeticiones
            reps_completadas = self._obtener_repeticiones_totales(sesion)
            reps_planificadas = sesion.repeticiones_planificadas * self._obtener_series_totales(sesion)

            # Verificar si RPE fue igual o menor al objetivo
            if reps_completadas < reps_planificadas or sesion.rpe_real > sesion.rpe_planificado:
                return False

        return True

    def _puede_progresar_volumen(self, ejercicio: str) -> bool:
        '''Verifica si puede progresar en volumen'''
        metricas = self.metricas_por_ejercicio.get(ejercicio)
        if not metricas:
            return False

        # Si la carga está estancada pero el RPE es bajo
        if (metricas.dias_sin_progresion > 7 and
                metricas.intensidad_promedio < 8.0 and
                metricas.volumen_semanal < 25):  # Máximo razonable de series
            return True

        return False

    def _puede_progresar_densidad(self, ejercicio: str) -> bool:
        '''Verifica si puede progresar en densidad'''
        historial = self.historial_sesiones[ejercicio]
        if not historial:
            return False

        ultima_sesion = historial[-1]

        # Si el volumen está en el máximo y el descanso puede reducirse
        if (ultima_sesion.tiempo_descanso > 90 and
                len(historial) >= 3):
            return True

        return False

    def _necesita_descarga(self, ejercicio: str) -> bool:
        '''Verifica si necesita una semana de descarga'''
        metricas = self.metricas_por_ejercicio.get(ejercicio)
        if not metricas:
            return False

        # Si la intensidad promedio es muy alta y hay estancamiento
        if (metricas.intensidad_promedio > 8.5 and
                metricas.dias_sin_progresion > 10):
            return True

        return False

    def aplicar_progresion(self, ejercicio: str, tipo_progresion: TipoProgresion) -> Dict[str, Any]:
        '''Aplica el tipo de progresión especificado'''
        if ejercicio not in self.historial_sesiones:
            return {'error': 'No hay historial para este ejercicio'}

        ultima_sesion = self.historial_sesiones[ejercicio][-1]

        if tipo_progresion == TipoProgresion.CARGA:
            return self._aplicar_progresion_carga(ejercicio, ultima_sesion)

        elif tipo_progresion == TipoProgresion.VOLUMEN:
            return self._aplicar_progresion_volumen(ejercicio, ultima_sesion)

        elif tipo_progresion == TipoProgresion.DENSIDAD:
            return self._aplicar_progresion_densidad(ejercicio, ultima_sesion)

        elif tipo_progresion == TipoProgresion.DESCARGA:
            return self._aplicar_descarga(ejercicio, ultima_sesion)

        elif tipo_progresion == TipoProgresion.COMPLEJIDAD:
            return self._aplicar_progresion_complejidad(ejercicio, ultima_sesion)

        else:  # MANTENIMIENTO
            return self._mantener_parametros(ejercicio, ultima_sesion)

    def _aplicar_progresion_carga(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Aplica progresión de carga'''
        incremento = self.criterios_progresion['carga']['incremento_minimo']

        # Ajustar incremento basándose en el ejercicio
        if 'press' in ejercicio.lower() or 'sentadilla' in ejercicio.lower():
            incremento = 2.5
        else:
            incremento = 1.25  # Incrementos menores para ejercicios de aislamiento

        peso_base = self._obtener_peso(ultima_sesion)
        nuevo_peso = peso_base + incremento

        return {
            'tipo': 'carga',
            'peso_anterior': peso_base,
            'peso_nuevo': nuevo_peso,
            'incremento': incremento,
            'series': self._obtener_series_totales(ultima_sesion),
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'rpe_objetivo': ultima_sesion.rpe_planificado,
            'mensaje': f"Incrementar peso de {peso_base}kg a {nuevo_peso}kg"
        }

    def _aplicar_progresion_volumen(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Aplica progresión de volumen'''
        series_actuales = self._obtener_series_totales(ultima_sesion)
        nuevas_series = min(series_actuales + 1, 6)  # Máximo 6 series

        return {
            'tipo': 'volumen',
            'peso': self._obtener_peso(ultima_sesion),
            'series_anteriores': series_actuales,
            'series_nuevas': nuevas_series,
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'rpe_objetivo': ultima_sesion.rpe_planificado,
            'mensaje': f"Incrementar de {series_actuales} a {nuevas_series} series"
        }

    def _aplicar_progresion_densidad(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Aplica progresión de densidad'''
        reduccion = self.criterios_progresion['densidad']['reduccion_descanso']
        nuevo_descanso = max(ultima_sesion.tiempo_descanso - reduccion, 60)

        return {
            'tipo': 'densidad',
            'peso': self._obtener_peso(ultima_sesion),
            'series': self._obtener_series_totales(ultima_sesion),
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'descanso_anterior': ultima_sesion.tiempo_descanso,
            'descanso_nuevo': nuevo_descanso,
            'rpe_objetivo': ultima_sesion.rpe_planificado,
            'mensaje': f"Reducir descanso de {ultima_sesion.tiempo_descanso}s a {nuevo_descanso}s"
        }

    def _aplicar_descarga(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Aplica semana de descarga'''
        peso_base = self._obtener_peso(ultima_sesion)
        peso_descarga = peso_base * 0.8  # 80% del peso
        series_actuales = self._obtener_series_totales(ultima_sesion)
        series_descarga = max(series_actuales - 1, 2)  # Reducir series
        rpe_descarga = max(ultima_sesion.rpe_planificado - 2, 6)  # RPE más bajo

        return {
            'tipo': 'descarga',
            'peso_anterior': peso_base,
            'peso_descarga': peso_descarga,
            'series_anteriores': series_actuales,
            'series_descarga': series_descarga,
            'rpe_anterior': ultima_sesion.rpe_planificado,
            'rpe_descarga': rpe_descarga,
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'mensaje': f"Semana de descarga: {peso_descarga}kg, {series_descarga} series, RPE {rpe_descarga}"
        }

    def _aplicar_progresion_complejidad(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Aplica progresión de complejidad'''
        variaciones = {
            'press_banca': 'press_banca_inclinado',
            'sentadilla': 'sentadilla_frontal',
            'peso_muerto': 'peso_muerto_rumano',
            'remo': 'remo_con_mancuerna'
        }

        ejercicio_base = ejercicio.lower().replace('_', ' ')
        nueva_variacion = variaciones.get(ejercicio, f"{ejercicio}_variacion")
        
        peso_base = self._obtener_peso(ultima_sesion)

        return {
            'tipo': 'complejidad',
            'ejercicio_anterior': ejercicio,
            'ejercicio_nuevo': nueva_variacion,
            'peso': peso_base * 0.9,  # Reducir peso para nueva variación
            'series': self._obtener_series_totales(ultima_sesion),
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'rpe_objetivo': ultima_sesion.rpe_planificado,
            'mensaje': f"Cambiar a variación más compleja: {nueva_variacion}"
        }

    def _mantener_parametros(self, ejercicio: str, ultima_sesion: RegistroSesion) -> Dict[str, Any]:
        '''Mantiene parámetros actuales'''
        return {
            'tipo': 'mantenimiento',
            'peso': self._obtener_peso(ultima_sesion),
            'series': self._obtener_series_totales(ultima_sesion),
            'repeticiones': ultima_sesion.repeticiones_planificadas,
            'rpe_objetivo': ultima_sesion.rpe_planificado,
            'mensaje': "Mantener parámetros actuales y enfocar en técnica"
        }

    def detectar_estancamientos(self) -> Dict[str, Dict]:
        '''Detecta estancamientos en todos los ejercicios'''
        estancamientos = {}

        for ejercicio, metricas in self.metricas_por_ejercicio.items():
            if metricas.dias_sin_progresion > 14:  # 2 semanas sin progresión
                tipo_progresion = self.determinar_tipo_progresion(ejercicio)
                recomendacion = self.aplicar_progresion(ejercicio, tipo_progresion)

                estancamientos[ejercicio] = {
                    'dias_estancado': metricas.dias_sin_progresion,
                    'ultima_progresion': metricas.ultima_progresion.isoformat() if metricas.ultima_progresion else None,
                    'tipo_progresion_recomendada': tipo_progresion.value,
                    'recomendacion': recomendacion
                }

        return estancamientos

    def generar_reporte_progresion(self) -> Dict[str, Any]:
        '''Genera reporte completo de progresión'''
        estancamientos = self.detectar_estancamientos()

        return {
            'cliente_id': self.cliente_id,
            'fecha_reporte': datetime.now().isoformat(),
            'metricas_por_ejercicio': {
                ejercicio: {
                    'carga_promedio': metricas.carga_total_promedio,
                    'volumen_semanal': metricas.volumen_semanal,
                    'intensidad_promedio': metricas.intensidad_promedio,
                    'tendencia': metricas.tendencia_carga,
                    'dias_sin_progresion': metricas.dias_sin_progresion
                }
                for ejercicio, metricas in self.metricas_por_ejercicio.items()
            },
            'estancamientos_detectados': estancamientos,
            'resumen': {
                'ejercicios_progresando': len(
                    [m for m in self.metricas_por_ejercicio.values() if m.dias_sin_progresion <= 7]),
                'ejercicios_estancados': len(
                    [m for m in self.metricas_por_ejercicio.values() if m.dias_sin_progresion > 14]),
                'ejercicios_total': len(self.metricas_por_ejercicio)
            }
        }


# Integración con el sistema existente
def crear_sistema_progresion(cliente_id: int) -> SistemaProgresionAvanzada:
    '''Factory function para crear sistema de progresión'''
    return SistemaProgresionAvanzada(cliente_id)


def obtener_recomendaciones_progresion(cliente_id: int) -> Dict:
    '''Función helper para obtener recomendaciones de progresión'''
    sistema = SistemaProgresionAvanzada(cliente_id)
    # En implementación real, cargaría datos desde base de datos
    return sistema.generar_reporte_progresion()
