import json
from copy import deepcopy

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion


class Command(BaseCommand):
    help = 'Previsualiza, sin escrituras, el freno Rehab sobre la autoridad Gym vigente.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', required=True, type=int)
        parser.add_argument('--fecha', required=True)

    def handle(self, *args, **options):
        fecha = parse_date(options['fecha'])
        if fecha is None:
            raise CommandError('--fecha debe usar YYYY-MM-DD')
        try:
            cliente = Cliente.objects.get(pk=options['cliente'])
            vigente = GymDecisionVersion.objects.get(cliente=cliente, fecha=fecha, vigente=True)
        except Cliente.DoesNotExist as exc:
            raise CommandError('Cliente inexistente.') from exc
        except GymDecisionVersion.DoesNotExist as exc:
            raise CommandError('No existe autoridad Gym vigente para esa fecha.') from exc

        # Captura contractual actual exclusivamente para preview. No resuelve,
        # materializa, persiste, actualiza ni cachea autoridad alguna.
        from core.services.physical_snapshot import build_physical_snapshot
        from entrenos.services.freno_rehab_gym_service import aplicar_freno_rehab_gym
        snapshot = build_physical_snapshot(cliente, fecha)
        simulated_snapshot = deepcopy(snapshot)
        rehab_items = (((simulated_snapshot.get('signals') or {})
                        .get('active_rehab') or {}).get('items') or [])
        current_enabled = any(
            bool((item.get('gym_risk_contract') or {}).get('execution_enabled'))
            for item in rehab_items
        )
        simulated_enabled = False
        for item in rehab_items:
            contract = item.get('gym_risk_contract') or {}
            assessment = item.get('executive_assessment') or {}
            if contract and assessment.get('would_hold') is True:
                contract['execution_enabled'] = True
                item['executive_capacity'] = {
                    'can_derive_restrictions': True,
                    'reason': assessment.get('reason') or 'rehab_recent_pain_hold',
                }
                simulated_enabled = True
        authority = deepcopy(vigente.snapshot or {})
        exercises = deepcopy((authority.get('entrenamiento') or {}).get('ejercicios') or [])
        projected, receipts = aplicar_freno_rehab_gym(
            cliente, exercises, simulated_snapshot, fecha,
        )
        affected_names = {row.get('ejercicio') for row in receipts}
        affected = [row for row in projected if row.get('nombre') in affected_names]
        unaffected = [row for row in projected if row.get('nombre') not in affected_names]
        contracts = [item.get('gym_risk_contract') for item in
                     snapshot['signals']['active_rehab'].get('items', [])
                     if item.get('gym_risk_contract')]
        rows = [
            {'type': 'meta', 'cliente_id': cliente.pk, 'fecha': fecha.isoformat(),
             'decision_id': vigente.decision_id, 'authority_version': vigente.version,
             'execution_enabled': False,
             'current_execution_enabled': current_enabled,
             'simulated_execution_enabled': simulated_enabled,
             'current_contracts': contracts},
            {'type': 'coverage', 'total': len(projected), 'affected': len(affected),
             'unaffected': len(unaffected)},
            {'type': 'affected', 'items': affected, 'receipts': receipts},
            {'type': 'unaffected', 'items': unaffected},
        ]
        for row in rows:
            self.stdout.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str))
