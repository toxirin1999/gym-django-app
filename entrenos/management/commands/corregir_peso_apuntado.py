"""Corrige un peso mal apuntado en el historial de un ejercicio (26-oct-2026).

La sentadilla hack se hace con 20 kg, pero el historial decía 21; el press
francés tenía una serie de 25,5 kg que eran 25. Sin --aplicar solo enseña qué
cambiaría.

    python manage.py corregir_peso_apuntado 2 --ejercicio "Sentadilla Hack" --de 21 --a 20
    python manage.py corregir_peso_apuntado 2 --ejercicio "Sentadilla Hack" --de 21 --a 20 --aplicar
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Corrige un peso mal apuntado en las series de un ejercicio (sin --aplicar, solo lo enseña).'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--ejercicio', required=True)
        parser.add_argument('--de', required=True, type=Decimal)
        parser.add_argument('--a', required=True, type=Decimal)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from clientes.models import Cliente
        from entrenos.models import EjercicioRealizado, GymDecisionLog, SerieRealizada

        cliente = Cliente.objects.filter(pk=opts['cliente_id']).first()
        if not cliente:
            raise CommandError('No existe ese cliente.')
        nombre, de, a = opts['ejercicio'], opts['de'], opts['a']
        if de == a or a <= 0:
            raise CommandError('El peso nuevo tiene que ser distinto y mayor que 0.')

        series = list(
            SerieRealizada.objects.filter(entreno__cliente=cliente, ejercicio__nombre__iexact=nombre, peso_kg=de)
            .select_related('entreno').order_by('entreno__fecha', 'serie_numero')
        )
        resumenes = list(EjercicioRealizado.objects.filter(
            entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, peso_kg=float(de),
        ).select_related('entreno'))
        logs = list(GymDecisionLog.objects.filter(cliente=cliente, ejercicio__iexact=nombre, peso_anterior=float(de)))

        if not (series or resumenes or logs):
            self.stdout.write(f'No hay nada apuntado con {de} kg en «{nombre}».')
            return
        for s in series:
            self.stdout.write(f'  serie  {s.entreno.fecha:%d/%m/%Y}  #{s.serie_numero}  {s.peso_kg} kg × {s.repeticiones}  → {a} kg')
        for e in resumenes:
            self.stdout.write(f'  resumen {e.entreno.fecha:%d/%m/%Y}  {e.peso_kg} kg  → {a} kg')
        for log in logs:
            self.stdout.write(f'  decisión {log.fecha_creacion:%d/%m/%Y}  peso anterior {log.peso_anterior} → {a}')
        self.stdout.write(f'{len(series)} series, {len(resumenes)} resúmenes y {len(logs)} decisiones.')

        if not opts['aplicar']:
            self.stdout.write('Nada cambiado. Repite con --aplicar para guardarlo.')
            return
        with transaction.atomic():
            for s in series:
                campos = ['peso_kg']
                s.peso_kg = a
                if s.peso_total_kg is not None:
                    s.peso_total_kg = a * (s.multiplicador_carga or 1)
                    campos.append('peso_total_kg')
                s.save(update_fields=campos)
            for e in resumenes:
                e.peso_kg = float(a)
                e.save(update_fields=['peso_kg'])
            for log in logs:
                log.peso_anterior = float(a)
                log.save(update_fields=['peso_anterior'])
        self.stdout.write(self.style.SUCCESS('Corregido.'))
