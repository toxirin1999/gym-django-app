"""Decisiones "subir reps" marcadas como "funcionó" sin llegar al objetivo (2-nov-2026).

Uso:  python manage.py revisar_subidas_reps 2            (solo enseña)
      python manage.py revisar_subidas_reps 2 --aplicar  (las pasa a "aún sin conclusión")

Desde hoy, subir de 19 a 20 reps cuando el objetivo era 22 queda "aún sin
conclusión", no "funcionó" (abducción del 30-oct). Esto corrige las que ya
estaban evaluadas con la regla anterior.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Revisa las subidas de reps evaluadas como validadas sin llegar al objetivo.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from entrenos.models import GymDecisionLog
        from entrenos.services.aprendizaje_decisiones_service import _sesion_evaluadora

        n = 0
        for log in GymDecisionLog.objects.filter(
            cliente_id=opts['cliente_id'], accion='subir_reps', resultado='validada',
        ).order_by('fecha_creacion'):
            objetivo = log.reps_sugeridas
            despues = _sesion_evaluadora(log)
            if not objetivo or not despues or despues['reps'] is None or despues['reps'] >= objetivo:
                continue
            if 'distancia' in (log.notas_resultado or '').lower():
                continue
            n += 1
            self.stdout.write(f'{log.fecha_creacion:%d/%m} {log.ejercicio}: objetivo {objetivo}, '
                              f'después {despues["reps"]} (antes {log.reps_anteriores})')
            if opts['aplicar']:
                log.resultado = 'neutra'
                log.notas_resultado = (f'Subió de {log.reps_anteriores} a {despues["reps"]} reps, '
                                       f'sin llegar a las {objetivo} del objetivo')
                log.save(update_fields=['resultado', 'notas_resultado'])
        accion = 'corregidas' if opts['aplicar'] else 'por corregir (añade --aplicar)'
        self.stdout.write(f'\n{n} {accion}.')
