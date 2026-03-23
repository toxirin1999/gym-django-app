from django.core.management.base import BaseCommand
from entrenos.models import EntrenoRealizado


class Command(BaseCommand):
    help = 'Recalcula volumen_total_kg para sesiones con valor 0 o NULL'

    def handle(self, *args, **options):
        sesiones = EntrenoRealizado.objects.filter(
            volumen_total_kg__isnull=True
        ) | EntrenoRealizado.objects.filter(volumen_total_kg=0)

        total = sesiones.count()
        self.stdout.write(f'Sesiones a recalcular: {total}')

        actualizadas = 0
        sin_volumen = 0

        for sesion in sesiones.iterator():
            volumen = sesion.calcular_volumen_total()
            if volumen > 0:
                EntrenoRealizado.objects.filter(pk=sesion.pk).update(volumen_total_kg=volumen)
                actualizadas += 1
            else:
                sin_volumen += 1

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {actualizadas} actualizadas, {sin_volumen} sin ejercicios registrados.'
        ))
