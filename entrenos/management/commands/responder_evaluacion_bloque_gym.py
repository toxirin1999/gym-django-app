import json

from django.core.management.base import BaseCommand, CommandError

from entrenos.models import EvaluacionBloqueGym
from entrenos.services.contrato_bloque_gym_service import (
    ActorBloqueNoAutorizado, EvaluacionBloqueCongelada,
    TransicionBloqueInvalida, responder_evaluacion_bloque_gym,
)


class Command(BaseCommand):
    help = 'Previsualiza o registra la revisión humana de un cierre de bloque.'

    def add_arguments(self, parser):
        parser.add_argument('--evaluacion', type=int, required=True)
        parser.add_argument('--respuesta', choices=['aceptar', 'rechazar'], required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        evaluacion = EvaluacionBloqueGym.objects.select_related('bloque__cliente__user').filter(
            pk=options['evaluacion'],
        ).first()
        if evaluacion is None:
            raise CommandError(f'No existe evaluación {options["evaluacion"]}.')
        payload = {
            'evaluacion_id': evaluacion.pk, 'bloque_id': evaluacion.bloque_id,
            'respuesta': options['respuesta'],
            'estado_revision_actual': evaluacion.estado_revision,
        }
        if not options['apply']:
            payload.update({'modo': 'dry-run', 'solo_lectura': True})
            self.stdout.write(json.dumps(payload, sort_keys=True))
            return
        try:
            evaluacion = responder_evaluacion_bloque_gym(
                evaluacion, actor=evaluacion.bloque.cliente.user,
                aceptar=options['respuesta'] == 'aceptar',
            )
        except (
            ActorBloqueNoAutorizado, EvaluacionBloqueCongelada,
            TransicionBloqueInvalida,
        ) as exc:
            raise CommandError(str(exc)) from exc
        evaluacion.bloque.refresh_from_db()
        payload.update({
            'modo': 'apply', 'solo_lectura': False,
            'estado_revision': evaluacion.estado_revision,
            'estado_bloque': evaluacion.bloque.estado,
        })
        self.stdout.write(json.dumps(payload, sort_keys=True))
