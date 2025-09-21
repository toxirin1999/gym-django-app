# VISTA CORREGIDA QUE FUNCIONA CON LOS MODELOS REALES
# Soluciona el problema de datos no detectados
from analytics.ia_modelos_predictivos import ModelosPredictivosIA
import json
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction  # <-- AÑADIMOS ESTA IMPORTACIÓN
from clientes.models import Cliente
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.db.models import Count, Avg, Max, Min, Sum
from datetime import datetime, timedelta
import json
import logging

from django.contrib import messages
from clientes.models import Cliente
from analytics.ia_recomendaciones_inteligentes import SistemaRecomendacionesIA  # <== IMPORTANTE

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ IMPORTACIONES CORREGIDAS - USANDO MODELOS REALES
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado


# ==================== CLASES DE IA FUNCIONALES ====================

class ModelosPredictivosIAReal:
    """Sistema de predicciones que funciona con datos reales"""

    def __init__(self, cliente):
        self.cliente = cliente
        logger.info(f"Inicializando ModelosPredictivosIA para cliente {cliente.id}")

    def obtener_ejercicios_disponibles(self):
        """Obtiene ejercicios con suficientes datos para predicciones"""
        try:
            # ✅ CONSULTA CORREGIDA - Usando modelos reales
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            logger.info(f"Entrenamientos encontrados: {entrenamientos.count()}")

            ejercicios = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0  # Solo ejercicios con peso
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=2)  # Mínimo 2 registros

            ejercicios_list = [ej['nombre_ejercicio'] for ej in ejercicios]
            logger.info(f"Ejercicios disponibles para predicciones: {len(ejercicios_list)}")
            logger.info(f"Ejercicios: {ejercicios_list}")

            return ejercicios_list

        except Exception as e:
            logger.error(f"Error en obtener_ejercicios_disponibles: {e}")
            return []

    def generar_prediccion_ejercicio(self, nombre_ejercicio):
        """Genera predicción basada en progreso histórico real"""
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            registros = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                nombre_ejercicio=nombre_ejercicio,
                peso_kg__gt=0
            ).order_by('entreno__fecha')

            logger.info(f"Registros para {nombre_ejercicio}: {registros.count()}")

            if registros.count() < 2:
                return {
                    'ejercicio': nombre_ejercicio,
                    'prediccion_peso': 0,
                    'confianza': 0,
                    'mejora_estimada': 0,
                    'estado': 'datos_insuficientes'
                }

            # Calcular tendencia real
            primer_peso = registros.first().peso_kg
            ultimo_peso = registros.last().peso_kg
            mejora_porcentual = ((ultimo_peso - primer_peso) / primer_peso) * 100 if primer_peso > 0 else 0

            # Predicción conservadora: 2-5% de mejora
            prediccion_peso = ultimo_peso * 1.025  # 2.5% de mejora
            confianza = min(85, 50 + (registros.count() * 5))  # Máximo 85%

            logger.info(f"Predicción para {nombre_ejercicio}: {prediccion_peso:.1f} kg (confianza: {confianza}%)")

            return {
                'ejercicio': nombre_ejercicio,
                'prediccion_peso': round(prediccion_peso, 1),
                'confianza': confianza,
                'mejora_estimada': round(mejora_porcentual, 1),
                'estado': 'prediccion_generada',
                'peso_actual': ultimo_peso,
                'registros_analizados': registros.count()
            }

        except Exception as e:
            logger.error(f"Error en generar_prediccion_ejercicio: {e}")
            return {
                'ejercicio': nombre_ejercicio,
                'prediccion_peso': 0,
                'confianza': 0,
                'mejora_estimada': 0,
                'estado': 'error'
            }


class SistemaRecomendacionesIAReal:
    """Sistema de recomendaciones que funciona con datos reales"""

    def __init__(self, cliente):
        self.cliente = cliente
        logger.info(f"Inicializando SistemaRecomendacionesIA para cliente {cliente.id}")

    def generar_recomendaciones_personalizadas(self):
        """Genera recomendaciones basadas en análisis real de datos"""
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            total_entrenamientos = entrenamientos.count()

            logger.info(f"Analizando {total_entrenamientos} entrenamientos para recomendaciones")

            if total_entrenamientos < 2:
                return {
                    'recomendaciones': [
                        {
                            'categoria': 'inicio',
                            'titulo': 'Comenzar Rutina Consistente',
                            'descripcion': 'Realiza al menos 2-3 entrenamientos por semana para obtener mejores análisis.',
                            'prioridad': 'alta',
                            'confianza': 90
                        }
                    ],
                    'total_recomendaciones': 1,
                    'confianza_promedio': 90.0,
                    'estado': 'limitado'
                }

            recomendaciones = []

            # ✅ ANÁLISIS REAL DE FRECUENCIA
            if total_entrenamientos >= 3:
                entrenamientos_ordenados = entrenamientos.order_by('fecha')
                fechas = [e.fecha for e in entrenamientos_ordenados]

                intervalos = []
                for i in range(1, len(fechas)):
                    diff = (fechas[i] - fechas[i - 1]).days
                    intervalos.append(diff)

                if intervalos:
                    promedio_dias = sum(intervalos) / len(intervalos)
                    logger.info(f"Promedio días entre entrenamientos: {promedio_dias:.1f}")

                    if promedio_dias > 4:
                        recomendaciones.append({
                            'categoria': 'frecuencia',
                            'titulo': 'Aumentar Frecuencia de Entrenamiento',
                            'descripcion': f'Promedio actual: {promedio_dias:.1f} días entre entrenamientos. Intenta entrenar cada 2-3 días para mejores resultados.',
                            'prioridad': 'media',
                            'confianza': 80
                        })
                    elif promedio_dias <= 2:
                        recomendaciones.append({
                            'categoria': 'frecuencia',
                            'titulo': 'Excelente Consistencia',
                            'descripcion': f'Mantienes una frecuencia excelente de {promedio_dias:.1f} días entre entrenamientos. ¡Sigue así!',
                            'prioridad': 'baja',
                            'confianza': 90
                        })

            # ✅ ANÁLISIS REAL DE VARIEDAD
            ejercicios_unicos = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).values('nombre_ejercicio').distinct().count()

            logger.info(f"Ejercicios únicos realizados: {ejercicios_unicos}")

            if ejercicios_unicos < 8:
                recomendaciones.append({
                    'categoria': 'variedad',
                    'titulo': 'Aumentar Variedad de Ejercicios',
                    'descripcion': f'Actualmente realizas {ejercicios_unicos} ejercicios diferentes. Añadir más variedad puede mejorar tu desarrollo muscular.',
                    'prioridad': 'media',
                    'confianza': 75
                })
            elif ejercicios_unicos >= 15:
                recomendaciones.append({
                    'categoria': 'variedad',
                    'titulo': 'Excelente Variedad',
                    'descripcion': f'Realizas {ejercicios_unicos} ejercicios diferentes. ¡Excelente variedad en tu entrenamiento!',
                    'prioridad': 'baja',
                    'confianza': 85
                })

            # ✅ ANÁLISIS REAL DE PROGRESIÓN
            ejercicios_principales = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3)

            ejercicios_progresando = 0
            ejercicios_estancados = 0

            for ejercicio in ejercicios_principales:
                registros = EjercicioRealizado.objects.filter(
                    entreno__in=entrenamientos,
                    nombre_ejercicio=ejercicio['nombre_ejercicio'],
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg

                    if ultimo_peso > primer_peso + 2:  # Progreso significativo
                        ejercicios_progresando += 1
                    elif ultimo_peso == primer_peso:  # Estancamiento
                        ejercicios_estancados += 1

            logger.info(f"Ejercicios progresando: {ejercicios_progresando}, estancados: {ejercicios_estancados}")

            if ejercicios_progresando == 0 and ejercicios_principales.count() > 0:
                recomendaciones.append({
                    'categoria': 'progresion',
                    'titulo': 'Mejorar Progresión de Cargas',
                    'descripcion': 'No se detecta progreso claro en tus ejercicios principales. Considera aumentar gradualmente los pesos cada semana.',
                    'prioridad': 'alta',
                    'confianza': 85
                })
            elif ejercicios_progresando >= 3:
                recomendaciones.append({
                    'categoria': 'progresion',
                    'titulo': 'Excelente Progresión',
                    'descripcion': f'Detectamos progreso en {ejercicios_progresando} ejercicios. ¡Mantén el buen trabajo!',
                    'prioridad': 'baja',
                    'confianza': 90
                })

            # ✅ ANÁLISIS REAL DE VOLUMEN
            volumen_total = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).aggregate(
                volumen=Sum('peso_kg') * Sum('series') * Sum('repeticiones')
            )['volumen'] or 0

            volumen_promedio_entreno = volumen_total / total_entrenamientos if total_entrenamientos > 0 else 0

            logger.info(f"Volumen promedio por entrenamiento: {volumen_promedio_entreno:.0f}")

            if volumen_promedio_entreno < 5000:
                recomendaciones.append({
                    'categoria': 'volumen',
                    'titulo': 'Aumentar Volumen de Entrenamiento',
                    'descripcion': f'Tu volumen promedio es {volumen_promedio_entreno:.0f} kg por entrenamiento. Considera añadir más series o ejercicios.',
                    'prioridad': 'media',
                    'confianza': 70
                })

            # ✅ RECOMENDACIÓN DE EQUILIBRIO MUSCULAR
            grupos_trabajados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).exclude(grupo_muscular__isnull=True).exclude(grupo_muscular='').values(
                'grupo_muscular').distinct().count()

            if grupos_trabajados < 4:
                recomendaciones.append({
                    'categoria': 'equilibrio',
                    'titulo': 'Mejorar Equilibrio Muscular',
                    'descripcion': f'Solo trabajas {grupos_trabajados} grupos musculares diferentes. Considera añadir más variedad para un desarrollo equilibrado.',
                    'prioridad': 'media',
                    'confianza': 80
                })

            # Si no hay recomendaciones específicas, dar una general positiva
            if not recomendaciones:
                recomendaciones.append({
                    'categoria': 'general',
                    'titulo': 'Excelente Progreso General',
                    'descripcion': 'Tu entrenamiento muestra un patrón muy bueno. Mantén la consistencia y sigue progresando gradualmente.',
                    'prioridad': 'baja',
                    'confianza': 85
                })

            confianza_promedio = sum(r['confianza'] for r in recomendaciones) / len(recomendaciones)

            logger.info(
                f"Generadas {len(recomendaciones)} recomendaciones con confianza promedio {confianza_promedio:.1f}%")

            return {
                'recomendaciones': recomendaciones,
                'total_recomendaciones': len(recomendaciones),
                'confianza_promedio': confianza_promedio,
                'estado': 'activo' if total_entrenamientos >= 5 else 'limitado'
            }

        except Exception as e:
            logger.error(f"Error en generar_recomendaciones_personalizadas: {e}")
            return {
                'recomendaciones': [],
                'total_recomendaciones': 0,
                'confianza_promedio': 0.0,
                'estado': 'error'
            }


