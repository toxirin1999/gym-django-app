from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import HyroxSession, HyroxReadinessLog
from .training_engine import HyroxTrainingEngine, HyroxLoadManager
from .services import calcular_rm_estimado

import logging
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# PUENTE SUEÑO → HYROX
# BitacoraDiaria con sueño < 6h o energía < 4 inyecta fatiga en próxima sesión
# ══════════════════════════════════════════════════════════════════════════════

@receiver(post_save, sender='clientes.BitacoraDiaria')
def sueno_to_hyrox_fatiga(sender, instance, created, update_fields=None, **kwargs):
    """
    Cuando se guarda una BitacoraDiaria detecta sueño insuficiente o baja energía
    e inyecta fatiga en la próxima HyroxSession planificada.
    """
    try:
        from hyrox.models import HyroxObjective
        from clientes.models import Cliente

        horas = float(instance.horas_sueno or 0)
        energia = instance.energia_subjetiva

        sueno_bajo = horas > 0 and horas < 6
        energia_baja = energia is not None and energia < 4

        if not sueno_bajo and not energia_baja:
            return

        # Obtener cliente: BitacoraDiaria puede tener FK a cliente o a usuario
        cliente = getattr(instance, 'cliente', None)
        if cliente is None:
            usuario = getattr(instance, 'usuario', None)
            if usuario:
                cliente = Cliente.objects.filter(user=usuario).first()
        if not cliente:
            return

        objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not objetivo:
            return

        proxima = HyroxSession.objects.filter(
            objective=objetivo,
            fecha__gte=instance.fecha,
            estado='planificado',
        ).order_by('fecha').first()

        if not proxima:
            return

        # Alta fatiga: sueño < 5h o energía muy baja (<3)
        if (horas > 0 and horas < 5) or (energia is not None and energia < 3):
            nueva_fatiga = 'Alta'
            motivo = (
                f"Sueño insuficiente ({horas:.1f}h)" if sueno_bajo
                else f"Energía muy baja ({energia}/10)"
            )
        else:
            nueva_fatiga = 'Media'
            motivo = (
                f"Sueño reducido ({horas:.1f}h)" if sueno_bajo
                else f"Energía baja ({energia}/10)"
            )

        # No degradar si ya hay fatiga Alta marcada por otra causa
        if proxima.muscle_fatigue_index == 'Alta' and nueva_fatiga == 'Media':
            return

        proxima.muscle_fatigue_index = nueva_fatiga
        proxima.fatiga_updated_at = timezone.now()
        proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])
        logger.info(
            f"[HYROX Sueño] Fatiga {nueva_fatiga} inyectada en sesión {proxima.id} "
            f"({proxima.fecha}): {motivo}"
        )

    except Exception as e:
        import traceback
        logger.error(f"[HYROX Sueño signal] Error: {e}")
        traceback.print_exc()


