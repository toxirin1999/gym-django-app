"""Overlay selectivo Rehab→Gym. Opera solo con el snapshot inmutable recibido."""
from copy import deepcopy


def _number(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value) if '.' in value else int(value)
        except ValueError:
            return None
    return None


def _baseline(cliente, nombre, fecha):
    from entrenos.models import EjercicioRealizado
    from django.db.models import Q
    qs = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, completado=True,
    ).filter(Q(entreno__fecha_ejecucion__lt=fecha) |
             Q(entreno__fecha_ejecucion__isnull=True, entreno__fecha__lt=fecha)) \
     .select_related('entreno').order_by('-entreno__fecha_ejecucion', '-entreno__fecha', '-pk')
    item = qs.first()
    if not item:
        return None
    return {'exercise_record_id': item.pk, 'peso_kg': item.peso_kg,
            'series': item.series, 'repeticiones': item.repeticiones}


def aplicar_freno_rehab_gym(cliente, ejercicios, physical_snapshot, fecha):
    output = deepcopy(ejercicios)
    items = (((physical_snapshot or {}).get('signals') or {}).get('active_rehab') or {}).get('items') or []
    holds = [item for item in items if
             (item.get('executive_capacity') or {}).get('can_derive_restrictions')
             and (item.get('gym_risk_contract') or {}).get('execution_enabled')]
    cambios = []
    for exercise in output:
        if exercise.get('motivo_freno_rehab') == 'rehab_recent_pain_hold':
            cambios.append({
                'tipo': 'freno_rehab_gym', 'ejercicio': exercise.get('nombre'),
                'episode_id': exercise.get('rehab_episode_id'),
                'contract_id': exercise.get('rehab_contract_id'),
                'matched_risk_tags': exercise.get('rehab_matched_risk_tags') or [],
                'dimensions': exercise.get('rehab_dimensiones_frenadas') or [],
                'reason': 'rehab_recent_pain_hold',
            })
            continue
        original_name = exercise.get('nombre_original') or exercise.get('nombre', '')
        current_tags = set(exercise.get('risk_tags') or [])
        for item in holds:
            contract = item['gym_risk_contract']
            matched = sorted(current_tags & set(contract.get('risk_tags') or []))
            if not matched:
                continue
            baseline = _baseline(cliente, original_name, fecha)
            if not baseline:
                exercise.setdefault('rehab_evidence', []).append({
                    'reason': 'insufficient_baseline', 'episode_id': item['episode_id'],
                    'contract_id': contract['id'], 'matched_risk_tags': matched,
                    'quantitative_hold_applied': False})
                continue
            proposed = {key: exercise.get(key) for key in ('peso_kg', 'peso_recomendado_kg', 'series', 'repeticiones')}
            dimensions = []
            for key, baseline_key in (('peso_kg', 'peso_kg'), ('peso_recomendado_kg', 'peso_kg'),
                                      ('series', 'series'), ('repeticiones', 'repeticiones')):
                current = _number(exercise.get(key))
                ceiling = _number(baseline.get(baseline_key))
                if current is not None and ceiling is not None and current > ceiling:
                    exercise[key] = ceiling
                    dimensions.append(key)
            # No se revierte una sustitución protectora; solo se bloquea una variante ascendente identificable.
            for key in list(exercise):
                if key.startswith('progresion_') or key in {'incremento_peso', 'subida_peso'}:
                    if exercise.get(key):
                        exercise.pop(key, None)
            exercise.update({
                'postura_local': 'sostener', 'progresion_bloqueada': True,
                'motivo_freno_rehab': 'rehab_recent_pain_hold',
                'rehab_matched_risk_tags': matched, 'rehab_episode_id': item['episode_id'],
                'rehab_contract_id': contract['id'], 'rehab_baseline': baseline,
                'rehab_propuesto': proposed,
                'rehab_final': {key: exercise.get(key) for key in proposed},
                'rehab_dimensiones_frenadas': dimensions,
            })
            receipt = {'tipo': 'freno_rehab_gym', 'ejercicio': exercise.get('nombre'),
                       'episode_id': item['episode_id'], 'contract_id': contract['id'],
                       'matched_risk_tags': matched, 'dimensions': dimensions,
                       'reason': 'rehab_recent_pain_hold'}
            cambios.append(receipt)
            break
    # Canonical order makes reapplication return the same receipt set.
    return output, cambios
