# 🤖 MODELOS PREDICTIVOS IA - VERSIÓN FUNCIONAL SIMPLIFICADA
# Compatible con Django ORM - Sin dependencias pesadas

from datetime import datetime, timedelta
from django.db.models import Count, Avg, Max, Min
import logging
from collections import defaultdict

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos Django
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente


class ModelosPredictivosIA:
    """
    Sistema de predicciones simplificado y funcional
    Compatible con cualquier cantidad de datos
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.configuracion = {
            'ventana_temporal_dias': 90,
            'min_datos_entrenamiento': 3,  # Reducido para funcionar con pocos datos
            'max_peso_realista': 200,
            'min_peso_realista': 0.5,
        }

    def generar_predicciones(self):
        ejercicios = self.obtener_ejercicios_disponibles()
        self.predicciones = []

        for ejercicio in ejercicios:
            try:
                pred = self.predecir_rendimiento_ejercicio(ejercicio)
                pred['nombre_ejercicio'] = ejercicio
                self.predicciones.append(pred)
            except Exception as e:
                logger.warning(f"[predicción] Fallo en {ejercicio}: {e}")

        return self.predicciones

    def _validar_peso(self, peso):
        """Valida que el peso esté en un rango realista"""
        try:
            peso_float = float(peso)
            if peso_float < self.configuracion['min_peso_realista']:
                return None
            if peso_float > self.configuracion['max_peso_realista']:
                return self.configuracion['max_peso_realista']
            return peso_float
        except (ValueError, TypeError):
            return None

    def evaluar_riesgo_lesion(self):
        """
        Evalúa el riesgo de lesión según carga semanal, recuperación y variabilidad.
        Basado en principios de ACWR (Gabbett) y fatiga acumulada.
        """
        import logging
        logger = logging.getLogger(__name__)

        hoy = datetime.today().date()
        hace_28_dias = hoy - timedelta(days=28)

        entrenos = EntrenoRealizado.objects.filter(cliente=self.cliente, fecha__range=(hace_28_dias, hoy))
        ejercicios = EjercicioRealizado.objects.filter(entreno__in=entrenos)

        # Si no hay ejercicios, devolver evaluación vacía
        if not ejercicios.exists():
            return {
                "nivel": "bajo",
                "puntuacion": 15,
                "factores": [],
                "mensaje": "No se encontraron suficientes datos de entrenamiento.",
                "acwr": 0,
                "carga_semanal": [0, 0, 0, 0],
                "recomendaciones": ["Añade más entrenamientos para evaluar el riesgo."],
                "riesgo_detectado": False,
                "mensaje_factores": "Sin datos disponibles.",
                "mensaje_progresion": "No evaluado",
                "mensaje_recuperacion": "No evaluado"
            }

        # Agrupar carga semanal
        carga_por_semana = defaultdict(float)
        dias_sin_entreno = set((hace_28_dias + timedelta(days=i)) for i in range(29))

        for ejercicio in ejercicios:
            fecha = ejercicio.entreno.fecha
            semana = (hoy - fecha).days // 7
            carga = ejercicio.volumen()
            carga_por_semana[semana] += carga
            dias_sin_entreno.discard(fecha)

        cargas = [carga_por_semana.get(i, 0) for i in reversed(range(4))]  # semanas 3,2,1,0
        descansos = [0] * 4
        for i in range(4):
            semana_ini = hoy - timedelta(days=(7 * (3 - i) + 6))
            semana_fin = hoy - timedelta(days=(7 * (3 - i)))
            descansos[i] = sum(1 for d in dias_sin_entreno if semana_ini <= d <= semana_fin)

        acwr = cargas[3] / (sum(cargas[:3]) / 3) if sum(cargas[:3]) > 0 else 0

        # Evaluación del riesgo
        riesgo = 0
        factores = []

        if acwr > 1.5:
            riesgo += 40
            factores.append("Incremento excesivo de carga en la última semana.")

        if max(cargas) - min(cargas) > 3000:
            riesgo += 20
            factores.append("Oscilaciones grandes de carga entre semanas.")

        if descansos[-1] <= 1 and descansos[-2] <= 1:
            riesgo += 25
            factores.append("Descanso insuficiente en las últimas semanas.")

        if cargas[3] > 6500:
            riesgo += 15
            factores.append("Carga semanal total elevada.")

        nivel = "bajo"
        if riesgo >= 70:
            nivel = "alto"
        elif riesgo >= 40:
            nivel = "moderado"

        recomendaciones = [
            "Reduce volumen o intensidad esta semana." if nivel == "alto" else "Mantén la progresión gradual actual.",
            "Incluye días de descanso activos.",
            "Monitorea la carga semanal acumulada.",
            "No incrementes peso más del 10% semanal."
        ]

        logger.debug(
            f"[Riesgo Lesión Evaluado] Resultado: {riesgo} - Nivel: {nivel} - ACWR: {acwr:.2f} - Cargas: {cargas} - Descansos: {descansos}"
        )

        return {
            "nivel": nivel,
            "puntuacion": riesgo,
            "factores": factores,
            "mensaje": f"Nivel de riesgo {nivel} basado en tus patrones recientes.",
            "acwr": round(acwr, 2),
            "carga_semanal": cargas,
            "recomendaciones": recomendaciones,
            "riesgo_detectado": riesgo >= 40,
            "mensaje_factores": "<br>".join(factores) or "Sin factores detectados.",
            "mensaje_progresion": "Progresión con tendencia estable." if acwr < 1.4 else "Progresión acelerada detectada.",
            "mensaje_recuperacion": "Descanso adecuado." if all(
                d > 1 for d in descansos[-2:]) else "Recuperación posiblemente insuficiente."
        }

    def recomendar_optimizaciones(self):
        """Sugerencias inteligentes de volumen e intensidad según progreso"""
        try:
            resumen = self.obtener_resumen_predicciones()
            mejora = resumen.get("precision_promedio", 0)
            ejercicios_ok = resumen.get("ejercicios_con_progreso", 0)

            logger.info(f"[OPTIMIZACION] Mejora: {mejora} | Ejercicios con progreso: {ejercicios_ok}")

            if ejercicios_ok == 0:
                return [
                    {"titulo": "Semana 1-2", "descripcion": "Introduce ejercicios clave y registra datos."},
                    {"titulo": "Semana 3-4", "descripcion": "Aumenta gradualmente intensidad. Prioriza técnica."},
                ]
            elif mejora < 65:
                return [
                    {"titulo": "Semana 1-2", "descripcion": "Reduce volumen a 8-10 series. Mejora recuperación."},
                    {"titulo": "Semana 3-4", "descripcion": "Introduce sesiones de movilidad. Controla intensidad."},
                ]
            elif mejora < 80:
                return [
                    {"titulo": "Semana 1-2", "descripcion": "Volumen moderado (12-14 series). Intensidad 75-80%."},
                    {"titulo": "Semana 3-4", "descripcion": "Mismo volumen, con ligera subida de carga."},
                ]
            else:
                return [
                    {"titulo": "Semana 1-2", "descripcion": "Mantén progresión actual. Técnicas avanzadas opcionales."},
                    {"titulo": "Semana 3-4", "descripcion": "Evalúa introducir drop sets o tempo controlado."},
                ]

        except Exception as e:
            logger.warning(f"[optimización] Error: {e}")
            return []

    def obtener_ejercicios_disponibles(self):
        """Obtiene lista de ejercicios con suficientes datos"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_temporal_dias'])

            ejercicios_query = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                entreno__fecha__gte=fecha_limite,
                peso_kg__gt=0,
                peso_kg__lt=self.configuracion['max_peso_realista']
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(
                cantidad__gte=self.configuracion['min_datos_entrenamiento']
            ).order_by('-cantidad')

            ejercicios = [item['nombre_ejercicio'] for item in ejercicios_query]
            logger.info(f"Ejercicios disponibles: {len(ejercicios)}")
            return ejercicios

        except Exception as e:
            logger.error(f"Error obteniendo ejercicios: {e}")
            return []

    def predecir_rendimiento_ejercicio(self, ejercicio):
        """
        Predice el rendimiento futuro de un ejercicio específico
        Usa análisis de tendencia simple pero efectivo
        """
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_temporal_dias'])

            # Obtener datos históricos
            registros = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                nombre_ejercicio=ejercicio,
                entreno__fecha__gte=fecha_limite,
                peso_kg__gt=0
            ).order_by('entreno__fecha')

            if registros.count() < self.configuracion['min_datos_entrenamiento']:
                return {
                    'prediccion_valida': False,
                    'razon': f'Se necesitan al menos {self.configuracion["min_datos_entrenamiento"]} registros',
                    'registros_actuales': registros.count()
                }

            # Convertir a listas para análisis
            pesos = []
            fechas = []
            for registro in registros:
                peso_validado = self._validar_peso(registro.peso_kg)
                if peso_validado:
                    pesos.append(peso_validado)
                    fechas.append(registro.entreno.fecha)

            if len(pesos) < 3:
                return {'prediccion_valida': False, 'razon': 'Datos insuficientes después de validación'}

            # Análisis de tendencia simple
            peso_inicial = pesos[0]
            peso_actual = pesos[-1]
            peso_maximo = max(pesos)
            peso_promedio = sum(pesos) / len(pesos)

            # Calcular progreso
            if peso_inicial > 0:
                progreso_total = ((peso_actual - peso_inicial) / peso_inicial) * 100
            else:
                progreso_total = 0

            # Calcular tendencia reciente (últimos 5 registros)
            registros_recientes = pesos[-5:] if len(pesos) >= 5 else pesos
            if len(registros_recientes) >= 2:
                tendencia_reciente = registros_recientes[-1] - registros_recientes[0]
            else:
                tendencia_reciente = 0

            # Predicción basada en tendencia y progreso
            factor_prediccion = 1.0

            if progreso_total > 15:  # Progreso excelente
                factor_prediccion = 1.05  # 5% de mejora
            elif progreso_total > 5:  # Progreso bueno
                factor_prediccion = 1.03  # 3% de mejora
            elif progreso_total > 0:  # Progreso leve
                factor_prediccion = 1.02  # 2% de mejora
            elif tendencia_reciente > 0:  # Tendencia positiva reciente
                factor_prediccion = 1.025  # 2.5% de mejora
            else:  # Sin progreso o regresión
                factor_prediccion = 1.01  # 1% de mejora conservadora

            peso_predicho = peso_actual * factor_prediccion

            # Validar predicción
            if peso_predicho > peso_maximo * 1.15:  # No más del 15% sobre el máximo histórico
                peso_predicho = peso_maximo * 1.05

            # Calcular confianza basada en cantidad de datos y consistencia
            confianza_base = min(95, 50 + len(pesos) * 3)

            # Ajustar confianza por consistencia
            if len(pesos) >= 5:
                variabilidad = (max(pesos[-5:]) - min(pesos[-5:])) / peso_promedio
                if variabilidad < 0.1:  # Muy consistente
                    confianza_base += 10
                elif variabilidad > 0.3:  # Muy variable
                    confianza_base -= 15

            confianza = max(60, min(95, confianza_base))

            return {
                'prediccion_valida': True,
                'peso_predicho': round(peso_predicho, 1),
                'peso_actual': peso_actual,
                'peso_maximo': peso_maximo,
                'progreso_total': round(progreso_total, 1),
                'tendencia_reciente': round(tendencia_reciente, 1),
                'confianza': round(confianza, 1),
                'datos_historicos': pesos,
                'fechas_historicas': [f.strftime('%Y-%m-%d') for f in fechas],
                'total_registros': len(pesos),
                'recomendacion': self._generar_recomendacion_prediccion(progreso_total, tendencia_reciente)
            }

        except Exception as e:
            logger.error(f"Error prediciendo {ejercicio}: {e}")
            return {'prediccion_valida': False, 'razon': f'Error: {str(e)}'}

    def _generar_recomendacion_prediccion(self, progreso_total, tendencia_reciente):
        """Genera recomendación basada en la predicción"""
        if progreso_total > 15:
            return "Excelente progreso. Continúa con la progresión actual."
        elif progreso_total > 5:
            return "Buen progreso. Considera aumentar gradualmente la carga."
        elif progreso_total > 0:
            return "Progreso leve. Revisa tu técnica y considera variar el entrenamiento."
        elif tendencia_reciente > 0:
            return "Tendencia positiva reciente. Mantén la consistencia."
        else:
            return "Sin progreso evidente. Considera cambiar el enfoque de entrenamiento."

    def obtener_resumen_predicciones(self):
        """Obtiene resumen general de todas las predicciones"""
        try:
            ejercicios_disponibles = self.obtener_ejercicios_disponibles()

            if not ejercicios_disponibles:
                return {
                    'modelos_activos': 0,
                    'precision_promedio': 0,
                    'total_predicciones': 0,
                    'ejercicios_disponibles': 0,
                    'estado': 'sin_datos'
                }

            predicciones_validas = 0
            suma_confianza = 0
            ejercicios_con_progreso = 0

            for ejercicio in ejercicios_disponibles[:8]:  # Limitar a 8 para rendimiento
                prediccion = self.predecir_rendimiento_ejercicio(ejercicio)
                if prediccion.get('prediccion_valida'):
                    predicciones_validas += 1
                    suma_confianza += prediccion.get('confianza', 0)
                    if prediccion.get('progreso_total', 0) > 0:
                        ejercicios_con_progreso += 1

            precision_promedio = suma_confianza / predicciones_validas if predicciones_validas > 0 else 0

            return {
                'modelos_activos': predicciones_validas,
                'precision_promedio': round(precision_promedio, 1),
                'total_predicciones': predicciones_validas,
                'ejercicios_disponibles': len(ejercicios_disponibles),
                'ejercicios_con_progreso': ejercicios_con_progreso,
                'estado': 'activo' if predicciones_validas > 0 else 'limitado'
            }

        except Exception as e:
            logger.error(f"Error en resumen de predicciones: {e}")
            return {
                'modelos_activos': 0,
                'precision_promedio': 0,
                'total_predicciones': 0,
                'ejercicios_disponibles': 0,
                'ejercicios_con_progreso': 0,
                'estado': 'error'
            }

    def generar_predicciones_multiples(self, ejercicios=None):
        """Genera predicciones para múltiples ejercicios"""
        try:
            if ejercicios is None:
                ejercicios = self.obtener_ejercicios_disponibles()[:5]

            predicciones = []
            for ejercicio in ejercicios:
                prediccion = self.predecir_rendimiento_ejercicio(ejercicio)
                if prediccion.get('prediccion_valida'):
                    predicciones.append({
                        'ejercicio': ejercicio,
                        'datos': prediccion
                    })

            return {
                'predicciones': predicciones,
                'total_generadas': len(predicciones),
                'fecha_generacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            logger.error(f"Error generando predicciones múltiples: {e}")
            return {'predicciones': [], 'total_generadas': 0}

    def obtener_estadisticas_cliente(self):
        """Obtiene estadísticas generales del cliente para contexto"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=90)

            total_entrenamientos = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_limite
            ).count()

            total_ejercicios = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                entreno__fecha__gte=fecha_limite,
                peso_kg__gt=0
            ).count()

            ejercicios_unicos = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                entreno__fecha__gte=fecha_limite
            ).values('nombre_ejercicio').distinct().count()

            return {
                'total_entrenamientos_90d': total_entrenamientos,
                'total_ejercicios_90d': total_ejercicios,
                'ejercicios_unicos': ejercicios_unicos,
                'promedio_ejercicios_por_entreno': round(total_ejercicios / total_entrenamientos,
                                                         1) if total_entrenamientos > 0 else 0,
                'periodo_analisis': '90 días'
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

    def validar_sistema(self):
        """Valida que el sistema esté funcionando correctamente"""
        try:
            ejercicios = self.obtener_ejercicios_disponibles()
            resumen = self.obtener_resumen_predicciones()
            estadisticas = self.obtener_estadisticas_cliente()

            return {
                'sistema_funcional': True,
                'ejercicios_disponibles': len(ejercicios),
                'modelos_activos': resumen.get('modelos_activos', 0),
                'total_entrenamientos': estadisticas.get('total_entrenamientos_90d', 0),
                'recomendacion_sistema': self._generar_recomendacion_sistema(resumen, estadisticas)
            }

        except Exception as e:
            logger.error(f"Error validando sistema: {e}")
            return {
                'sistema_funcional': False,
                'error': str(e)
            }

    def _generar_recomendacion_sistema(self, resumen, estadisticas):
        """Genera recomendación para mejorar el sistema"""
        entrenamientos = estadisticas.get('total_entrenamientos_90d', 0)
        modelos_activos = resumen.get('modelos_activos', 0)

        if entrenamientos < 5:
            return "Registra más entrenamientos para obtener predicciones más precisas."
        elif modelos_activos == 0:
            return "Asegúrate de registrar el peso en tus ejercicios para generar predicciones."
        elif modelos_activos < 3:
            return "Mantén consistencia en tus ejercicios principales para mejorar las predicciones."
        else:
            return "Sistema funcionando correctamente. Continúa registrando tus entrenamientos."
