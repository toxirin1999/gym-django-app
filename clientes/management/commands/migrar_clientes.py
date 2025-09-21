# clientes/management/commands/migrar_clientes.py

from django.core.management.base import BaseCommand
from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Actualiza los clientes existentes con los nuevos campos de personalización.'

    def handle(self, *args, **kwargs):
        # self.stdout es como usar print(), pero para comandos.
        self.stdout.write(self.style.NOTICE('Iniciando la actualización de clientes...'))

        # Buscamos a los clientes que tienen el valor temporal que pusimos en el paso 1
        clientes_a_migrar = Cliente.objects.filter(dias_disponibles=0)

        count = clientes_a_migrar.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No hay clientes que necesiten ser actualizados.'))
            return

        for cliente in clientes_a_migrar:
            # Asignamos valores por defecto
            cliente.dias_disponibles = 4
            cliente.tiempo_por_sesion = 75
            cliente.nivel_estres = 5
            cliente.calidad_sueño = 7
            cliente.nivel_energia = 7
            cliente.flexibilidad_horario = True
            cliente.save()
            self.stdout.write(f' -> Cliente "{cliente.nombre}" (ID: {cliente.id}) actualizado.')

        self.stdout.write(self.style.SUCCESS(f'\n¡Proceso finalizado! Se actualizaron {count} clientes.'))
