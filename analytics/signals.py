# 🔄 SIGNALS PARA EL CENTRO DE ANÁLISIS
# Archivo: analytics/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import logging

from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from .models import (
    MetricaRendimiento, AnalisisEjercicio, TendenciaProgresion,
    PrediccionRendimiento, RecomendacionEntrenamiento
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=EntrenoRealizado)
def actualizar_metricas_entreno(sender, instance, created, **kwargs):
    """
    Actualiza métricas cuando se crea o modifica un entrenamiento
    """
    if created:
        logger.info(f"Nuevo entrenamiento creado para {instance.cliente.nombre}")

        # Calcular métricas del día
        calcular_metricas_dia(instance.cliente, instance.fecha)

        # Generar recomendaciones automáticas si es necesario
        generar_recomendaciones_automaticas(instance.cliente)


@receiver(post_save, sender=EjercicioLiftinDetallado)
def actualizar_analisis_ejercicio(sender, instance, created, **kwargs):
    """
    Actualiza análisis de ejercicio cuando se crea o modifica un ejercicio detallado
    """
    if created:
        logger.info(f"Nuevo ejercicio detallado: {instance.nombre_ejercicio}")

        # Actualizar análisis del ejercicio
        actualizar_analisis_ejercicio_especifico(
            instance.entreno.cliente,
            instance.nombre_ejercicio,
            instance.entreno.fecha
        )

        # Calcular tendencias de progresión
        calcular_tendencia_progresion(
            instance.entreno.cliente,
            instance.nombre_ejercicio
        )


def calcular_metricas_dia(cliente, fecha):
    """
    Calcula y guarda las métricas de rendimiento para un día específico
    """
    try:
        # Obtener entrenamientos del día
        entrenamientos_dia = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha=fecha
        )

        if not entrenamientos_dia.exists():
            return

        # Calcular métricas básicas
        volumen_total = 0
        calorias_totales = sum([e.calorias_quemadas or 0 for e in entrenamientos_dia])
        duracion_total = sum([e.duracion_minutos or 0 for e in entrenamientos_dia])

        # Calcular volumen usando datos de ejercicios parseados
        from entrenos.utils.utils import parsear_ejercicios

        for entreno in entrenamientos_dia:
            if entreno.notas_liftin:
                ejercicios = parsear_ejercicios(entreno.notas_liftin)
                for ej in ejercicios:
                    try:
                        peso = float(ej.get('peso', 0)) if ej.get('peso') != 'PC' else 0
                        series = int(ej.get('series', 1)) if ej.get('series') else 1
                        reps = int(ej.get('repeticiones', 1)) if ej.get('repeticiones') else 1
                        volumen_total += peso * series * reps
                    except (ValueError, TypeError):
                        continue

        # Calcular intensidad promedio
        intensidad_promedio = volumen_total / duracion_total if duracion_total > 0 else 0

        # Calcular frecuencia cardíaca promedio
        fc_promedios_validos = [getattr(e, 'fc_promedio', 0) or 0 for e in entrenamientos_dia]
        fc_promedio = sum(fc_promedios_validos) / len(fc_promedios_validos) if fc_promedios_validos else 0

        # --- FIN DE LA CORRECCIÓN ---

        # Crear o actualizar métrica del día
        metrica, created = MetricaRendimiento.objects.update_or_create(
            cliente=cliente,
            fecha=fecha,
            defaults={
                'volumen_total': volumen_total,
                'intensidad_promedio': intensidad_promedio,
                'calorias_totales': calorias_totales,
                'duracion_total': duracion_total,
                'fc_promedio': fc_promedio,
                'entrenamientos_dia': entrenamientos_dia.count()

            }
        )

        logger.info(f"Métricas {'creadas' if created else 'actualizadas'} para {cliente.nombre} - {fecha}")

    except Exception as e:
        logger.error(f"Error calculando métricas para {cliente.nombre} - {fecha}: {e}")