def _calcular_y_guardar_carga(instance):
    """
    Calcula TRIMP, zona cardíaca, CTL/ATL/TSB al completar una sesión.
    Todas las señales de carga objetiva pasan por aquí.
    """
    objetivo = instance.objective
    campos_actualizados = []

    # 1. TRIMP (requiere duración + FC media)
    trimp = HyroxLoadManager.calcular_trimp(
        instance.tiempo_total_minutos,
        instance.hr_media,
        objetivo,
    )
    if trimp is not None:
        instance.trimp = trimp
        campos_actualizados.append('trimp')

    # 2. Zona cardíaca predominante
    if instance.hr_media:
        zona = HyroxLoadManager.calcular_zona_predominante(instance.hr_media, objetivo)
        if zona:
            instance.zona_cardiaca_predominante = zona
            campos_actualizados.append('zona_cardiaca_predominante')

    # 3. CTL / ATL / TSB — sólo si tenemos TRIMP en alguna sesión
    carga = HyroxLoadManager.calcular_ctl_atl_tsb(objetivo)
    if carga['ctl'] > 0 or trimp:
        instance.ctl = carga['ctl']
        instance.atl = carga['atl']
        instance.tsb = carga['tsb']
        campos_actualizados += ['ctl', 'atl', 'tsb']

    if campos_actualizados:
        instance.save(update_fields=campos_actualizados)

    # 4. Validación RPE vs FC (no bloquea, solo loguea/genera alerta en notes)
    alerta_rpe_fc = HyroxLoadManager.validar_rpe_vs_fc(instance)
    if alerta_rpe_fc:
        logger.info(f"[HYROX FC/RPE] Sesión {instance.id}: {alerta_rpe_fc}")
        # Inyectar la alerta en la primera actividad de la sesión para que la vea el usuario
        primera_act = instance.activities.first()
        if primera_act:
            notas = primera_act.data_metricas.get('notas', '')
            if 'DISCORDANTE' not in notas and 'RPE alto vs FC' not in notas:
                primera_act.data_metricas['notas'] = (
                    f"{notas} | {alerta_rpe_fc}".strip(' |')
                )
                primera_act.save(update_fields=['data_metricas'])

    return carga


@receiver(post_save, sender=HyroxSession)
def autorregular_plan_futuro(sender, instance, created, update_fields=None, **kwargs):
    """
    Autorregulación avanzada + carga objetiva al completar una sesión.
    Orden de ejecución:
      1. Calcular TRIMP / zona / CTL-ATL-TSB
      2. Adaptar plan continuo (RPE, TSB)
      3. Actualizar Race Readiness
      4. Ajustar fatiga de la próxima sesión
    """
    # update_fields indica un save() parcial interno — evitar recursión infinita
    if update_fields is not None:
        return
    if instance.estado != 'completado' or not instance.rpe_global:
        return

    # ── 1. CARGA OBJETIVA ──────────────────────────────────────────────────
    carga = _calcular_y_guardar_carga(instance)
    tsb_actual = carga.get('tsb')

    # ── 2. ADAPTACIÓN CONTINUA ─────────────────────────────────────────────
    HyroxTrainingEngine.apply_continuous_adaptation(instance)

    # ── 3. RACE READINESS ──────────────────────────────────────────────────
    if instance.objective:
        current_score = instance.objective.get_race_readiness_score()
        HyroxReadinessLog.objects.update_or_create(
            objective=instance.objective,
            fecha=timezone.now().date(),
            defaults={'score': current_score}
        )

    # ── 4. FATIGA EN PRÓXIMA SESIÓN ────────────────────────────────────────
    proxima = HyroxSession.objects.filter(
        objective=instance.objective,
        fecha__gt=instance.fecha,
        estado='planificado'
    ).order_by('fecha').first()

    if proxima:
        # Umbral FC máxima personalizado por edad
        hr_umbral = HyroxLoadManager.get_fc_max(instance.objective)

        nueva_fatiga = None

        # A. TSB muy negativo → alta fatiga objetiva
        if tsb_actual is not None and tsb_actual < -20:
            nueva_fatiga = 'Alta'

        # B. Sobreesfuerzo por RPE o FC máxima
        elif instance.rpe_global >= 9 or (instance.hr_maxima and instance.hr_maxima > hr_umbral * 0.95):
            nueva_fatiga = 'Alta'

        # C. Zona cardíaca en Z4/Z5 con duración significativa → fatiga moderada-alta
        elif (instance.zona_cardiaca_predominante in ('Z4', 'Z5')
              and instance.tiempo_total_minutos
              and instance.tiempo_total_minutos >= 30):
            nueva_fatiga = 'Alta'

        # D. Progreso fluido: RPE bajo Y zona Z1/Z2
        elif (instance.rpe_global <= 5
              and instance.zona_cardiaca_predominante in ('Z1', 'Z2', None)):
            nueva_fatiga = 'Baja'

        if nueva_fatiga:
            proxima.muscle_fatigue_index = nueva_fatiga
            proxima.fatiga_updated_at    = timezone.now()
            proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])

    # ── 5. FC REPOSO ELEVADA ──────────────────────────────────────────────────
    # Si la FC de reposo de hoy supera la basal +7 lpm → posible enfermedad/fatiga
    # no detectada por RPE subjetivo → inyectar fatiga Media en próxima sesión.
    try:
        hoy_readiness = HyroxReadinessLog.objects.filter(
            objective=instance.objective,
            fecha=timezone.now().date(),
            fc_reposo__isnull=False,
        ).order_by('-fecha').first()

        if hoy_readiness and hoy_readiness.fc_reposo:
            fc_hoy = hoy_readiness.fc_reposo
            fc_basal = HyroxLoadManager.get_fc_reposo_basal(instance.objective, dias=14)
            if fc_hoy > fc_basal + 7:
                if not proxima:
                    proxima = HyroxSession.objects.filter(
                        objective=instance.objective,
                        fecha__gt=instance.fecha,
                        estado='planificado'
                    ).order_by('fecha').first()
                if proxima and proxima.muscle_fatigue_index != 'Alta':
                    proxima.muscle_fatigue_index = 'Media'
                    proxima.fatiga_updated_at = timezone.now()
                    proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])
                    logger.info(
                        f"[HYROX FC Reposo] FC hoy {fc_hoy} lpm vs basal {fc_basal} lpm "
                        f"(+{fc_hoy - fc_basal} lpm). Fatiga Media inyectada en sesión {proxima.id}."
                    )
    except Exception as e:
        logger.error(f"[HYROX FC Reposo check] Error: {e}")


