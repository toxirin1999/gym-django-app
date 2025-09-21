# 🧠 SISTEMA DE RECOMENDACIONES INTELIGENTES - VERSIÓN DJANGO FUNCIONAL
# Sistema simplificado y funcional compatible con Django ORM

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Max, Min
from collections import defaultdict, Counter
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos Django
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente


class SistemaRecomendacionesIA:
    """
    Sistema de recomendaciones inteligentes simplificado y funcional
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.configuracion = {
            'max_recomendaciones': 8,
            'ventana_analisis_dias': 60,
            'min_entrenamientos': 3,
            'grupos_musculares': {
                'pecho': ['press banca', 'press inclinado', 'fondos', 'aperturas', 'press'],
                'espalda': ['dominadas', 'remo', 'peso muerto', 'jalones', 'pullover'],
                'piernas': ['sentadilla', 'prensa', 'extensiones', 'curl femoral', 'gemelos'],
                'hombros': ['press militar', 'elevaciones laterales', 'elevaciones frontales', 'pájaros'],
                'brazos': ['curl biceps', 'press frances', 'triceps', 'curl', 'extensiones'],
                'core': ['abdominales', 'plancha', 'crunches', 'russian twist']
            }
        }

    def recomendar_rutina_adaptativa(self, objetivo, dias_disponibles):
        """
        Genera una rutina base adaptada según el objetivo y los días disponibles
        """
        tipos_entreno = {
            'fuerza': ['Fullbody pesado', 'Empuje', 'Tirón', 'Piernas pesadas'],
            'hipertrofia': ['Pecho-Bíceps', 'Espalda-Tríceps', 'Piernas-Hombros', 'Fullbody moderado'],
            'resistencia': ['Circuito funcional', 'Entreno tipo HIIT', 'Fullbody ligero', 'Core + cardio'],
            'salud': ['Movilidad + fuerza básica', 'Entreno fullbody suave', 'Bicicleta o caminata + core'],
        }

        base = tipos_entreno.get(objetivo.lower(), ['Fullbody'])

        # Limitar a los días disponibles
        rutina_sugerida = base[:dias_disponibles] if dias_disponibles <= len(base) else base

        return {
            'objetivo': objetivo.title(),
            'frecuencia': dias_disponibles,
            'sesiones_sugeridas': rutina_sugerida,
            'mensaje': f"Rutina adaptada para {dias_disponibles} días con foco en {objetivo}"
        }

    def recomendar_deload_inteligente(self):
        """
        Recomienda una semana de descarga si se detecta alta carga acumulada
        """
        try:
            perfil = self._analizar_perfil_usuario()
            frecuencia = perfil['frecuencia_entrenamiento']
            intensidad = perfil['intensidad_promedio']
            tendencia = perfil['progreso_reciente']['tendencia']

            # Condiciones de fatiga
            necesita_deload = (
                    frecuencia >= 5 and intensidad >= 75 and tendencia != 'ascendente'
            )

            if necesita_deload:
                return {
                    'recomendado': True,
                    'mensaje': "Tu cuerpo muestra signos de fatiga acumulada. Se recomienda una semana de descarga.",
                    'sugerencias': [
                        "Reduce el volumen total al 50%",
                        "Usa pesos al 60% de tu 1RM",
                        "Enfócate en técnica y movilidad",
                        "Duerme 8 horas diarias durante la semana"
                    ]
                }
            else:
                return {
                    'recomendado': False,
                    'mensaje': "No es necesaria una descarga esta semana.",
                    'sugerencias': []
                }

        except Exception as e:
            logger.error(f"Error en deload inteligente: {e}")
            return {
                'recomendado': False,
                'mensaje': "Error al evaluar necesidad de descarga.",
                'sugerencias': []
            }

    def generar_recomendaciones_personalizadas(self):
        """Genera recomendaciones personalizadas basadas en datos reales del usuario"""
        try:
            # Verificar si hay datos suficientes
            if not self._tiene_datos_suficientes():
                return self._generar_recomendaciones_usuario_nuevo()

            # Analizar perfil del usuario
            perfil_usuario = self._analizar_perfil_usuario()

            # Generar recomendaciones por categoría
            recomendaciones = {
                'ejercicios_nuevos': self._recomendar_ejercicios_nuevos(),
                'progresion_inteligente': self._recomendar_progresion_inteligente(),
                'equilibrio_muscular': self._recomendar_equilibrio_muscular(),
                'periodizacion': self._recomendar_periodizacion_simple(),
                'recuperacion': self._recomendar_recuperacion_optimizada(),
                'nutricion_timing': self._recomendar_nutricion_timing(),
                'objetivos_smart': self._generar_objetivos_smart()
            }

            # Calcular confianza del sistema
            confianza = self._calcular_confianza_recomendaciones(perfil_usuario)

            return {
                'recomendaciones': recomendaciones,
                'confianza_sistema': confianza,
                'perfil_usuario': perfil_usuario,
                'tiene_datos_suficientes': True
            }

        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
            return self._generar_recomendaciones_error()

    def _tiene_datos_suficientes(self):
        """Verifica si hay datos suficientes para generar recomendaciones"""
        fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])

        entrenamientos_count = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_limite
        ).count()

        return entrenamientos_count >= self.configuracion['min_entrenamientos']

    def _analizar_perfil_usuario(self):
        """Analiza el perfil del usuario basado en datos reales"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])

            # Obtener entrenamientos recientes
            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=fecha_limite
            ).order_by('-fecha')

            if not entrenamientos.exists():
                return self._perfil_usuario_default()

            # Calcular métricas básicas
            total_entrenamientos = entrenamientos.count()
            dias_transcurridos = (datetime.now().date() - fecha_limite).days
            frecuencia_semanal = (total_entrenamientos / dias_transcurridos) * 7

            # Obtener ejercicios realizados
            ejercicios = EjercicioRealizado.objects.filter(
                entreno__in=entrenamientos,
                peso_kg__gt=0
            )

            # Calcular intensidad promedio (duración de entrenamientos)
            duracion_promedio = entrenamientos.aggregate(
                promedio=Avg('duracion_minutos')
            )['promedio'] or 60

            # Determinar nivel de experiencia
            ejercicios_unicos = ejercicios.values('nombre_ejercicio').distinct().count()
            nivel_experiencia = self._determinar_nivel_experiencia(ejercicios_unicos, total_entrenamientos)

            # Calcular consistencia (entrenamientos en las últimas 4 semanas)
            fecha_4_semanas = datetime.now().date() - timedelta(days=28)
            entrenamientos_recientes = entrenamientos.filter(fecha__gte=fecha_4_semanas).count()
            consistencia = min(100, (entrenamientos_recientes / 12) * 100)  # 3 entrenamientos/semana = 100%

            # Analizar progreso reciente
            progreso_reciente = self._analizar_progreso_reciente(ejercicios)

            return {
                'nivel_experiencia': nivel_experiencia,
                'frecuencia_entrenamiento': round(frecuencia_semanal, 1),
                'consistencia': round(consistencia, 1),
                'intensidad_promedio': round(duracion_promedio, 0),
                'progreso_reciente': progreso_reciente,
                'total_entrenamientos': total_entrenamientos,
                'ejercicios_unicos': ejercicios_unicos
            }

        except Exception as e:
            logger.error(f"Error analizando perfil: {e}")
            return self._perfil_usuario_default()

    def _determinar_nivel_experiencia(self, ejercicios_unicos, total_entrenamientos):
        """Determina el nivel de experiencia del usuario"""
        if total_entrenamientos < 10 or ejercicios_unicos < 8:
            return 'principiante'
        elif total_entrenamientos < 30 or ejercicios_unicos < 15:
            return 'intermedio'
        else:
            return 'avanzado'

    def _analizar_progreso_reciente(self, ejercicios):
        """Analiza el progreso reciente del usuario"""
        try:
            if not ejercicios.exists():
                return {'porcentaje_mejora': 0, 'tendencia': 'sin_datos'}

            # Obtener ejercicios con múltiples registros
            ejercicios_con_progreso = []

            for nombre_ejercicio in ejercicios.values_list('nombre_ejercicio', flat=True).distinct():
                registros = ejercicios.filter(nombre_ejercicio=nombre_ejercicio).order_by('entreno__fecha')

                if registros.count() >= 3:
                    primer_peso = registros.first().peso_kg
                    ultimo_peso = registros.last().peso_kg

                    if primer_peso > 0:
                        mejora = ((ultimo_peso - primer_peso) / primer_peso) * 100
                        ejercicios_con_progreso.append(mejora)

            if ejercicios_con_progreso:
                progreso_promedio = np.mean(ejercicios_con_progreso)

                if progreso_promedio > 5:
                    tendencia = 'ascendente'
                elif progreso_promedio > -2:
                    tendencia = 'estable'
                else:
                    tendencia = 'descendente'

                return {
                    'porcentaje_mejora': round(progreso_promedio, 1),
                    'tendencia': tendencia
                }
            else:
                return {'porcentaje_mejora': 0, 'tendencia': 'insuficientes_datos'}

        except Exception as e:
            logger.error(f"Error analizando progreso: {e}")
            return {'porcentaje_mejora': 0, 'tendencia': 'error'}

    def _recomendar_ejercicios_nuevos(self):
        """Recomienda ejercicios nuevos basados en gaps musculares"""
        try:
            # Obtener ejercicios realizados por el usuario
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])

            ejercicios_realizados = set(
                EjercicioRealizado.objects.filter(
                    entreno__cliente=self.cliente,
                    entreno__fecha__gte=fecha_limite
                ).values_list('nombre_ejercicio', flat=True).distinct()
            )

            # Normalizar nombres para comparación
            ejercicios_realizados_norm = {self._normalizar_nombre(ej) for ej in ejercicios_realizados}

            recomendaciones = []

            # Analizar cada grupo muscular
            for grupo, ejercicios_grupo in self.configuracion['grupos_musculares'].items():
                # Encontrar ejercicios del grupo que no ha hecho
                ejercicios_nuevos = []

                for ejercicio in ejercicios_grupo:
                    # Verificar si el usuario ha hecho algún ejercicio similar
                    if not any(
                            ejercicio.lower() in ej_realizado.lower() for ej_realizado in ejercicios_realizados_norm):
                        ejercicios_nuevos.append(ejercicio.title())

                if ejercicios_nuevos:
                    # Calcular prioridad basada en cuántos ejercicios del grupo ha hecho
                    ejercicios_grupo_realizados = sum(
                        1 for ej_grupo in ejercicios_grupo
                        if any(ej_grupo.lower() in ej_realizado.lower() for ej_realizado in ejercicios_realizados_norm)
                    )

                    if ejercicios_grupo_realizados == 0:
                        prioridad = 'alta'
                    elif ejercicios_grupo_realizados < 2:
                        prioridad = 'media'
                    else:
                        prioridad = 'baja'

                    recomendaciones.append({
                        'grupo_muscular': grupo.title(),
                        'ejercicios_sugeridos': ejercicios_nuevos[:3],
                        'razon': f'Ampliar variedad en {grupo}',
                        'prioridad': prioridad
                    })

            return recomendaciones[:5]  # Limitar a 5 recomendaciones

        except Exception as e:
            logger.error(f"Error recomendando ejercicios nuevos: {e}")
            return self._ejercicios_nuevos_default()

    def _recomendar_progresion_inteligente(self):
        """Recomienda progresión inteligente para ejercicios actuales"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=30)  # Últimas 4 semanas

            # Obtener ejercicios con múltiples registros
            ejercicios_frecuentes = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                entreno__fecha__gte=fecha_limite,
                peso_kg__gt=0
            ).values('nombre_ejercicio').annotate(
                cantidad=Count('id')
            ).filter(cantidad__gte=3).order_by('-cantidad')

            recomendaciones = []

            for ejercicio_data in ejercicios_frecuentes[:5]:  # Top 5 ejercicios
                nombre_ejercicio = ejercicio_data['nombre_ejercicio']

                # Obtener registros del ejercicio ordenados por fecha
                registros = EjercicioRealizado.objects.filter(
                    entreno__cliente=self.cliente,
                    nombre_ejercicio=nombre_ejercicio,
                    entreno__fecha__gte=fecha_limite,
                    peso_kg__gt=0
                ).order_by('entreno__fecha')

                if registros.count() >= 3:
                    pesos = [r.peso_kg for r in registros]

                    # Analizar tendencia
                    peso_inicial = pesos[0]
                    peso_final = pesos[-1]
                    peso_maximo = max(pesos)

                    # Determinar tipo de recomendación
                    if peso_final == peso_maximo and len(set(pesos[-3:])) == 1:
                        # Estancado en las últimas 3 sesiones
                        recomendaciones.append({
                            'ejercicio': nombre_ejercicio,
                            'tipo_progresion': 'cambio_variables',
                            'sugerencia': 'Aumentar series o cambiar rango de repeticiones',
                            'razon': 'Estancamiento detectado en las últimas sesiones',
                            'peso_actual': peso_final
                        })
                    elif peso_final > peso_inicial * 1.1:
                        # Progreso rápido
                        recomendaciones.append({
                            'ejercicio': nombre_ejercicio,
                            'tipo_progresion': 'aceleracion',
                            'sugerencia': f'Considerar aumentar a {peso_final + 2.5} kg',
                            'razon': 'Progreso consistente, capacidad para más carga',
                            'peso_actual': peso_final
                        })
                    elif peso_final < peso_inicial:
                        # Regresión
                        recomendaciones.append({
                            'ejercicio': nombre_ejercicio,
                            'tipo_progresion': 'recuperacion',
                            'sugerencia': 'Revisar técnica y tiempo de recuperación',
                            'razon': 'Disminución en el peso utilizado',
                            'peso_actual': peso_final
                        })

            return recomendaciones

        except Exception as e:
            logger.error(f"Error en progresión inteligente: {e}")
            return []

    def _recomendar_equilibrio_muscular(self):
        """Recomienda mejoras en el equilibrio muscular"""
        try:
            fecha_limite = datetime.now().date() - timedelta(days=self.configuracion['ventana_analisis_dias'])

            # Obtener todos los ejercicios realizados
            ejercicios = EjercicioRealizado.objects.filter(
                entreno__cliente=self.cliente,
                entreno__fecha__gte=fecha_limite,
                peso_kg__gt=0
            )

            if not ejercicios.exists():
                return []

            # Contar ejercicios por grupo muscular
            volumen_por_grupo = defaultdict(int)

            for ejercicio in ejercicios:
                nombre_norm = self._normalizar_nombre(ejercicio.nombre_ejercicio)
                grupo_encontrado = False

                for grupo, ejercicios_grupo in self.configuracion['grupos_musculares'].items():
                    if any(ej.lower() in nombre_norm for ej in ejercicios_grupo):
                        volumen_por_grupo[grupo] += ejercicio.series * ejercicio.repeticiones * ejercicio.peso_kg
                        grupo_encontrado = True
                        break

                if not grupo_encontrado:
                    volumen_por_grupo['otros'] += ejercicio.series * ejercicio.repeticiones * ejercicio.peso_kg

            # Calcular porcentajes
            volumen_total = sum(volumen_por_grupo.values())
            if volumen_total == 0:
                return []

            recomendaciones = []

            for grupo, volumen in volumen_por_grupo.items():
                porcentaje = (volumen / volumen_total) * 100

                if porcentaje < 10 and grupo != 'otros':  # Grupo subdesarrollado
                    recomendaciones.append({
                        'grupo_muscular': grupo.title(),
                        'porcentaje_actual': round(porcentaje, 1),
                        'recomendacion': f'Aumentar volumen en {grupo}',
                        'prioridad': 'alta' if porcentaje < 5 else 'media',
                        'sugerencia': f'Agregar 1-2 ejercicios más de {grupo} por semana'
                    })

            return recomendaciones[:3]  # Top 3 prioridades

        except Exception as e:
            logger.error(f"Error en equilibrio muscular: {e}")
            return []

    def _recomendar_periodizacion_simple(self):
        """Recomienda periodización simple basada en el perfil del usuario"""
        try:
            perfil = self._analizar_perfil_usuario()
            nivel = perfil['nivel_experiencia']
            frecuencia = perfil['frecuencia_entrenamiento']

            if nivel == 'principiante':
                return {
                    'tipo': 'lineal',
                    'duracion_fase': '4-6 semanas',
                    'incrementos': '2.5-5 kg por semana',
                    'deload_frecuencia': 'cada 6 semanas',
                    'enfoque': 'Aprendizaje de técnica y adaptación'
                }
            elif nivel == 'intermedio':
                return {
                    'tipo': 'ondulante',
                    'duracion_fase': '3-4 semanas',
                    'incrementos': '1.25-2.5 kg por semana',
                    'deload_frecuencia': 'cada 4 semanas',
                    'enfoque': 'Variación de intensidad y volumen'
                }
            else:  # avanzado
                return {
                    'tipo': 'conjugado',
                    'duracion_fase': '2-3 semanas',
                    'incrementos': '0.5-1.25 kg por semana',
                    'deload_frecuencia': 'cada 3 semanas',
                    'enfoque': 'Especialización y picos de rendimiento'
                }

        except Exception as e:
            logger.error(f"Error en periodización: {e}")
            return self._periodizacion_default()

    def _recomendar_recuperacion_optimizada(self):
        """Recomienda estrategias de recuperación basadas en frecuencia de entrenamiento"""
        try:
            perfil = self._analizar_perfil_usuario()
            frecuencia = perfil['frecuencia_entrenamiento']

            if frecuencia > 5:
                nivel_fatiga = 'alto'
                estrategias = [
                    'Reducir frecuencia a 4-5 días por semana',
                    'Incluir días de descanso activo',
                    'Priorizar 7-8 horas de sueño',
                    'Considerar masajes semanales'
                ]
                frecuencia_masajes = 'semanal'
            elif frecuencia > 3:
                nivel_fatiga = 'moderado'
                estrategias = [
                    'Mantener 1-2 días de descanso completo',
                    'Incluir estiramientos post-entreno',
                    'Hidratación adecuada',
                    'Técnicas de relajación'
                ]
                frecuencia_masajes = 'quincenal'
            else:
                nivel_fatiga = 'bajo'
                estrategias = [
                    'Mantener rutina actual',
                    'Considerar aumentar frecuencia gradualmente',
                    'Enfocarse en calidad del sueño',
                    'Actividades de movilidad'
                ]
                frecuencia_masajes = 'mensual'

            return {
                'nivel_fatiga': nivel_fatiga,
                'estrategias_recomendadas': estrategias,
                'frecuencia_masajes': frecuencia_masajes,
                'dias_descanso_recomendados': max(1, 7 - int(frecuencia))
            }

        except Exception as e:
            logger.error(f"Error en recuperación: {e}")
            return self._recuperacion_default()

    def _recomendar_nutricion_timing(self):
        """Recomienda timing de nutrición personalizado"""
        try:
            perfil = self._analizar_perfil_usuario()
            intensidad = perfil['intensidad_promedio']
            frecuencia = perfil['frecuencia_entrenamiento']
            progreso = perfil['progreso_reciente']
            nivel = perfil['nivel_experiencia']

            # Clasificación de intensidad
            if intensidad > 90:
                categoria = 'alta'
                pre_entreno = {
                    'timing': '30-60 minutos antes: carbohidratos complejos + proteína',
                    'ejemplo': 'Avena con plátano y proteína en polvo'
                }
                post_entreno = {
                    'timing': '30 minutos después: proteína + carbohidratos simples',
                    'ejemplo': 'Batido de proteína con plátano y miel'
                }
                explicacion = "Tus entrenamientos son largos, por lo que necesitas combustible eficiente antes y una buena recuperación después."
            elif intensidad > 60:
                categoria = 'moderada'
                pre_entreno = {
                    'timing': '30 minutos antes: snack ligero con carbohidratos',
                    'ejemplo': 'Plátano o tostada con miel'
                }
                post_entreno = {
                    'timing': '60 minutos después: comida balanceada',
                    'ejemplo': 'Pollo con arroz y verduras'
                }
                explicacion = "Tu entreno tiene duración moderada, por lo que una ingesta ligera antes y una comida completa después es suficiente."
            else:
                categoria = 'baja'
                pre_entreno = {
                    'timing': 'No necesario si comes 2-3 horas antes',
                    'ejemplo': 'Hidratación adecuada es suficiente'
                }
                post_entreno = {
                    'timing': 'Comida regular dentro de 2 horas',
                    'ejemplo': 'Cualquier comida balanceada'
                }
                explicacion = "Tus sesiones son más cortas, por lo que puedes mantener una estrategia nutricional simple."

            # Ajuste adicional según progreso
            if progreso['porcentaje_mejora'] < 2 and categoria != 'alta':
                explicacion += " Además, no se detecta mucho progreso, por lo que podrías revisar si estás comiendo lo suficiente antes de entrenar."

            if frecuencia >= 5 and categoria == 'alta':
                explicacion += " Como entrenas con mucha frecuencia, asegúrate de reponer energía bien cada día."

            return {
                'pre_entreno': pre_entreno,
                'post_entreno': post_entreno,
                'explicacion': explicacion,
                'categoria_intensidad': categoria,
                'tipo_entrenamiento_dia': self._sugerencia_tiempo_entreno(),
                'duracion_promedio': intensidad
            }

        except Exception as e:
            logger.error(f"Error en nutrición timing: {e}")
            return self._nutricion_default()

    def _sugerencia_tiempo_entreno(self):
        """Sugiere alimentos según el momento más frecuente del día para entrenar"""
        try:
            # Buscar hora promedio del entreno
            entrenos = EntrenoRealizado.objects.filter(cliente=self.cliente).exclude(hora_inicio__isnull=True)
            if not entrenos.exists():
                return "Entrena a la hora que te sientas con más energía, idealmente 1-2 h después de comer."

            horas = [e.hora_inicio.hour for e in entrenos if e.hora_inicio]
            if not horas:
                return "Entrena cuando tengas energía y tiempo suficiente, idealmente bien alimentado."

            promedio = sum(horas) / len(horas)

            if promedio < 11:
                return "🍳 Entrenas por la mañana. Desayuna bien: avena, fruta y huevos son buena opción."
            elif promedio < 17:
                return "🥗 Entrenas por la tarde. Un buen almuerzo o snack con plátano y proteína te ayudará."
            else:
                return "🍽️ Entrenas por la noche. Evita comidas muy pesadas justo antes y prioriza recuperación ligera."

        except Exception as e:
            logger.warning(f"Error en sugerencia por hora de entreno: {e}")
            return "Entrena en el momento del día que te permita mayor consistencia."

    def _generar_objetivos_smart(self):
        """Genera objetivos SMART basados en el progreso del usuario"""
        try:
            perfil = self._analizar_perfil_usuario()
            progreso = perfil['progreso_reciente']
            nivel = perfil['nivel_experiencia']

            objetivos = []

            # Objetivo de frecuencia
            frecuencia_actual = perfil['frecuencia_entrenamiento']
            if frecuencia_actual < 3:
                objetivos.append({
                    'categoria': 'Frecuencia',
                    'objetivo': f'Entrenar {min(4, frecuencia_actual + 1)} veces por semana',
                    'plazo': '4 semanas',
                    'medible': 'Número de entrenamientos semanales',
                    'alcanzable': True
                })

            # Objetivo de progresión
            if progreso['porcentaje_mejora'] > 0:
                objetivos.append({
                    'categoria': 'Progresión',
                    'objetivo': f'Aumentar peso promedio en {progreso["porcentaje_mejora"] * 0.5:.1f}%',
                    'plazo': '6 semanas',
                    'medible': 'Peso promedio en ejercicios principales',
                    'alcanzable': True
                })

            # Objetivo de consistencia
            if perfil['consistencia'] < 80:
                objetivos.append({
                    'categoria': 'Consistencia',
                    'objetivo': f'Alcanzar {min(90, perfil["consistencia"] + 15):.0f}% de consistencia',
                    'plazo': '8 semanas',
                    'medible': 'Porcentaje de entrenamientos completados',
                    'alcanzable': True
                })

            # Objetivo de variedad (para principiantes)
            if nivel == 'principiante':
                objetivos.append({
                    'categoria': 'Variedad',
                    'objetivo': f'Aprender {max(3, 15 - perfil["ejercicios_unicos"])} ejercicios nuevos',
                    'plazo': '12 semanas',
                    'medible': 'Número de ejercicios únicos realizados',
                    'alcanzable': True
                })

            return objetivos[:4]  # Máximo 4 objetivos

        except Exception as e:
            logger.error(f"Error generando objetivos: {e}")
            return self._objetivos_default()

    # ============================================================================
    # MÉTODOS DE UTILIDAD Y FALLBACKS
    # ============================================================================

    def _normalizar_nombre(self, nombre):
        """Normaliza nombres de ejercicios para comparación"""
        if not nombre:
            return ""
        return str(nombre).strip().lower()

    def _calcular_confianza_recomendaciones(self, perfil_usuario):
        """Calcula la confianza del sistema basada en la cantidad de datos"""
        try:
            total_entrenamientos = perfil_usuario.get('total_entrenamientos', 0)
            ejercicios_unicos = perfil_usuario.get('ejercicios_unicos', 0)

            # Factores de confianza
            factor_entrenamientos = min(100, (total_entrenamientos / 20) * 50)  # 50% máximo
            factor_variedad = min(100, (ejercicios_unicos / 15) * 30)  # 30% máximo
            factor_consistencia = perfil_usuario.get('consistencia', 0) * 0.2  # 20% máximo

            confianza = factor_entrenamientos + factor_variedad + factor_consistencia
            return round(min(100, max(30, confianza)), 1)

        except Exception as e:
            logger.error(f"Error calculando confianza: {e}")
            return 60.0

    def _generar_recomendaciones_usuario_nuevo(self):
        """Genera recomendaciones para usuarios nuevos sin datos suficientes"""
        return {
            'recomendaciones': {
                'ejercicios_nuevos': self._ejercicios_nuevos_principiante(),
                'progresion_inteligente': [],
                'equilibrio_muscular': [],
                'periodizacion': self._periodizacion_principiante(),
                'recuperacion': self._recuperacion_principiante(),
                'nutricion_timing': self._nutricion_default(),
                'objetivos_smart': self._objetivos_principiante()
            },
            'confianza_sistema': 40.0,
            'perfil_usuario': self._perfil_usuario_nuevo(),
            'tiene_datos_suficientes': False
        }

    def _generar_recomendaciones_error(self):
        """Genera recomendaciones por defecto en caso de error"""
        return {
            'recomendaciones': {
                'ejercicios_nuevos': [],
                'progresion_inteligente': [],
                'equilibrio_muscular': [],
                'periodizacion': self._periodizacion_default(),
                'recuperacion': self._recuperacion_default(),
                'nutricion_timing': self._nutricion_default(),
                'objetivos_smart': []
            },
            'confianza_sistema': 30.0,
            'perfil_usuario': self._perfil_usuario_default(),
            'tiene_datos_suficientes': False
        }

    # ============================================================================
    # MÉTODOS DE FALLBACK Y DEFAULTS
    # ============================================================================

    def _perfil_usuario_default(self):
        return {
            'nivel_experiencia': 'principiante',
            'frecuencia_entrenamiento': 2.0,
            'consistencia': 50.0,
            'intensidad_promedio': 60.0,
            'progreso_reciente': {'porcentaje_mejora': 0, 'tendencia': 'sin_datos'},
            'total_entrenamientos': 0,
            'ejercicios_unicos': 0
        }

    def _perfil_usuario_nuevo(self):
        return {
            'nivel_experiencia': 'principiante',
            'frecuencia_entrenamiento': 0.0,
            'consistencia': 0.0,
            'intensidad_promedio': 45.0,
            'progreso_reciente': {'porcentaje_mejora': 0, 'tendencia': 'usuario_nuevo'},
            'total_entrenamientos': 0,
            'ejercicios_unicos': 0
        }

    def _ejercicios_nuevos_principiante(self):
        return [
            {
                'grupo_muscular': 'Pecho',
                'ejercicios_sugeridos': ['Press Banca', 'Fondos', 'Aperturas'],
                'razon': 'Ejercicios fundamentales para principiantes',
                'prioridad': 'alta'
            },
            {
                'grupo_muscular': 'Espalda',
                'ejercicios_sugeridos': ['Remo', 'Dominadas Asistidas', 'Jalones'],
                'razon': 'Equilibrio muscular esencial',
                'prioridad': 'alta'
            },
            {
                'grupo_muscular': 'Piernas',
                'ejercicios_sugeridos': ['Sentadilla', 'Prensa', 'Extensiones'],
                'razon': 'Base de fuerza fundamental',
                'prioridad': 'alta'
            }
        ]

    def _ejercicios_nuevos_default(self):
        return [
            {
                'grupo_muscular': 'Variedad',
                'ejercicios_sugeridos': ['Press Banca', 'Sentadilla', 'Remo'],
                'razon': 'Ejercicios fundamentales recomendados',
                'prioridad': 'media'
            }
        ]

    def _periodizacion_default(self):
        return {
            'tipo': 'lineal',
            'duracion_fase': '4 semanas',
            'incrementos': '2.5 kg por semana',
            'deload_frecuencia': 'cada 4 semanas',
            'enfoque': 'Progresión gradual y consistente'
        }

    def _periodizacion_principiante(self):
        return {
            'tipo': 'adaptación',
            'duracion_fase': '6-8 semanas',
            'incrementos': 'Enfoque en técnica antes que peso',
            'deload_frecuencia': 'según sensaciones',
            'enfoque': 'Aprendizaje de movimientos básicos'
        }

    def _recuperacion_default(self):
        return {
            'nivel_fatiga': 'moderado',
            'estrategias_recomendadas': [
                'Dormir 7-8 horas diarias',
                'Hidratación adecuada',
                'Días de descanso regulares'
            ],
            'frecuencia_masajes': 'mensual',
            'dias_descanso_recomendados': 2
        }

    def _recuperacion_principiante(self):
        return {
            'nivel_fatiga': 'bajo',
            'estrategias_recomendadas': [
                'Comenzar gradualmente',
                'Escuchar al cuerpo',
                'Descansar entre entrenamientos',
                'Mantener buena hidratación'
            ],
            'frecuencia_masajes': 'opcional',
            'dias_descanso_recomendados': 3
        }

    def _nutricion_default(self):
        return {
            'pre_entreno': {
                'timing': '1-2 horas antes: comida balanceada',
                'ejemplo': 'Comida normal con carbohidratos y proteína'
            },
            'post_entreno': {
                'timing': 'Dentro de 2 horas: comida completa',
                'ejemplo': 'Cualquier comida balanceada'
            }
        }

    def _objetivos_default(self):
        return [
            {
                'categoria': 'Consistencia',
                'objetivo': 'Entrenar 3 veces por semana',
                'plazo': '4 semanas',
                'medible': 'Número de entrenamientos',
                'alcanzable': True
            }
        ]

    def _objetivos_principiante(self):
        return [
            {
                'categoria': 'Hábito',
                'objetivo': 'Establecer rutina de 2-3 entrenamientos semanales',
                'plazo': '6 semanas',
                'medible': 'Entrenamientos completados por semana',
                'alcanzable': True
            },
            {
                'categoria': 'Técnica',
                'objetivo': 'Dominar 8 ejercicios básicos',
                'plazo': '8 semanas',
                'medible': 'Ejercicios realizados con buena técnica',
                'alcanzable': True
            }
        ]


from .ia_recomendaciones_inteligentes import SistemaRecomendacionesIA

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from clientes.models import Cliente
from analytics.ia_recomendaciones_inteligentes import SistemaRecomendacionesIA
import logging

logger = logging.getLogger(__name__)

import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from clientes.models import Cliente
from analytics.ia_recomendaciones_inteligentes import SistemaRecomendacionesIA

logger = logging.getLogger(__name__)


def recomendaciones_inteligentes(request, cliente_id):
    """Vista para recomendaciones inteligentes - CORREGIDA"""
    try:
        # Obtener cliente real o fallback
        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            logger.info(f"Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")
        except Exception as e:
            logger.warning(f"Cliente {cliente_id} no encontrado: {e}")
            cliente = crear_cliente_fallback(cliente_id, "Usuario")

        # Verificar cache
        cache_key = f'recomendaciones_inteligentes_{cliente_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            cached_data['cliente'] = cliente
            logger.info("Datos de recomendaciones obtenidos desde cache")
            return render(request, 'analytics/recomendaciones_inteligentes.html', cached_data)

        # Inicializar sistema de recomendaciones
        sistema_recomendaciones = SistemaRecomendacionesIA(cliente)

        # Generar recomendaciones completas
        recomendaciones_data = sistema_recomendaciones.generar_recomendaciones_completas()
        logger.info(f"Recomendaciones generadas: {recomendaciones_data.get('total_recomendaciones', 0)}")

        # Obtener recomendaciones prioritarias
        recomendaciones_prioritarias = sistema_recomendaciones.obtener_recomendaciones_prioritarias(3)

        # Generar plan de mejora
        plan_mejora = sistema_recomendaciones.generar_plan_mejora()

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
            'recomendaciones': recomendaciones_data.get('recomendaciones', []),
            'total_recomendaciones': recomendaciones_data.get('total_recomendaciones', 0),
            'confianza_promedio': recomendaciones_data.get('confianza_promedio', 0.0),
            'estado_sistema': recomendaciones_data.get('estado_sistema', 'limitado'),
            'recomendaciones_prioritarias': recomendaciones_prioritarias,
            'plan_mejora': plan_mejora,
            'entrenamientos_analizados': recomendaciones_data.get('entrenamientos_analizados', 0),
            'fecha_analisis': recomendaciones_data.get('fecha_analisis', datetime.now().strftime('%Y-%m-%d')),
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            # Datos de verificación
            'total_entrenamientos_reales': total_entrenamientos,
            'total_ejercicios_reales': total_ejercicios,
            'error_message': None
        }

        # Guardar en cache por 1 hora
        cache.set(cache_key, context, 3600)

        logger.info(f"Vista recomendaciones generada exitosamente - {context['total_recomendaciones']} recomendaciones")

        return render(request, 'analytics/recomendaciones_inteligentes.html', context)

    except Exception as e:
        logger.error(f"Error crítico en recomendaciones_inteligentes: {e}")

        cliente_fallback = crear_cliente_fallback(cliente_id, "Usuario")

        return render(request, 'analytics/recomendaciones_inteligentes.html', {
            'cliente': cliente_fallback,
            'recomendaciones': [],
            'total_recomendaciones': 0,
            'confianza_promedio': 0.0,
            'estado_sistema': 'error',
            'recomendaciones_prioritarias': [],
            'plan_mejora': {},
            'entrenamientos_analizados': 0,
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d'),
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'total_entrenamientos_reales': 0,
            'total_ejercicios_reales': 0,
            'error_message': 'Error al cargar recomendaciones. Intenta nuevamente.'
        })


# Función de utilidad para crear instancia
def crear_sistema_recomendaciones(cliente):
    """Crea una instancia del sistema de recomendaciones para un cliente"""
    return SistemaRecomendacionesIA(cliente)


if __name__ == "__main__":
    print("🧠 SISTEMA DE RECOMENDACIONES INTELIGENTES - VERSIÓN DJANGO")
    print("✅ Compatible con Django ORM")
    print("✅ Manejo robusto de datos limitados")
    print("✅ Recomendaciones prácticas y aplicables")
    print("✅ Logging y manejo de errores mejorado")