def actualizar_analisis_ejercicio_especifico(cliente, nombre_ejercicio, fecha):
    """
    Actualiza el análisis de un ejercicio específico
    """
    try:
        # Obtener todos los ejercicios de este tipo para el cliente
        from entrenos.utils.utils import parsear_ejercicios

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

        ejercicios_tipo = []
        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)
            for ej in ejercicios:
                if ej['nombre'] == nombre_ejercicio:
                    ej['fecha'] = entreno.fecha
                    ejercicios_tipo.append(ej)

        if len(ejercicios_tipo) < 2:
            return

        # Ordenar por fecha
        ejercicios_tipo.sort(key=lambda x: x['fecha'])

        # Calcular progresión
        primero = ejercicios_tipo[0]
        ultimo = ejercicios_tipo[-1]

        try:
            peso_inicial = float(primero.get('peso', 0)) if primero.get('peso') != 'PC' else 0
            peso_final = float(ultimo.get('peso', 0)) if ultimo.get('peso') != 'PC' else 0

            if peso_inicial > 0:
                progresion_peso = ((peso_final - peso_inicial) / peso_inicial) * 100
            else:
                progresion_peso = 0

            # Calcular volumen inicial y final
            vol_inicial = peso_inicial * int(primero.get('series', 1)) * int(primero.get('repeticiones', 1))
            vol_final = peso_final * int(ultimo.get('series', 1)) * int(ultimo.get('repeticiones', 1))

            if vol_inicial > 0:
                progresion_volumen = ((vol_final - vol_inicial) / vol_inicial) * 100
            else:
                progresion_volumen = 0

            # Crear o actualizar análisis
            analisis, created = AnalisisEjercicio.objects.update_or_create(
                cliente=cliente,
                nombre_ejercicio=nombre_ejercicio,
                fecha=fecha,
                defaults={
                    'peso_inicial': peso_inicial,
                    'peso_final': peso_final,
                    'progresion_peso': progresion_peso,
                    'volumen_inicial': vol_inicial,
                    'volumen_final': vol_final,
                    'progresion_volumen': progresion_volumen,
                    'sesiones_totales': len(ejercicios_tipo),
                    'peso_maximo': max(
                        [float(e.get('peso', 0)) if e.get('peso') != 'PC' else 0 for e in ejercicios_tipo])
                }
            )

            logger.info(f"Análisis {'creado' if created else 'actualizado'} para {nombre_ejercicio}")

        except (ValueError, TypeError) as e:
            logger.error(f"Error en cálculos de análisis para {nombre_ejercicio}: {e}")

    except Exception as e:
        logger.error(f"Error actualizando análisis de {nombre_ejercicio}: {e}")


def calcular_tendencia_progresion(cliente, nombre_ejercicio):
    """
    Calcula la tendencia de progresión para un ejercicio específico
    """
    try:
        # Obtener análisis recientes del ejercicio
        analisis_recientes = AnalisisEjercicio.objects.filter(
            cliente=cliente,
            nombre_ejercicio=nombre_ejercicio
        ).order_by('-fecha')[:10]

        if len(analisis_recientes) < 3:
            return

        # Calcular tendencia general
        progresiones = [a.progresion_peso for a in analisis_recientes if a.progresion_peso is not None]

        if progresiones:
            tendencia_general = sum(progresiones) / len(progresiones)

            # Determinar si está mejorando, estancado o empeorando
            if tendencia_general > 5:
                estado = 'mejorando'
            elif tendencia_general > -2:
                estado = 'estancado'
            else:
                estado = 'empeorando'

            # Calcular estadísticas adicionales
            peso_maximo = max([a.peso_maximo for a in analisis_recientes])
            sesiones_totales = sum([a.sesiones_totales for a in analisis_recientes])

            # Crear o actualizar tendencia
            fecha_inicio = analisis_recientes.last().fecha
            fecha_fin = analisis_recientes.first().fecha

            tendencia, created = TendenciaProgresion.objects.update_or_create(
                cliente=cliente,
                nombre_ejercicio=nombre_ejercicio,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                defaults={
                    'tendencia_general': tendencia_general,
                    'estado': estado,
                    'peso_maximo': peso_maximo,
                    'sesiones_totales': sesiones_totales,
                    'confianza': min(len(progresiones) * 10, 95)  # Más datos = más confianza
                }
            )

            logger.info(f"Tendencia {'creada' if created else 'actualizada'} para {nombre_ejercicio}: {estado}")

            # Generar predicciones si la tendencia es positiva
            if tendencia_general > 0:
                generar_predicciones_ejercicio(cliente, nombre_ejercicio, tendencia)

    except Exception as e:
        logger.error(f"Error calculando tendencia para {nombre_ejercicio}: {e}")


