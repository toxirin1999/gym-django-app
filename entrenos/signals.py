import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado, ActividadRealizada
from entrenos.utils.utils import parse_reps_and_series
from django.utils.timezone import make_aware
from datetime import datetime

logger = logging.getLogger(__name__)

# Keywords que mapean un ejercicio de gym a un RM de HyroxObjective
_SENTADILLA_KW = ('sentadilla', 'squat', 'goblet', 'hack squat', 'front squat')
_PESO_MUERTO_KW = ('peso muerto', 'deadlift', 'rdl', 'romanian', 'sumo dead')


@receiver(post_save, sender=EntrenoRealizado)
def crear_ejercicios_detallados(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.notas_liftin:
        return

    ejercicios = parsear_ejercicios(instance.notas_liftin)
    for orden, ej in enumerate(ejercicios):
        try:
            nombre = ej.get('nombre', '').strip()
            peso = ej.get('peso', 0)
            if peso == 'PC':
                peso = 0
            peso = float(str(peso).replace(',', '.'))

            rep_str = str(ej.get('repeticiones', '1x1')).lower().replace('×', 'x').replace(' ', '')
            partes = rep_str.split('x')
            rep_min = int(partes[1]) if len(partes) > 1 else 1
            series = int(partes[0]) if len(partes) > 0 else 1

            EjercicioLiftinDetallado.objects.get_or_create(
                entreno=instance,
                nombre_ejercicio=nombre,
                defaults={
                    'peso_kg': peso,
                    'repeticiones_min': rep_min,
                    'repeticiones_max': rep_min,
                    'series_realizadas': series,
                    'fecha_creacion': make_aware(datetime.now()),
                    'orden_ejercicio': orden,
                    'completado': True
                }
            )
        except Exception as e:
            print(f"❌ Error al crear ejercicio en entreno {instance.id}: {e}")


@receiver(post_save, sender=EntrenoRealizado)
def sincronizar_hub_actividad(sender, instance, created, raw=False, **kwargs):
    """
    Cada vez que se guarda un EntrenoRealizado, asegura que existe
    un registro correspondiente en ActividadRealizada (hub central).
    Actualiza métricas si el entreno ya existía.
    """
    if raw:
        return

    # Calcular RPE medio desde ejercicios realizados
    rpe_medio = None
    try:
        rpes = [
            ej.rpe for ej in instance.ejercicios_realizados.all()
            if ej.rpe is not None
        ]
        if rpes:
            rpe_medio = round(sum(rpes) / len(rpes), 1)
    except Exception:
        pass

    # Título: nombre de la rutina
    titulo = ''
    try:
        titulo = instance.nombre_rutina_liftin or (instance.rutina.nombre if instance.rutina else '')
    except Exception:
        pass

    # Duración: si no está en el entreno, buscar en sesion_detalle
    _dur_raw = instance.duracion_minutos
    try:
        duracion = int(_dur_raw) if _dur_raw is not None else None
    except (TypeError, ValueError):
        duracion = None
    if not duracion:
        try:
            duracion = instance.sesion_detalle.duracion_minutos or None
        except Exception:
            pass
    # Parsear tiempo_total_formateado como último recurso (ej: "1:10:23" → 70 min)
    if not duracion and instance.tiempo_total_formateado:
        try:
            partes = instance.tiempo_total_formateado.replace('h', ':').replace('m', '').split(':')
            partes = [p.strip() for p in partes if p.strip()]
            if len(partes) == 3:
                duracion = int(partes[0]) * 60 + int(partes[1])
            elif len(partes) == 2:
                duracion = int(partes[0]) * 60 + int(partes[1])
            elif len(partes) == 1:
                duracion = int(partes[0])
        except Exception:
            pass

    # Propagar duración a EntrenoRealizado si se recuperó de otra fuente
    if duracion and not instance.duracion_minutos:
        try:
            EntrenoRealizado.objects.filter(pk=instance.pk).update(duracion_minutos=duracion)
        except Exception:
            pass

    # RPE: si no viene de ejercicios, intentar desde sesion_detalle
    if not rpe_medio:
        try:
            rpe_medio = instance.sesion_detalle.rpe_medio or None
        except Exception:
            pass

    # Carga UA: sRPE × minutos. Si no hay RPE manual, estimar desde FC.
    hr_media = instance.frecuencia_cardiaca_promedio
    hr_maxima = instance.frecuencia_cardiaca_maxima
    carga_ua = None
    dur_valida = duracion is not None and duracion > 0
    rpe_efectivo = rpe_medio
    if not rpe_efectivo and hr_media and dur_valida:
        try:
            from hyrox.training_engine import HyroxLoadManager
            from hyrox.models import HyroxObjective
            objetivo = HyroxObjective.objects.filter(cliente=instance.cliente, estado='activo').first()
            rpe_efectivo = HyroxLoadManager.estimar_rpe_desde_fc(hr_media, objetivo)
        except Exception:
            pass
    if rpe_efectivo and dur_valida:
        carga_ua = round(float(rpe_efectivo) * duracion, 1)
    elif dur_valida:
        carga_ua = round(6.5 * duracion, 1)

    from datetime import date as _date
    hoy = _date.today()

    defaults = {
        'cliente': instance.cliente,
        'tipo': 'gym',
        'titulo': titulo,
        'fecha': instance.fecha,
        # fecha_realizado: solo se fija en la primera creación (hoy).
        # En updates posteriores no se sobreescribe para preservar la fecha real.
        'hora_inicio': instance.hora_inicio,
        'duracion_minutos': duracion,
        'volumen_kg': instance.volumen_total_kg,
        'calorias': instance.calorias_quemadas,
        'rpe_medio': rpe_medio,
        'carga_ua': carga_ua,
        'hr_media': hr_media,
        'hr_maxima': hr_maxima,
        'fuente': 'liftin' if instance.fuente_datos == 'liftin' else 'manual',
    }

    try:
        obj, created = ActividadRealizada.objects.update_or_create(
            entreno_gym=instance,
            defaults=defaults,
        )
        # Fijar fecha_realizado solo al crear (preservar si ya existía)
        if created and not obj.fecha_realizado:
            obj.fecha_realizado = hoy
            obj.save(update_fields=['fecha_realizado'])

        # Invalidar caché ACWR para que el dashboard refleje el nuevo entreno
        from django.core.cache import cache as _cache
        _cache.delete(f'dashboard_acwr_unificado_{instance.cliente_id}')
        _cache.delete(f'dashboard_gamif_{instance.cliente_id}')
        _cache.delete(f'dashboard_stats_{instance.cliente_id}')
    except Exception as e:
        print(f"❌ Hub ActividadRealizada error (entreno {instance.id}): {e}")

    # JOI post-entreno se genera en guardar_entrenamiento_activo (views.py) para
    # poder incluir rpe_final, que se calcula DESPUÉS de crear los ejercicios.


@receiver(post_save, sender=EntrenoRealizado)
def detectar_molestia_recurrente(sender, instance, created, raw=False, **kwargs):
    """Si la misma zona corporal aparece con molestia en 3+ sesiones recientes → GymDecisionLog."""
    if raw:
        return
    try:
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from datetime import timedelta, date

        zonas_esta_sesion = set(
            instance.ejercicios_realizados.filter(
                molestia_reportada=True
            ).exclude(molestia_zona='').values_list('molestia_zona', flat=True)
        )
        if not zonas_esta_sesion:
            return

        ventana = date.today() - timedelta(days=21)
        for zona in zonas_esta_sesion:
            count = EjercicioRealizado.objects.filter(
                entreno__cliente=instance.cliente,
                molestia_reportada=True,
                molestia_zona=zona,
                entreno__fecha__gte=ventana,
            ).count()
            if count >= 3:
                clave_zona = f'ZONA:{zona}'
                ya_existe = GymDecisionLog.objects.filter(
                    cliente=instance.cliente,
                    ejercicio=clave_zona,
                    accion='cambiar_variante',
                    fecha_creacion__date__gte=ventana,
                ).exists()
                if not ya_existe:
                    GymDecisionLog.objects.create(
                        cliente=instance.cliente,
                        ejercicio=clave_zona,
                        accion='cambiar_variante',
                        motivo=f'Molestia recurrente en {zona} (≥3 sesiones en 21 días). Reducir o sustituir movimientos que carguen esta zona la próxima semana.',
                        confianza='alta',
                    )
    except Exception as e:
        print(f"⚠️ Molestia recurrente check error (entreno {instance.id}): {e}")


@receiver(post_save, sender=EntrenoRealizado)
def detectar_estancamiento(sender, instance, created, raw=False, **kwargs):
    """
    Para cada ejercicio de la sesión, comprueba si las últimas 3 apariciones
    tienen el mismo peso y reps (sin tope de máquina). Si es así → GymDecisionLog.
    """
    if raw:
        return
    try:
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from datetime import timedelta

        ejercicios_sesion = instance.ejercicios_realizados.filter(
            completado=True
        ).values_list('nombre_ejercicio', flat=True).distinct()

        for nombre in ejercicios_sesion:
            ultimas = EjercicioRealizado.objects.filter(
                entreno__cliente=instance.cliente,
                nombre_ejercicio__iexact=nombre,
                completado=True,
                es_tope_maquina=False,
                peso_kg__gt=0,
            ).order_by('-entreno__fecha')[:3]

            if len(ultimas) < 3:
                continue

            pesos = [float(e.peso_kg or 0) for e in ultimas]
            reps  = [e.repeticiones or 0 for e in ultimas]

            # Tolerancia: ±0.5 kg en peso, exacto en reps
            mismo_peso = max(pesos) - min(pesos) <= 0.5
            mismas_reps = len(set(reps)) == 1

            if not (mismo_peso and mismas_reps):
                continue

            # No duplicar si ya hay un log reciente (últimos 14 días)
            ventana = instance.fecha - timedelta(days=14)
            ya_existe = GymDecisionLog.objects.filter(
                cliente=instance.cliente,
                ejercicio__iexact=nombre,
                accion='cambiar_variante',
                fecha_creacion__date__gte=ventana,
            ).exists()
            if ya_existe:
                continue

            GymDecisionLog.objects.create(
                cliente=instance.cliente,
                ejercicio=nombre,
                accion='cambiar_variante',
                motivo=(
                    f'Sin progresión en 3 sesiones consecutivas '
                    f'({pesos[0]} kg × {reps[0]} reps). '
                    f'Cambiar estímulo: variante, rango de reps o tempo.'
                ),
                confianza='alta',
                peso_anterior=pesos[0],
                reps_anteriores=reps[0],
            )

    except Exception as e:
        print(f"⚠️ Estancamiento check error (entreno {instance.id}): {e}")


@receiver(post_save, sender=EntrenoRealizado)
def actualizar_decision_log(sender, instance, created, raw=False, **kwargs):
    """Evalúa decisiones previas y genera nuevas al guardar un EntrenoRealizado."""
    if raw:
        return
    try:
        from entrenos.services.decision_log_service import (
            evaluar_decisiones_para_entreno,
            generar_decisiones_para_entreno,
        )
        evaluar_decisiones_para_entreno(instance)
        generar_decisiones_para_entreno(instance)
    except Exception as e:
        print(f"⚠️ Decision log error (entreno {instance.id}): {e}")


@receiver(post_save, sender='entrenos.RecordPersonal')
def joi_mensaje_pr(sender, instance, created, raw=False, **kwargs):
    """Genera mensaje JOI cuando se rompe un récord personal."""
    if raw or not created or instance.superado:
        return
    try:
        from django.core.cache import cache as _cache
        import datetime as _dt
        _fecha = getattr(instance, 'fecha', None) or _dt.date.today()
        _lock = (
            f'joi_pr_lock_{instance.cliente_id}'
            f'_{instance.ejercicio_nombre}'
            f'_{_fecha}'
            f'_{instance.valor}'
        )
        if _cache.get(_lock):
            return
        _cache.set(_lock, True, 86400)  # 24h — un PR concreto solo genera 1 mensaje al día

        from joi.services import generar_mensaje_joi
        generar_mensaje_joi(
            cliente=instance.cliente,
            trigger='pr_roto',
            datos_extra={
                'ejercicio': instance.ejercicio_nombre,
                'valor': str(instance.valor),
                'tipo_record': instance.tipo_record,
            },
        )
    except Exception:
        pass


@receiver(post_save, sender='entrenos.RecordPersonal')  # lazy string resuelto por Django apps registry
def sincronizar_rm_con_hyrox(sender, instance, created, raw=False, **kwargs):
    """
    Cuando se establece un nuevo récord oficial de peso máximo,
    actualiza rm_sentadilla / rm_peso_muerto en el HyroxObjective activo.
    Fuente: PR oficial (exacto). Delegado a hyrox_bridge.sync_rm_to_hyrox.
    """
    if raw or instance.superado:
        return
    if instance.tipo_record not in ('peso_maximo', 'one_rep_max'):
        return

    try:
        from hyrox.models import HyroxObjective
        from entrenos.services.hyrox_bridge import campo_rm_para_ejercicio, sync_rm_to_hyrox

        campo = campo_rm_para_ejercicio(instance.ejercicio_nombre)
        if not campo:
            return

        objetivo = HyroxObjective.objects.filter(
            cliente=instance.cliente, estado='activo',
        ).first()
        if not objetivo:
            return

        sync_rm_to_hyrox(objetivo, campo, float(instance.valor))
    except Exception as e:
        logger.error('sincronizar_rm_con_hyrox error: %s', e)


# ── JOI — intervención del plan ──────────────────────────────────────────────
from entrenos.models import GymDecisionLog as _GymDecisionLog

# Acciones que representan una decisión activa del sistema (el plan aprendió algo).
# 'subir_peso'/'subir_reps' se omiten — son progresión normal, no intervención.
_ACCIONES_JOI = {'cambiar_variante', 'bajar_peso', 'deload', 'mantener'}

@receiver(post_save, sender=_GymDecisionLog)
def joi_decision_plan(sender, instance, created, **kwargs):
    """
    Cuando el plan toma una decisión de intervención activa, JOI la verbaliza.
    Lock de 30 min por usuario: evita spam si la misma sesión genera varios logs.
    """
    if not created:
        return
    if instance.accion not in _ACCIONES_JOI:
        return
    # 'mantener' solo interesa cuando la causa es técnica o molestia, no rutina
    if instance.accion == 'mantener':
        motivo_lower = (instance.motivo or '').lower()
        if not any(k in motivo_lower for k in ('técnica', 'tecnica', 'molestia', 'dolor', 'comprometida')):
            return

    try:
        from django.core.cache import cache
        from joi.services import generar_mensaje_joi

        cliente = instance.cliente
        lock_key = f'joi_decision_lock_{cliente.pk}'
        if cache.get(lock_key):
            return
        cache.set(lock_key, True, 1800)  # 30 min

        generar_mensaje_joi(cliente, 'decision_plan', {
            'accion':        instance.accion,
            'ejercicio':     instance.ejercicio,
            'motivo':        instance.motivo or '',
            'peso_anterior': instance.peso_anterior,
            'rpe_anterior':  instance.rpe_anterior,
            'valor_cambio':  instance.valor_cambio,
            'confianza':     instance.confianza,
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'[JOI decision_plan] {e}')


# ── Phase 23A — JOI verbaliza preferencia aprendida ──────────────────────────
from entrenos.models import PreferenciaPlanAprendida as _PreferenciaPlanAprendida

@receiver(post_save, sender=_PreferenciaPlanAprendida)
def joi_preferencia_aprendida(sender, instance, created, **kwargs):
    """
    Cuando el plan consolida una preferencia nueva (o reactiva una suspendida),
    JOI la verbaliza. Cada preferencia por tipo se genera una sola vez.
    """
    if instance.estado != _PreferenciaPlanAprendida.ESTADO_ACTIVA:
        return
    # Solo al crear (primera vez) o al reactivar desde suspendida
    if not created:
        # update_fields check: only fire if 'estado' was explicitly saved
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'estado' not in update_fields:
            return

    try:
        from joi.services import generar_mensaje_joi
        from django.core.cache import cache

        cliente = instance.cliente
        # Lock per (cliente, tipo) — one message per preference type
        lock_key = f'joi_preferencia_lock_{cliente.pk}_{instance.tipo}'
        if cache.get(lock_key):
            return
        cache.set(lock_key, True, 86400)  # 24h — one message per activation

        generar_mensaje_joi(cliente, 'preferencia_aprendida', {
            'tipo_preferencia': instance.tipo,
            'descripcion':      instance.descripcion or '',
            'evidencia_count':  instance.evidencia_count,
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'[JOI preferencia_aprendida] {e}')


# ── Calibración RPE personal ──────────────────────────────────────────────────
from django.db.models import Avg as _Avg

@receiver(post_save, sender=EntrenoRealizado)
def calibrar_rpe_personal(sender, instance, created, raw=False, update_fields=None, **kwargs):
    """
    Detecta discordancia persistente entre RPE reportado y zona FC real.
    Patrón: avg_RPE ≤ 6.5 pero FC ≥ 80 % FC_max (zona Z4) en 3+ sesiones.
    Cuando se confirma, guarda el bias en one_rm_data['_rpe_bias'] y dispara JOI.
    """
    if raw or update_fields is not None:
        return
    if not instance.frecuencia_cardiaca_promedio:
        return

    try:
        from django.core.cache import cache
        from joi.services import generar_mensaje_joi

        cliente = instance.cliente
        lock_key = f'rpe_cal_lock_{cliente.pk}'
        if cache.get(lock_key):
            return

        # FC máxima del usuario (desde HyroxObjective si existe, sino 220-edad)
        fc_max = 185  # default
        try:
            from hyrox.models import HyroxObjective
            from hyrox.training_engine import HyroxLoadManager
            obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
            if obj:
                fc_max = HyroxLoadManager.get_fc_max(obj)
            elif cliente.fecha_nacimiento:
                from django.utils import timezone as _tz
                edad = (_tz.now().date() - cliente.fecha_nacimiento).days // 365
                fc_max = max(150, 220 - edad)
        except Exception:
            pass

        umbral_z4 = fc_max * 0.80

        # Analizar las últimas 3 sesiones con FC y RPE
        sesiones = (
            EntrenoRealizado.objects
            .filter(cliente=cliente, frecuencia_cardiaca_promedio__isnull=False)
            .order_by('-fecha')[:3]
        )
        if sesiones.count() < 3:
            return

        discordantes = 0
        rpcs_reportados, rpcs_estimados = [], []
        for s in sesiones:
            avg_rpe = EjercicioRealizado.objects.filter(
                entreno=s, rpe__isnull=False
            ).aggregate(avg=_Avg('rpe'))['avg']
            if avg_rpe is None:
                continue
            zona_fc = s.frecuencia_cardiaca_promedio
            rpe_estimado = round(6 + (zona_fc - fc_max * 0.6) / (fc_max * 0.4) * 4, 1)
            rpe_estimado = max(1, min(10, rpe_estimado))
            if avg_rpe <= 6.5 and zona_fc >= umbral_z4:
                discordantes += 1
                rpcs_reportados.append(avg_rpe)
                rpcs_estimados.append(rpe_estimado)

        if discordantes < 3:
            return

        # Calcular bias y guardar en one_rm_data
        rpe_reportado_medio = round(sum(rpcs_reportados) / len(rpcs_reportados), 1)
        rpe_estimado_medio  = round(sum(rpcs_estimados) / len(rpcs_estimados), 1)
        bias = round(rpe_estimado_medio - rpe_reportado_medio, 1)

        one_rm = cliente.one_rm_data or {}
        bias_anterior = one_rm.get('_rpe_bias', 0)
        # Solo actualizar y notificar si el bias cambió significativamente
        if abs(bias - bias_anterior) < 0.5:
            return

        one_rm['_rpe_bias'] = bias
        cliente.one_rm_data = one_rm
        cliente.save(update_fields=['one_rm_data'])

        cache.set(lock_key, True, 86400)  # 24h — un aviso al día máximo

        zona_fc_str = 'Z4' if (sum(s.frecuencia_cardiaca_promedio for s in sesiones) / 3) < fc_max * 0.90 else 'Z5'
        generar_mensaje_joi(cliente, 'rpe_calibracion', {
            'sesiones_analizadas': 3,
            'rpe_medio_reportado': rpe_reportado_medio,
            'zona_fc_real': zona_fc_str,
            'diferencia_estimada': f'+{bias} puntos',
        })

        import logging
        logging.getLogger(__name__).info(
            f"[RPE Calibración] {cliente.user.username}: bias={bias} "
            f"(reportado {rpe_reportado_medio} vs estimado {rpe_estimado_medio})"
        )

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[RPE calibracion] {e}")