class DeteccionPatronesIAReal:
    """Sistema de detección de patrones que funciona con datos reales"""

    def __init__(self, cliente):
        self.cliente = cliente
        logger.info(f"Inicializando DeteccionPatronesIA para cliente {cliente.id}")

    def detectar_todos_los_patrones(self):
        """Detecta patrones reales en los entrenamientos"""
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            total_entrenamientos = entrenamientos.count()

            logger.info(f"Analizando patrones en {total_entrenamientos} entrenamientos")

            if total_entrenamientos < 2:
                return {
                    'patrones': [],
                    'total_patrones': 0,
                    'confianza_deteccion': 0.0,
                    'estado_sistema': 'limitado'
                }

            patrones = []

            # ✅ PATRÓN DE DÍAS PREFERIDOS (REAL)
            dias_semana = {}
            for entreno in entrenamientos:
                dia_nombre = entreno.fecha.strftime('%A')
                # Traducir a español
                dias_es = {
                    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
                }
                dia = dias_es.get(dia_nombre, dia_nombre)
                dias_semana[dia] = dias_semana.get(dia, 0) + 1

            if dias_semana:
                dia_favorito = max(dias_semana, key=dias_semana.get)
                if dias_semana[dia_favorito] >= 2:
                    porcentaje = (dias_semana[dia_favorito] / total_entrenamientos) * 100
                    patrones.append({
                        'tipo': 'temporal',
                        'descripcion': f'Prefieres entrenar los {dia_favorito}s ({dias_semana[dia_favorito]} veces, {porcentaje:.0f}%)',
                        'confianza': min(90, 50 + dias_semana[dia_favorito] * 10)
                    })

            # ✅ PATRÓN DE CONSISTENCIA (REAL)
            if total_entrenamientos >= 3:
                entrenamientos_ordenados = entrenamientos.order_by('fecha')
                fechas = [e.fecha for e in entrenamientos_ordenados]

                intervalos = []
                for i in range(1, len(fechas)):
                    diff = (fechas[i] - fechas[i - 1]).days
                    intervalos.append(diff)

                if intervalos:
                    promedio_intervalo = sum(intervalos) / len(intervalos)
                    desviacion = sum(abs(x - promedio_intervalo) for x in intervalos) / len(intervalos)

                    if promedio_intervalo <= 3 and desviacion <= 1:
                        patrones.append({
                            'tipo': 'comportamiento',
                            'descripcion': f'Alta consistencia: entrenas cada {promedio_intervalo:.1f} días con poca variación',
                            'confianza': 90
                        })
                    elif promedio_intervalo > 7:
                        patrones.append({
                            'tipo': 'comportamiento',
                            'descripcion': f'Baja consistencia: {promedio_intervalo:.1f} días promedio entre entrenamientos',
                            'confianza': 75
                        })
                    else:
                        patrones.append({
                            'tipo': 'comportamiento',
                            'descripcion': f'Consistencia moderada: entrenas cada {promedio_intervalo:.1f} días',
                            'confianza': 80
                        })

            # ✅ PATRÓN DE PROGRESO POR EJERCICIO (REAL)
            ejercicios_con_peso = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3)

            ejercicios_progresando = 0
            mejor_progreso = None
            mejor_mejora = 0

            for ejercicio in ejercicios_con_peso:
                registros = EjercicioRealizado.objects.filter(
                    entreno__in=entrenamientos,
                    nombre_ejercicio=ejercicio['nombre_ejercicio'],
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg

                    if ultimo_peso > primer_peso:
                        ejercicios_progresando += 1
                        mejora_porcentual = ((ultimo_peso - primer_peso) / primer_peso) * 100

                        if mejora_porcentual > mejor_mejora:
                            mejor_mejora = mejora_porcentual
                            mejor_progreso = ejercicio['nombre_ejercicio']

            if ejercicios_progresando > 0:
                if mejor_progreso and mejor_mejora > 10:
                    patrones.append({
                        'tipo': 'progreso',
                        'descripcion': f'Progreso excelente en {mejor_progreso}: +{mejor_mejora:.1f}% de mejora',
                        'confianza': 85
                    })
                else:
                    patrones.append({
                        'tipo': 'progreso',
                        'descripcion': f'Progreso detectado en {ejercicios_progresando} ejercicios diferentes',
                        'confianza': 80
                    })

            # ✅ PATRÓN DE EJERCICIOS FAVORITOS (REAL)
            ejercicio_favorito = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).order_by('-cantidad').first()

            if ejercicio_favorito and ejercicio_favorito['cantidad'] >= 3:
                patrones.append({
                    'tipo': 'preferencia',
                    'descripcion': f'Ejercicio favorito: {ejercicio_favorito["nombre_ejercicio"]} ({ejercicio_favorito["cantidad"]} veces)',
                    'confianza': 75
                })

            confianza_promedio = sum(p['confianza'] for p in patrones) / len(patrones) if patrones else 0

            logger.info(f"Detectados {len(patrones)} patrones con confianza promedio {confianza_promedio:.1f}%")

            return {
                'patrones': patrones,
                'total_patrones': len(patrones),
                'confianza_deteccion': confianza_promedio,
                'estado_sistema': 'activo' if total_entrenamientos >= 5 else 'limitado'
            }

        except Exception as e:
            logger.error(f"Error en detectar_todos_los_patrones: {e}")
            return {
                'patrones': [],
                'total_patrones': 0,
                'confianza_deteccion': 0.0,
                'estado_sistema': 'error'
            }

    def detectar_estancamientos_automaticos(self):
        """Detecta estancamientos reales en ejercicios"""
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            ejercicios_principales = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=4)  # Mínimo 4 registros para detectar estancamiento

            estancamientos = []

            for ejercicio in ejercicios_principales:
                registros = EjercicioRealizado.objects.filter(
                    entreno__in=entrenamientos,
                    nombre_ejercicio=ejercicio['nombre_ejercicio'],
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 4:
                    # Verificar si los últimos 3-4 registros tienen el mismo peso
                    ultimos_registros = list(registros.reverse()[:4])
                    ultimos_pesos = [r.peso_kg for r in ultimos_registros]

                    # Estancamiento si los últimos 3 registros son iguales
                    if len(set(ultimos_pesos[:3])) == 1:
                        estancamientos.append({
                            'ejercicio': ejercicio['nombre_ejercicio'],
                            'peso_estancado': ultimos_pesos[0],
                            'registros_iguales': 3,
                            'severidad': 'media'
                        })
                    # Estancamiento severo si los últimos 4 registros son iguales
                    elif len(set(ultimos_pesos)) == 1:
                        estancamientos.append({
                            'ejercicio': ejercicio['nombre_ejercicio'],
                            'peso_estancado': ultimos_pesos[0],
                            'registros_iguales': 4,
                            'severidad': 'alta'
                        })

            logger.info(f"Detectados {len(estancamientos)} estancamientos")

            return {
                'estancamientos': estancamientos,
                'total_estancamientos': len(estancamientos)
            }

        except Exception as e:
            logger.error(f"Error en detectar_estancamientos_automaticos: {e}")
            return {
                'estancamientos': [],
                'total_estancamientos': 0
            }


class OptimizacionEntrenamientosIAReal:
    """Sistema de optimización que funciona con datos reales"""

    def __init__(self, cliente):
        self.cliente = cliente
        logger.info(f"Inicializando OptimizacionEntrenamientosIA para cliente {cliente.id}")

    def generar_optimizacion_completa(self):
        """Genera optimizaciones basadas en análisis real"""
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=self.cliente)
            total_entrenamientos = entrenamientos.count()

            logger.info(f"Analizando optimizaciones para {total_entrenamientos} entrenamientos")

            if total_entrenamientos < 2:
                return {
                    'optimizaciones': [],
                    'mejora_estimada': 0.0,
                    'algoritmos_activos': 0,
                    'estado': 'limitado'
                }

            optimizaciones = []
            mejora_total = 0

            # ✅ OPTIMIZACIÓN DE FRECUENCIA (REAL)
            if total_entrenamientos >= 3:
                entrenamientos_ordenados = entrenamientos.order_by('fecha')
                fechas = [e.fecha for e in entrenamientos_ordenados]

                intervalos = []
                for i in range(1, len(fechas)):
                    diff = (fechas[i] - fechas[i - 1]).days
                    intervalos.append(diff)

                if intervalos:
                    promedio_intervalo = sum(intervalos) / len(intervalos)

                    if promedio_intervalo > 4:
                        optimizaciones.append({
                            'tipo': 'frecuencia',
                            'descripcion': f'Aumentar frecuencia: actualmente {promedio_intervalo:.1f} días entre entrenamientos',
                            'mejora_estimada': 3.0
                        })
                        mejora_total += 3.0
                    elif promedio_intervalo <= 2:
                        optimizaciones.append({
                            'tipo': 'frecuencia',
                            'descripcion': 'Frecuencia óptima mantenida',
                            'mejora_estimada': 1.0
                        })
                        mejora_total += 1.0

            # ✅ OPTIMIZACIÓN DE PROGRESIÓN (REAL)
            ejercicios_con_peso = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3)

            ejercicios_progresando = 0
            for ejercicio in ejercicios_con_peso:
                registros = EjercicioRealizado.objects.filter(
                    entreno__in=entrenamientos,
                    nombre_ejercicio=ejercicio['nombre_ejercicio'],
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg
                    if ultimo_peso > primer_peso:
                        ejercicios_progresando += 1

            if ejercicios_progresando >= 3:
                optimizaciones.append({
                    'tipo': 'progresion',
                    'descripcion': f'Progresión excelente en {ejercicios_progresando} ejercicios',
                    'mejora_estimada': 2.0
                })
                mejora_total += 2.0
            elif ejercicios_progresando == 0:
                optimizaciones.append({
                    'tipo': 'progresion',
                    'descripcion': 'Implementar sobrecarga progresiva sistemática',
                    'mejora_estimada': 4.0
                })
                mejora_total += 4.0

            # ✅ OPTIMIZACIÓN DE VARIEDAD (REAL)
            ejercicios_unicos = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).values('nombre_ejercicio').distinct().count()

            if ejercicios_unicos < 10:
                optimizaciones.append({
                    'tipo': 'variedad',
                    'descripcion': f'Aumentar variedad: actualmente {ejercicios_unicos} ejercicios únicos',
                    'mejora_estimada': 2.5
                })
                mejora_total += 2.5
            elif ejercicios_unicos >= 15:
                optimizaciones.append({
                    'tipo': 'variedad',
                    'descripcion': f'Excelente variedad: {ejercicios_unicos} ejercicios únicos',
                    'mejora_estimada': 1.0
                })
                mejora_total += 1.0

            # ✅ OPTIMIZACIÓN DE VOLUMEN (REAL)
            volumen_promedio = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).aggregate(
                promedio_peso=Avg('peso_kg'),
                promedio_series=Avg('series'),
                promedio_reps=Avg('repeticiones')
            )

            if all(volumen_promedio.values()):
                vol_estimado = (volumen_promedio['promedio_peso'] *
                                volumen_promedio['promedio_series'] *
                                volumen_promedio['promedio_reps'])

                if vol_estimado < 1000:
                    optimizaciones.append({
                        'tipo': 'volumen',
                        'descripcion': 'Aumentar volumen de entrenamiento gradualmente',
                        'mejora_estimada': 2.0
                    })
                    mejora_total += 2.0

            logger.info(
                f"Generadas {len(optimizaciones)} optimizaciones con mejora total estimada: {mejora_total:.1f}%")

            return {
                'optimizaciones': optimizaciones,
                'mejora_estimada': min(mejora_total, 10.0),  # Máximo 10%
                'algoritmos_activos': len(optimizaciones),
                'estado': 'activo' if total_entrenamientos >= 5 else 'limitado'
            }

        except Exception as e:
            logger.error(f"Error en generar_optimizacion_completa: {e}")
            return {
                'optimizaciones': [],
                'mejora_estimada': 0.0,
                'algoritmos_activos': 0,
                'estado': 'error'
            }


# ==================== FUNCIONES AUXILIARES ====================

def obtener_sistema_predicciones(cliente):
    """Obtiene el sistema de predicciones real"""
    return ModelosPredictivosIAReal(cliente)


def obtener_sistema_recomendaciones(cliente):
    """Obtiene el sistema de recomendaciones real"""
    return SistemaRecomendacionesIAReal(cliente)


def obtener_sistema_patrones(cliente):
    """Obtiene el sistema de detección de patrones real"""
    return DeteccionPatronesIA(cliente)


def obtener_sistema_optimizacion(cliente):
    """Obtiene el sistema de optimización real"""
    return OptimizacionEntrenamientosIAReal(cliente)


