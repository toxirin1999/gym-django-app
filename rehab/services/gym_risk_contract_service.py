import unicodedata
from copy import deepcopy
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from rehab.models import ContratoRiesgoGymFaseRehab, EpisodioRehab
from rutinas.models import EjercicioBase


CATALOGO_RIESGO_GYM_V1 = {
    'schema_version': 1,
    'risk_tag': 'carga_dominante_rodilla',
    'exact_names': (
        'Extensión de cuádriceps en máquina', 'Prensa de piernas', 'Sentadilla con barra',
        'Sentadilla goblet', 'Sentadilla hack', 'Sentadilla isométrica en pared',
        'Zancadas',
    ),
}


def _normalize(value):
    value = unicodedata.normalize('NFKD', value.casefold())
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


@transaction.atomic
def publicar_sucesora(contract, **changes):
    current = ContratoRiesgoGymFaseRehab.objects.select_for_update().get(pk=contract.pk)
    active = ContratoRiesgoGymFaseRehab.objects.filter(fase=current.fase, activo=True).first()
    if active and active.pk != current.pk:
        return active
    fields = ('schema_version', 'risk_tags', 'pain_hold_min', 'freshness_days',
              'action', 'scope', 'red_flag_action')
    data = {field: deepcopy(getattr(current, field)) for field in fields}
    data.update(changes)
    next_version = current.version + 1
    existing = ContratoRiesgoGymFaseRehab.objects.filter(
        fase=current.fase, version=next_version
    ).first()
    if existing:
        raise ValidationError(
            'Conflicto de versión sucesora: ya existe una versión inactiva; '
            'revísela explícitamente antes de publicar.'
        )
    ContratoRiesgoGymFaseRehab.objects.filter(pk=current.pk).update(activo=False)
    return ContratoRiesgoGymFaseRehab.objects.create(
        fase=current.fase, version=next_version, activo=True, **data
    )


def auditar_cobertura(today=None):
    today = today or date.today()
    exercises = list(EjercicioBase.objects.order_by('nombre', 'pk'))
    expected = {_normalize(name) for name in CATALOGO_RIESGO_GYM_V1['exact_names']}
    grouped = {}
    for exercise in exercises:
        grouped.setdefault(_normalize(exercise.nombre), []).append(exercise)
    exact, ambiguous, covered = [], [], []
    flattened_tags = set()
    for tags in ContratoRiesgoGymFaseRehab.objects.filter(activo=True).values_list('risk_tags', flat=True):
        flattened_tags.update(tags or [])
    for normalized in sorted(expected):
        candidates = grouped.get(normalized, [])
        evidence = [
            {'exercise_id': exercise.pk, 'name': exercise.nombre,
             'current_risk_tags': sorted(exercise.risk_tags or [])}
            for exercise in sorted(candidates, key=lambda item: (item.nombre, item.pk))
        ]
        if len(evidence) == 1:
            exact.append(evidence[0])
        elif len(evidence) > 1:
            ambiguous.append({'normalized_name': normalized, 'candidates': evidence})
    for exercise in exercises:
        if set(exercise.risk_tags or []) & flattened_tags:
            covered.append({
                'exercise_id': exercise.pk, 'name': exercise.nombre,
                'matched_tags': sorted(set(exercise.risk_tags or []) & flattened_tags),
            })
    absent = [name for name in CATALOGO_RIESGO_GYM_V1['exact_names']
              if _normalize(name) not in grouped]

    would_hold = []
    episodes = EpisodioRehab.objects.filter(
        estado='ACTIVO', fase_actual__contratos_riesgo_gym__activo=True
    ).select_related('fase_actual').prefetch_related('registros_diarios').order_by('pk').distinct()
    for episode in episodes:
        contract = episode.fase_actual.contratos_riesgo_gym.get(activo=True)
        records = [r for r in episode.registros_diarios.all() if r.fecha <= today]
        latest = max(records, key=lambda r: (r.fecha, r.pk), default=None)
        if latest and 0 <= (today - latest.fecha).days <= contract.freshness_days \
                and latest.dolor_manana >= contract.pain_hold_min and not latest.bandera_roja:
            would_hold.append({'episode_id': episode.pk, 'record_id': latest.pk,
                               'pain': latest.dolor_manana, 'age_days': (today-latest.fecha).days})
    return {
        'schema_version': 1, 'catalog_version': CATALOGO_RIESGO_GYM_V1['schema_version'],
        'proposed_risk_tag': CATALOGO_RIESGO_GYM_V1['risk_tag'],
        'exact_matches': exact, 'ambiguous': ambiguous,
        'covered_by_existing_tags': sorted(covered, key=lambda row: (row['name'], row['exercise_id'])),
        'absent': sorted(absent),
        'episodes_would_hold': would_hold, 'execution_enabled': False, 'read_only': True,
    }
