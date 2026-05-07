from django.db.models.signals import post_save
from django.dispatch import receiver
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado, ActividadRealizada
from entrenos.utils.utils import parse_reps_and_series
from django.utils.timezone import make_aware
from datetime import datetime

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
    duracion = instance.duracion_minutos
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

    # Carga UA: TRIMP si hay FC (fisiológico), sRPE si hay RPE, fallback moderado si solo duración
    hr_media = instance.frecuencia_cardiaca_promedio
    hr_maxima = instance.frecuencia_cardiaca_maxima
    carga_ua = None
    dur_valida = duracion is not None and duracion > 0
    if hr_media and dur_valida:
        try:
            from hyrox.training_engine import HyroxLoadManager
            from hyrox.models import HyroxObjective
            objetivo = HyroxObjective.objects.filter(cliente=instance.cliente, estado='activo').first()
            carga_ua = HyroxLoadManager.calcular_trimp(duracion, hr_media, objetivo)
        except Exception:
            pass
    if carga_ua is None and rpe_medio and dur_valida:
        carga_ua = round(float(rpe_medio) * duracion, 1)
    elif carga_ua is None and dur_valida:
        carga_ua = round(6.5 * duracion, 1)   # fallback moderado-alto si no hay FC ni RPE

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
    except Exception as e:
        print(f"❌ Hub ActividadRealizada error (entreno {instance.id}): {e}")


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


@receiver(post_save, sender='entrenos.RecordPersonal')  # lazy string resuelto por Django apps registry
def sincronizar_rm_con_hyrox(sender, instance, created, raw=False, **kwargs):
    """
    Cuando se establece un nuevo récord de peso máximo en gym,
    actualiza rm_sentadilla / rm_peso_muerto en el HyroxObjective activo
    si el nuevo valor supera al almacenado.
    Solo actúa sobre récords vigentes (superado=False) y de tipo peso_maximo.
    """
    if raw or instance.superado:
        return
    if instance.tipo_record not in ('peso_maximo', 'one_rep_max'):
        return

    nombre = (instance.ejercicio_nombre or '').lower()
    nuevo_valor = float(instance.valor)

    if any(kw in nombre for kw in _SENTADILLA_KW):
        campo = 'rm_sentadilla'
    elif any(kw in nombre for kw in _PESO_MUERTO_KW):
        campo = 'rm_peso_muerto'
    else:
        return

    try:
        from hyrox.models import HyroxObjective
        from django.core.cache import cache as _cache

        objetivo = HyroxObjective.objects.filter(
            cliente=instance.cliente,
            estado='activo',
        ).first()
        if not objetivo:
            return

        actual = getattr(objetivo, campo) or 0
        if nuevo_valor > actual:
            setattr(objetivo, campo, nuevo_valor)
            objetivo.save(update_fields=[campo])
            _cache.delete(f'hyrox_readiness_{objetivo.pk}')
            _cache.delete(f'dashboard_acwr_unificado_{instance.cliente_id}')
            print(
                f"🏋️ Hyrox RM actualizado: {instance.ejercicio_nombre} → "
                f"{campo}={nuevo_valor} kg (anterior: {actual} kg)"
            )
    except Exception as e:
        print(f"⚠️ sincronizar_rm_con_hyrox error: {e}")