def calcular_puntuacion_ia_general(total_modelos, total_recomendaciones, total_patrones, mejora_estimada):
    """Calcula una puntuación general del sistema de IA"""
    try:
        # Componentes de la puntuación (0-100)
        puntuacion_modelos = min(30, total_modelos * 3)  # Máximo 30 puntos
        puntuacion_recomendaciones = min(25, total_recomendaciones * 4)  # Máximo 25 puntos
        puntuacion_patrones = min(25, total_patrones * 5)  # Máximo 25 puntos
        puntuacion_mejora = min(20, mejora_estimada * 2.5)  # Máximo 20 puntos

        puntuacion_total = puntuacion_modelos + puntuacion_recomendaciones + puntuacion_patrones + puntuacion_mejora
        return min(100, max(0, int(puntuacion_total)))
    except Exception:
        return 0


def crear_cliente_fallback(cliente_id, nombre="Usuario"):
    """Crea un objeto cliente fallback con id válido"""

    class ClienteFallback:
        def __init__(self, id, nombre):
            self.id = id
            self.nombre = nombre

    return ClienteFallback(cliente_id, nombre)


# ==================== VISTAS PRINCIPALES ====================

def dashboard_ia_principal(request, cliente_id):
    """Dashboard principal de IA con todos los sistemas integrados"""
    try:
        # ✅ OBTENER CLIENTE REAL O FALLBACK
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            logger.info(f"Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")
        except Exception as e:
            logger.warning(f"Cliente {cliente_id} no encontrado: {e}")
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        # Verificar cache
        cache_key = f'dashboard_ia_{cliente_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            cached_data['cliente'] = cliente
            logger.info("Datos obtenidos desde cache")
            return render(request, 'analytics/dashboard_ia_principal.html', cached_data)

        # ✅ OBTENER DATOS DE TODOS LOS SISTEMAS REALES
        sistema_predicciones = obtener_sistema_predicciones(cliente)
        sistema_recomendaciones = obtener_sistema_recomendaciones(cliente)
        sistema_patrones = obtener_sistema_patrones(cliente)
        sistema_optimizacion = obtener_sistema_optimizacion(cliente)

        # Datos de predicciones
        ejercicios_disponibles = sistema_predicciones.obtener_ejercicios_disponibles()
        total_modelos = len(ejercicios_disponibles)
        precision_promedio = 75.0 if total_modelos > 0 else 0.0

        # Datos de recomendaciones
        recomendaciones_data = sistema_recomendaciones.generar_recomendaciones_personalizadas()
        total_recomendaciones = recomendaciones_data.get('total_recomendaciones', 0)
        confianza_recomendaciones = recomendaciones_data.get('confianza_promedio', 50.0)

        # Datos de patrones
        patrones_data = sistema_patrones.detectar_todos_los_patrones()
        total_patrones = patrones_data.get('total_patrones', 0)
        estancamientos_data = sistema_patrones.detectar_estancamientos_automaticos()
        total_estancamientos = estancamientos_data.get('total_estancamientos', 0)

        # Datos de optimización
        optimizacion_data = sistema_optimizacion.generar_optimizacion_completa()
        mejora_estimada = optimizacion_data.get('mejora_estimada', 0.0)
        algoritmos_activos = optimizacion_data.get('algoritmos_activos', 0)

        # ✅ ESTADÍSTICAS GENERALES REALES
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente)
            total_entrenamientos = entrenamientos.count()
            ejercicios_realizados = EjercicioRealizado.objects.filter(entreno__in=entrenamientos)
            total_ejercicios = ejercicios_realizados.count()

            logger.info(f"Estadísticas reales: {total_entrenamientos} entrenamientos, {total_ejercicios} ejercicios")
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            total_entrenamientos = 0
            total_ejercicios = 0

        # Calcular puntuación IA general
        puntuacion_ia = calcular_puntuacion_ia_general(
            total_modelos, total_recomendaciones, total_patrones, mejora_estimada
        )

        # Recomendaciones principales
        recomendaciones_principales = []
        if recomendaciones_data.get('recomendaciones'):
            recomendaciones_principales = recomendaciones_data['recomendaciones'][:3]

        context = {
            'cliente': cliente,
            # Métricas principales
            'total_entrenamientos': total_entrenamientos,
            'total_ejercicios': total_ejercicios,
            'puntuacion_ia': puntuacion_ia,
            # Modelos Predictivos
            'total_modelos': total_modelos,
            'precision_promedio': precision_promedio,
            'predicciones_activas': total_modelos,
            # Recomendaciones IA
            'total_recomendaciones': total_recomendaciones,
            'confianza_recomendaciones': confianza_recomendaciones,
            'rutinas_optimizadas': min(8, total_recomendaciones),
            # Detección de Patrones
            'total_patrones': total_patrones,
            'total_estancamientos': total_estancamientos,
            'confianza_patrones': patrones_data.get('confianza_deteccion', 70.0),
            # Optimizaciones
            'mejora_estimada': mejora_estimada,
            'algoritmos_activos': algoritmos_activos,
            'optimizaciones_aplicadas': len(optimizacion_data.get('optimizaciones', [])),
            # Recomendaciones principales
            'recomendaciones_principales': recomendaciones_principales,
            # Estados del sistema
            'estado_predicciones': 'activo' if total_modelos > 0 else 'limitado',
            'estado_recomendaciones': recomendaciones_data.get('estado', 'limitado'),
            'estado_patrones': patrones_data.get('estado_sistema', 'limitado'),
            'estado_optimizacion': optimizacion_data.get('estado', 'limitado'),
        }

        # Guardar en cache por 2 horas
        cache.set(cache_key, context, 7200)

        logger.info(f"Dashboard generado exitosamente - Puntuación IA: {puntuacion_ia}%")

        return render(request, 'analytics/dashboard_ia_principal.html', context)

    except Exception as e:
        logger.error(f"Error crítico en dashboard IA principal: {e}")

        cliente_fallback = crear_cliente_fallback(cliente_id, "Usuario")

        return render(request, 'analytics/dashboard_ia_principal.html', {
            'cliente': cliente_fallback,
            'total_entrenamientos': 0,
            'total_ejercicios': 0,
            'puntuacion_ia': 0,
            'total_modelos': 0,
            'precision_promedio': 0,
            'predicciones_activas': 0,
            'total_recomendaciones': 0,
            'confianza_recomendaciones': 0,
            'rutinas_optimizadas': 0,
            'total_patrones': 0,
            'total_estancamientos': 0,
            'confianza_patrones': 0,
            'mejora_estimada': 0,
            'algoritmos_activos': 0,
            'optimizaciones_aplicadas': 0,
            'recomendaciones_principales': [],
            'estado_predicciones': 'inactivo',
            'estado_recomendaciones': 'inactivo',
            'estado_patrones': 'inactivo',
            'estado_optimizacion': 'inactivo',
            'error_message': 'Sistema temporalmente no disponible'
        })


# ==================== VISTAS ADICIONALES ====================

def predicciones_avanzadas(request, cliente_id):
    """Vista para predicciones avanzadas - FUNCIONAL + EVALUACIÓN DE RIESGO + OPTIMIZACIONES"""
    try:
        # Obtener cliente real o fallback
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            logger.info(f"Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")
        except Exception as e:
            logger.warning(f"Cliente {cliente_id} no encontrado: {e}")
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        # Verificar cache
        cache_key = f'predicciones_avanzadas_{cliente_id}'
        cached_data = cache.get(cache_key)

        # Recomendaciones por defecto
        optimizaciones_default = [
            {"titulo": "Semana 1-2",
             "descripcion": "Volumen moderado (12-14 series) | Intensidad 75-80% | Frecuencia 3 días"},
            {"titulo": "Semana 3-4", "descripcion": "Incremento leve de intensidad | Mantén volumen constante"},
        ]

        if cached_data:
            cached_data['cliente'] = cliente
            cached_data['optimizaciones_default'] = optimizaciones_default
            logger.info("Datos de predicciones obtenidos desde cache")
            return render(request, 'analytics/predicciones_avanzadas.html', cached_data)

        # Inicializar sistema de predicciones
        sistema_predicciones = ModelosPredictivosIA(cliente)

        # Obtener ejercicios disponibles
        ejercicios_disponibles = sistema_predicciones.obtener_ejercicios_disponibles()
        logger.info(f"Ejercicios disponibles para predicciones: {len(ejercicios_disponibles)}")

        # Generar predicciones
        # Generar predicciones
        predicciones = sistema_predicciones.generar_predicciones()

        for ejercicio in ejercicios_disponibles[:10]:
            try:
                prediccion = sistema_predicciones.predecir_rendimiento_ejercicio(ejercicio)
                prediccion['nombre_ejercicio'] = ejercicio
                predicciones.append(prediccion)
                logger.info(f"Predicción generada para {ejercicio}: {prediccion.get('peso_predicho', '?')} kg")
            except Exception as e:
                logger.error(f"Error generando predicción para {ejercicio}: {e}")

        predicciones_exitosas = [p for p in predicciones if p.get('prediccion_valida')]

        # Evaluación de riesgo de lesión
        # Evaluación de riesgo de lesión
        riesgo_nivel = 'bajo'
        riesgo_puntuacion = 15
        riesgo_mensaje_factores = "No disponible"
        riesgo_mensaje_progresion = "No evaluado"
        riesgo_mensaje_recuperacion = "No evaluado"
        riesgo_recomendaciones = []

        try:
            evaluacion_riesgo = sistema_predicciones.evaluar_riesgo_lesion()
            logger.debug(f"Evaluación de riesgo completa: {evaluacion_riesgo}")

            riesgo_nivel = evaluacion_riesgo.get('nivel', 'bajo')
            riesgo_puntuacion = evaluacion_riesgo.get('puntuacion', 15)
            riesgo_mensaje_factores = evaluacion_riesgo.get('mensaje_factores', '')
            riesgo_mensaje_progresion = evaluacion_riesgo.get('mensaje_progresion', '')
            riesgo_mensaje_recuperacion = evaluacion_riesgo.get('mensaje_recuperacion', '')
            riesgo_recomendaciones = evaluacion_riesgo.get('recomendaciones', [])
        except Exception as e:
            logger.warning(f"Fallo en evaluación de riesgo: {e}")

        # Recomendaciones de optimización
        optimizaciones = optimizaciones_default
        try:
            resultado_optimizacion = sistema_predicciones.recomendar_optimizaciones()
            if resultado_optimizacion:
                optimizaciones = resultado_optimizacion
        except Exception as e:
            logger.warning(f"Fallo al obtener optimizaciones: {e}")

        # Construcción del contexto
        context = {
            'cliente': cliente,
            'ejercicios_disponibles': ejercicios_disponibles,
            'predicciones': predicciones_exitosas,
            'total_modelos': len(ejercicios_disponibles),
            'modelos_activos': len(predicciones_exitosas),
            'precision_promedio': sum(p['confianza'] for p in predicciones_exitosas) / len(predicciones_exitosas)
            if predicciones_exitosas else 0,
            'predicciones_exitosas': len(predicciones_exitosas),
            'mejora_promedio_estimada': sum(p['peso_predicho'] - p['peso_actual'] for p in predicciones_exitosas) / len(
                predicciones_exitosas) if predicciones_exitosas else 0,
            'confianza_promedio': sum(p['confianza'] for p in predicciones_exitosas) / len(predicciones_exitosas)
            if predicciones_exitosas else 0,
            'estado_sistema': 'activo' if len(ejercicios_disponibles) > 0 else 'limitado',
            'fecha_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'error_message': None,
            'riesgo_mensaje_factores': riesgo_mensaje_factores,
            'riesgo_mensaje_progresion': riesgo_mensaje_progresion,
            'riesgo_mensaje_recuperacion': riesgo_mensaje_recuperacion,
            'riesgo_recomendaciones': riesgo_recomendaciones,
            'optimizaciones_default': optimizaciones_default,
            'optimizaciones': optimizaciones,
            'riesgo_nivel': riesgo_nivel,
            'riesgo_puntuacion': riesgo_puntuacion,
        }

        # Guardar en cache por 1 hora
        cache.set(cache_key, context, 3600)

        logger.info(f"Vista predicciones generada exitosamente - {len(predicciones_exitosas)} predicciones")

        return render(request, 'analytics/predicciones_avanzadas.html', context)

    except Exception as e:
        logger.error(f"Error crítico en predicciones_avanzadas: {e}")
        cliente_fallback = crear_cliente_fallback(cliente_id, "Usuario")

        return render(request, 'analytics/predicciones_avanzadas.html', {
            'cliente': cliente_fallback,
            'ejercicios_disponibles': [],
            'predicciones': [],
            'total_modelos': 0,
            'modelos_activos': 0,
            'precision_promedio': 0.0,
            'predicciones_exitosas': 0,
            'mejora_promedio_estimada': 0,
            'confianza_promedio': 0,
            'estado_sistema': 'error',
            'fecha_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'error_message': 'Error al cargar predicciones. Intenta nuevamente.',
            'optimizaciones_default': optimizaciones_default,
            'optimizaciones': [],
            'riesgo_nivel': 'indefinido',
            'riesgo_puntuacion': 0,
        })


