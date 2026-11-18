"""Reevalúa una propuesta de zona ya evaluada con la regla vigente, conservando el resultado anterior.

    python manage.py reevaluar_propuesta_zona 2 1                 # solo muestra qué cambiaría
    python manage.py reevaluar_propuesta_zona 2 1 --aplicar       # guarda la corrección
"""
from django.core.management.base import BaseCommand, CommandError

MOTIVO = ('la comparación no medía un antes y un durante de la propuesta y no consta que se aplicara '
          '(nota 49, regla nueva del 18/11)')


class Command(BaseCommand):
    help = 'Reevalúa una propuesta de zona con la regla vigente y guarda el resultado anterior.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('propuesta_id', type=int)
        parser.add_argument('--aplicar', action='store_true')
        parser.add_argument('--motivo', default=MOTIVO)

    def handle(self, *args, cliente_id, propuesta_id, aplicar, motivo, **opts):
        from clientes.models import Cliente
        from entrenos.models import PropuestaZonaGym
        from entrenos.services.propuesta_zona_service import (
            frase_evaluacion, reevaluar_propuesta, sesiones_con_ajuste_registrado,
        )

        try:
            cliente = Cliente.objects.get(pk=cliente_id)
            p = PropuestaZonaGym.objects.get(pk=propuesta_id, cliente=cliente)
        except (Cliente.DoesNotExist, PropuestaZonaGym.DoesNotExist) as exc:
            raise CommandError(str(exc))
        if p.estado != PropuestaZonaGym.ESTADO_EVALUADA:
            raise CommandError(f'La propuesta está «{p.estado}», no evaluada.')
        self.stdout.write(f'Ventana {p.inicio}–{p.fin}; ejercicios {p.ejercicios}')
        self.stdout.write(f'Sesiones con el ajuste registrado: {sesiones_con_ajuste_registrado(cliente, p)}')
        self.stdout.write(f'Antes: {p.resultado} · {p.notas_resultado}')
        resultado, notas, cambio = reevaluar_propuesta(cliente, p, motivo, aplicar=aplicar)
        self.stdout.write(f'Regla nueva: {resultado} · {notas}')
        if not cambio:
            self.stdout.write('Sin cambios.')
        elif aplicar:
            p.refresh_from_db()
            self.stdout.write('Guardado. Texto en Memoria/Centro: ' + frase_evaluacion(p))
        else:
            self.stdout.write('(No se ha guardado nada: añade --aplicar.)')
