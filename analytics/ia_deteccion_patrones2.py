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
