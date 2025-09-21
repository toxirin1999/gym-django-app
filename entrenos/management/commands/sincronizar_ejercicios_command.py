from django.core.management.base import BaseCommand
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from entrenos.utils.utils import parsear_ejercicios
from clientes.models import Cliente
from django.utils.timezone import make_aware
from datetime import datetime


class Command(BaseCommand):
    help = 'Sincroniza ejercicios desde notas_liftin a EjercicioLiftinDetallado'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int, help='ID del cliente para sincronizar')

    def handle(self, *args, **kwargs):
        cliente_id = kwargs['cliente_id']
        cliente = Cliente.objects.get(id=cliente_id)
        entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente).exclude(notas_liftin__isnull=True).exclude(
            notas_liftin='')

        creados = 0
        duplicados = 0
        errores = 0

        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)
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

                    _, creado = EjercicioLiftinDetallado.objects.get_or_create(
                        entreno=entreno,
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
                    if creado:
                        creados += 1
                    else:
                        duplicados += 1
                except Exception as e:
                    errores += 1
                    self.stderr.write(f"❌ Error en entreno {entreno.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"✅ Sincronización completada"))
        self.stdout.write(f"➕ Ejercicios creados: {creados}")
        self.stdout.write(f"🔁 Duplicados omitidos: {duplicados}")
        self.stdout.write(f"⚠️ Errores: {errores}")