def generar_predicciones_ejercicio(cliente, nombre_ejercicio, tendencia):
    """
    Genera predicciones de rendimiento para un ejercicio específico
    """
    try:
        # Obtener último análisis
        ultimo_analisis = AnalisisEjercicio.objects.filter(
            cliente=cliente,
            nombre_ejercicio=nombre_ejercicio
        ).order_by('-fecha').first()

        if not ultimo_analisis:
            return

        # Calcular incremento promedio mensual
        incremento_mensual = (tendencia.tendencia_general / 100) * ultimo_analisis.peso_final / 4

        # Generar predicciones a 1, 3 y 6 meses
        for meses in [1, 3, 6]:
            fecha_prediccion = timezone.now().date() + timedelta(days=30 * meses)
            peso_estimado = ultimo_analisis.peso_final + (incremento_mensual * meses)

            # Calcular confianza (decrece con el tiempo)
            confianza = max(tendencia.confianza - (meses * 10), 30)

            # Crear predicción
            prediccion, created = PrediccionRendimiento.objects.update_or_create(
                cliente=cliente,
                nombre_ejercicio=nombre_ejercicio,
                fecha_prediccion=fecha_prediccion,
                defaults={
                    'peso_estimado': peso_estimado,
                    'confianza': confianza,
                    'metodo_calculo': 'tendencia_lineal',
                    'activa': True
                }
            )

            if created:
                logger.info(f"Predicción creada para {nombre_ejercicio} a {meses} meses: {peso_estimado}kg")

    except Exception as e:
        logger.error(f"Error generando predicciones para {nombre_ejercicio}: {e}")


# En analytics/signals.py