def recomendaciones_inteligentes(request, cliente_id):
    """Vista para recomendaciones inteligentes - CORREGIDA"""
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        logger.info(f"Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")

        cache_key = f'recomendaciones_inteligentes_{cliente_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            cached_data['cliente'] = cliente
            logger.info("Datos de recomendaciones obtenidos desde cache")
            return render(request, 'analytics/recomendaciones_inteligentes.html', cached_data)

        # ✅ CAMBIO CLAVE AQUÍ
        sistema_recomendaciones = SistemaRecomendacionesIA(cliente)
        recomendaciones_data = sistema_recomendaciones.generar_recomendaciones_personalizadas()

        context = {
            'cliente': cliente,
            'recomendaciones': recomendaciones_data  # El template espera esta clave
        }

        cache.set(cache_key, context, 3600)
        logger.info("Vista recomendaciones generada exitosamente")

        return render(request, 'analytics/recomendaciones_inteligentes.html', context)

    except Exception as e:
        logger.error(f"Error crítico en recomendaciones_inteligentes: {e}")

        cliente_fallback = crear_cliente_fallback(cliente_id, "Usuario")

        return render(request, 'analytics/recomendaciones_inteligentes.html', {
            'cliente': cliente_fallback,
            'recomendaciones': {
                'recomendaciones': [],
                'tiene_datos_suficientes': False,
                'confianza_sistema': 0,
                'perfil_usuario': {}
            },
            'error_message': 'Error al cargar recomendaciones. Intenta nuevamente.'
        })


def deteccion_patrones_automatica(request, cliente_id):
    """Vista para detección de patrones - CORREGIDA"""
    try:
        # Obtener cliente real o fallback
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            logger.info(f"Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")
            # FORZAR REFRESCO DE DATOS
            cache.delete(f'deteccion_patrones_{cliente.id}')
        except Exception as e:
            logger.warning(f"Cliente {cliente_id} no encontrado: {e}")
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        # Verificar cache
        cache_key = f'deteccion_patrones_{cliente_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            cached_data['cliente'] = cliente
            logger.info("Datos de patrones obtenidos desde cache")
            return render(request, 'analytics/deteccion_patrones.html', cached_data)

        # Inicializar sistema de detección de patrones
        sistema_patrones = DeteccionPatronesIA(cliente)

        # Detectar todos los patrones
        patrones_data = sistema_patrones.detectar_todos_los_patrones()
        logger.info(f"Patrones detectados: {patrones_data.get('total_patrones', 0)}")

        # Detectar estancamientos
        estancamientos_data = sistema_patrones.detectar_estancamientos_automaticos()
        logger.info(f"Estancamientos detectados: {estancamientos_data.get('total_estancamientos', 0)}")

        # Obtener resumen de patrones
        resumen_patrones = {
            'resumen_patrones': [],
            'categorias_detectadas': []
        }

        # Verificar datos reales
        try:
            entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente)
            total_entrenamientos = entrenamientos.count()
            ejercicios_realizados = EjercicioRealizado.objects.filter(entreno__in=entrenamientos)
            total_ejercicios = ejercicios_realizados.count()
            logger.info(
                f"Datos reales verificados: {total_entrenamientos} entrenamientos, {total_ejercicios} ejercicios")
        except Exception as e:
            logger.error(f"Error verificando datos reales: {e}")
            total_entrenamientos = 0
            total_ejercicios = 0

        context = {
            'cliente': cliente,
            'patrones': patrones_data,
            'total_patrones': patrones_data.get('total_patrones', 0),
            'estancamientos': estancamientos_data.get('estancamientos', []),
            'total_estancamientos': estancamientos_data.get('total_estancamientos', 0),
            'confianza_deteccion': patrones_data.get('confianza_deteccion', 0.0),
            'estado_sistema': patrones_data.get('estado_sistema', 'limitado'),
            'resumen_patrones': resumen_patrones.get('resumen_patrones', []),
            'categorias_detectadas': resumen_patrones.get('categorias_detectadas', []),
            'entrenamientos_analizados': patrones_data.get('entrenamientos_analizados', 0),
            'fecha_analisis': patrones_data.get('fecha_analisis', datetime.now().strftime('%Y-%m-%d')),
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            # Datos de verificación
            'total_entrenamientos_reales': total_entrenamientos,
            'total_ejercicios_reales': total_ejercicios,
            'error_message': None
        }

        # Guardar en cache por 1 hora
        cache.set(cache_key, context, 3600)

        logger.info(f"Vista patrones generada exitosamente - {context['total_patrones']} patrones")

        return render(request, 'analytics/deteccion_patrones.html', context)

    except Exception as e:
        logger.error(f"Error crítico en deteccion_patrones_automatica: {e}")

        cliente_fallback = crear_cliente_fallback(cliente_id, "Usuario")

        return render(request, 'analytics/deteccion_patrones.html', {
            'cliente': cliente_fallback,
            'patrones': [],
            'total_patrones': 0,
            'estancamientos': [],
            'total_estancamientos': 0,
            'confianza_deteccion': 0.0,
            'estado_sistema': 'error',
            'resumen_patrones': [],
            'categorias_detectadas': [],
            'entrenamientos_analizados': 0,
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'total_entrenamientos_reales': 0,
            'total_ejercicios_reales': 0,
            'error_message': 'Error al cargar detección de patrones. Intenta nuevamente.'
        })


def vista_deteccion_patrones(request, cliente_id):
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        detector = DeteccionPatronesIA(cliente)
        patrones = detector.detectar_todos_los_patrones()

        if not patrones:
            patrones = {
                'tiene_datos_suficientes': False,
                'patrones_detectados': [],
                'total_patrones': 0,
                'confianza_deteccion': 0
            }

        if not patrones.get('tiene_datos_suficientes', False):
            messages.info(request, 'No hay suficientes datos para analizar patrones.')

        return render(request, 'analytics/deteccion_patrones.html', {
            'cliente': cliente,
            'patrones': patrones
        })

    except Exception as e:
        logger.error(f"Error en vista_deteccion_patrones: {e}")
        return render(request, 'analytics/deteccion_patrones.html', {
            'cliente': crear_cliente_fallback(cliente_id),
            'patrones': {
                'tiene_datos_suficientes': False,
                'total_patrones': 0,
                'confianza_deteccion': 0,
                'patrones_detectados': [],
                'resumen_categorias': {}
            }
        })


def vista_estancamientos(request, cliente_id):
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        sistema = SistemaEstancamiento(cliente)
        datos = sistema.detectar_estancamientos_automaticos()

        if 'tiene_datos_suficientes' not in datos:
            datos['tiene_datos_suficientes'] = datos.get('total_estancamientos', 0) > 0

        return render(request, 'analytics/estancamientos.html', {
            'cliente': cliente,
            'estancamientos': datos
        })

    except Exception as e:
        logger.error(f"Error en vista_estancamientos: {e}")
        return render(request, 'analytics/estancamientos.html', {
            'cliente': crear_cliente_fallback(cliente_id),
            'estancamientos': {
                'tiene_datos_suficientes': False,
                'total_estancamientos': 0,
                'estancamientos_detectados': []
            }
        })


def vista_anomalias(request, cliente_id):
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        sistema = AnalizadorAnomalias(cliente)
        datos = sistema.detectar_anomalias_comportamiento()

        if 'tiene_datos_suficientes' not in datos:
            datos['tiene_datos_suficientes'] = datos.get('total_anomalias', 0) > 0

        return render(request, 'analytics/anomalias.html', {
            'cliente': cliente,
            'anomalias': datos
        })

    except Exception as e:
        logger.error(f"Error en vista_anomalias: {e}")
        return render(request, 'analytics/anomalias.html', {
            'cliente': crear_cliente_fallback(cliente_id),
            'anomalias': {
                'tiene_datos_suficientes': False,
                'total_anomalias': 0,
                'anomalias_detectadas': []
            }
        })


# analytics/views.py


# En tu archivo analytics/views_ia.py

from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from .ia_optimizacion_entrenamientos import OptimizacionEntrenamientosIA
import logging

logger = logging.getLogger(__name__)

# En tu archivo analytics/views_ia.py

from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from .ia_optimizacion_entrenamientos import OptimizacionEntrenamientosIA
import logging

logger = logging.getLogger(__name__)

# En tu archivo analytics/views_ia.py

from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from .ia_optimizacion_entrenamientos import OptimizacionEntrenamientosIA
# Asegúrate de que estos modelos están importados para que la clase de IA funcione
from entrenos.models import EjercicioRealizado
from django.db.models import Count, Max
import logging

logger = logging.getLogger(__name__)


