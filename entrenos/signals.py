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

    # Carga UA
    carga_ua = None
    if rpe_medio and instance.duracion_minutos:
        carga_ua = round(rpe_medio * instance.duracion_minutos, 1)

    defaults = {
        'cliente': instance.cliente,
        'tipo': 'gym',
        'titulo': titulo,
        'fecha': instance.fecha,
        'hora_inicio': instance.hora_inicio,
        'duracion_minutos': instance.duracion_minutos,
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
