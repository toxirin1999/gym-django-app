"""Cierra como inconclusa una decisión que se evaluó con una sesión que no podía evaluarla.

    python manage.py corregir_decision_inconclusa 2 492             # solo muestra qué cambiaría
    python manage.py corregir_decision_inconclusa 2 492 --aplicar   # guarda la corrección

El resultado anterior y el motivo quedan en las notas de la decisión.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Corrige a inconcluso una decisión evaluada con una sesión de otro bloque.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('decision_id', type=int)
        parser.add_argument('--aplicar', action='store_true')
        parser.add_argument('--motivo', default=(
            'la única sesión posterior que la comprobó era de otro bloque y no consta una '
            'evaluación válida (nota 49, regla del 18/11)'))

    def handle(self, *args, cliente_id, decision_id, aplicar, motivo, **opts):
        from entrenos.models import GymDecisionLog
        from entrenos.services.aprendizaje_decisiones_service import (
            _ultima_elegible_hasta_evaluacion, decisiones_evaluadas, frase_decision,
        )
        from entrenos.services.decision_log_service import corregir_decision_a_inconcluso

        try:
            log = GymDecisionLog.objects.select_related('cliente', 'entreno_origen').get(
                pk=decision_id, cliente_id=cliente_id)
        except GymDecisionLog.DoesNotExist as exc:
            raise CommandError(str(exc))
        ultima = _ultima_elegible_hasta_evaluacion(log)
        if ultima is None:
            raise CommandError('No hay sesión posterior que contrastar.')
        self.stdout.write(f'Antes: {log.resultado} · {log.notas_resultado}')
        antes_conteo = decisiones_evaluadas(log.cliente, dias=60)
        try:
            resultado, notas = corregir_decision_a_inconcluso(log, ultima.entreno, motivo, aplicar=aplicar)
        except ValueError as exc:
            raise CommandError(str(exc))
        self.stdout.write(f'Después: {resultado} · {notas}')
        if aplicar:
            log.refresh_from_db()
            self.stdout.write('Texto en Memoria: ' + frase_decision(log))
            despues_conteo = decisiones_evaluadas(log.cliente, dias=60)
            for k in ('con_conclusion', 'no_funcionaron'):
                self.stdout.write(f'{k}: {antes_conteo.get(k)} -> {despues_conteo.get(k)}')
        else:
            self.stdout.write('(No se ha guardado nada: añade --aplicar.)')