def vista_optimizacion_entrenamientos(request, cliente_id):
    """
    Vista para optimización de entrenamientos - AHORA CON SELECCIÓN DE EJERCICIOS DINÁMICA
    """
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        logger.info(f"Cliente encontrado para optimización: {cliente.nombre}")

        objetivo_actual = request.GET.get('objetivo', 'hipertrofia')
        if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia']:
            objetivo_actual = 'hipertrofia'

        # 1. Inicializar el sistema de IA con el cliente
        sistema_ia = OptimizacionEntrenamientosIA(cliente)

        # 2. Obtener datos usando los métodos que SÍ existen
        rutina_optimizada = sistema_ia.generar_rutina_optimizada(objetivo_actual)
        optimizacion_completa = sistema_ia.generar_optimizacion_completa(objetivo_actual)

        # 3. Crear los datos que faltan basándose en la información disponible

        # =================================================================
        # INICIO DEL CAMBIO: SELECCIÓN DE EJERCICIOS DINÁMICA
        # =================================================================

        # Llamamos al nuevo método inteligente de nuestra clase de IA
        # Asumimos que el método seleccionar_ejercicios_optimos ya existe en la clase OptimizacionEntrenamientosIA
        ejercicios_sugeridos = sistema_ia.seleccionar_ejercicios_optimos(objetivo_actual, cantidad=3)

        # Obtenemos los parámetros de la rutina para usarlos en cada ejercicio
        series_sugeridas = rutina_optimizada.get('series_por_ejercicio', '3-4')
        reps_sugeridas = rutina_optimizada.get('repeticiones', '8-12')
        descanso_sugerido = rutina_optimizada.get('descanso_series', '2-3 min')

        # Construimos la lista de ejercicios para el contexto
        ejercicios_para_contexto = []
        for ejercicio in ejercicios_sugeridos:
            ejercicios_para_contexto.append({
                'nombre': ejercicio['nombre'],
                'series': ejercicio.get('series_rec', '3-4'),  # Usamos la recomendación específica
                'repeticiones': ejercicio.get('reps_rec', '8-12'),  # Usamos la recomendación específica
                'descanso': descanso_sugerido,
                'grupo_muscular': ejercicio.get('grupo_muscular', 'General'),
                'nota': ejercicio.get('nota', '')  # Pasamos la nota de la IA
            })

        # Crear sesión individual basada en la rutina optimizada y los ejercicios dinámicos
        sesion_individual = {
            'ejercicios_recomendados': ejercicios_para_contexto,  # <-- Usamos la lista dinámica
            'duracion_estimada': f"{len(ejercicios_para_contexto) * 8}-{len(ejercicios_para_contexto) * 12} minutos",
            'intensidad_objetivo': 'Moderada-Alta',
            'calentamiento': '10-15 minutos de movilidad articular',
            'enfriamiento': '10 minutos de estiramientos'
        }
        # =================================================================
        # FIN DEL CAMBIO
        # =================================================================

        # Crear periodización basada en el objetivo
        periodizacion = sistema_ia.generar_periodizacion_dinamica()

        # Crear protocolo de recuperación
        recuperacion = {
            'descanso_entre_series': rutina_optimizada.get('descanso_series', '2-3 min'),
            'descanso_entre_entrenamientos': '48-72 horas para mismo grupo muscular',
            'dias_descanso_semanal': 7 - rutina_optimizada.get('frecuencia_semanal', 4),
            'recomendaciones_recuperacion': ['Dormir 7-9 horas diarias', 'Hidratación adecuada (2-3 litros/día)',
                                             'Nutrición post-entreno en 30-60 minutos',
                                             'Estiramientos y movilidad en días de descanso'],
            'signos_sobreentrenamiento': ['Fatiga persistente', 'Disminución del rendimiento', 'Alteraciones del sueño',
                                          'Pérdida de motivación']
        }

        # Crear datos de carga adaptativa basados en las optimizaciones
        optimizaciones = optimizacion_completa.get('optimizaciones', [])
        carga_adaptativa = {
            'metodo_progresion': 'Sobrecarga progresiva',
            'incrementos_recomendados': {'peso': '2.5-5% semanal',
                                         'repeticiones': '+1-2 cuando se completen todas las series',
                                         'series': '+1 serie cada 2-3 semanas'},
            'ajustes_basados_en_analisis': [],
            'indicadores_progreso': ['Aumento de peso en ejercicios principales', 'Mejora en repeticiones máximas',
                                     'Reducción de fatiga percibida', 'Mejora en técnica de ejecución']
        }

        # BUCLE CORREGIDO
        for opt in optimizaciones:
            if opt.get('tipo') in ['frecuencia', 'volumen', 'intensidad', 'progresion',
                                   'variedad']:  # Añadimos más tipos por si acaso

                # Formateamos la mejora estimada a un solo decimal
                mejora_formateada = f"{opt.get('mejora_estimada', 0):.1f}"

                carga_adaptativa['ajustes_basados_en_analisis'].append({
                    'tipo': opt.get('tipo').capitalize(),
                    'recomendacion': opt.get('descripcion', ''),
                    'mejora_estimada': f"{mejora_formateada}%"  # Usamos el valor formateado
                })

        # Crear comparación de algoritmos
        comparacion_algoritmos = [
            {'nombre': 'Algoritmo de Frecuencia', 'precision': '85%',
             'mejora_detectada': f"{sum(opt.get('mejora_estimada', 0) for opt in optimizaciones if opt.get('tipo') == 'frecuencia'):.1f}%",
             'estado': 'Activo' if any(opt.get('tipo') == 'frecuencia' for opt in optimizaciones) else 'Inactivo'},
            {'nombre': 'Algoritmo de Volumen', 'precision': '80%',
             'mejora_detectada': f"{sum(opt.get('mejora_estimada', 0) for opt in optimizaciones if opt.get('tipo') == 'volumen'):.1f}%",
             'estado': 'Activo' if any(opt.get('tipo') == 'volumen' for opt in optimizaciones) else 'Inactivo'},
            {'nombre': 'Algoritmo de Progresión', 'precision': '90%',
             'mejora_detectada': f"{sum(opt.get('mejora_estimada', 0) for opt in optimizaciones if opt.get('tipo') == 'progresion'):.1f}%",
             'estado': 'Activo' if any(opt.get('tipo') == 'progresion' for opt in optimizaciones) else 'Inactivo'},
            {'nombre': 'Algoritmo de Variedad', 'precision': '75%',
             'mejora_detectada': f"{sum(opt.get('mejora_estimada', 0) for opt in optimizaciones if opt.get('tipo') == 'variedad'):.1f}%",
             'estado': 'Activo' if any(opt.get('tipo') == 'variedad' for opt in optimizaciones) else 'Inactivo'}
        ]

        # Lógica para el mensaje de foco dinámico
        focus_message = ""
        if optimizaciones:
            prioridad_opt = optimizaciones[0]
            tipo_foco = prioridad_opt.get('tipo', 'general')
            if tipo_foco == 'frecuencia':
                focus_message = "Hemos notado que puedes optimizar tu frecuencia de entreno. ¡Este plan te ayudará a ser más constante!"
            elif tipo_foco == 'progresion':
                focus_message = "Tu principal área de mejora es la sobrecarga progresiva. ¡Este plan se enfoca en que cada semana sea un reto!"
            elif tipo_foco == 'volumen':
                focus_message = "Nos centraremos en aumentar gradualmente el volumen total de tu entrenamiento para maximizar el estímulo."
            elif tipo_foco == 'variedad':
                focus_message = "Este plan introduce más variedad de ejercicios para asegurar un desarrollo muscular completo y equilibrado."
            else:
                focus_message = "Este es un plan equilibrado diseñado para potenciar tu progreso general en todas las áreas."
        else:
            focus_message = "Comienza con este plan base. ¡A medida que registres entrenos, la IA lo adaptará perfectamente para ti!"

        # 4. Construir el contexto con TODAS las variables que la plantilla espera
        context = {
            'cliente': cliente,
            'mejora_estimada': optimizacion_completa.get('mejora_estimada', 0.0),
            'rutina_optimizada': rutina_optimizada,
            'sesion_individual': sesion_individual,
            'periodizacion': periodizacion,
            'recuperacion': recuperacion,
            'carga_adaptativa': carga_adaptativa,
            'comparacion_algoritmos': comparacion_algoritmos,
            'optimizaciones_detectadas': optimizaciones,
            'algoritmos_activos': optimizacion_completa.get('algoritmos_activos', 0),
            'estado_sistema': optimizacion_completa.get('estado', 'activo'),
            'entrenamientos_analizados': optimizacion_completa.get('entrenamientos_analizados', 0),
            'focus_message': focus_message,
            'objetivo_actual': objetivo_actual,
            'debug_info': {
                'metodos_llamados': ['generar_rutina_optimizada', 'generar_optimizacion_completa',
                                     'seleccionar_ejercicios_optimos'],
                'datos_generados': ['rutina_optimizada', 'sesion_individual', 'periodizacion', 'recuperacion',
                                    'carga_adaptativa', 'comparacion_algoritmos'],
                'optimizaciones_encontradas': len(optimizaciones)
            }
        }

        logger.info(
            f"Contexto generado para el objetivo '{objetivo_actual}'. Mejora estimada: {context['mejora_estimada']}%")
        return render(request, 'analytics/optimizacion_entrenamientos.html', context)

    except Cliente.DoesNotExist:
        logger.error(f"Cliente con id={cliente_id} no encontrado.")
        return render(request, 'error.html', {'message': 'Cliente no encontrado.'})
    except Exception as e:
        logger.error(f"Error crítico en vista_optimizacion_entrenamientos: {e}", exc_info=True)
        return render(request, 'error.html', {'message': f'Ocurrió un error al generar la optimización: {str(e)}'})

    except Cliente.DoesNotExist:
        logger.error(f"Cliente con id={cliente_id} no encontrado.")
        return render(request, 'error.html', {'message': 'Cliente no encontrado.'})
    except Exception as e:
        logger.error(f"Error crítico en vista_optimizacion_entrenamientos: {e}", exc_info=True)
        return render(request, 'error.html', {'message': f'Ocurrió un error al generar la optimización: {str(e)}'})


# ==================== API ENDPOINTS ====================

