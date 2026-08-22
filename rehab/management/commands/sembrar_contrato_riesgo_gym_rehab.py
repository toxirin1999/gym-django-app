import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rehab.models import ContratoRiesgoGymFaseRehab, FaseProtocolo


class Command(BaseCommand):
    help = 'Prepara el contrato Fase 1 rotuliana; dry-run salvo --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            phase = FaseProtocolo.objects.get(
                protocolo__slug='tendinopatia-rotuliana', protocolo__version=1,
                slug='fase-1-isometrica', orden=1,
            )
        except FaseProtocolo.DoesNotExist as exc:
            raise CommandError('No existe la Fase 1 exacta del protocolo v1.') from exc
        payload = {
            'operation': 'apply' if options['apply'] else 'dry_run', 'phase_id': phase.pk,
            'protocol_slug': phase.protocolo.slug, 'contract_version': 1,
            'risk_tags': ['carga_dominante_rodilla'], 'execution_enabled': False,
        }
        if options['apply']:
            _, created = ContratoRiesgoGymFaseRehab.objects.get_or_create(
                fase=phase, version=1,
                defaults=dict(schema_version=1, risk_tags=['carga_dominante_rodilla'],
                              pain_hold_min=5, freshness_days=3, action='sostener',
                              scope='matching_exercises', red_flag_action='proteger', activo=True,
                              execution_enabled=False),
            )
            payload['created'] = created
        self.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=False))
