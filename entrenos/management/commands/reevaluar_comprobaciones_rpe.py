"""Vuelve a juzgar las comprobaciones que se dieron por fallidas con RPE 8 fijo (26-oct-2026).

Hasta hoy, "Lo que comprobé" daba por fallido un cambio si el RPE pasaba de 8,
aunque el plan pidiera 9 (extensiones en polea 30 × 15 a RPE 9). Este comando
busca esas comprobaciones y las vuelve a evaluar con el RPE que pedía el plan.
Sin --aplicar solo enseña cuáles.

    python manage.py reevaluar_comprobaciones_rpe 2
    python manage.py reevaluar_comprobaciones_rpe 2 --aplicar
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

PREFIJO = 'El objetivo exigió un RPE'


class Command(BaseCommand):
    help = 'Re-evalúa comprobaciones fallidas por RPE con el RPE objetivo del plan.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--dias', type=int, default=21)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from datetime import timedelta

        from django.utils import timezone

        from clientes.models import Cliente
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from entrenos.services.decision_log_service import (
            _evaluar_log, _rpe_pedido, normalizar_ejercicio,
        )
        from rutinas.models import EjercicioBase

        cliente = Cliente.objects.filter(pk=opts['cliente_id']).first()
        if not cliente:
            raise CommandError('No existe ese cliente.')
        desde = timezone.now() - timedelta(days=opts['dias'])
        logs = GymDecisionLog.objects.filter(
            cliente=cliente, resultado='fallida', notas_resultado__startswith=PREFIJO,
            fecha_evaluacion__gte=desde,
        ).order_by('fecha_evaluacion')
        revisadas = 0
        for log in logs:
            nombre = log.ejercicio_normalizado or normalizar_ejercicio(log.ejercicio)
            sesion = (
                EjercicioRealizado.objects.filter(
                    entreno__cliente=cliente, completado=True,
                    entreno__fecha__gte=log.fecha_evaluacion.date() - timedelta(days=1),
                    entreno__fecha__lte=log.fecha_evaluacion.date(),
                ).filter(Q(nombre_ejercicio__iexact=log.ejercicio) | Q(nombre_ejercicio__iexact=nombre))
                .select_related('entreno').order_by('-entreno__fecha').first()
            )
            if not sesion or sesion.rpe is None:
                continue
            pedido = _rpe_pedido(sesion.entreno, nombre)
            if float(sesion.rpe) > pedido:
                continue  # sí estuvo por encima de lo que pedía el plan
            revisadas += 1
            self.stdout.write(f'  {log.ejercicio} ({sesion.entreno.fecha:%d/%m}): RPE {sesion.rpe:g}, '
                              f'el plan pedía {pedido:g} → se vuelve a evaluar')
            if opts['aplicar']:
                GymDecisionLog.objects.filter(pk=log.pk).update(
                    resultado=None, notas_resultado='', fecha_evaluacion=None,
                )
                log.refresh_from_db()
                base = EjercicioBase.objects.filter(nombre__iexact=sesion.nombre_ejercicio).first()
                _evaluar_log(log, sesion, base.tipo_progresion if base else 'peso_reps')
                log.refresh_from_db()
                self.stdout.write(f'    ahora: {log.resultado} · {log.notas_resultado}')
        if not revisadas:
            self.stdout.write('No hay comprobaciones que corregir.')
        elif not opts['aplicar']:
            self.stdout.write('Nada cambiado. Repite con --aplicar para guardarlo.')
