# logros/services.py

import logging
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    PerfilGamificacion, Arquetipo, PruebaLegendaria, PruebaUsuario,
    HistorialPuntos, Quest, QuestUsuario, Notificacion
)
from entrenos.models import EntrenoRealizado, SerieRealizada

logger = logging.getLogger('gamificacion')


@receiver(post_save, sender=EntrenoRealizado)
def procesar_gamificacion_post_entreno(sender, instance, created, **kwargs):
    """Signal que se ejecuta automáticamente después de crear un EntrenoRealizado"""
    if created:
        logger.info(f"SIGNAL: Detectado nuevo entreno {instance.id}. Iniciando procesamiento.")
        CodiceService.procesar_entreno_completo(instance)


class CodiceService:
    """
    Servicio principal para gestionar la lógica del "Códice de las Leyendas".
    """

    @classmethod
    @transaction.atomic
    def procesar_entreno_completo(cls, entreno):
        """Procesa un entrenamiento completo y actualiza toda la gamificación"""
        logger.info(f"INICIO: Procesando entreno {entreno.id} para {entreno.cliente.nombre}")

        # Obtener o crear el perfil de gamificación
        perfil, created = PerfilGamificacion.objects.select_for_update().get_or_create(
            cliente=entreno.cliente,
            defaults={'nivel_actual': Arquetipo.objects.order_by('nivel').first()}
        )

        if created:
            logger.info(f"Creado nuevo perfil de gamificación para {entreno.cliente.nombre}")

        # 1. Actualizar estadísticas base y otorgar puntos por actividad
        cls._actualizar_estadisticas_base(perfil, entreno)

        # 2. Verificar y otorgar Pruebas Legendarias
        pruebas_completadas = cls._verificar_pruebas_legendarias(perfil, entreno)

        # 3. Verificar y actualizar Misiones (Quests)
        quests_completadas = cls._verificar_quests(perfil, entreno)

        # 4. Actualizar el nivel (Arquetipo) del usuario
        nivel_subido = perfil.actualizar_nivel()

        # 5. Crear notificaciones para logros importantes
        cls._crear_notificaciones(perfil, pruebas_completadas, quests_completadas, nivel_subido)

        perfil.save()
        logger.info(f"FIN: Procesamiento completo para entreno {entreno.id}. Puntos totales: {perfil.puntos_totales}")

        return {
            'pruebas_completadas': pruebas_completadas,
            'quests_completadas': quests_completadas,
            'nivel_subido': nivel_subido,
            'puntos_totales': perfil.puntos_totales
        }

    @classmethod
    def _calc_total_flexiones(cls, perfil, entreno, prueba):
        """
        Calcula el número total de repeticiones para ejercicios que son 'flexiones'.
        """
        # Buscamos en todas las series realizadas por el cliente que contengan "flexion" en el nombre.
        # Esto cubre "Flexiones", "Flexiones con lastre", etc.
        total_flexiones = SerieRealizada.objects.filter(
            entreno__cliente=perfil.cliente,
            ejercicio__nombre__icontains='flexion'
        ).aggregate(total_reps=Sum('repeticiones'))['total_reps'] or 0

        return total_flexiones

    @classmethod
    def _actualizar_estadisticas_base(cls, perfil, entreno):
        """Actualiza las estadísticas básicas del perfil y otorga puntos por actividad"""

        # Actualizar contador de entrenamientos
        perfil.entrenos_totales += 1

        # Calcular y actualizar racha
        cls._actualizar_racha(perfil, entreno)

        # Otorgar puntos base por completar el entrenamiento
        puntos_base = cls._calcular_puntos_base(entreno)
        perfil.puntos_totales += puntos_base

        # Registrar en el historial
        HistorialPuntos.objects.create(
            perfil=perfil,
            puntos=puntos_base,
            entreno=entreno,
            descripcion=f"Entrenamiento completado - {entreno.rutina.nombre if entreno.rutina else 'Rutina personalizada'}"
        )
        aware_datetime = timezone.make_aware(
            datetime.combine(entreno.fecha, datetime.min.time())
        )
        # Actualizar fecha del último entrenamiento
        perfil.fecha_ultimo_entreno = entreno.fecha

        logger.info(
            f"Estadísticas actualizadas: +{puntos_base} puntos, {perfil.entrenos_totales} entrenamientos totales")

    @classmethod
    def _actualizar_racha(cls, perfil, entreno):
        """Actualiza la racha de entrenamientos del usuario"""
        if perfil.fecha_ultimo_entreno:
            dias_diferencia = (entreno.fecha - perfil.fecha_ultimo_entreno.date()).days

            if dias_diferencia == 1:
                # Entrenamiento consecutivo
                perfil.racha_actual += 1
            elif dias_diferencia > 1:
                # Se rompió la racha
                perfil.racha_actual = 1
            # Si dias_diferencia == 0, es el mismo día, no cambia la racha
        else:
            # Primer entrenamiento
            perfil.racha_actual = 1

        # Actualizar racha máxima si es necesario
        if perfil.racha_actual > perfil.racha_maxima:
            perfil.racha_maxima = perfil.racha_actual

    @classmethod
    def _calcular_puntos_base(cls, entreno):
        """Calcula los puntos base por completar un entrenamiento"""
        puntos = 50  # Puntos base

        # Bonus por volumen
        if hasattr(entreno, 'volumen_total_kg') and entreno.volumen_total_kg:
            # 1 punto extra por cada 1000kg de volumen
            puntos += int(entreno.volumen_total_kg / 1000)

        # Bonus por duración
        if hasattr(entreno, 'duracion_minutos') and entreno.duracion_minutos:
            try:
                # Aseguramos que sea un número antes de operar
                duracion_num = int(entreno.duracion_minutos)
                puntos += min(int(duracion_num / 10), 30)
            except (ValueError, TypeError):
                # Si no se puede convertir, simplemente no se añaden puntos por duración
                logger.warning(
                    f"El campo 'duracion_minutos' del entreno {entreno.id} no es un número válido: {entreno.duracion_minutos}")
                pass
        return puntos

    @classmethod
    def _verificar_pruebas_legendarias(cls, perfil, entreno):
        """Verifica y otorga las Pruebas Legendarias disponibles para el usuario"""

        # Obtener todas las pruebas disponibles hasta el nivel actual del usuario
        nivel_actual = perfil.nivel_actual.nivel if perfil.nivel_actual else 1
        pruebas_disponibles = PruebaLegendaria.objects.filter(
            arquetipo__nivel__lte=nivel_actual
        ).exclude(
            pruebausuario__perfil=perfil,
            pruebausuario__completada=True
        )

        pruebas_completadas = []

        for prueba in pruebas_disponibles:
            # Calcular el progreso actual para esta prueba
            progreso = cls._calcular_progreso_prueba(perfil, prueba, entreno)

            # Obtener o crear el registro de progreso del usuario
            prueba_usuario, created = PruebaUsuario.objects.get_or_create(
                perfil=perfil,
                prueba=prueba,
                defaults={'progreso_actual': progreso}
            )

            # Actualizar el progreso
            prueba_usuario.progreso_actual = progreso

            # Verificar si se completó la prueba
            if progreso >= prueba.meta_valor and not prueba_usuario.completada:
                prueba_usuario.completada = True
                prueba_usuario.fecha_completada = timezone.now()

                # Otorgar puntos
                perfil.puntos_totales += prueba.puntos_recompensa

                # Registrar en el historial
                HistorialPuntos.objects.create(
                    perfil=perfil,
                    puntos=prueba.puntos_recompensa,
                    prueba_legendaria=prueba,
                    descripcion=f"Prueba Legendaria completada: {prueba.nombre}"
                )

                pruebas_completadas.append(prueba)
                logger.info(
                    f"¡PRUEBA COMPLETADA! {perfil.cliente.nombre} -> '{prueba.nombre}' (+{prueba.puntos_recompensa} puntos)")

            prueba_usuario.save()

        return pruebas_completadas

    @classmethod
    def _calcular_progreso_prueba(cls, perfil, prueba, entreno):
        """Calcula el progreso de una prueba específica usando la clave de cálculo"""

        calculadores = {
            # Pruebas básicas de iniciación
            'primer_entrenamiento': cls._calc_total_entrenos,
            'racha_7_dias': cls._calc_racha_actual,
            'cien_entrenos': cls._calc_total_entrenos,

            # Pruebas de volumen
            'volumen_maraton': cls._calc_volumen_total_kg,
            'volumen_semanal_alto': cls._calc_volumen_semanal,
            'volumen_mensual_titan': cls._calc_volumen_mensual,

            # Pruebas de fuerza (requieren cálculo de 1RM)
            'rm_100kg_banca': cls._calc_rm_press_banca,
            'rm_140kg_sentadilla': cls._calc_rm_sentadilla,
            'rm_180kg_peso_muerto': cls._calc_rm_peso_muerto,

            # Pruebas de consistencia
            'racha_30_dias': cls._calc_racha_actual,
            'entrenos_perfectos': cls._calc_entrenos_perfectos,

            # Pruebas épicas
            'grito_del_saiyan': cls._calc_records_semanales,
            'plus_ultra': cls._calc_superacion_prediccion,
            'flexiones_totales_meta_100': cls._calc_total_flexiones,  # <-- Añade esta línea
            'racha_dias_meta_3': cls._calc_racha_actual,  # <-- Y esta para el otro warning
        }

        clave = prueba.clave_calculo
        if clave in calculadores:
            return calculadores[clave](perfil, entreno, prueba)
        else:
            logger.warning(f"No se encontró calculador para la clave: {clave}")
            return 0

    # --------------------------------------------------------------------------
    # FUNCIONES DE CÁLCULO ESPECÍFICAS PARA CADA TIPO DE PRUEBA
    # --------------------------------------------------------------------------

    @classmethod
    def _calc_total_entrenos(cls, perfil, entreno, prueba):
        """Calcula el total de entrenamientos realizados"""
        return perfil.entrenos_totales

    @classmethod
    def _calc_racha_actual(cls, perfil, entreno, prueba):
        """Calcula la racha actual de entrenamientos"""
        return perfil.racha_actual

    @classmethod
    def _calc_volumen_total_kg(cls, perfil, entreno, prueba):
        """Calcula el volumen total acumulado en kg"""
        total_volumen = EntrenoRealizado.objects.filter(
            cliente=perfil.cliente
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0
        return float(total_volumen)

    @classmethod
    def _calc_volumen_semanal(cls, perfil, entreno, prueba):
        """Calcula el volumen de la semana actual"""
        inicio_semana = timezone.now().date() - timedelta(days=timezone.now().weekday())
        fin_semana = inicio_semana + timedelta(days=6)

        volumen_semanal = EntrenoRealizado.objects.filter(
            cliente=perfil.cliente,
            fecha__date__range=[inicio_semana, fin_semana]  # <-- CORREGIDO de 'fecha_realizacion__date__range'
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

        return float(volumen_semanal)

    @classmethod
    def _calc_volumen_mensual(cls, perfil, entreno, prueba):
        """Calcula el volumen del mes actual"""
        inicio_mes = timezone.now().replace(day=1).date()

        volumen_mensual = EntrenoRealizado.objects.filter(
            cliente=perfil.cliente,
            fecha__date__gte=inicio_mes  # <-- CORREGIDO de 'fecha_realizacion__date__gte'
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

        return float(volumen_mensual)

    @classmethod
    def _calc_rm_press_banca(cls, perfil, entreno, prueba):
        """Calcula el 1RM estimado en Press de Banca"""
        return cls._calcular_1rm_ejercicio(perfil.cliente, 'Press de Banca')

    @classmethod
    def _calc_rm_sentadilla(cls, perfil, entreno, prueba):
        """Calcula el 1RM estimado en Sentadilla"""
        return cls._calcular_1rm_ejercicio(perfil.cliente, 'Sentadilla')

    @classmethod
    def _calc_rm_peso_muerto(cls, perfil, entreno, prueba):
        """Calcula el 1RM estimado en Peso Muerto"""
        return cls._calcular_1rm_ejercicio(perfil.cliente, 'Peso Muerto')

    @classmethod
    def _calc_entrenos_perfectos(cls, perfil, entreno, prueba):
        """Calcula el número de entrenamientos perfectos (todas las series completadas)"""
        # Esta lógica requiere verificar que todas las series planificadas se completaron
        # Por simplicidad, asumimos que un entreno es perfecto si tiene volumen > 0
        entrenos_perfectos = EntrenoRealizado.objects.filter(
            cliente=perfil.cliente,
            volumen_total_kg__gt=0
        ).count()
        return entrenos_perfectos

    @classmethod
    def _calc_records_semanales(cls, perfil, entreno, prueba):
        """Calcula cuántos récords personales se han batido en la última semana"""
        # Esta es una lógica compleja que requeriría comparar con entrenamientos anteriores
        # Por ahora, devolvemos 0 como placeholder
        return 0

    @classmethod
    def _calc_superacion_prediccion(cls, perfil, entreno, prueba):
        """Verifica si se ha superado una predicción de IA"""
        # Esta lógica requiere integración con el sistema de predicciones
        # Por ahora, devolvemos 0 como placeholder
        return 0

    @classmethod
    def _calcular_1rm_ejercicio(cls, cliente, nombre_ejercicio):
        """Calcula el 1RM estimado para un ejercicio específico usando la fórmula de Brzycki"""
        try:
            # Buscar la serie más pesada reciente para este ejercicio
            serie_maxima = SerieRealizada.objects.filter(
                entreno__cliente=cliente,
                ejercicio__nombre__icontains=nombre_ejercicio,
                peso_kg__gt=0,
                repeticiones_realizadas__gt=0
            ).order_by('-peso_kg', '-repeticiones_realizadas').first()

            if not serie_maxima:
                return 0

            peso = serie_maxima.peso_kg
            reps = serie_maxima.repeticiones_realizadas

            # Fórmula de Brzycki: 1RM = peso / (1.0278 - 0.0278 * reps)
            if reps == 1:
                return float(peso)
            elif reps <= 10:
                rm_estimado = peso / (1.0278 - 0.0278 * reps)
                return float(rm_estimado)
            else:
                # Para más de 10 repeticiones, usar fórmula alternativa
                rm_estimado = peso * (1 + reps / 30)
                return float(rm_estimado)

        except Exception as e:
            logger.error(f"Error calculando 1RM para {nombre_ejercicio}: {e}")
            return 0

    @classmethod
    def _verificar_quests(cls, perfil, entreno):
        """Verifica y actualiza el progreso de las misiones (quests) activas"""
        # Esta lógica se mantiene similar a la original
        # Por ahora, devolvemos una lista vacía
        return []

    @classmethod
    def _crear_notificaciones(cls, perfil, pruebas_completadas, quests_completadas, nivel_subido):
        """Crea notificaciones para los logros obtenidos"""

        # Notificación por pruebas legendarias completadas
        for prueba in pruebas_completadas:
            Notificacion.objects.create(
                perfil=perfil,
                tipo='logro',
                titulo=f"¡Prueba Legendaria Completada!",
                mensaje=f"Has completado la prueba '{prueba.nombre}' y ganado {prueba.puntos_recompensa} puntos."
            )

        # Notificación por subida de nivel
        if nivel_subido and perfil.nivel_actual:
            Notificacion.objects.create(
                perfil=perfil,
                tipo='nivel',
                titulo=f"¡Ascensión Épica!",
                mensaje=f"Has alcanzado el nivel de {perfil.nivel_actual.titulo_arquetipo}. {perfil.nivel_actual.filosofia}"
            )


# --------------------------------------------------------------------------
# SERVICIO DE ANÁLISIS (MANTIENE LA FUNCIONALIDAD ORIGINAL)
# --------------------------------------------------------------------------

class AnalisisGamificacionService:
    """Servicio para generar análisis y reportes de gamificación"""

    @classmethod
    def analizar_cliente(cls, cliente, dias=30):
        """Genera un análisis completo de gamificación para un cliente"""
        try:
            perfil = PerfilGamificacion.objects.get(cliente=cliente)
        except PerfilGamificacion.DoesNotExist:
            return cls._analisis_vacio()

        fecha_inicio = timezone.now() - timedelta(days=dias)

        # Análisis de puntos
        historial_reciente = HistorialPuntos.objects.filter(
            perfil=perfil,
            fecha__gte=fecha_inicio
        ).order_by('fecha')

        puntos_por_dia = {}
        for registro in historial_reciente:
            dia = registro.fecha.date()
            puntos_por_dia[dia] = puntos_por_dia.get(dia, 0) + registro.puntos

        # Análisis de pruebas
        pruebas_completadas = PruebaUsuario.objects.filter(
            perfil=perfil,
            completada=True,
            fecha_completada__gte=fecha_inicio
        ).count()

        return {
            'perfil': perfil,
            'puntos_periodo': sum(puntos_por_dia.values()),
            'puntos_por_dia': puntos_por_dia,
            'pruebas_completadas_periodo': pruebas_completadas,
            'racha_actual': perfil.racha_actual,
            'nivel_actual': perfil.nivel_actual,
            'progreso_siguiente_nivel': cls._calcular_progreso_siguiente_nivel(perfil),
        }

    @classmethod
    def _analisis_vacio(cls):
        """Retorna un análisis vacío para clientes sin perfil de gamificación"""
        return {
            'perfil': None,
            'puntos_periodo': 0,
            'puntos_por_dia': {},
            'pruebas_completadas_periodo': 0,
            'racha_actual': 0,
            'nivel_actual': None,
            'progreso_siguiente_nivel': 0,
        }

    @classmethod
    def _calcular_progreso_siguiente_nivel(cls, perfil):
        """Calcula el progreso hacia el siguiente nivel"""
        if not perfil.nivel_actual:
            return 0

        siguiente_arquetipo = Arquetipo.objects.filter(
            nivel__gt=perfil.nivel_actual.nivel
        ).order_by('nivel').first()

        if not siguiente_arquetipo:
            return 100  # Ya está en el nivel máximo

        puntos_actuales = perfil.puntos_totales
        puntos_nivel_actual = perfil.nivel_actual.puntos_requeridos
        puntos_siguiente_nivel = siguiente_arquetipo.puntos_requeridos

        progreso = ((puntos_actuales - puntos_nivel_actual) /
                    (puntos_siguiente_nivel - puntos_nivel_actual)) * 100

        return min(max(progreso, 0), 100)
