# ⚡ OPTIMIZACIÓN DE ENTRENAMIENTOS - VERSIÓN FUNCIONAL SIMPLIFICADA
# Compatible con Django ORM - SIN dependencias externas - Funciona con datos reales

from datetime import datetime, timedelta
from django.db.models import Sum, Avg, Max, Min, Count, Q
from collections import defaultdict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos Django
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente


class OptimizacionEntrenamientosIA:
    """
    Sistema inteligente de optimización simplificado
    SIN dependencias de sklearn, numpy, pandas
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.configuracion = {
            'ventana_analisis_dias': 90,
            'min_entrenamientos': 2,  # Muy realista
            'objetivos_disponibles': {
                'fuerza': {
                    'reps_objetivo': (1, 5),
                    'series_objetivo': (3, 6),
                    'intensidad_objetivo': (85, 95),
                    'descanso_objetivo': (3, 5),
                    'frecuencia_objetivo': 3
                },
                'hipertrofia': {
                    'reps_objetivo': (6, 12),
                    'series_objetivo': (3, 5),
                    'intensidad_objetivo': (70, 85),
                    'descanso_objetivo': (1, 3),
                    'frecuencia_objetivo': 4
                },
                'resistencia': {
                    'reps_objetivo': (12, 20),
                    'series_objetivo': (2, 4),
                    'intensidad_objetivo': (60, 75),
                    'descanso_objetivo': (0.5, 2),
                    'frecuencia_objetivo': 5
                }
            }
        }
        logger.info(f"Inicializando OptimizacionEntrenamientosIA para cliente {cliente.id}")

    def seleccionar_ejercicios_optimos(self, objetivo='hipertrofia', cantidad=3):
        """
        Selecciona una lista de ejercicios y AHORA TAMBIÉN recomienda series/reps
        basándose en el historial real del usuario y el objetivo actual.
        """
        try:
            # --- Parte 1: Selección de ejercicios (lógica que ya teníamos) ---
            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente
            )

            if not ejercicios_realizados.exists():
                return [
                    {'nombre': 'Press de Banca', 'grupo_muscular': 'Pecho', 'series_rec': '3-4', 'reps_rec': '8-12',
                     'nota': 'Rutina base'},
                    {'nombre': 'Sentadilla', 'grupo_muscular': 'Piernas', 'series_rec': '3-4', 'reps_rec': '8-12',
                     'nota': 'Rutina base'},
                    {'nombre': 'Remo con Barra', 'grupo_muscular': 'Espalda', 'series_rec': '3-4', 'reps_rec': '8-12',
                     'nota': 'Rutina base'},
                ]

            frecuencia_ejercicios = ejercicios_realizados.values(
                'nombre_ejercicio', 'grupo_muscular'
            ).annotate(
                frecuencia=Count('id'),
                peso_max=Max('peso_kg')
            ).order_by('-frecuencia', '-peso_max')

            ejercicios_seleccionados_base = []
            grupos_prioritarios = ['Pecho', 'Espalda', 'Piernas', 'Hombros', 'Brazos']
            for grupo in grupos_prioritarios:
                if len(ejercicios_seleccionados_base) >= cantidad: break
                mejor_ejercicio_grupo = frecuencia_ejercicios.filter(grupo_muscular=grupo).first()
                if mejor_ejercicio_grupo and mejor_ejercicio_grupo['nombre_ejercicio'] not in [e['nombre'] for e in
                                                                                               ejercicios_seleccionados_base]:
                    ejercicios_seleccionados_base.append({
                        'nombre': mejor_ejercicio_grupo['nombre_ejercicio'],
                        'grupo_muscular': mejor_ejercicio_grupo['grupo_muscular']
                    })

            ejercicios_restantes = frecuencia_ejercicios.exclude(
                nombre_ejercicio__in=[e['nombre'] for e in ejercicios_seleccionados_base])
            for ejercicio in ejercicios_restantes:
                if len(ejercicios_seleccionados_base) >= cantidad: break
                ejercicios_seleccionados_base.append({
                    'nombre': ejercicio['nombre_ejercicio'],
                    'grupo_muscular': ejercicio['grupo_muscular']
                })

            # --- Parte 2: NUEVA LÓGICA para personalizar series y repeticiones ---

            # Obtenemos los parámetros base de la rutina optimizada
            rutina_base = self.generar_rutina_optimizada(objetivo)
            series_base = rutina_base.get('series_por_ejercicio', '3-5')
            reps_base = rutina_base.get('repeticiones', '8-12')

            ejercicios_finales = []
            for ejercicio_base in ejercicios_seleccionados_base:
                nombre_ejercicio = ejercicio_base['nombre']

                # Analizamos el rendimiento reciente en este ejercicio específico
                historial_ejercicio = ejercicios_realizados.filter(
                    nombre_ejercicio=nombre_ejercicio
                ).order_by('-entreno__fecha')[:3]  # Últimos 3 registros

                series_rec = series_base
                reps_rec = reps_base
                nota = "Mantener progresión estándar."

                if historial_ejercicio.exists():
                    # Calculamos el promedio de repeticiones recientes
                    reps_promedio_reciente = historial_ejercicio.aggregate(Avg('repeticiones'))['repeticiones__avg']

                    # Lógica de recomendación basada en el objetivo
                    if objetivo == 'fuerza':
                        if reps_promedio_reciente > 6:
                            reps_rec = '3-5'
                            nota = f"Bajar reps desde ~{reps_promedio_reciente:.0f} para enfocar en fuerza."
                    elif objetivo == 'hipertrofia':
                        if reps_promedio_reciente < 6:
                            reps_rec = '8-10'
                            nota = f"Subir reps desde ~{reps_promedio_reciente:.0f} para más volumen."
                        elif reps_promedio_reciente > 14:
                            reps_rec = '10-12'
                            nota = f"Bajar reps desde ~{reps_promedio_reciente:.0f} y subir peso."
                    elif objetivo == 'resistencia':
                        if reps_promedio_reciente < 12:
                            reps_rec = '15-20'
                            nota = f"Subir reps desde ~{reps_promedio_reciente:.0f} para enfocar en resistencia."

                ejercicios_finales.append({
                    'nombre': nombre_ejercicio,
                    'grupo_muscular': ejercicio_base['grupo_muscular'],
                    'series_rec': series_rec,
                    'reps_rec': reps_rec,
                    'nota': nota
                })

            return ejercicios_finales

        except Exception as e:
            logger.error(f"Error en la versión avanzada de seleccionar_ejercicios_optimos: {e}")
            return [
                {'nombre': 'Press de Banca', 'grupo_muscular': 'Pecho', 'series_rec': '3-4', 'reps_rec': '8-12',
                 'nota': 'Error, usando rutina base'},
                {'nombre': 'Sentadilla', 'grupo_muscular': 'Piernas', 'series_rec': '3-4', 'reps_rec': '8-12',
                 'nota': 'Error, usando rutina base'},
                {'nombre': 'Remo con Barra', 'grupo_muscular': 'Espalda', 'series_rec': '3-4', 'reps_rec': '8-12',
                 'nota': 'Error, usando rutina base'},
            ]

    def generar_periodizacion_dinamica(self):
        """
        Analiza el historial reciente para detectar la fase de entrenamiento actual
        y proponer un plan de periodización lógico.
        """
        try:
            # 1. Obtener los entrenamientos de las últimas 6 semanas
            seis_semanas_atras = datetime.now().date() - timedelta(weeks=6)
            entrenamientos_recientes = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=seis_semanas_atras
            )

            if entrenamientos_recientes.count() < 4:  # Necesitamos un mínimo de datos
                raise ValueError("Datos insuficientes para análisis de periodización.")

            # 2. Analizar las métricas clave de los ejercicios en este periodo
            ejercicios_recientes = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos_recientes,
                peso_kg__gt=0
            )

            if not ejercicios_recientes.exists():
                raise ValueError("No hay ejercicios con peso en el historial reciente.")

            # Calculamos el promedio de repeticiones y la tendencia del peso
            reps_promedio = ejercicios_recientes.aggregate(Avg('repeticiones'))['repeticiones__avg']

            # Analizamos la tendencia del peso en los ejercicios principales
            ejercicios_principales = ejercicios_recientes.values('nombre_ejercicio').annotate(
                num_registros=Count('id')
            ).filter(num_registros__gte=2)

            progreso_peso_total = 0
            if ejercicios_principales.exists():
                for ej in ejercicios_principales:
                    registros = ejercicios_recientes.filter(nombre_ejercicio=ej['nombre_ejercicio']).order_by(
                        'entreno__fecha')
                    peso_inicial = registros.first().peso_kg
                    peso_final = registros.last().peso_kg
                    if peso_final > peso_inicial:
                        progreso_peso_total += (peso_final - peso_inicial)

            # 3. Lógica de Detección de Fase Actual
            fase_actual_detectada = "Hipertrofia"  # Por defecto
            if progreso_peso_total / ejercicios_principales.count() > 5 and reps_promedio < 7:
                fase_actual_detectada = "Fuerza"
            elif reps_promedio > 13:
                fase_actual_detectada = "Resistencia"
            elif entrenamientos_recientes.count() < 6:
                fase_actual_detectada = "Adaptación"

            # 4. Construir el Plan de Periodización basado en la fase detectada
            plan_completo = [
                {'nombre': 'Adaptación', 'duracion': '2-3 semanas', 'objetivo': 'Preparar el cuerpo'},
                {'nombre': 'Hipertrofia', 'duracion': '4-6 semanas', 'objetivo': 'Crecimiento muscular'},
                {'nombre': 'Fuerza', 'duracion': '3-5 semanas', 'objetivo': 'Aumentar 1RM'},
                {'nombre': 'Resistencia', 'duracion': '3-4 semanas', 'objetivo': 'Mejorar capacidad'},
            ]

            # Reordenamos el plan para que empiece después de la fase actual
            try:
                indice_actual = [p['nombre'] for p in plan_completo].index(fase_actual_detectada)
                fases_planificadas = plan_completo[indice_actual + 1:] + plan_completo[:indice_actual + 1]
            except ValueError:
                fases_planificadas = plan_completo

            duracion_actual = "4-6 semanas"  # Valor por defecto
            for fase in plan_completo:
                if fase['nombre'] == fase_actual_detectada:
                    duracion_actual = fase['duracion']
                    break

            return {
                'fase_actual': fase_actual_detectada,
                'duracion_fase': duracion_actual,  # <-- AHORA USAMOS EL VALOR REAL
                'fases_planificadas': fases_planificadas[:3],
                'analisis_completo': True
            }

        except Exception as e:
            logger.warning(f"No se pudo generar periodización dinámica: {e}. Usando plan genérico.")
            return {
                'fase_actual': 'Hipertrofia',
                'duracion_fase': '4-6 semanas',
                'fases_planificadas': [
                    {'nombre': 'Fuerza', 'duracion': '3-4 semanas', 'objetivo': 'Aumentar fuerza máxima'},
                    {'nombre': 'Resistencia', 'duracion': '3-4 semanas', 'objetivo': 'Mejorar capacidad'},
                ],
                'analisis_completo': False
            }

    def generar_optimizacion_completa(self, objetivo='hipertrofia'):
        """
        Genera optimización completa basada en datos reales
        """
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])

            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_limite
            ).order_by('fecha')

            total_entrenamientos = entrenamientos.count()

            if total_entrenamientos < self.configuracion['min_entrenamientos']:
                return self._respuesta_datos_insuficientes()

            optimizaciones = []

            # 1. OPTIMIZACIÓN DE FRECUENCIA
            optimizaciones.extend(self._optimizar_frecuencia(entrenamientos, objetivo))

            # 2. OPTIMIZACIÓN DE VOLUMEN
            optimizaciones.extend(self._optimizar_volumen(entrenamientos, objetivo))

            # 3. OPTIMIZACIÓN DE INTENSIDAD
            optimizaciones.extend(self._optimizar_intensidad(entrenamientos, objetivo))

            # 4. OPTIMIZACIÓN DE VARIEDAD
            optimizaciones.extend(self._optimizar_variedad(entrenamientos, objetivo))

            # 5. OPTIMIZACIÓN DE PROGRESIÓN
            optimizaciones.extend(self._optimizar_progresion(entrenamientos, objetivo))

            # Calcular mejora estimada total
            mejora_total = sum(opt.get('mejora_estimada', 0) for opt in optimizaciones)
            mejora_total = min(mejora_total, 15.0)  # Máximo 15% de mejora

            resultado = {
                'optimizaciones': optimizaciones,
                'mejora_estimada': round(mejora_total, 1),
                'algoritmos_activos': len(optimizaciones),
                'estado': 'activo' if total_entrenamientos >= 5 else 'limitado',
                'objetivo_entrenamiento': objetivo,
                'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
                'entrenamientos_analizados': total_entrenamientos
            }

            logger.info(f"Generadas {len(optimizaciones)} optimizaciones para cliente {self.cliente.id}")
            return resultado

        except Exception as e:
            logger.error(f"Error generando optimización: {e}")
            return self._respuesta_error()

    def _optimizar_frecuencia(self, entrenamientos, objetivo):
        """
        Optimiza la frecuencia de entrenamiento
        """
        optimizaciones = []

        try:
            if entrenamientos.count() < 3:
                return optimizaciones

            # Calcular frecuencia actual
            fechas = [e.fecha for e in entrenamientos]
            intervalos = []

            for i in range(1, len(fechas)):
                diff = (fechas[i] - fechas[i - 1]).days
                intervalos.append(diff)

            if intervalos:
                promedio_intervalo = sum(intervalos) / len(intervalos)
                frecuencia_semanal_actual = 7 / promedio_intervalo if promedio_intervalo > 0 else 0

                objetivo_config = self.configuracion['objetivos_disponibles'][objetivo]
                frecuencia_objetivo = objetivo_config['frecuencia_objetivo']

                if frecuencia_semanal_actual < frecuencia_objetivo - 0.5:
                    diferencia = frecuencia_objetivo - frecuencia_semanal_actual
                    optimizaciones.append({
                        'tipo': 'frecuencia',
                        'descripcion': f'Aumentar frecuencia de {frecuencia_semanal_actual:.1f} a {frecuencia_objetivo} entrenamientos por semana',
                        'mejora_estimada': min(4.0, diferencia * 1.5),
                        'prioridad': 'alta' if diferencia > 1 else 'media',
                        'accion_especifica': f'Entrenar cada {7 / frecuencia_objetivo:.1f} días en lugar de cada {promedio_intervalo:.1f} días',
                        'objetivo_numerico': frecuencia_objetivo
                    })
                elif frecuencia_semanal_actual > frecuencia_objetivo + 1:
                    optimizaciones.append({
                        'tipo': 'frecuencia',
                        'descripcion': f'Reducir frecuencia para mejor recuperación: de {frecuencia_semanal_actual:.1f} a {frecuencia_objetivo} por semana',
                        'mejora_estimada': 2.0,
                        'prioridad': 'media',
                        'accion_especifica': f'Permitir más descanso entre entrenamientos',
                        'objetivo_numerico': frecuencia_objetivo
                    })
                else:
                    optimizaciones.append({
                        'tipo': 'frecuencia',
                        'descripcion': f'Frecuencia óptima mantenida: {frecuencia_semanal_actual:.1f} entrenamientos por semana',
                        'mejora_estimada': 1.0,
                        'prioridad': 'baja',
                        'accion_especifica': 'Mantener frecuencia actual',
                        'objetivo_numerico': frecuencia_objetivo
                    })

        except Exception as e:
            logger.error(f"Error optimizando frecuencia: {e}")

        return optimizaciones

    def _optimizar_volumen(self, entrenamientos, objetivo):
        """
        Optimiza el volumen de entrenamiento
        """
        optimizaciones = []

        try:
            # Calcular volumen actual
            ejercicios_con_peso = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            )

            if ejercicios_con_peso.exists():
                # Calcular series y ejercicios promedio por entrenamiento
                total_series = ejercicios_con_peso.aggregate(Sum('series'))['series__sum'] or 0
                total_ejercicios = ejercicios_con_peso.count()

                series_por_entreno = total_series / entrenamientos.count()
                ejercicios_por_entreno = total_ejercicios / entrenamientos.count()

                objetivo_config = self.configuracion['objetivos_disponibles'][objetivo]
                series_objetivo_min = objetivo_config['series_objetivo'][0]
                series_objetivo_max = objetivo_config['series_objetivo'][1]

                # Estimar series objetivo por entrenamiento (asumiendo 6-8 ejercicios)
                series_objetivo_total = (series_objetivo_min + series_objetivo_max) / 2 * 7  # 7 ejercicios promedio

                if series_por_entreno < series_objetivo_total * 0.8:
                    diferencia = series_objetivo_total - series_por_entreno
                    optimizaciones.append({
                        'tipo': 'volumen',
                        'descripcion': f'Aumentar volumen: de {series_por_entreno:.1f} a {series_objetivo_total:.1f} series por entrenamiento',
                        'mejora_estimada': min(3.5, diferencia * 0.2),
                        'prioridad': 'alta',
                        'accion_especifica': f'Añadir {diferencia:.0f} series por entrenamiento',
                        'objetivo_numerico': series_objetivo_total
                    })
                elif series_por_entreno > series_objetivo_total * 1.3:
                    optimizaciones.append({
                        'tipo': 'volumen',
                        'descripcion': f'Reducir volumen para mejor recuperación: de {series_por_entreno:.1f} a {series_objetivo_total:.1f} series',
                        'mejora_estimada': 2.0,
                        'prioridad': 'media',
                        'accion_especifica': 'Reducir series por ejercicio o número de ejercicios',
                        'objetivo_numerico': series_objetivo_total
                    })

                # Optimizar número de ejercicios
                if ejercicios_por_entreno < 5:
                    optimizaciones.append({
                        'tipo': 'volumen',
                        'descripcion': f'Aumentar variedad: de {ejercicios_por_entreno:.1f} a 6-8 ejercicios por entrenamiento',
                        'mejora_estimada': 2.5,
                        'prioridad': 'media',
                        'accion_especifica': 'Añadir 1-2 ejercicios por sesión',
                        'objetivo_numerico': 7
                    })

        except Exception as e:
            logger.error(f"Error optimizando volumen: {e}")

        return optimizaciones

    def _optimizar_intensidad(self, entrenamientos, objetivo):
        """
        Optimiza la intensidad de entrenamiento
        """
        optimizaciones = []

        try:
            objetivo_config = self.configuracion['objetivos_disponibles'][objetivo]
            reps_objetivo_min = objetivo_config['reps_objetivo'][0]
            reps_objetivo_max = objetivo_config['reps_objetivo'][1]

            # Analizar repeticiones actuales
            ejercicios = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            )

            if ejercicios.exists():
                reps_promedio = ejercicios.aggregate(Avg('repeticiones'))['repeticiones__avg']

                if reps_promedio < reps_objetivo_min:
                    optimizaciones.append({
                        'tipo': 'intensidad',
                        'descripcion': f'Aumentar repeticiones: de {reps_promedio:.1f} a {reps_objetivo_min}-{reps_objetivo_max} para {objetivo}',
                        'mejora_estimada': 3.0,
                        'prioridad': 'alta',
                        'accion_especifica': f'Reducir peso y aumentar repeticiones al rango {reps_objetivo_min}-{reps_objetivo_max}',
                        'objetivo_numerico': (reps_objetivo_min + reps_objetivo_max) / 2
                    })
                elif reps_promedio > reps_objetivo_max:
                    optimizaciones.append({
                        'tipo': 'intensidad',
                        'descripcion': f'Reducir repeticiones: de {reps_promedio:.1f} a {reps_objetivo_min}-{reps_objetivo_max} para {objetivo}',
                        'mejora_estimada': 2.5,
                        'prioridad': 'media',
                        'accion_especifica': f'Aumentar peso y reducir repeticiones al rango {reps_objetivo_min}-{reps_objetivo_max}',
                        'objetivo_numerico': (reps_objetivo_min + reps_objetivo_max) / 2
                    })
                else:
                    optimizaciones.append({
                        'tipo': 'intensidad',
                        'descripcion': f'Intensidad óptima para {objetivo}: {reps_promedio:.1f} repeticiones promedio',
                        'mejora_estimada': 1.0,
                        'prioridad': 'baja',
                        'accion_especifica': 'Mantener rango de repeticiones actual',
                        'objetivo_numerico': reps_promedio
                    })

            # Analizar RPE si está disponible
            ejercicios_con_rpe = ejercicios.filter(rpe__isnull=False, rpe__gt=0)
            if ejercicios_con_rpe.exists():
                rpe_promedio = ejercicios_con_rpe.aggregate(Avg('rpe'))['rpe__avg']

                if objetivo == 'fuerza' and rpe_promedio < 8:
                    optimizaciones.append({
                        'tipo': 'intensidad',
                        'descripcion': f'Aumentar intensidad para fuerza: RPE de {rpe_promedio:.1f} a 8-9',
                        'mejora_estimada': 3.5,
                        'prioridad': 'alta',
                        'accion_especifica': 'Entrenar más cerca del fallo muscular',
                        'objetivo_numerico': 8.5
                    })
                elif objetivo == 'hipertrofia' and (rpe_promedio < 6 or rpe_promedio > 9):
                    optimizaciones.append({
                        'tipo': 'intensidad',
                        'descripcion': f'Ajustar intensidad para hipertrofia: RPE de {rpe_promedio:.1f} a 7-8',
                        'mejora_estimada': 2.5,
                        'prioridad': 'media',
                        'accion_especifica': 'Mantener RPE en rango 7-8',
                        'objetivo_numerico': 7.5
                    })

        except Exception as e:
            logger.error(f"Error optimizando intensidad: {e}")

        return optimizaciones

    def _optimizar_variedad(self, entrenamientos, objetivo):
        """
        Optimiza la variedad de ejercicios
        """
        optimizaciones = []

        try:
            # Analizar grupos musculares trabajados
            grupos_trabajados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).exclude(
                grupo_muscular__isnull=True
            ).exclude(
                grupo_muscular=''
            ).values('grupo_muscular').distinct().count()

            ejercicios_unicos = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).values('nombre_ejercicio').distinct().count()

            if grupos_trabajados < 5:
                optimizaciones.append({
                    'tipo': 'variedad',
                    'descripcion': f'Aumentar grupos musculares: de {grupos_trabajados} a 6-8 grupos por semana',
                    'mejora_estimada': 3.0,
                    'prioridad': 'alta',
                    'accion_especifica': f'Incluir ejercicios para {6 - grupos_trabajados} grupos musculares adicionales',
                    'objetivo_numerico': 6
                })

            if ejercicios_unicos < 8:
                optimizaciones.append({
                    'tipo': 'variedad',
                    'descripcion': f'Aumentar variedad de ejercicios: de {ejercicios_unicos} a 10-12 ejercicios diferentes',
                    'mejora_estimada': 2.5,
                    'prioridad': 'media',
                    'accion_especifica': f'Incorporar {10 - ejercicios_unicos} ejercicios nuevos',
                    'objetivo_numerico': 10
                })

            # Analizar balance entre ejercicios compuestos y aislados
            ejercicios_compuestos = ['sentadilla', 'peso muerto', 'press banca', 'dominadas', 'remo', 'press militar']
            ejercicios_realizados = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos
            ).values_list('nombre_ejercicio', flat=True)

            ejercicios_compuestos_realizados = 0
            for ejercicio in ejercicios_realizados:
                for compuesto in ejercicios_compuestos:
                    if compuesto.lower() in ejercicio.lower():
                        ejercicios_compuestos_realizados += 1
                        break

            if ejercicios_compuestos_realizados < 3:
                optimizaciones.append({
                    'tipo': 'variedad',
                    'descripcion': f'Incluir más ejercicios compuestos: actualmente {ejercicios_compuestos_realizados}, objetivo 4-5',
                    'mejora_estimada': 4.0,
                    'prioridad': 'alta',
                    'accion_especifica': 'Añadir ejercicios como sentadilla, peso muerto, press banca',
                    'objetivo_numerico': 4
                })

        except Exception as e:
            logger.error(f"Error optimizando variedad: {e}")

        return optimizaciones

    def _optimizar_progresion(self, entrenamientos, objetivo):
        """
        Optimiza la progresión de cargas
        """
        optimizaciones = []

        try:
            # Analizar progresión en ejercicios principales
            ejercicios_principales = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3)

            ejercicios_sin_progreso = 0
            ejercicios_con_progreso = 0

            for ejercicio in ejercicios_principales:
                registros = EjercicioRealizado.objects.filter(
                    entreno__in=entrenamientos,
                    nombre_ejercicio=ejercicio['nombre_ejercicio'],
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg

                    if ultimo_peso <= primer_peso:
                        ejercicios_sin_progreso += 1
                    else:
                        ejercicios_con_progreso += 1

            if ejercicios_sin_progreso > ejercicios_con_progreso:
                optimizaciones.append({
                    'tipo': 'progresion',
                    'descripcion': f'Implementar progresión sistemática: {ejercicios_sin_progreso} ejercicios sin progreso detectado',
                    'mejora_estimada': 5.0,
                    'prioridad': 'alta',
                    'accion_especifica': 'Aumentar peso 2.5-5% semanalmente cuando se completen todas las series',
                    'objetivo_numerico': 2.5  # Porcentaje de aumento semanal
                })
            elif ejercicios_con_progreso == 0 and ejercicios_principales.count() > 0:
                optimizaciones.append({
                    'tipo': 'progresion',
                    'descripcion': 'Establecer sistema de progresión de cargas',
                    'mejora_estimada': 4.0,
                    'prioridad': 'alta',
                    'accion_especifica': 'Implementar aumentos graduales de peso cada 1-2 semanas',
                    'objetivo_numerico': 2.5
                })
            else:
                optimizaciones.append({
                    'tipo': 'progresion',
                    'descripcion': f'Progresión detectada en {ejercicios_con_progreso} ejercicios',
                    'mejora_estimada': 1.5,
                    'prioridad': 'baja',
                    'accion_especifica': 'Mantener progresión actual',
                    'objetivo_numerico': ejercicios_con_progreso
                })

        except Exception as e:
            logger.error(f"Error optimizando progresión: {e}")

        return optimizaciones

    def generar_rutina_optimizada(self, objetivo='hipertrofia'):
        """
        Genera una rutina optimizada basada en el análisis
        """
        try:
            optimizacion = self.generar_optimizacion_completa(objetivo)

            if optimizacion['estado'] == 'error':
                return self._rutina_generica(objetivo)

            objetivo_config = self.configuracion['objetivos_disponibles'][objetivo]

            rutina = {
                'objetivo': objetivo,
                'frecuencia_semanal': objetivo_config['frecuencia_objetivo'],
                'ejercicios_por_dia': 6,
                'series_por_ejercicio': f"{objetivo_config['series_objetivo'][0]}-{objetivo_config['series_objetivo'][1]}",
                'repeticiones': f"{objetivo_config['reps_objetivo'][0]}-{objetivo_config['reps_objetivo'][1]}",
                'descanso_series': f"{objetivo_config['descanso_objetivo'][0]}-{objetivo_config['descanso_objetivo'][1]} min",
                'distribucion': self._generar_distribucion_semanal(objetivo),
                'optimizaciones_aplicadas': [opt['descripcion'] for opt in optimizacion['optimizaciones']],
                'mejora_estimada': optimizacion['mejora_estimada']
            }

            return rutina

        except Exception as e:
            logger.error(f"Error generando rutina optimizada: {e}")
            return self._rutina_generica(objetivo)

    def _generar_distribucion_semanal(self, objetivo):
        """
        Genera distribución semanal según el objetivo
        """
        if objetivo == 'fuerza':
            return {
                'dia_1': 'Tren superior (fuerza)',
                'dia_2': 'Tren inferior (fuerza)',
                'dia_3': 'Descanso',
                'dia_4': 'Tren superior (volumen)',
                'dia_5': 'Descanso',
                'dia_6': 'Descanso',
                'dia_7': 'Descanso'
            }
        elif objetivo == 'hipertrofia':
            return {
                'dia_1': 'Pecho y tríceps',
                'dia_2': 'Espalda y bíceps',
                'dia_3': 'Piernas',
                'dia_4': 'Hombros y abdomen',
                'dia_5': 'Descanso',
                'dia_6': 'Descanso',
                'dia_7': 'Descanso'
            }
        else:  # resistencia
            return {
                'dia_1': 'Cuerpo completo',
                'dia_2': 'Cardio y core',
                'dia_3': 'Cuerpo completo',
                'dia_4': 'Cardio y flexibilidad',
                'dia_5': 'Cuerpo completo',
                'dia_6': 'Descanso activo',
                'dia_7': 'Descanso'
            }

    def _rutina_generica(self, objetivo):
        """
        Rutina genérica cuando no hay datos suficientes
        """
        objetivo_config = self.configuracion['objetivos_disponibles'][objetivo]

        return {
            'objetivo': objetivo,
            'frecuencia_semanal': objetivo_config['frecuencia_objetivo'],
            'ejercicios_por_dia': 6,
            'series_por_ejercicio': f"{objetivo_config['series_objetivo'][0]}-{objetivo_config['series_objetivo'][1]}",
            'repeticiones': f"{objetivo_config['reps_objetivo'][0]}-{objetivo_config['reps_objetivo'][1]}",
            'descanso_series': f"{objetivo_config['descanso_objetivo'][0]}-{objetivo_config['descanso_objetivo'][1]} min",
            'distribucion': self._generar_distribucion_semanal(objetivo),
            'optimizaciones_aplicadas': ['Rutina base para comenzar'],
            'mejora_estimada': 0.0,
            'nota': 'Rutina genérica - registra más entrenamientos para optimizaciones personalizadas'
        }

    def _respuesta_datos_insuficientes(self):
        """
        Respuesta cuando no hay suficientes datos
        """
        return {
            'optimizaciones': [
                {
                    'tipo': 'inicio',
                    'descripcion': 'Registrar más entrenamientos para generar optimizaciones personalizadas',
                    'mejora_estimada': 0.0,
                    'prioridad': 'alta',
                    'accion_especifica': 'Completar al menos 5 entrenamientos para análisis detallado',
                    'objetivo_numerico': 5
                }
            ],
            'mejora_estimada': 0.0,
            'algoritmos_activos': 0,
            'estado': 'limitado',
            'objetivo_entrenamiento': 'general',
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'entrenamientos_analizados': 0
        }

    def _respuesta_error(self):
        """
        Respuesta cuando hay error
        """
        return {
            'optimizaciones': [],
            'mejora_estimada': 0.0,
            'algoritmos_activos': 0,
            'estado': 'error',
            'objetivo_entrenamiento': 'general',
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'entrenamientos_analizados': 0,
            'error_message': 'Error al procesar optimizaciones'
        }