def generar_recomendaciones_automaticas(cliente):
    """
    Genera recomendaciones automáticas basadas en el análisis de datos
    """
    try:
        # Verificar si ya hay recomendaciones recientes
        recomendaciones_recientes = RecomendacionEntrenamiento.objects.filter(
            cliente=cliente,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        if recomendaciones_recientes > 5:
            return  # No generar más recomendaciones si ya hay muchas recientes

        # Analizar métricas recientes
        metricas_recientes = MetricaRendimiento.objects.filter(
            cliente=cliente,
            fecha__gte=timezone.now().date() - timedelta(days=30)
        ).order_by('-fecha')[:10]

        if not metricas_recientes:
            return

        # Análisis de consistencia
        entrenamientos_mes = len(metricas_recientes)
        if entrenamientos_mes < 8:  # Menos de 2 entrenamientos por semana
            RecomendacionEntrenamiento.objects.create(
                cliente=cliente,
                titulo="Aumentar Frecuencia de Entrenamiento",
                descripcion=f"Has entrenado solo {entrenamientos_mes} veces este mes. Intenta entrenar al menos 3-4 veces por semana para mejores resultados.",
                tipo="frecuencia",
                # --- CORRECCIÓN AQUÍ ---
                prioridad=1,  # Cambiado de "alta" a 1
                # -----------------------
                expires_at=timezone.now() + timedelta(days=30)
            )

        # Análisis de volumen
        volumenes = [m.volumen_total for m in metricas_recientes if m.volumen_total]
        if volumenes:
            volumen_promedio = sum(volumenes) / len(volumenes)
            volumen_reciente = sum(volumenes[:3]) / min(3, len(volumenes))

            if volumen_reciente < volumen_promedio * 0.8:  # Volumen ha bajado más del 20%
                RecomendacionEntrenamiento.objects.create(
                    cliente=cliente,
                    titulo="Volumen de Entrenamiento Bajo",
                    descripcion="Tu volumen de entrenamiento ha disminuido recientemente. Considera aumentar el peso o las repeticiones gradualmente.",
                    tipo="volumen",
                    # --- CORRECCIÓN AQUÍ ---
                    prioridad=2,  # Cambiado de "media" a 2
                    # -----------------------
                    expires_at=timezone.now() + timedelta(days=30)
                )

        # Análisis de ejercicios estancados
        ejercicios_estancados = TendenciaProgresion.objects.filter(
            cliente=cliente,
            tipo_tendencia='estable',  # Corregido: 'estado' -> 'tipo_tendencia' y 'estancado' -> 'estable'
            fecha_fin__gte=timezone.now().date() - timedelta(days=30)
        )

        if ejercicios_estancados.count() > 2:
            ejercicios_nombres = ", ".join([e.nombre_ejercicio for e in ejercicios_estancados[:3]])
            RecomendacionEntrenamiento.objects.create(
                cliente=cliente,
                titulo="Ejercicios Estancados Detectados",
                descripcion=f"Los ejercicios {ejercicios_nombres} muestran poco progreso. Considera cambiar la rutina o técnica.",
                tipo="progresion",
                # --- CORRECCIÓN AQUÍ ---
                prioridad=2,  # Cambiado de "media" a 2
                # -----------------------
                expires_at=timezone.now() + timedelta(days=30)
            )

        logger.info(f"Recomendaciones automáticas generadas para {cliente.nombre}")

    except Exception as e:
        logger.error(f"Error generando recomendaciones automáticas para {cliente.nombre}: {e}")


@receiver(post_delete, sender=EntrenoRealizado)
def limpiar_metricas_entreno_eliminado(sender, instance, **kwargs):
    """
    Limpia métricas cuando se elimina un entrenamiento
    """
    try:
        # Recalcular métricas del día
        entrenamientos_restantes = EntrenoRealizado.objects.filter(
            cliente=instance.cliente,
            fecha=instance.fecha
        )

        if not entrenamientos_restantes.exists():
            # Eliminar métricas del día si no quedan entrenamientos
            MetricaRendimiento.objects.filter(
                cliente=instance.cliente,
                fecha=instance.fecha
            ).delete()

            logger.info(f"Métricas eliminadas para {instance.cliente.nombre} - {instance.fecha}")
        else:
            # Recalcular métricas del día
            calcular_metricas_dia(instance.cliente, instance.fecha)

    except Exception as e:
        logger.error(f"Error limpiando métricas eliminadas: {e}")


# Función para recalcular todas las métricas (útil para migraciones o correcciones)
def recalcular_todas_las_metricas(cliente=None):
    """
    Recalcula todas las métricas para un cliente específico o todos los clientes
    """
    from clientes.models import Cliente

    if cliente:
        clientes = [cliente]
    else:
        clientes = Cliente.objects.all()

    for cliente in clientes:
        logger.info(f"Recalculando métricas para {cliente.nombre}")

        # Obtener todas las fechas de entrenamientos
        fechas_entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).values_list('fecha', flat=True).distinct()

        for fecha in fechas_entrenamientos:
            calcular_metricas_dia(cliente, fecha)

        # Recalcular análisis de ejercicios
        from entrenos.utils.utils import parsear_ejercicios

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

        ejercicios_unicos = set()
        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)
            for ej in ejercicios:
                ejercicios_unicos.add(ej['nombre'])

        for nombre_ejercicio in ejercicios_unicos:
            # Usar la fecha más reciente para el análisis
            fecha_reciente = entrenamientos.order_by('-fecha').first().fecha
            actualizar_analisis_ejercicio_especifico(cliente, nombre_ejercicio, fecha_reciente)
            calcular_tendencia_progresion(cliente, nombre_ejercicio)

        logger.info(f"Métricas recalculadas para {cliente.nombre}")

# Comando para ejecutar desde Django shell:
# from analytics.signals import recalcular_todas_las_metricas
# recalcular_todas_las_metricas()