# ==============================================================================
# SSoT (Single Source of Truth) - Integración con Gym/Liftin
# ==============================================================================
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from hyrox.models import HyroxObjective

@receiver(post_save, sender=EntrenoRealizado)
def sync_gym_impact_to_hyrox(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
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
                proxima.fatiga_updated_at = timezone.now()
                proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])
                
    except Exception as e:
        import traceback
        print(f"Error en el SSoT Signal Gym -> Hyrox: {e}")
        traceback.print_exc()

@receiver(post_save, sender=HyroxSession)
def sincronizar_hyrox_al_hub(sender, instance, created, raw=False, update_fields=None, **kwargs):
    """
    Cuando una HyroxSession pasa a 'completado', crea o actualiza su registro
    en el hub ActividadRealizada.
    """
    if raw or update_fields is not None or instance.estado != 'completado':
        return

    try:
        from entrenos.models import ActividadRealizada
        from clientes.models import Cliente

        cliente = instance.objective.cliente
        titulo = instance.titulo or f"Hyrox — {instance.fecha}"

        # Carga UA: RPE × duración
        carga_ua = None
        if instance.rpe_global and instance.tiempo_total_minutos:
            carga_ua = round(instance.rpe_global * instance.tiempo_total_minutos, 1)

        ActividadRealizada.objects.update_or_create(
            sesion_hyrox=instance,
            defaults={
                'cliente': cliente,
                'tipo': 'hyrox',
                'titulo': titulo,
                'fecha': instance.fecha,
                'duracion_minutos': instance.tiempo_total_minutos,
                'rpe_medio': instance.rpe_global,
                'carga_ua': carga_ua,
                'fuente': 'hyrox_engine',
            }
        )
    except Exception as e:
        import traceback
        print(f"❌ Hub ActividadRealizada error (HyroxSession {instance.id}): {e}")
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
            proxima.fatiga_updated_at = None
            proxima.save(update_fields=['muscle_fatigue_index', 'fatiga_updated_at'])
            
            # Recálculo de RM real no lo hacemos on-delete sincrónicamente para evitar 
            # latencia al usuario, pero se actualizará en su próximo Liftin sync automático.
            
    except Exception as e:
        import traceback
        print(f"Error revirtiendo SSoT Signal Gym -> Hyrox on delete: {e}")
        traceback.print_exc()
