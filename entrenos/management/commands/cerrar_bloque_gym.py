import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from entrenos.models import ContratoBloqueGym
from entrenos.services.contrato_bloque_gym_service import (
    BloqueAbierto, EvidenciaBloqueIncompleta, EvaluacionBloqueCongelada,
    cerrar_bloque_gym, previsualizar_cierre_bloque_gym,
)


class Command(BaseCommand):
    help = 'Previsualiza o persiste el cierre longitudinal Gym. Dry-run por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--bloque', type=int, required=True)
        parser.add_argument('--hoy', type=date.fromisoformat)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        bloque = ContratoBloqueGym.objects.filter(pk=options['bloque']).first()
        if bloque is None:
            raise CommandError(f'No existe bloque {options["bloque"]}.')
        hoy = options['hoy']
        if isinstance(hoy, str):
            try:
                hoy = date.fromisoformat(hoy)
            except ValueError as exc:
                raise CommandError('--hoy debe usar YYYY-MM-DD') from exc
        if not options['apply']:
            resultado = previsualizar_cierre_bloque_gym(bloque, hoy=hoy)
            for semana in resultado['evidencia_snapshot']['semanas']:
                self.stdout.write(json.dumps({'tipo': 'semana', **semana}, sort_keys=True))
            resumen = {clave: valor for clave, valor in resultado.items() if clave != 'evidencia_snapshot'}
            self.stdout.write(json.dumps({'tipo': 'resumen', **resumen}, sort_keys=True))
            return
        try:
            evaluacion = cerrar_bloque_gym(bloque, hoy=hoy)
        except (BloqueAbierto, EvidenciaBloqueIncompleta, EvaluacionBloqueCongelada) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({
            'tipo': 'resumen', 'modo': 'apply', 'solo_lectura': False,
            'bloque_id': bloque.pk, 'evaluacion_id': evaluacion.pk,
            'version_calculo': evaluacion.version_calculo,
            'estado_resultado': evaluacion.estado_resultado,
            'fingerprint_evidencia': evaluacion.fingerprint_evidencia,
            'estado_revision': evaluacion.estado_revision,
        }, sort_keys=True))