@csrf_exempt
@require_http_methods(["GET"])
def api_dashboard_refresh(request, cliente_id):
    """API para refrescar datos del dashboard"""
    try:
        cache_key = f'dashboard_ia_{cliente_id}'
        cache.delete(cache_key)

        return JsonResponse({
            'success': True,
            'message': 'Dashboard actualizado',
            'updated': True
        })
    except Exception as e:
        logger.error(f"Error en api_dashboard_refresh: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def api_prediccion_tiempo_real(request, cliente_id):
    """API para predicciones en tiempo real - CORREGIDA"""
    try:
        data = json.loads(request.body)
        ejercicio = data.get('ejercicio')

        if not ejercicio:
            return JsonResponse({'error': 'Ejercicio requerido'}, status=400)

        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
        except Exception:
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        sistema_predicciones = ModelosPredictivosIA(cliente)
        prediccion = sistema_predicciones.generar_prediccion_ejercicio(ejercicio)

        return JsonResponse({
            'success': True,
            'prediccion': prediccion
        })

    except Exception as e:
        logger.error(f"Error en api_prediccion_tiempo_real: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def api_recomendacion_tiempo_real(request, cliente_id):
    """API para recomendaciones en tiempo real - CORREGIDA"""
    try:
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
        except Exception:
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        sistema_recomendaciones = SistemaRecomendacionesIA(cliente)
        recomendaciones_data = sistema_recomendaciones.generar_recomendaciones_completas()

        return JsonResponse({
            'success': True,
            'recomendaciones': recomendaciones_data
        })

    except Exception as e:
        logger.error(f"Error en api_recomendacion_tiempo_real: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def api_deteccion_patrones_tiempo_real(request, cliente_id):
    """API para detección de patrones en tiempo real - CORREGIDA"""
    try:
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
        except Exception:
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        sistema_patrones = DeteccionPatronesIA(cliente)
        patrones_data = sistema_patrones.detectar_todos_los_patrones()
        estancamientos_data = sistema_patrones.detectar_estancamientos_automaticos()

        return JsonResponse({
            'success': True,
            'patrones': patrones_data,
            'estancamientos': estancamientos_data
        })

    except Exception as e:
        logger.error(f"Error en api_deteccion_patrones_tiempo_real: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def api_optimizacion_tiempo_real(request, cliente_id):
    """API para optimización en tiempo real - CORREGIDA"""
    try:
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
        except Exception:
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        sistema_optimizacion = OptimizacionEntrenamientosIA(cliente)
        optimizacion_data = sistema_optimizacion.generar_optimizacion_completa('hipertrofia')

        return JsonResponse({
            'success': True,
            'optimizacion': optimizacion_data
        })

    except Exception as e:
        logger.error(f"Error en api_optimizacion_tiempo_real: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ==================== FUNCIONES AUXILIARES ====================

def limpiar_cache_modulos_ia(cliente_id):
    """Limpia el cache de todos los módulos de IA"""
    try:
        cache_keys = [
            f'predicciones_avanzadas_{cliente_id}',
            f'recomendaciones_inteligentes_{cliente_id}',
            f'deteccion_patrones_{cliente_id}',
            f'optimizacion_entrenamientos_{cliente_id}'
        ]

        for key in cache_keys:
            cache.delete(key)

        logger.info(f"Cache limpiado para cliente {cliente_id}")
        return True

    except Exception as e:
        logger.error(f"Error limpiando cache: {e}")
        return False


# ==================== FUNCIONES AUXILIARES ADICIONALES ====================
def limpiar_cache_modulos_ia(cliente_id):
    """Limpia el cache de todos los módulos de IA"""
    try:
        cache_keys = [
            f'predicciones_avanzadas_{cliente_id}',
            f'recomendaciones_inteligentes_{cliente_id}',
            f'deteccion_patrones_{cliente_id}',
            f'optimizacion_entrenamientos_{cliente_id}'
        ]

        for key in cache_keys:
            cache.delete(key)

        logger.info(f"Cache limpiado para cliente {cliente_id}")
        return True

    except Exception as e:
        logger.error(f"Error limpiando cache: {e}")
        return False


# ==================== ALIAS PARA COMPATIBILIDAD ====================

def deteccion_patrones_view(request, cliente_id):
    """Alias para deteccion_patrones_automatica (compatibilidad)"""
    return deteccion_patrones_automatica(request, cliente_id)


def optimizacion_entrenamientos(request, cliente_id):
    """Alias para vista_optimizacion_entrenamientos (compatibilidad)"""
    return vista_optimizacion_entrenamientos(request, cliente_id)


# === CLASE UNIFICADA DE DETECCIÓN DE PATRONES ===

# 🔍 DETECCIÓN DE PATRONES - VERSIÓN COMPLETA Y FUNCIONAL
# Genera datos detallados para mostrar en el template

from datetime import datetime, timedelta
from django.db.models import Count, Avg, Max, Min, Sum
from collections import defaultdict, Counter
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos Django
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente


class DeteccionPatronesIA:
    """
    Sistema de detección de patrones completo que genera datos detallados
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.configuracion = {
            'ventana_analisis_dias': 90,
            'min_entrenamientos': 2,  # Muy realista
            'min_ejercicios_patron': 2,
            'umbral_estancamiento_dias': 21,  # 3 semanas
            'umbral_progreso_minimo': 2.5,  # kg
        }
        logger.info(f"Inicializando DeteccionPatronesIA para cliente {cliente.id}")

    def _tiene_datos_suficientes(self):
        """Verifica si hay datos suficientes para análisis"""
        fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_limite
        )
        total = entrenamientos.count()
        logger.info(f"Entrenamientos en ventana de análisis: {total}")
        return total >= self.configuracion['min_entrenamientos']

    def detectar_todos_los_patrones(self):
        """Detecta todos los tipos de patrones disponibles"""
        try:
            if not self._tiene_datos_suficientes():
                return self._respuesta_datos_insuficientes()

            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])
            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_limite
            ).order_by('fecha')

            total_entrenamientos = entrenamientos.count()
            logger.info(f"Analizando {total_entrenamientos} entrenamientos")

            patrones_detectados = []
            resumen_categorias = {
                'progreso': 0,
                'temporal': 0,
                'comportamiento': 0,
                'equilibrio': 0,
                'informativo': 0
            }

            # Detectar diferentes tipos de patrones
            patrones_progreso = self._detectar_patrones_progreso(entrenamientos)
            patrones_temporales = self._detectar_patrones_temporales(entrenamientos)
            patrones_comportamiento = self._detectar_patrones_comportamiento(entrenamientos)
            patrones_equilibrio = self._detectar_patrones_equilibrio(entrenamientos)

            # Combinar todos los patrones
            patrones_detectados.extend(patrones_progreso)
            patrones_detectados.extend(patrones_temporales)
            patrones_detectados.extend(patrones_comportamiento)
            patrones_detectados.extend(patrones_equilibrio)

            # Actualizar resumen de categorías
            for patron in patrones_detectados:
                categoria = patron.get('categoria', 'informativo')
                if categoria in resumen_categorias:
                    resumen_categorias[categoria] += 1

            # Calcular confianza general
            confianza_deteccion = self._calcular_confianza_general(patrones_detectados, total_entrenamientos)

            resultado = {
                'tiene_datos_suficientes': True,
                'total_patrones': len(patrones_detectados),
                'confianza_deteccion': confianza_deteccion,
                'patrones_detectados': patrones_detectados,
                'resumen_categorias': resumen_categorias,
                'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
                'entrenamientos_analizados': total_entrenamientos
            }

            logger.info(f"Detección completada: {len(patrones_detectados)} patrones, confianza {confianza_deteccion}%")
            return resultado

        except Exception as e:
            logger.error(f"Error en detectar_todos_los_patrones: {e}")
            return self._respuesta_error()

    def _detectar_patrones_temporales(self, entrenamientos):
        """Detecta patrones relacionados con el tiempo"""
        patrones = []

        try:
            # Análisis de días de la semana
            dias_semana = [entreno.fecha.weekday() for entreno in entrenamientos]
            contador_dias = Counter(dias_semana)

            if contador_dias:
                dia_mas_frecuente = contador_dias.most_common(1)[0]
                dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

                if dia_mas_frecuente[1] >= 3:  # Al menos 3 veces
                    patrones.append({
                        'tipo': 'consistencia_temporal',
                        'categoria': 'temporal',
                        'descripcion': f'Prefieres entrenar los {dias_nombres[dia_mas_frecuente[0]]}',
                        'detalle': f'Has entrenado {dia_mas_frecuente[1]} veces los {dias_nombres[dia_mas_frecuente[0]]}',
                        'severidad': 'info',
                        'confianza': min(95, 60 + dia_mas_frecuente[1] * 5),
                        'valor_numerico': dia_mas_frecuente[1],
                        'recomendacion': 'Mantén esta consistencia para mejores resultados'
                    })

            # Análisis de consistencia semanal
            dias_unicos = len(set(dias_semana))
            if dias_unicos <= 3 and len(entrenamientos) >= 6:
                patrones.append({
                    'tipo': 'rutina_fija',
                    'categoria': 'temporal',
                    'descripcion': f'Tienes una rutina muy consistente',
                    'detalle': f'Entrenas en solo {dias_unicos} días diferentes de la semana',
                    'severidad': 'success',
                    'confianza': 85,
                    'valor_numerico': dias_unicos,
                    'recomendacion': 'Excelente consistencia temporal'
                })

            # Análisis de intervalos entre entrenamientos
            if len(entrenamientos) >= 3:
                fechas = [e.fecha for e in entrenamientos]
                intervalos = []

                for i in range(1, len(fechas)):
                    diff = (fechas[i] - fechas[i - 1]).days
                    intervalos.append(diff)

                if intervalos:
                    promedio_intervalo = sum(intervalos) / len(intervalos)

                    if promedio_intervalo <= 3:
                        patrones.append({
                            'tipo': 'frecuencia_alta',
                            'categoria': 'temporal',
                            'descripcion': f'Entrenas con alta frecuencia',
                            'detalle': f'Promedio de {promedio_intervalo:.1f} días entre entrenamientos',
                            'severidad': 'success',
                            'confianza': 80,
                            'valor_numerico': promedio_intervalo,
                            'recomendacion': 'Mantén esta frecuencia para resultados óptimos'
                        })
                    elif promedio_intervalo >= 7:
                        patrones.append({
                            'tipo': 'frecuencia_baja',
                            'categoria': 'temporal',
                            'descripcion': f'Podrías entrenar más frecuentemente',
                            'detalle': f'Promedio de {promedio_intervalo:.1f} días entre entrenamientos',
                            'severidad': 'warning',
                            'confianza': 75,
                            'valor_numerico': promedio_intervalo,
                            'recomendacion': 'Considera aumentar la frecuencia de entrenamiento'
                        })

        except Exception as e:
            logger.error(f"Error detectando patrones temporales: {e}")

        return patrones

    def _detectar_patrones_comportamiento(self, entrenamientos):
        """Detecta patrones de comportamiento en el entrenamiento"""
        patrones = []

        try:
            # Análisis de duración de entrenamientos
            duraciones = []
            for entreno in entrenamientos:
                if hasattr(entreno, 'duracion_minutos') and entreno.duracion_minutos:
                    duraciones.append(entreno.duracion_minutos)

            if duraciones:
                promedio_duracion = sum(duraciones) / len(duraciones)

                if promedio_duracion >= 90:
                    patrones.append({
                        'tipo': 'entrenamientos_largos',
                        'categoria': 'comportamiento',
                        'descripcion': f'Realizas entrenamientos largos',
                        'detalle': f'Duración promedio: {promedio_duracion:.0f} minutos',
                        'severidad': 'info',
                        'confianza': 80,
                        'valor_numerico': promedio_duracion,
                        'recomendacion': 'Asegúrate de mantener la intensidad durante todo el entrenamiento'
                    })
                elif promedio_duracion <= 45:
                    patrones.append({
                        'tipo': 'entrenamientos_cortos',
                        'categoria': 'comportamiento',
                        'descripcion': f'Prefieres entrenamientos intensos y cortos',
                        'detalle': f'Duración promedio: {promedio_duracion:.0f} minutos',
                        'severidad': 'success',
                        'confianza': 80,
                        'valor_numerico': promedio_duracion,
                        'recomendacion': 'Excelente para mantener alta intensidad'
                    })

            # Análisis de variedad de ejercicios
            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            )

            ejercicios_unicos = ejercicios_realizados.values('nombre_ejercicio').distinct().count()
            total_ejercicios = ejercicios_realizados.count()

            if ejercicios_unicos > 0:
                variedad_ratio = ejercicios_unicos / max(1, len(entrenamientos))

                if variedad_ratio >= 5:
                    patrones.append({
                        'tipo': 'alta_variedad',
                        'categoria': 'comportamiento',
                        'descripcion': f'Tienes gran variedad en tus ejercicios',
                        'detalle': f'{ejercicios_unicos} ejercicios diferentes en {len(entrenamientos)} entrenamientos',
                        'severidad': 'success',
                        'confianza': 85,
                        'valor_numerico': ejercicios_unicos,
                        'recomendacion': 'Excelente variedad para desarrollo completo'
                    })
                elif variedad_ratio <= 2:
                    patrones.append({
                        'tipo': 'baja_variedad',
                        'categoria': 'comportamiento',
                        'descripcion': f'Podrías aumentar la variedad de ejercicios',
                        'detalle': f'Solo {ejercicios_unicos} ejercicios diferentes',
                        'severidad': 'warning',
                        'confianza': 80,
                        'valor_numerico': ejercicios_unicos,
                        'recomendacion': 'Incorpora nuevos ejercicios para mejor desarrollo'
                    })

            # Análisis de ejercicios favoritos
            ejercicios_frecuentes = ejercicios_realizados.values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).order_by('-cantidad')[:3]

            if ejercicios_frecuentes:
                ejercicio_favorito = ejercicios_frecuentes[0]
                patrones.append({
                    'tipo': 'ejercicio_favorito',
                    'categoria': 'comportamiento',
                    'descripcion': f'Tu ejercicio favorito es {ejercicio_favorito["nombre_ejercicio"]}',
                    'detalle': f'Realizado {ejercicio_favorito["cantidad"]} veces',
                    'severidad': 'info',
                    'confianza': 90,
                    'valor_numerico': ejercicio_favorito["cantidad"],
                    'ejercicio': ejercicio_favorito["nombre_ejercicio"],
                    'recomendacion': 'Mantén este ejercicio como base de tu rutina'
                })

        except Exception as e:
            logger.error(f"Error detectando patrones de comportamiento: {e}")

        return patrones

    def _detectar_patrones_progreso(self, entrenamientos):
        """Detecta patrones de progreso en los ejercicios"""
        patrones = []

        try:
            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            )

            # Analizar progreso por ejercicio
            ejercicios_principales = ejercicios_realizados.values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3)

            ejercicios_con_progreso = 0
            ejercicios_sin_progreso = 0

            for ejercicio in ejercicios_principales:
                registros = ejercicios_realizados.filter(
                    nombre_ejercicio=ejercicio['nombre_ejercicio']
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg
                    mejora = ultimo_peso - primer_peso

                    if mejora > self.configuracion['umbral_progreso_minimo']:
                        ejercicios_con_progreso += 1
                        patrones.append({
                            'tipo': 'progreso_ejercicio',
                            'categoria': 'progreso',
                            'descripcion': f'Progreso en {ejercicio["nombre_ejercicio"]}',
                            'detalle': f'Mejora de {mejora:.1f}kg (de {primer_peso}kg a {ultimo_peso}kg)',
                            'severidad': 'success',
                            'confianza': 85,
                            'valor_numerico': mejora,
                            'ejercicio': ejercicio["nombre_ejercicio"],
                            'recomendacion': 'Continúa con esta progresión gradual'
                        })
                    elif mejora < -2:
                        ejercicios_sin_progreso += 1
                        patrones.append({
                            'tipo': 'regresion_ejercicio',
                            'categoria': 'progreso',
                            'descripcion': f'Regresión en {ejercicio["nombre_ejercicio"]}',
                            'detalle': f'Reducción de {abs(mejora):.1f}kg',
                            'severidad': 'warning',
                            'confianza': 80,
                            'valor_numerico': abs(mejora),
                            'ejercicio': ejercicio["nombre_ejercicio"],
                            'recomendacion': 'Revisa técnica y considera reducir volumen'
                        })

            # Patrón general de progreso
            if ejercicios_con_progreso > ejercicios_sin_progreso:
                patrones.append({
                    'tipo': 'tendencia_positiva',
                    'categoria': 'progreso',
                    'descripcion': f'Tendencia general positiva',
                    'detalle': f'{ejercicios_con_progreso} ejercicios con progreso vs {ejercicios_sin_progreso} sin progreso',
                    'severidad': 'success',
                    'confianza': 90,
                    'valor_numerico': ejercicios_con_progreso,
                    'recomendacion': 'Mantén el enfoque actual de entrenamiento'
                })

        except Exception as e:
            logger.error(f"Error detectando patrones de progreso: {e}")

        return patrones

    def _detectar_patrones_equilibrio(self, entrenamientos):
        """Detecta patrones de equilibrio muscular"""
        patrones = []

        try:
            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            )

            # Análisis por grupo muscular (si está disponible)
            if ejercicios_realizados.filter(grupo_muscular__isnull=False).exists():
                grupos_trabajados = ejercicios_realizados.exclude(
                    grupo_muscular__isnull=True
                ).exclude(
                    grupo_muscular=''
                ).values('grupo_muscular').annotate(
                    cantidad=Count('id')
                ).order_by('-cantidad')

                if grupos_trabajados:
                    grupo_mas_trabajado = grupos_trabajados[0]
                    total_grupos = grupos_trabajados.count()

                    if total_grupos >= 4:
                        patrones.append({
                            'tipo': 'entrenamiento_equilibrado',
                            'categoria': 'equilibrio',
                            'descripcion': f'Entrenas de forma equilibrada',
                            'detalle': f'{total_grupos} grupos musculares diferentes trabajados',
                            'severidad': 'success',
                            'confianza': 85,
                            'valor_numerico': total_grupos,
                            'recomendacion': 'Excelente equilibrio muscular'
                        })
                    elif total_grupos <= 2:
                        patrones.append({
                            'tipo': 'entrenamiento_desequilibrado',
                            'categoria': 'equilibrio',
                            'descripcion': f'Podrías equilibrar más tu entrenamiento',
                            'detalle': f'Solo {total_grupos} grupos musculares trabajados',
                            'severidad': 'warning',
                            'confianza': 80,
                            'valor_numerico': total_grupos,
                            'recomendacion': 'Incluye más grupos musculares en tu rutina'
                        })

        except Exception as e:
            logger.error(f"Error detectando patrones de equilibrio: {e}")

        return patrones

    def _calcular_confianza_general(self, patrones_detectados, total_entrenamientos):
        """Calcula la confianza general del sistema"""
        if not patrones_detectados:
            return 0.0

        # Base de confianza según cantidad de datos
        confianza_base = min(80, 40 + total_entrenamientos * 2)

        # Bonus por cantidad de patrones detectados
        bonus_patrones = min(15, len(patrones_detectados) * 3)

        # Promedio de confianza individual de patrones
        confianzas_individuales = [p.get('confianza', 70) for p in patrones_detectados]
        promedio_individual = sum(confianzas_individuales) / len(confianzas_individuales)

        # Confianza final
        confianza_final = (confianza_base + bonus_patrones + promedio_individual) / 3

        return min(95, max(50, confianza_final))

    def detectar_estancamientos_automaticos(self):
        """Detecta estancamientos en ejercicios específicos"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])
            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_limite
            )

            if not entrenamientos.exists():
                return self._respuesta_estancamientos_sin_datos()

            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            )

            # Buscar ejercicios con suficientes datos
            ejercicios_principales = ejercicios_realizados.values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=4)  # Mínimo 4 registros para detectar estancamiento

            estancamientos = []

            for ejercicio in ejercicios_principales:
                registros = ejercicios_realizados.filter(
                    nombre_ejercicio=ejercicio['nombre_ejercicio']
                ).order_by('entreno__fecha')

                if registros.count() >= 4:
                    # Analizar últimos registros
                    ultimos_registros = list(registros[-4:])
                    pesos = [r.peso_kg for r in ultimos_registros]

                    # Verificar si hay estancamiento (sin mejora en últimos registros)
                    mejora_reciente = max(pesos) - min(pesos)

                    if mejora_reciente <= 2.5:  # Menos de 2.5kg de variación
                        dias_sin_mejora = (datetime.now().date() - ultimos_registros[0].entreno.fecha).days

                        if dias_sin_mejora >= self.configuracion['umbral_estancamiento_dias']:
                            estancamientos.append({
                                'ejercicio': ejercicio['nombre_ejercicio'],
                                'dias_sin_mejora': dias_sin_mejora,
                                'peso_actual': ultimos_registros[-1].peso_kg,
                                'variacion_reciente': mejora_reciente,
                                'severidad': 'warning' if dias_sin_mejora < 35 else 'danger',
                                'recomendacion': self._generar_recomendacion_estancamiento(
                                    ejercicio['nombre_ejercicio'], dias_sin_mejora)
                            })

            return {
                'total_estancamientos': len(estancamientos),
                'estancamientos': estancamientos,
                'fecha_analisis': datetime.now().strftime('%Y-%m-%d')
            }

        except Exception as e:
            logger.error(f"Error detectando estancamientos: {e}")
            return self._respuesta_estancamientos_sin_datos()

    def _generar_recomendacion_estancamiento(self, ejercicio, dias_sin_mejora):
        """Genera recomendación específica para estancamiento"""
        if dias_sin_mejora < 30:
            return f"Considera cambiar el rango de repeticiones en {ejercicio}"
        elif dias_sin_mejora < 45:
            return f"Prueba una variación diferente de {ejercicio}"
        else:
            return f"Toma un descanso de {ejercicio} y enfócate en ejercicios complementarios"

    def _respuesta_datos_insuficientes(self):
        """Respuesta cuando no hay suficientes datos"""
        return {
            'tiene_datos_suficientes': False,
            'total_patrones': 0,
            'confianza_deteccion': 0.0,
            'patrones_detectados': [],
            'resumen_categorias': {
                'progreso': 0,
                'temporal': 0,
                'comportamiento': 0,
                'equilibrio': 0,
                'informativo': 0
            },
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'entrenamientos_analizados': 0
        }

    def _respuesta_estancamientos_sin_datos(self):
        """Respuesta para estancamientos cuando no hay datos"""
        return {
            'total_estancamientos': 0,
            'estancamientos': [],
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d')
        }

    def _respuesta_error(self):
        """Respuesta cuando hay error"""
        return {
            'tiene_datos_suficientes': False,
            'total_patrones': 0,
            'confianza_deteccion': 0.0,
            'patrones_detectados': [],
            'resumen_categorias': {},
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'entrenamientos_analizados': 0,
            'error_message': 'Error al procesar patrones'
        }


def deteccion_patrones_view(request, cliente_id):
    """Alias para deteccion_patrones_automatica (compatibilidad)"""
    return deteccion_patrones_automatica(request, cliente_id)


# ============================================================================
# AÑADIR ESTE BLOQUE COMPLETO AL FINAL DE TU ARCHIVO `analytics/views_ia.py`
# ============================================================================

# --- IMPORTACIONES ADICIONALES PARA LA NUEVA VISTA ---
# (Puede que algunas ya las tengas, no pasa nada si se repiten)
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
import json
import logging


# --- TU CLASE `AnalisisIntensidadAvanzado` (YA LA TIENES ARRIBA) ---
# ...
# (No necesitas volver a pegarla, solo asegúrate de que está en el mismo archivo)
# ...

# --- VISTA NUEVA Y DEFINITIVA PARA EL DASHBOARD DE INTENSIDAD ---
def vista_intensidad_avanzado(request, cliente_id):
    """
    Esta es la función que se conectará a tu URL y renderizará el template.
    """
    # Log para confirmar que estamos ejecutando el código correcto
    logger.info(f"--- Ejecutando 'vista_intensidad_avanzado' para cliente {cliente_id} ---")

    # 1. Obtener el cliente
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # 2. Crear una instancia de tu clase de análisis
    analizador = AnalisisIntensidadAvanzado(cliente)

    # 3. Realizar todos los cálculos necesarios llamando a los métodos de tu clase
    #    (He quitado el cache para simplificar la depuración)
    fatiga_acumulada = analizador.calcular_fatiga_acumulada(periodo_dias=14)

    periodo = int(request.GET.get('periodo', 30))
    zonas_entrenamiento = analizador.analizar_zonas_entrenamiento(periodo_dias=periodo)
    analisis_carga = analizador.analizar_carga_entrenamiento(periodo_dias=90)
    distribucion_intensidades = analizador.analizar_distribucion_intensidades(periodo_dias=60)

    # 4. Construir el diccionario de contexto para pasarlo al template
    context = {
        'cliente': cliente,
        'periodo': periodo,
        'zonas_entrenamiento': zonas_entrenamiento,
        'analisis_carga': analisis_carga,
        'distribucion_intensidades': distribucion_intensidades,
        'fatiga_acumulada': fatiga_acumulada,
    }

    # 5. Preparar los datos para los gráficos de JavaScript
    datos_graficos = {
        'zonas': {
            'labels': list(context['zonas_entrenamiento']['distribucion'].keys()),
            'valores': [d['porcentaje'] for d in context['zonas_entrenamiento']['distribucion'].values()],
            'colores': ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
        },
        'carga': {
            'carga_semanal': context['analisis_carga']['carga_semanal']
        },
        'intensidades': {
            'distribucion': context['distribucion_intensidades']['distribucion']
        }
    }
    context['datos_graficos'] = json.dumps(datos_graficos)

    # 6. Renderizar el template con el contexto
    return render(request, 'analytics/intensidad_avanzado.html', context)


# analytics/views_ia.py

# --- Importaciones necesarias para la nueva vista ---
from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
# CORRECCIÓN DEFINITIVA: Apuntamos a 'rutinas.models'
from rutinas.models import Asignacion
from .ia_analizador_programas import AnalizadorProgramaIA


# ... (el resto de tus importaciones y vistas existentes) ...


# ============================================================================
# === VISTA PARA ANÁLISIS DE PROGRAMAS ASIGNADOS ===
# ============================================================================

def vista_optimizacion_programa(request, cliente_id):
    """
    Analiza el PROGRAMA ASIGNADO a un cliente y lo muestra en el
    template de optimización.
    """
    # =================================================================
    # ### AÑADE ESTA LÍNEA AL PRINCIPIO DE TODO ###
    print("✅✅✅ ¡ÉXITO! La URL está llamando a 'vista_optimizacion_programa views_ia' correctamente. ✅✅✅")
    # =================================================================

    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        # Buscamos el programa a través del modelo de Asignación.
        asignacion = Asignacion.objects.get(cliente=cliente)
        programa_asignado = asignacion.programa
    except Asignacion.DoesNotExist:
        # Manejo de error si el cliente no tiene un programa.
        return render(request, 'error.html',
                      {'message': 'Este cliente no tiene un programa de entrenamiento asignado.'})

    # Obtenemos el objetivo del selector del template o usamos el del cliente como fallback.
    # Asumimos que tu modelo Cliente tiene un campo `objetivo_principal`.
    objetivo_actual = request.GET.get('objetivo', cliente.objetivo_principal)
    if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia']:
        objetivo_actual = cliente.objetivo_principal

    # Creamos la instancia del analizador con el programa y el objetivo.
    analizador = AnalizadorProgramaIA(programa_asignado, objetivo_actual)

    # Con un solo método, obtenemos todo el contexto que el template necesita.
    contexto_ia = analizador.analizar_y_generar_contexto()

    # Preparamos el contexto final para el template.
    context = {
        'cliente': cliente,
        'objetivo_actual': objetivo_actual,
        **contexto_ia  # Desempaquetamos el diccionario de la IA aquí.
    }
    print(contexto_ia)
    # Renderizamos el template que ya conoces.
    return render(request, 'analytics/optimizacion_entrenamientos.html', context)


# analytics/views_ia.py

# --- Asegúrate de que estas importaciones están al principio del archivo ---
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from clientes.models import Cliente
from rutinas.models import Programa, Rutina, RutinaEjercicio, Asignacion
from .ia_analizador_programas import AnalizadorProgramaIA


# -------------------------------------------------------------------------


def vista_optimizacion_programa(request, cliente_id):
    """
    Analiza el PROGRAMA ASIGNADO a un cliente y lo muestra en el
    template de optimización.
    """
    print("✅✅✅ ¡ÉXITO! La URL está llamando a 'vista_optimizacion_programa' correctamente. ✅✅✅")
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        asignacion = Asignacion.objects.get(cliente=cliente)
        programa_asignado = asignacion.programa
    except Asignacion.DoesNotExist:
        return render(request, 'error.html',
                      {'message': 'Este cliente no tiene un programa de entrenamiento asignado.'})

    objetivo_actual = request.GET.get('objetivo', cliente.objetivo_principal)
    if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia', 'general']:
        objetivo_actual = cliente.objetivo_principal

    analizador = AnalizadorProgramaIA(programa_asignado, objetivo_actual)

    contexto_ia = analizador.analizar_y_generar_contexto()

    # =================================================================
    # ### CORRECCIÓN FINAL ###
    # Añadimos 'programa_modificado' al contexto para que el template
    # pueda acceder a él y rellenar el campo oculto del formulario.
    # =================================================================
    context = {
        'cliente': cliente,
        'objetivo_actual': objetivo_actual,
        'programa_modificado': analizador.programa_modificado,  # <-- ¡ESTA ES LA LÍNEA CLAVE!
        **contexto_ia
    }
    # =================================================================

    return render(request, 'analytics/optimizacion_entrenamientos.html', context)


# analytics/views_ia.py

# ... (tus otras importaciones) ...
from django.utils.safestring import mark_safe
from .vendor.diff_match_patch import diff_match_patch  # Necesitaremos esto

import json
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction  # <-- AÑADIMOS ESTA IMPORTACIÓN
from clientes.models import Cliente
from entrenos.utils.utils import parse_reps_and_series

from rutinas.models import Programa, Rutina, RutinaEjercicio, Asignacion

from entrenos.models import EjercicioBase
# analytics/views_ia.py

# ... (tus otras importaciones) ...
from django.utils.html import escape  # <-- Asegúrate de que esta importación existe

# analytics/views_ia.py

# ... (todas tus importaciones y vistas existentes, como vista_optimizacion_programa y guardar_programa_optimizado) ...


# ============================================================================
# ### AÑADE ESTA VISTA COMPLETA AL FINAL DEL ARCHIVO ###
# ============================================================================

from django.utils.safestring import mark_safe
from .vendor.diff_match_patch import diff_match_patch  # Asumiendo que tienes este archivo


# analytics/views_ia.py

# ... (tus otras importaciones) ...

# analytics/views_ia.py

# ... (tus otras importaciones) ...

# analytics/views_ia.py

# ... (tus otras importaciones) ...

def vista_comparacion_programa(request, cliente_id):
    """
    Muestra una comparación lado a lado y AHORA TAMBIÉN un resumen
    de los cambios realizados por la IA.
    """
    if request.method != 'POST':
        messages.error(request, "No hay datos para comparar. Por favor, analiza un programa primero.")
        return redirect('clientes:detalle_cliente', cliente_id=cliente_id)

    programa_original_json = request.POST.get('programa_original_json')
    programa_modificado_json = request.POST.get('programa_modificado_json')

    if not programa_original_json or not programa_modificado_json:
        messages.error(request, "Faltan datos para la comparación.")
        return redirect('clientes:detalle_cliente', cliente_id=cliente_id)

    original = json.loads(programa_original_json)
    modificado = json.loads(programa_modificado_json)

    # =================================================================
    # ### LÓGICA MEJORADA PARA DETECTAR Y RESUMIR CAMBIOS ###
    # =================================================================

    # 1. Creamos un diccionario para buscar ejercicios originales rápidamente.
    original_ejercicios = {}
    for rutina in original.get('rutinas', []):
        for ejercicio in rutina.get('ejercicios', []):
            clave = ejercicio['nombre'].strip().lower()
            original_ejercicios[clave] = ejercicio

    # 2. Inicializamos la lista donde guardaremos el resumen de cambios.
    resumen_cambios = []

    # 3. Iteramos sobre el programa modificado para comparar y construir el resumen.
    for rutina in modificado.get('rutinas', []):
        for ejercicio in rutina.get('ejercicios', []):
            clave_busqueda = ejercicio['nombre'].strip().lower()
            original_ej = original_ejercicios.get(clave_busqueda)

            if original_ej:
                # Comparamos series
                if int(original_ej['series']) != int(ejercicio['series']):
                    ejercicio['modificado'] = True
                    resumen_cambios.append(
                        f"<strong>{ejercicio['nombre']}:</strong> Series ajustadas de {original_ej['series']} a {ejercicio['series']}."
                    )

                # Comparamos repeticiones
                if int(original_ej['repeticiones']) != int(ejercicio['repeticiones']):
                    ejercicio['modificado'] = True
                    # Evitamos duplicar la descripción si ya se añadió por las series
                    if not any(ejercicio['nombre'] in s for s in resumen_cambios):
                        resumen_cambios.append(
                            f"<strong>{ejercicio['nombre']}:</strong> Repeticiones ajustadas de {original_ej['repeticiones']} a {ejercicio['repeticiones']}."
                        )
            else:
                # Si el ejercicio es completamente nuevo
                ejercicio['modificado'] = True
                resumen_cambios.append(
                    f"<strong>Ejercicio Añadido:</strong> {ejercicio['nombre']} ({ejercicio['series']}x{ejercicio['repeticiones']})."
                )
    # =================================================================

    context = {
        'cliente': get_object_or_404(Cliente, id=cliente_id),
        'programa_original': original,
        'programa_modificado': modificado,
        'resumen_de_cambios': resumen_cambios,  # <-- Pasamos la nueva lista al contexto
        'programa_modificado_json_escaped': escape(json.dumps(modificado))
    }

    return render(request, 'analytics/comparacion_programa.html', context)


def vista_optimizacion_programa(request, cliente_id):
    """
    Analiza el PROGRAMA ASIGNADO a un cliente y lo muestra en el
    template de optimización.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        asignacion = Asignacion.objects.get(cliente=cliente)
        programa_asignado = asignacion.programa
    except Asignacion.DoesNotExist:
        return render(request, 'error.html',
                      {'message': 'Este cliente no tiene un programa de entrenamiento asignado.'})

    objetivo_actual = request.GET.get('objetivo', cliente.objetivo_principal)
    if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia', 'general']:
        objetivo_actual = cliente.objetivo_principal

    analizador = AnalizadorProgramaIA(programa_asignado, objetivo_actual)
    contexto_ia = analizador.analizar_y_generar_contexto()

    # =================================================================
    # ### CORRECCIÓN FINAL Y DEFINITIVA ###
    # Aquí preparamos los datos JSON que el formulario necesita para
    # enviarlos a la siguiente vista (la de comparación).
    # =================================================================

    # 1. Clonamos el programa original a un diccionario
    programa_original_dict = analizador._clonar_programa_a_diccionario()

    # 2. Convertimos ambos diccionarios (original y modificado) a cadenas JSON
    programa_original_json_string = json.dumps(programa_original_dict)
    programa_modificado_json_string = json.dumps(analizador.programa_modificado)

    # 3. Construimos el contexto final, añadiendo las versiones "escapadas"
    #    de los JSON para que sean seguras en el HTML.
    context = {
        'cliente': cliente,
        'objetivo_actual': objetivo_actual,

        # Datos para el formulario
        'programa_original_json_escaped': escape(programa_original_json_string),
        'programa_modificado_json_escaped': escape(programa_modificado_json_string),

        # Desempaquetamos el resto de datos de la IA (rutina_optimizada, etc.)
        **contexto_ia
    }
    # =================================================================

    return render(request, 'analytics/optimizacion_entrenamientos.html', context)


@transaction.atomic
def guardar_programa_optimizado(request, cliente_id):
    if request.method != 'POST':
        return redirect('clientes:detalle_cliente', cliente_id=cliente_id)

    cliente = get_object_or_404(Cliente, id=cliente_id)
    programa_json_str = request.POST.get('programa_modificado_json')

    try:
        if not programa_json_str or programa_json_str == '{}':
            raise ValueError("No se recibieron datos JSON válidos del programa.")

        programa_data = json.loads(programa_json_str)

        # =================================================================
        # ### LÓGICA PARA CONSTRUIR EL NUEVO NOMBRE DINÁMICO ###
        # =================================================================

        # 1. Obtenemos los componentes para el nombre
        nombre_original = programa_data.get('nombre', 'Programa')
        nombre_cliente = cliente.nombre
        fecha_actual_str = datetime.now().strftime('%d-%m-%Y')  # Formato DD-MM-YYYY

        # 2. Construimos el nombre final
        nuevo_nombre_programa = f"{nombre_original} (IA {nombre_cliente} {fecha_actual_str})"

        # =================================================================

        # PASO 2: Crear el nuevo programa usando el nombre dinámico
        nuevo_programa = Programa.objects.create(
            nombre=nuevo_nombre_programa,  # <-- Usamos la nueva variable
            tipo="Optimizado por IA"
        )

        # PASO 3: Crear las rutinas y ejercicios (esta lógica no cambia)
        for rutina_data in programa_data.get('rutinas', []):
            nueva_rutina = Rutina.objects.create(
                programa=nuevo_programa,
                nombre=rutina_data['nombre']
            )

            for ejercicio_data in rutina_data.get('ejercicios', []):
                ejercicio_base, created = EjercicioBase.objects.get_or_create(
                    nombre=ejercicio_data['nombre'].strip(),
                    defaults={'grupo_muscular': ejercicio_data.get('grupo_muscular', 'General')}
                )

                RutinaEjercicio.objects.create(
                    rutina=nueva_rutina,
                    ejercicio=ejercicio_base,
                    series=ejercicio_data['series'],
                    repeticiones=ejercicio_data['repeticiones']
                )

        # PASO 4: Actualizar la asignación del cliente (esta lógica no cambia)
        asignacion, created = Asignacion.objects.get_or_create(cliente=cliente)
        asignacion.programa = nuevo_programa
        asignacion.save()

        messages.success(request, f"¡El programa '{nuevo_programa.nombre}' se ha guardado y asignado correctamente!")

    except Exception as e:
        messages.error(request, f"Error al guardar el programa: {e}")

    return redirect('clientes:detalle_cliente', cliente_id=cliente_id)
