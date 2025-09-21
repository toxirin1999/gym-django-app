from django.db.models.signals import post_save
from django.dispatch import receiver
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from entrenos.utils.utils import parse_reps_and_series
from django.utils.timezone import make_aware
from datetime import datetime


@receiver(post_save, sender=EntrenoRealizado)
def crear_ejercicios_detallados(sender, instance, created, **kwargs):
    if not instance.notas_liftin:
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
