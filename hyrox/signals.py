from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import HyroxSession, HyroxReadinessLog
from .training_engine import HyroxTrainingEngine
from .services import calcular_rm_estimado

@receiver(post_save, sender=HyroxSession)
def autorregular_plan_futuro(sender, instance, created, **kwargs):
    """
    Paso 3: Lógica de Autorregulación Avanzada y Actualización de Dashboard en tiempo real.
    Ajusta el volumen y el feedback de la próxima sesión según el esfuerzo de hoy.
    """
    # Solo actuamos cuando una sesión pasa a estado 'completado'
    if instance.estado == 'completado' and instance.rpe_global:
        
        # Opcional: Ejecutar motor avanzado (si aplica x0.8 o x1.1 a métricas internas)
        HyroxTrainingEngine.apply_continuous_adaptation(instance)

        # 1. ACTUALIZAR RACE READINESS SCORE (Para que la gráfica suba instantáneamente)
        if instance.objective:
            current_score = instance.objective.get_race_readiness_score()
            HyroxReadinessLog.objects.update_or_create(
                objective=instance.objective,
                fecha=timezone.now().date(),
                defaults={'score': current_score}
            )

        # 2. AUTORREGULACIÓN DE LA PRÓXIMA SESIÓN
        proxima = HyroxSession.objects.filter(
            objective=instance.objective, 
            fecha__gt=instance.fecha, 
            estado='planificado'
        ).order_by('fecha').first()

        if proxima:
            # Calcular umbral HR máxima basado en la edad del cliente (fórmula 220 - edad)
            hr_umbral = 185  # fallback genérico
            try:
                from django.utils import timezone as tz
                import datetime
                fn = instance.objective.cliente.fecha_nacimiento
                if fn:
                    edad = (tz.now().date() - fn).days // 365
                    hr_umbral = 220 - edad
            except Exception:
                pass

            # CASO A: SOBREESFUERZO (RPE >= 9 o HR Max > umbral por edad)
            if instance.rpe_global >= 9 or (instance.hr_maxima and instance.hr_maxima > hr_umbral):
                proxima.feedback_ia = (
                    "David, hemos detectado un nivel de fatiga alto. He reducido la carga de esta sesión "
                    "para priorizar la recuperación estratégica y llegar fuerte al 19 de abril."
                )
                proxima.muscle_fatigue_index = 'Alta'
                proxima.save(update_fields=['feedback_ia', 'muscle_fatigue_index'])
            
            # CASO B: PROGRESO FLUIDO (RPE <= 5)
            elif instance.rpe_global <= 5:
                proxima.feedback_ia = (
                    "Tu última sesión fue muy eficiente. Hoy subiremos un poco la intensidad "
                    "para seguir cerrando la brecha de fuerza en tus cuádriceps."
                )
                proxima.muscle_fatigue_index = 'Baja'
                proxima.save(update_fields=['feedback_ia', 'muscle_fatigue_index'])


# ==============================================================================
# SSoT (Single Source of Truth) - Integración con Gym/Liftin
# ==============================================================================
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from hyrox.models import HyroxObjective

