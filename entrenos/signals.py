from django.db.models.signals import post_save
from django.dispatch import receiver
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado, ActividadRealizada
from entrenos.utils.utils import parse_reps_and_series
from django.utils.timezone import make_aware
from datetime import datetime


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

    # Carga UA con fallbacks:
    # 1. RPE × duración (estándar)
    # 2. RPE por defecto (5.0 = moderado) × duración si no hay RPE
    # 3. Volumen / 100 como estimación mínima si no hay duración
    carga_ua = None
    if rpe_medio and duracion:
        carga_ua = round(float(rpe_medio) * duracion, 1)
    elif duracion:
        carga_ua = round(5.0 * duracion, 1)   # esfuerzo moderado por defecto
    elif instance.volumen_total_kg and instance.volumen_total_kg > 0:
        carga_ua = round(float(instance.volumen_total_kg) / 100, 1)

    defaults = {
        'cliente': instance.cliente,
        'tipo': 'gym',
        'titulo': titulo,
        'fecha': instance.fecha,
        'hora_inicio': instance.hora_inicio,
        'duracion_minutos': duracion,
        'volumen_kg': instance.volumen_total_kg,
        'calorias': instance.calorias_quemadas,
        'rpe_medio': rpe_medio,
        'carga_ua': carga_ua,
        'fuente': 'liftin' if instance.fuente_datos == 'liftin' else 'manual',
    }

    try:
        ActividadRealizada.objects.update_or_create(
            entreno_gym=instance,
            defaults=defaults,
        )
    except Exception as e:
        print(f"❌ Hub ActividadRealizada error (entreno {instance.id}): {e}")
