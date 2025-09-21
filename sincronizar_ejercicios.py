
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from entrenos.utils import parsear_ejercicios
from clientes.models import Cliente
from django.utils.timezone import make_aware
from datetime import datetime

def sincronizar_ejercicios(cliente_id):
    cliente = Cliente.objects.get(id=cliente_id)
    entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

    creados = 0
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

                EjercicioLiftinDetallado.objects.get_or_create(
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
                creados += 1
            except Exception as e:
                print(f"❌ Error al crear ejercicio para entreno {entreno.id}: {e}")
    print(f"✅ Sincronización completa. Ejercicios creados: {creados}")