@receiver(post_save, sender=EntrenoRealizado)
def sync_gym_impact_to_hyrox(sender, instance, created, **kwargs):
    """
    Signal transversal que se dispara cuando el usuario guarda un entrenamiento
    en el módulo general (Gym/Liftin).
    
    Responsabilidades:
    1. Sincronizar RMs (peso máximo) hacia el objetivo de Hyrox (Sentadilla/Peso Muerto).
    2. Inyectar fatiga (muscle_fatigue_index) en la próxima sesión de Hyrox si hay volumen pesado de piernas.
    """
    try:
        objetivo = HyroxObjective.objects.filter(cliente=instance.cliente, estado='activo').first()
        if not objetivo:
            return # Si no está entrenando para Hyrox, salimos

        # Usar el mapeador central (El puente de idiomas)
        from entrenos.services.services import MAPEO_EJERCICIOS_A_PRINCIPAL
        
        hubo_actualizacion_rm = False
        volumen_pierna_kg = 0

        # Para los ejercicios, revisamos EjercicioRealizado y EjercicioLiftinDetallado
        ejercicios_list = list(instance.ejercicios_realizados.filter(completado=True))
        if hasattr(instance, 'ejercicios_liftin_detallados'):
            ejercicios_list.extend(list(instance.ejercicios_liftin_detallados.filter(completado=True)))

        for ej in ejercicios_list:
            # Normalizar nombre
            nombre_raw = getattr(ej, 'nombre_ejercicio', getattr(ej, 'nombre', ''))
            nombre_norm = nombre_raw.lower().strip()
            
            # 1. TRADUCCIÓN: ¿Qué ejercicio es realmente?
            slug = MAPEO_EJERCICIOS_A_PRINCIPAL.get(nombre_norm)
            
            peso_lift = float(getattr(ej, 'peso_kg', 0) or 0)
            reps_lift = int(getattr(ej, 'repeticiones', getattr(ej, 'series_realizadas', 1)) or 1)
            
            # --- Lógica de RM ---
            if peso_lift > 0 and slug in ['Sentadilla', 'Peso Muerto']:
                rm_estimado = calcular_rm_estimado(peso_lift, reps_lift)
                
                if slug == 'Sentadilla':
                    if not objetivo.rm_sentadilla or rm_estimado > objetivo.rm_sentadilla:
                        objetivo.rm_sentadilla = round(rm_estimado, 1)
                        hubo_actualizacion_rm = True
                
                elif slug == 'Peso Muerto':
                    if not objetivo.rm_peso_muerto or rm_estimado > objetivo.rm_peso_muerto:
                        objetivo.rm_peso_muerto = round(rm_estimado, 1)
                        hubo_actualizacion_rm = True

            # --- Lógica de Fatiga / Volumen de Piernas ---
            # Si el slug es Sentadilla, o si el grupo muscular en BD es Cuádriceps/Isquios
            grupo_bd = getattr(ej, 'grupo_muscular', None)
            from entrenos.services.services import MAPEO_MUSCULAR
            grupo_calc = MAPEO_MUSCULAR.get(nombre_norm, grupo_bd)
            
            if slug == 'Sentadilla' or slug == 'Peso Muerto' or (grupo_calc in ['Cuádriceps', 'Isquios']):
                try:
                    vol_ej = float(getattr(ej, 'volumen_ejercicio', peso_lift * reps_lift * int(getattr(ej, 'series', 1) or 1)))
                    volumen_pierna_kg += vol_ej
                except:
                    pass

        if hubo_actualizacion_rm:
            objetivo.save(update_fields=['rm_sentadilla', 'rm_peso_muerto'])

        # --- REFINAMIENTO DEL TRIGGER Y FÚTBOL ---
        nombres_ejercicios = [getattr(e, 'nombre_ejercicio', getattr(e, 'nombre', '')).lower() for e in ejercicios_list]
        es_futbol = any('futbol' in n or 'fútbol' in n for n in nombres_ejercicios)
        
        # Obtener RPE global de la sesión si existe
        rpe_medio = 0
        if hasattr(instance, 'sesion_entrenamiento') and instance.sesion_entrenamiento:
            rpe_medio = instance.sesion_entrenamiento.rpe_medio or 0
        elif hasattr(instance, 'esfuerzo_percibido'):
            rpe_medio = instance.esfuerzo_percibido or 0

        # Lógica de Inyección de Fatiga
        fatiga_inyectada = None
        motivo_fatiga = ""

        if es_futbol:
            if rpe_medio >= 9:
                fatiga_inyectada = 'Alta'
                motivo_fatiga = f"El fútbol de ayer fue de máxima exigencia (RPE {rpe_medio}). Priorizamos descanso total o movilidad para proteger articulaciones."
            elif rpe_medio >= 8:
                fatiga_inyectada = 'Alta'
                motivo_fatiga = f"Partido intenso de fútbol ayer (RPE {rpe_medio}). Tus cuádriceps están comprometidos, hoy evitamos Sled y Squats pesados."
        else:
            if volumen_pierna_kg > 2500 or rpe_medio >= 8.5:
                fatiga_inyectada = 'Alta'
                motivo_fatiga = (
                    "El coach ha detectado un impacto estructural tras tu sesión pesada "
                    f"de piernas ayer ({int(volumen_pierna_kg)}kg movidos, RPE {rpe_medio}). "
                    "Hoy adaptaremos los ritmos."
                )

        if fatiga_inyectada:
            proxima = HyroxSession.objects.filter(
                objective=objetivo, 
                fecha__gte=instance.fecha, 
                estado='planificado'
            ).order_by('fecha').first()
            
            if proxima:
                proxima.muscle_fatigue_index = fatiga_inyectada
                proxima.feedback_ia = motivo_fatiga
                proxima.fatiga_updated_at = timezone.now()
                proxima.save(update_fields=['muscle_fatigue_index', 'feedback_ia', 'fatiga_updated_at'])
                
    except Exception as e:
        import traceback
        print(f"Error en el SSoT Signal Gym -> Hyrox: {e}")
        traceback.print_exc()

from django.db.models.signals import post_delete

@receiver(post_delete, sender=EntrenoRealizado)
def revert_gym_impact_on_hyrox(sender, instance, **kwargs):
    """
    Signal que se dispara si el usuario borra una sesión del módulo Gym.
    Revertirá preventivamente la fatiga 'Alta' inyectada en las próximas 48 horas 
    de HyroxSession, y la idea es volver al estado anterior (o 'Baja').
    *La regeneración de RMs requeriría un recálculo asíncrono pesado, pero podemos
     priorizar la integridad de la fatiga para evitar Coach feedback erróneos.*
    """
    try:
        objetivo = HyroxObjective.objects.filter(cliente=instance.cliente, estado='activo').first()
        if not objetivo:
            return

        # Buscar la próxima sesión que haya sido afectada
        proxima = HyroxSession.objects.filter(
            objective=objetivo, 
            fecha__gte=instance.fecha, 
            estado='planificado'
        ).order_by('fecha').first()
        
        if proxima and proxima.muscle_fatigue_index == 'Alta' and proxima.fatiga_updated_at:
            # Revertimos a Baja por default si el usuario elimina la sesión pesada
            proxima.muscle_fatigue_index = 'Baja'
            proxima.feedback_ia = None
            proxima.fatiga_updated_at = None
            proxima.save(update_fields=['muscle_fatigue_index', 'feedback_ia', 'fatiga_updated_at'])
            
            # Recálculo de RM real no lo hacemos on-delete sincrónicamente para evitar 
            # latencia al usuario, pero se actualizará en su próximo Liftin sync automático.
            
    except Exception as e:
        import traceback
        print(f"Error revirtiendo SSoT Signal Gym -> Hyrox on delete: {e}")
        traceback.print_exc()
